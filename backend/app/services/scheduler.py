from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.interval import IntervalTrigger

from ..config import settings
from ..database import SessionLocal
from .issue_ingestion import save_crawled_articles
from .multi_source_crawler import MultiSourcePollingCrawler

scheduler = BackgroundScheduler(timezone="Asia/Seoul")


def run_latest_news_job() -> None:
    db = SessionLocal()
    try:
        crawler = MultiSourcePollingCrawler()
        articles = crawler.crawl_latest(settings.crawler_limit_per_source)
        save_crawled_articles(db, articles)
    except Exception:
        db.rollback()
    finally:
        db.close()


def start_scheduler() -> None:
    if not settings.crawler_schedule_enabled or scheduler.running:
        return

    scheduler.add_job(
        run_latest_news_job,
        trigger=IntervalTrigger(minutes=settings.crawler_interval_minutes),
        id="multi_source_latest_news_crawl",
        replace_existing=True,
    )
    scheduler.start()


def stop_scheduler() -> None:
    if scheduler.running:
        scheduler.shutdown(wait=False)
