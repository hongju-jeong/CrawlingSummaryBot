from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..config import settings
from ..models import DeliveryLog, Issue, IssueSummary, Report
from ..repository import get_or_create_default_channel, get_or_create_source, normalize_preview_text
from .naver_latest_crawler import CrawledArticle
from .openai_summary import OpenAISummaryService


@dataclass
class IngestionResult:
    collected_count: int
    saved_count: int
    skipped_count: int
    failed_count: int


def save_crawled_articles(db: Session, articles: list[CrawledArticle]) -> IngestionResult:
    source = get_or_create_source(db)
    channel = get_or_create_default_channel(db)
    saved_count = 0
    skipped_count = 0
    failed_count = 0

    for article in articles:
        try:
            article_hash = build_unique_hash(article.article_url)
            existing = db.scalar(select(Issue).where(Issue.unique_hash == article_hash))
            if existing is not None:
                existing.title = article.title
                existing.original_url = article.article_url
                existing.press_name = article.press_name
                existing.published_at = article.published_at
                existing.raw_content = article.raw_content
                existing.updated_at = datetime.now(timezone.utc)
                update_reporting_state(db, existing, channel.id)
                skipped_count += 1
                continue

            issue = Issue(
                source_id=source.id,
                external_id=article.article_url,
                press_name=article.press_name,
                title=article.title,
                original_url=article.article_url,
                category="뉴스",
                region=None,
                published_at=article.published_at,
                raw_content=article.raw_content,
                status="collected",
                unique_hash=article_hash,
            )
            db.add(issue)
            db.flush()
            update_reporting_state(db, issue, channel.id)
            saved_count += 1
        except Exception:
            failed_count += 1

    db.commit()
    return IngestionResult(
        collected_count=len(articles),
        saved_count=saved_count,
        skipped_count=skipped_count,
        failed_count=failed_count,
    )


def build_unique_hash(article_url: str) -> str:
    return hashlib.sha256(article_url.encode("utf-8")).hexdigest()


def update_reporting_state(db: Session, issue: Issue, channel_id: int) -> None:
    summary_text, llm_provider, llm_model, summary_status = build_summary(
        title=issue.title,
        press_name=issue.press_name or "",
        raw_content=issue.raw_content or "",
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

    preview_message = f"*[최신 뉴스 브리핑]* {issue.title}\n요약: {summary_text}"
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

    delivery_log = db.scalar(
        select(DeliveryLog).where(DeliveryLog.report_id == report.id).order_by(DeliveryLog.created_at.desc())
    )
    if delivery_log is None:
        db.add(
            DeliveryLog(
                report_id=report.id,
                channel_id=channel_id,
                delivery_status="pending",
                delivered_at=None,
                retry_count=0,
            )
        )


def build_summary(*, title: str, press_name: str, raw_content: str) -> tuple[str, str, str, str]:
    fallback = normalize_preview_text(raw_content) or "아직 기사 본문이 수집되지 않았습니다."

    if not settings.openai_api_key:
        return fallback, "system", "preview-truncation", "completed"

    try:
        service = OpenAISummaryService()
        summary = service.summarize_article(title=title, press_name=press_name, raw_content=raw_content)
        if summary:
            return summary, "openai", settings.openai_model, "completed"
    except Exception:
        pass

    return fallback, "system", "preview-truncation", "completed"
