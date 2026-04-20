import json
from datetime import date, datetime, timedelta

from backend.app.database import Base, SessionLocal, engine
from backend.app.models import Issue, IssueSummary, Source
from backend.app.services.reporting.daily_summary import DailyIssueRecord, build_daily_payload


def make_record(
    *,
    issue_id: int,
    topic: str,
    title: str,
    source_name: str,
    original_url: str,
    published_at: datetime,
    summary: str,
    importance: str = "보통",
    tracking_keywords: list[str] | None = None,
) -> DailyIssueRecord:
    return DailyIssueRecord(
        issue_id=issue_id,
        topic=topic,
        title=title,
        source_name=source_name,
        original_url=original_url,
        published_at=published_at,
        summary=summary,
        raw_content=summary,
        importance=importance,
        tracking_keywords=tracking_keywords or [],
    )


def test_daily_payload_uses_event_clusters_not_raw_article_count():
    now = datetime(2026, 4, 19, 9, 0, 0)
    records = [
        make_record(
            issue_id=1,
            topic="경제",
            title="SK하이닉스 1분기 실적 기대에 주가 급등",
            source_name="연합뉴스",
            original_url="https://example.com/1",
            published_at=now,
            summary="SK하이닉스 실적 기대와 주가 급등 소식",
            importance="높음",
            tracking_keywords=["SK하이닉스", "실적"],
        ),
        make_record(
            issue_id=2,
            topic="경제",
            title="SK하이닉스 실적 기대에 주가 급등",
            source_name="KBS News",
            original_url="https://example.com/2",
            published_at=now + timedelta(hours=1),
            summary="SK하이닉스 실적과 주가 상승을 다룬 기사",
            importance="보통",
            tracking_keywords=["SK하이닉스", "주가"],
        ),
        make_record(
            issue_id=3,
            topic="경제",
            title="기준금리 동결에 시장 변동성 확대",
            source_name="연합뉴스",
            original_url="https://example.com/3",
            published_at=now + timedelta(hours=2),
            summary="기준금리 동결과 시장 변동성 기사",
            importance="높음",
            tracking_keywords=["기준금리", "시장"],
        ),
    ]

    payload = build_daily_payload(summary_date=date(2026, 4, 19), records=records)
    economy = next(topic for topic in payload["topics"] if topic["topic"] == "경제")
    keywords = {item["keyword"]: item for item in economy["keywords"]}
    assert "sk하이닉스" in keywords
    assert "기준금리" in keywords
    assert keywords["sk하이닉스"]["representative_article_url"] in {"https://example.com/1", "https://example.com/2"}


def test_daily_payload_omits_empty_topics():
    payload = build_daily_payload(summary_date=date(2026, 4, 19), records=[])
    assert payload["topics"] == []


def test_daily_payload_loads_records_from_db_without_joinedload_error():
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)

    db = SessionLocal()
    try:
        source = Source(name="연합뉴스", source_type="crawler", base_url="https://www.yna.co.kr/")
        db.add(source)
        db.flush()

        issue = Issue(
            source_id=source.id,
            press_name="연합뉴스",
            external_id="daily-summary-1",
            title="대통령 회동 후 경제 정책 발표",
            original_url="https://example.com/daily-summary-1",
            category="정치",
            raw_content="대통령과 관계 장관이 회동한 뒤 경제 정책을 발표했다.",
            unique_hash="daily-summary-1",
            published_at=datetime(2026, 4, 19, 9, 0, 0),
            status="sent",
        )
        db.add(issue)
        db.flush()

        summary = IssueSummary(
            issue_id=issue.id,
            llm_provider="openai",
            llm_model="gpt-5.4-mini",
            prompt_version="v1",
            summary_text="경제 정책 발표 관련 기사 요약",
            importance="높음",
            key_points_json=json.dumps(["회동", "경제 정책"], ensure_ascii=False),
            research_value="정책 방향을 추적할 가치가 있다.",
            tracking_keywords_json=json.dumps(["대통령", "경제정책"], ensure_ascii=False),
            summary_status="completed",
        )
        db.add(summary)
        db.commit()

        from backend.app.services.reporting.daily_summary import _load_daily_issue_records

        records = _load_daily_issue_records(db, summary_date=date(2026, 4, 19))
        assert len(records) == 1
        assert records[0].topic == "정치"
        assert records[0].tracking_keywords == ["대통령", "경제정책"]
    finally:
        db.close()
