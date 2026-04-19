from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
from typing import Callable

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..config import settings
from ..models import DeliveryLog, Issue, IssueSummary, Report
from ..repository import get_or_create_default_channel, get_or_create_source, normalize_preview_text
from .openai_summary import OpenAISummaryService
from .slack_reporter import SlackReporter
from .source_types import CrawledArticle
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
) -> IngestionResult:
    channel = get_or_create_default_channel(db)
    saved_count = 0
    skipped_count = 0
    failed_count = 0

    for article in articles:
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
                update_reporting_state(db, existing, channel.id, should_send=False, event_callback=event_callback)
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
            update_reporting_state(db, issue, channel.id, should_send=True, event_callback=event_callback)
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
    return IngestionResult(
        collected_count=len(articles),
        saved_count=saved_count,
        skipped_count=skipped_count,
        failed_count=failed_count,
    )

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
    channel_id: int,
    *,
    should_send: bool,
    event_callback: EventCallback | None = None,
) -> None:
    summary_text, llm_provider, llm_model, summary_status = build_summary(
        title=issue.title,
        press_name=issue.press_name or "",
        raw_content=issue.raw_content or "",
        topic=issue.category,
    )
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
            summary_status=summary_status,
        )
        db.add(summary)
        db.flush()
    else:
        summary.llm_provider = llm_provider
        summary.llm_model = llm_model
        summary.summary_text = summary_text
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
        },
    )

    preview_lines = [
        f"[{issue.category}] {summary_text}",
        f"출처: {issue.press_name or issue.source.name if issue.source else issue.press_name or '출처 미상'}",
    ]
    if issue.original_url:
        preview_lines.append(f"링크: {issue.original_url}")
    preview_message = "\n".join(preview_lines)
    report = db.scalar(select(Report).where(Report.issue_id == issue.id, Report.channel_id == channel_id))
    if report is None:
        report = Report(
            issue_id=issue.id,
            summary_id=summary.id,
            channel_id=channel_id,
            report_title=issue.title,
            preview_message=preview_message,
            report_status="ready",
        )
        db.add(report)
        db.flush()
    else:
        report.summary_id = summary.id
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
        channel_id=channel_id,
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

    emit_event(
        event_callback,
        "delivery_started",
        {
            "issue_id": issue.id,
            "title": issue.title,
            "category": issue.category,
            "destination": settings.default_report_destination,
        },
    )
    send_result = SlackReporter().send_summary(
        summary_text,
        topic=issue.category,
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


def build_summary(*, title: str, press_name: str, raw_content: str, topic: str) -> tuple[str, str, str, str]:
    fallback = normalize_preview_text(raw_content) or "아직 기사 본문이 수집되지 않았습니다."

    if not settings.openai_api_key:
        return fallback, "system", "preview-truncation", "completed"

    try:
        service = OpenAISummaryService()
        summary = service.summarize_article(
            title=title,
            press_name=press_name,
            raw_content=raw_content,
            topic=topic,
        )
        if summary:
            return summary, "openai", settings.openai_model, "completed"
    except Exception:
        pass

    return fallback, "system", "preview-truncation", "completed"


def emit_event(event_callback: EventCallback | None, event_type: str, payload: dict) -> None:
    if event_callback is None:
        return
    event_callback(event_type, payload)
