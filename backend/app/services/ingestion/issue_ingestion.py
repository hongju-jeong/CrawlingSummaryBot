from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
import queue
import threading
from typing import Callable
import json
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from ...config import settings
from ...database import SessionLocal
from ...models import DeliveryLog, Issue, IssueSummary, Report
from ...repository import get_or_create_channel_for_topic, get_or_create_source, normalize_preview_text
from ..reporting.openai_summary import OpenAISummaryService
from ..runtime.crawl_control import is_cancelled
from ..runtime.runtime_profile import get_effective_report_worker_threads
from ..reporting.slack_reporter import SlackReporter, format_article_message
from ..crawling.source_types import CrawledArticle
from .topic_classifier import classify_topic


@dataclass
class IngestionResult:
    collected_count: int
    saved_count: int
    skipped_count: int
    failed_count: int


EventCallback = Callable[[str, dict], None]


def save_crawled_articles(
    db: Session,
    articles: list[CrawledArticle],
    *,
    event_callback: EventCallback | None = None,
    cancel_token: Any | None = None,
) -> IngestionResult:
    saved_count = 0
    skipped_count = 0
    failed_count = 0
    post_process_jobs: list[tuple[int, bool]] = []

    for article in articles:
        if is_cancelled(cancel_token):
            break
        try:
            emit_event(
                event_callback,
                "item_started",
                {
                    "title": article.title,
                    "source": article.press_name,
                    "url": article.article_url,
                },
            )
            source = get_or_create_source(
                db,
                name=article.source_name,
                source_type=article.source_type,
                base_url=article.article_url,
            )
            topic, _ = classify_topic(
                title=article.title,
                raw_content=article.raw_content,
                source_name=article.source_name,
                topic_hint=article.topic_hint,
            )
            article_hash = build_unique_hash(
                article_url=article.article_url,
                title=article.title,
                press_name=article.press_name,
                published_at=article.published_at,
            )
            existing = db.scalar(select(Issue).where(Issue.unique_hash == article_hash))
            if existing is not None:
                existing.title = article.title
                existing.original_url = article.article_url
                existing.press_name = article.press_name
                existing.published_at = article.published_at
                existing.raw_content = article.raw_content
                existing.category = topic
                existing.region = article.region
                existing.source_id = source.id
                existing.updated_at = datetime.now(timezone.utc)
                db.flush()
                post_process_jobs.append((existing.id, False))
                emit_event(
                    event_callback,
                    "item_skipped",
                    {
                        "title": existing.title,
                        "source": existing.press_name or article.source_name,
                        "category": existing.category,
                        "status": existing.status,
                    },
                )
                skipped_count += 1
                continue

            issue = Issue(
                source_id=source.id,
                external_id=article.article_url,
                press_name=article.press_name,
                title=article.title,
                original_url=article.article_url,
                category=topic,
                region=article.region,
                published_at=article.published_at,
                raw_content=article.raw_content,
                status="collected",
                unique_hash=article_hash,
            )
            db.add(issue)
            db.flush()
            emit_event(
                event_callback,
                "item_saved",
                {
                    "issue_id": issue.id,
                    "title": issue.title,
                    "source": issue.press_name or issue.source.name if issue.source else issue.press_name or article.source_name,
                    "category": issue.category,
                },
            )
            post_process_jobs.append((issue.id, True))
            saved_count += 1
        except Exception:
            failed_count += 1
            emit_event(
                event_callback,
                "item_failed",
                {
                    "title": article.title,
                    "source": article.press_name or article.source_name,
                },
            )

    db.commit()
    _run_post_process_jobs(post_process_jobs, event_callback=event_callback, cancel_token=cancel_token)
    return IngestionResult(
        collected_count=len(articles),
        saved_count=saved_count,
        skipped_count=skipped_count,
        failed_count=failed_count,
    )


def _run_post_process_jobs(
    jobs: list[tuple[int, bool]],
    *,
    event_callback: EventCallback | None = None,
    cancel_token: Any | None = None,
) -> None:
    if not jobs:
        return

    max_workers = min(get_effective_report_worker_threads(), len(jobs))
    if max_workers <= 1:
        for issue_id, should_send in jobs:
            if is_cancelled(cancel_token):
                break
            _process_reporting_job(issue_id, should_send, event_callback, cancel_token=cancel_token)
        return

    work_queue: queue.Queue[tuple[int, bool] | None] = queue.Queue()
    for job in jobs:
        work_queue.put(job)
    for _ in range(max_workers):
        work_queue.put(None)

    threads = [
        threading.Thread(
            target=_reporting_worker,
            args=(work_queue, event_callback, cancel_token),
            name=f"report-worker-{index}",
            daemon=True,
        )
        for index in range(max_workers)
    ]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()


