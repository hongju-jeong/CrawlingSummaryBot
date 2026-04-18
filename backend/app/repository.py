from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from .config import settings
from .models import DeliveryLog, Issue, Report, ReportChannel, Source


def list_issues(db: Session) -> list[dict]:
    issues = db.scalars(
        select(Issue).options(joinedload(Issue.source)).order_by(Issue.published_at.desc(), Issue.collected_at.desc())
    ).all()
    return [
        {
            "id": issue.id,
            "title": issue.title,
            "source": issue.press_name or (issue.source.name if issue.source else settings.crawler_source_name),
            "category": issue.category,
            "time": format_relative_time(issue.published_at or issue.collected_at),
            "report_status": to_issue_status(issue.status),
        }
        for issue in issues
    ]


def get_issue_preview(db: Session, issue_id: int) -> dict | None:
    report = db.scalar(
        select(Report)
        .options(joinedload(Report.issue).joinedload(Issue.source), joinedload(Report.summary), joinedload(Report.channel))
        .where(Report.issue_id == issue_id)
        .order_by(Report.created_at.desc())
    )
    if report is None:
        issue = db.scalar(
            select(Issue).options(joinedload(Issue.source)).where(Issue.id == issue_id)
        )
        if issue is None:
            return None
        content = normalize_preview_text(issue.raw_content)
        summary = content or "아직 기사 본문이 수집되지 않았습니다."
        return {
            "issue_id": issue.id,
            "title": issue.title,
            "source": issue.press_name or (issue.source.name if issue.source else settings.crawler_source_name),
            "category": issue.category,
            "channel": settings.default_report_channel,
            "destination": settings.default_report_destination,
            "summary": summary,
            "preview_message": f"[{issue.category}] {summary}",
        }

    return {
        "issue_id": report.issue.id,
        "title": report.issue.title,
        "source": report.issue.press_name or (
            report.issue.source.name if report.issue.source else settings.crawler_source_name
        ),
        "category": report.issue.category,
        "channel": report.channel.name,
        "destination": report.channel.destination,
        "summary": report.summary.summary_text,
        "preview_message": report.preview_message,
    }


def get_issue_detail(db: Session, issue_id: int) -> dict | None:
    issue = db.scalar(
        select(Issue).options(joinedload(Issue.source)).where(Issue.id == issue_id)
    )
    if issue is None:
        return None

    return {
        "issue_id": issue.id,
        "title": issue.title,
        "source": issue.press_name or (issue.source.name if issue.source else settings.crawler_source_name),
        "category": issue.category,
        "original_url": issue.original_url,
        "published_at": issue.published_at,
        "raw_content": issue.raw_content or "",
    }


def list_delivery_logs(db: Session) -> list[dict]:
    rows = db.scalars(
        select(DeliveryLog)
        .options(joinedload(DeliveryLog.report).joinedload(Report.issue), joinedload(DeliveryLog.channel))
        .order_by(DeliveryLog.created_at.desc())
    ).all()
    return [
        {
            "id": row.id,
            "title": row.report.issue.title if row.report and row.report.issue else "제목 없음",
            "category": row.report.issue.category if row.report and row.report.issue else "사회",
            "channel": row.channel.name if row.channel else settings.default_report_channel,
            "time": format_log_time(row.delivered_at or row.created_at),
            "status": to_display_status(row.delivery_status),
            "delivered_at": row.delivered_at,
        }
        for row in rows
    ]


def get_or_create_source(db: Session, *, name: str, source_type: str, base_url: str) -> Source:
    source = db.scalar(select(Source).where(Source.name == name))
    if source is not None:
        source.source_type = source_type
        source.base_url = base_url
        return source

    source = Source(
        name=name,
        source_type=source_type,
        base_url=base_url,
        is_active=True,
    )
    db.add(source)
    db.flush()
    return source


def get_or_create_default_channel(db: Session) -> ReportChannel:
    channel = db.scalar(select(ReportChannel).where(ReportChannel.name == settings.default_report_channel))
    if channel is not None:
        return channel

    channel = ReportChannel(
        name=settings.default_report_channel,
        channel_type="slack",
        destination=settings.default_report_destination,
        is_active=True,
    )
    db.add(channel)
    db.flush()
    return channel


def normalize_preview_text(content: str | None, max_length: int = 220) -> str:
    if not content:
        return ""
    text = " ".join(content.split())
    return text[: max_length - 1] + "…" if len(text) > max_length else text


def format_relative_time(dt: datetime | None) -> str:
    if dt is None:
        return "방금 전"

    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)

    now = datetime.now(timezone.utc)
    delta = now - dt.astimezone(timezone.utc)
    seconds = max(int(delta.total_seconds()), 0)

    if seconds < 60:
        return "방금 전"
    if seconds < 3600:
        return f"{seconds // 60}분 전"
    if seconds < 86400:
        return f"{seconds // 3600}시간 전"
    return f"{seconds // 86400}일 전"


def format_log_time(dt: datetime | None) -> str:
    if dt is None:
        return "-"
    return dt.strftime("%H:%M")


def to_display_status(status: str) -> str:
    mapping = {
        "pending": "대기",
        "sent": "성공",
        "failed": "실패",
    }
    return mapping.get(status, status)


def to_issue_status(status: str) -> str:
    mapping = {
        "collected": "수집 완료",
        "summarized": "AI 요약 완료",
        "sent": "전송 완료",
        "failed": "전송 실패",
    }
    return mapping.get(status, status)
