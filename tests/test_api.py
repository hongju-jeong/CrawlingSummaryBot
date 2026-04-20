from backend.app.api.routes.delivery_logs import read_delivery_logs
from backend.app.api.routes.issues import read_issue_detail, read_issue_preview, read_issues
from backend.app.config import settings
from backend.app.database import Base, SessionLocal, engine
from backend.app.models import DeliveryLog, Issue, IssueSummary, Report, ReportChannel, Source
from backend.app.repository import get_destination_for_topic
from backend.app.schemas import DeliveryLogListResponse, IssueDetailResponse, IssueListResponse, ReportPreviewResponse


def reset_db() -> None:
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)


def seed_issue() -> int:
    db = SessionLocal()
    try:
        source = Source(name="Naver News Main", source_type="crawler", base_url="https://news.naver.com/")
        db.add(source)
        db.flush()
        issue = Issue(
            source_id=source.id,
            press_name="문화일보",
            external_id="https://n.news.naver.com/article/021/0002785289",
            title="테스트 기사",
            original_url="https://n.news.naver.com/article/021/0002785289",
            category="정치",
            raw_content="테스트 본문입니다. 자동 보고 미리보기에서 요약으로 사용됩니다.",
            unique_hash="abc123",
            status="collected",
        )
        db.add(issue)
        db.flush()
        channel = ReportChannel(name="Slack", channel_type="slack", destination="#exec-briefing")
        db.add(channel)
        db.flush()
        summary = IssueSummary(
            issue_id=issue.id,
            llm_provider="system",
            llm_model="preview-truncation",
            prompt_version="v1",
            summary_text="테스트 본문입니다. 자동 보고 미리보기에서 요약으로 사용됩니다.",
            summary_status="completed",
        )
        db.add(summary)
        db.flush()
        report = Report(
            issue_id=issue.id,
            summary_id=summary.id,
            channel_id=channel.id,
            report_title=issue.title,
            preview_message=(
                "[정치] 테스트 본문입니다. 자동 보고 미리보기에서 요약으로 사용됩니다.\n"
                "출처: 문화일보\n"
                "링크: https://n.news.naver.com/article/021/0002785289"
            ),
            report_status="ready",
        )
        db.add(report)
        db.flush()
        db.add(
            DeliveryLog(
                report_id=report.id,
                channel_id=channel.id,
                delivery_status="pending",
                retry_count=0,
            )
        )
        db.commit()
        db.refresh(issue)
        return issue.id
    finally:
        db.close()


def test_issue_endpoints_return_db_data():
    reset_db()
    issue_id = seed_issue()

    db = SessionLocal()
    try:
        issues_response = read_issues(db)
        assert isinstance(issues_response, IssueListResponse)
        assert issues_response.total == 1
        assert issues_response.items[0].source == "문화일보"

        preview_response = read_issue_preview(issue_id, db)
        assert isinstance(preview_response, ReportPreviewResponse)
        assert preview_response.title == "테스트 기사"
        assert preview_response.source == "문화일보"
        assert preview_response.category == "정치"
        assert "테스트 본문" in preview_response.summary
        assert "출처: 문화일보" in preview_response.preview_message
        assert "링크: https://n.news.naver.com/article/021/0002785289" in preview_response.preview_message

        detail_response = read_issue_detail(issue_id, db)
        assert isinstance(detail_response, IssueDetailResponse)
        assert detail_response.title == "테스트 기사"
        assert detail_response.source == "문화일보"
        assert detail_response.category == "정치"
        assert detail_response.raw_content == "테스트 본문입니다. 자동 보고 미리보기에서 요약으로 사용됩니다."

        logs_response = read_delivery_logs(db)
        assert isinstance(logs_response, DeliveryLogListResponse)
        assert logs_response.total == 1
        assert logs_response.items[0].channel == "Slack"
        assert logs_response.items[0].category == "정치"
        assert logs_response.items[0].status == "대기"
    finally:
        db.close()


def test_topic_destination_prefers_configured_mapping():
    original_channels = dict(settings.topic_channels)
    try:
        settings.topic_channels = {"정치": "#custom-politics"}
        assert get_destination_for_topic("정치") == "#custom-politics"
        assert get_destination_for_topic("없는주제") == settings.default_report_destination
    finally:
        settings.topic_channels = original_channels
