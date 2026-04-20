from backend.app.config import settings
from backend.app.services.runtime.runtime_profile import get_runtime_profile
from backend.app.services.runtime.scheduler import (
    activate_auto_crawl_schedule,
    scheduler,
    start_scheduler,
    stop_scheduler,
)


def test_scheduler_starts_daily_job_only_until_manual_activation():
    original_values = (
        settings.crawler_schedule_enabled,
        settings.daily_summary_enabled,
        settings.crawler_interval_minutes,
        settings.daily_summary_cron_hour,
        settings.daily_summary_cron_minute,
    )
    try:
        stop_scheduler()
        scheduler.remove_all_jobs()
        settings.crawler_schedule_enabled = True
        settings.daily_summary_enabled = True
        settings.crawler_interval_minutes = 30
        settings.daily_summary_cron_hour = 0
        settings.daily_summary_cron_minute = 0

        start_scheduler()
        job_ids = {job.id for job in scheduler.get_jobs()}
        assert "daily_keyword_digest" in job_ids
        runtime = get_runtime_profile()
        assert runtime["scheduler_running"] is True
        assert runtime["auto_crawl_armed"] is False
        assert runtime["auto_crawl_active"] is False
        assert runtime["crawl_interval_minutes"] == 30
        assert runtime["next_crawl_run_at"] is None

        activate_auto_crawl_schedule()
        job_ids = {job.id for job in scheduler.get_jobs()}
        assert "multi_source_latest_news_crawl" in job_ids
        runtime = get_runtime_profile()
        assert runtime["auto_crawl_armed"] is True
        assert runtime["auto_crawl_last_status"] in (None, "running", "completed", "failed")
        assert runtime["next_crawl_run_at"] is not None
    finally:
        stop_scheduler()
        scheduler.remove_all_jobs()
        (
            settings.crawler_schedule_enabled,
            settings.daily_summary_enabled,
            settings.crawler_interval_minutes,
            settings.daily_summary_cron_hour,
            settings.daily_summary_cron_minute,
        ) = original_values
