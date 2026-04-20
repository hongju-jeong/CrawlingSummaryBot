from datetime import datetime, timedelta
from threading import Lock
from zoneinfo import ZoneInfo

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger

from ...config import settings
from ...database import SessionLocal
from ..ingestion.issue_ingestion import save_crawled_articles
from ..crawling.multi_source_crawler import MultiSourcePollingCrawler
from ..reporting.daily_summary import send_daily_summary

scheduler = BackgroundScheduler(timezone="Asia/Seoul")
SEOUL_TZ = ZoneInfo("Asia/Seoul")
AUTO_CRAWL_JOB_ID = "multi_source_latest_news_crawl"
DAILY_DIGEST_JOB_ID = "daily_keyword_digest"
_auto_crawl_state_lock = Lock()
_auto_crawl_state = {
    "active": False,
    "source_groups": [],
    "last_started_at": None,
    "last_finished_at": None,
    "last_status": None,
    "last_collected_count": 0,
    "last_saved_count": 0,
    "last_skipped_count": 0,
    "last_failed_count": 0,
    "last_sent_count": 0,
    "recent_events": [],
    "event_seq": 0,
}


def run_latest_news_job() -> None:
    db = SessionLocal()
    source_groups = list(settings.crawler_enabled_source_groups)
    _set_auto_crawl_state(
        active=True,
        source_groups=source_groups,
        last_started_at=datetime.now(SEOUL_TZ),
        last_finished_at=None,
        last_status="running",
        last_collected_count=0,
        last_saved_count=0,
        last_skipped_count=0,
        last_failed_count=0,
        last_sent_count=0,
        recent_events=[],
    )
    _record_auto_crawl_event(
        "run_started",
        {
            "title": "자동 크롤링 실행",
            "process_count": settings.crawler_processes,
            "source_groups": source_groups,
        },
    )
    try:
        crawler = MultiSourcePollingCrawler()
        articles = crawler.crawl_latest(settings.crawler_limit_per_source)
        _record_auto_crawl_event(
            "crawl_completed",
            {
                "title": "자동 크롤링 수집 완료",
                "discovered_count": len(articles),
                "source_groups": source_groups,
            },
        )
        result = save_crawled_articles(db, articles, event_callback=lambda event_type, payload: _record_auto_crawl_event(event_type, payload))
        _set_auto_crawl_state(
            active=False,
            last_finished_at=datetime.now(SEOUL_TZ),
            last_status="completed",
            last_collected_count=result.collected_count,
            last_saved_count=result.saved_count,
            last_skipped_count=result.skipped_count,
            last_failed_count=result.failed_count,
        )
        _record_auto_crawl_event(
            "run_completed",
            {
                "title": "자동 크롤링 완료",
                "saved_count": result.saved_count,
                "skipped_count": result.skipped_count,
                "failed_count": result.failed_count,
            },
        )
    except Exception:
        db.rollback()
        _set_auto_crawl_state(
            active=False,
            last_finished_at=datetime.now(SEOUL_TZ),
            last_status="failed",
        )
        _record_auto_crawl_event(
            "run_failed",
            {
                "title": "자동 크롤링 실패",
            },
        )
    finally:
        db.close()


def run_daily_summary_job() -> None:
    if not settings.daily_summary_enabled:
        return

    db = SessionLocal()
    try:
        target_date = datetime.now(SEOUL_TZ).date() - timedelta(days=1)
        send_daily_summary(db, summary_date=target_date)
        db.commit()
    except Exception:
        db.rollback()
    finally:
        db.close()


def start_scheduler() -> None:
    if not settings.crawler_schedule_enabled:
        return

    if scheduler.running:
        _ensure_daily_digest_job()
        return

    scheduler.start()
    _ensure_daily_digest_job()


def activate_auto_crawl_schedule() -> None:
    if not settings.crawler_schedule_enabled:
        return
    if not scheduler.running:
        scheduler.start()
    if scheduler.get_job(AUTO_CRAWL_JOB_ID) is not None:
        return

    scheduler.add_job(
        run_latest_news_job,
        trigger=IntervalTrigger(minutes=settings.crawler_interval_minutes),
        id=AUTO_CRAWL_JOB_ID,
        replace_existing=True,
    )
    _ensure_daily_digest_job()


def stop_scheduler() -> None:
    if scheduler.running:
        scheduler.shutdown(wait=False)


def get_scheduler_status() -> dict[str, object]:
    crawl_job = scheduler.get_job(AUTO_CRAWL_JOB_ID)
    daily_job = scheduler.get_job(DAILY_DIGEST_JOB_ID)
    with _auto_crawl_state_lock:
        auto_crawl_state = dict(_auto_crawl_state)
    return {
        "running": scheduler.running,
        "auto_crawl_armed": crawl_job is not None,
        "crawl_interval_minutes": settings.crawler_interval_minutes,
        "next_crawl_run_at": crawl_job.next_run_time.isoformat() if crawl_job and crawl_job.next_run_time else None,
        "next_daily_summary_run_at": (
            daily_job.next_run_time.isoformat() if daily_job and daily_job.next_run_time else None
        ),
        "auto_crawl_active": auto_crawl_state["active"],
        "auto_crawl_source_groups": auto_crawl_state["source_groups"],
        "auto_crawl_last_started_at": (
            auto_crawl_state["last_started_at"].isoformat() if auto_crawl_state["last_started_at"] else None
        ),
        "auto_crawl_last_finished_at": (
            auto_crawl_state["last_finished_at"].isoformat() if auto_crawl_state["last_finished_at"] else None
        ),
        "auto_crawl_last_status": auto_crawl_state["last_status"],
        "auto_crawl_last_collected_count": auto_crawl_state["last_collected_count"],
        "auto_crawl_last_saved_count": auto_crawl_state["last_saved_count"],
        "auto_crawl_last_skipped_count": auto_crawl_state["last_skipped_count"],
        "auto_crawl_last_failed_count": auto_crawl_state["last_failed_count"],
        "auto_crawl_last_sent_count": auto_crawl_state["last_sent_count"],
        "auto_crawl_recent_events": auto_crawl_state["recent_events"],
    }


def _ensure_daily_digest_job() -> None:
    if not settings.daily_summary_enabled:
        return
    if scheduler.get_job(DAILY_DIGEST_JOB_ID) is not None:
        return
    scheduler.add_job(
        run_daily_summary_job,
        trigger=CronTrigger(
            hour=settings.daily_summary_cron_hour,
            minute=settings.daily_summary_cron_minute,
            timezone="Asia/Seoul",
        ),
        id=DAILY_DIGEST_JOB_ID,
        replace_existing=True,
    )


def _set_auto_crawl_state(**updates) -> None:
    with _auto_crawl_state_lock:
        _auto_crawl_state.update(updates)


def _record_auto_crawl_event(event_type: str, payload: dict[str, object]) -> None:
    with _auto_crawl_state_lock:
        _auto_crawl_state["event_seq"] += 1
        event = {
            "seq": _auto_crawl_state["event_seq"],
            "type": event_type,
            **payload,
        }
        _auto_crawl_state["recent_events"] = (_auto_crawl_state["recent_events"] + [event])[-80:]
        if event_type == "delivery_sent":
            _auto_crawl_state["last_sent_count"] += 1