def _reporting_worker(
    work_queue: queue.Queue[tuple[int, bool] | None],
    event_callback: EventCallback | None,
    cancel_token: Any | None,
) -> None:
    while not is_cancelled(cancel_token):
        job = work_queue.get()
        if job is None:
            break
        issue_id, should_send = job
        _process_reporting_job(issue_id, should_send, event_callback, cancel_token=cancel_token)


def _process_reporting_job(
    issue_id: int,
    should_send: bool,
    event_callback: EventCallback | None = None,
    cancel_token: Any | None = None,
) -> None:
    db = SessionLocal()
    try:
        if is_cancelled(cancel_token):
            return
        issue = db.scalar(
            select(Issue)
            .options(joinedload(Issue.source))
            .where(Issue.id == issue_id)
        )
        if issue is None:
            return
        update_reporting_state(
            db,
            issue,
            should_send=should_send,
            event_callback=event_callback,
            cancel_token=cancel_token,
        )
        db.commit()
    except Exception as error:
        db.rollback()
        emit_event(
            event_callback,
            "item_failed",
            {
                "issue_id": issue_id,
                "title": getattr(locals().get("issue"), "title", "알 수 없는 기사"),
                "category": getattr(locals().get("issue"), "category", "미분류"),
                "status": "failed",
                "error": str(error),
            },
        )
    finally:
        db.close()

def build_unique_hash(
    *,
    article_url: str,
    title: str,
    press_name: str,
    published_at: datetime | None,
) -> str:
    if article_url:
        seed = article_url
    else:
        published = published_at.isoformat() if published_at else ""
        seed = f"{press_name}|{title}|{published}"
    return hashlib.sha256(seed.encode("utf-8")).hexdigest()


def update_reporting_state(
    db: Session,
    issue: Issue,
    *,
    should_send: bool,
    event_callback: EventCallback | None = None,
    cancel_token: Any | None = None,
) -> None:
    if is_cancelled(cancel_token):
        issue.status = "summarized"
        return
    (
        topic,
        summary_text,
        importance,
        key_points,
        research_value,
        tracking_keywords,
        llm_provider,
        llm_model,
        summary_status,
    ) = build_summary(
        title=issue.title,
        press_name=issue.press_name or "",
        raw_content=issue.raw_content or "",
        source_name=issue.source.name if issue.source else issue.press_name or "출처 미상",
        provisional_topic=issue.category,
    )
    issue.category = topic
    channel = get_or_create_channel_for_topic(db, issue.category)
    summary = db.scalar(
        select(IssueSummary).where(IssueSummary.issue_id == issue.id).order_by(IssueSummary.created_at.desc())
    )
    if summary is None:
        summary = IssueSummary(
            issue_id=issue.id,
            llm_provider=llm_provider,
            llm_model=llm_model,
            prompt_version="v1",
            summary_text=summary_text,
            importance=importance,
            key_points_json=json.dumps(key_points, ensure_ascii=False),
            research_value=research_value,
            tracking_keywords_json=json.dumps(tracking_keywords, ensure_ascii=False),
            summary_status=summary_status,
        )
        db.add(summary)
        db.flush()
    else:
        summary.llm_provider = llm_provider
        summary.llm_model = llm_model
        summary.summary_text = summary_text
        summary.importance = importance
        summary.key_points_json = json.dumps(key_points, ensure_ascii=False)
        summary.research_value = research_value
        summary.tracking_keywords_json = json.dumps(tracking_keywords, ensure_ascii=False)
        summary.summary_status = summary_status

    emit_event(
        event_callback,
        "summary_completed",
        {
            "issue_id": issue.id,
            "title": issue.title,
            "source": issue.press_name or issue.source.name if issue.source else issue.press_name or "출처 미상",
            "category": issue.category,
            "summary": summary_text,
            "importance": importance,
        },
    )

    preview_message = format_article_message(
        topic=issue.category,
        summary_text=summary_text,
        importance=importance,
        key_points=key_points,
        research_value=research_value,
        tracking_keywords=tracking_keywords,
        source_name=issue.press_name or issue.source.name if issue.source else issue.press_name or "출처 미상",
        article_url=issue.original_url,
    )
    report = db.scalar(select(Report).where(Report.issue_id == issue.id).order_by(Report.created_at.desc()))
    if report is None:
        report = Report(
            issue_id=issue.id,
            summary_id=summary.id,
            channel_id=channel.id,
            report_title=issue.title,
            preview_message=preview_message,
            report_status="ready",
        )
        db.add(report)
        db.flush()
    else:
        report.summary_id = summary.id
        report.channel_id = channel.id
        report.report_title = issue.title
        report.preview_message = preview_message

    if not should_send:
        issue.status = "summarized"
        emit_event(
            event_callback,
            "item_completed",
            {
                "issue_id": issue.id,
                "title": issue.title,
                "category": issue.category,
                "status": issue.status,
            },
        )
        return

    delivery_log = DeliveryLog(
        report_id=report.id,
        channel_id=channel.id,
        delivery_status="pending",
        delivered_at=None,
        retry_count=0,
    )
    db.add(delivery_log)
    db.flush()

    if not settings.slack_auto_send:
        report.report_status = "ready"
        issue.status = "summarized"
        emit_event(
            event_callback,
            "delivery_ready",
            {
                "issue_id": issue.id,
                "title": issue.title,
                "category": issue.category,
                "status": report.report_status,
            },
        )
        return
    if is_cancelled(cancel_token):
        delivery_log.delivery_status = "cancelled"
        report.report_status = "cancelled"
        issue.status = "cancelled"
        emit_event(
            event_callback,
            "run_cancelled",
            {
                "issue_id": issue.id,
                "title": issue.title,
                "category": issue.category,
                "status": issue.status,
            },
        )
        return

    emit_event(
        event_callback,
        "delivery_started",
        {
            "issue_id": issue.id,
            "title": issue.title,
            "category": issue.category,
            "destination": report.channel.destination if report.channel else settings.default_report_destination,
        },
    )
    send_result = SlackReporter().send_summary(
        summary_text,
        topic=issue.category,
        importance=importance,
        key_points=key_points,
        research_value=research_value,
        tracking_keywords=tracking_keywords,
        source_name=issue.press_name or issue.source.name if issue.source else issue.press_name or "출처 미상",
        article_url=issue.original_url,
    )
    if send_result.success:
        delivery_log.delivery_status = "sent"
        delivery_log.delivered_at = datetime.now(timezone.utc)
        delivery_log.response_code = str(send_result.status_code) if send_result.status_code is not None else None
        delivery_log.response_body = send_result.response_body
        report.report_status = "sent"
        issue.status = "sent"
        emit_event(
            event_callback,
            "delivery_sent",
            {
                "issue_id": issue.id,
                "title": issue.title,
                "category": issue.category,
                "status": "sent",
            },
        )
    else:
        delivery_log.delivery_status = "failed"
        delivery_log.error_message = send_result.error_message
        delivery_log.response_code = str(send_result.status_code) if send_result.status_code is not None else None
        delivery_log.response_body = send_result.response_body
        report.report_status = "failed"
        issue.status = "failed"
        emit_event(
            event_callback,
            "delivery_failed",
            {
                "issue_id": issue.id,
                "title": issue.title,
                "category": issue.category,
                "status": "failed",
                "error": send_result.error_message,
            },
        )


def build_summary(
    *,
    title: str,
    press_name: str,
    raw_content: str,
    source_name: str,
    provisional_topic: str,
) -> tuple[str, str, str, list[str], str, list[str], str, str, str]:
    fallback = normalize_preview_text(raw_content) or "아직 기사 본문이 수집되지 않았습니다."

    if not settings.openai_api_key:
        return provisional_topic, fallback, "보통", [], "", [], "system", "preview-truncation", "completed"

    try:
        service = OpenAISummaryService()
        analysis = service.analyze_article(
            title=title,
            press_name=press_name,
            raw_content=raw_content,
        )
        if analysis.summary:
            return (
                analysis.topic,
                analysis.summary,
                analysis.importance,
                analysis.key_points,
                analysis.research_value,
                analysis.tracking_keywords,
                "openai",
                settings.openai_model,
                "completed",
            )
    except Exception:
        pass

    return provisional_topic, fallback, "보통", [], "", [], "system", "preview-truncation", "completed"


def emit_event(event_callback: EventCallback | None, event_type: str, payload: dict) -> None:
    if event_callback is None:
        return
    event_callback(event_type, payload)
