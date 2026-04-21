import json
import re
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import date, datetime, time

from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from ...config import settings
from ...models import DailySummary, Issue, ReportChannel
from ..crawling.source_registry import SOURCE_DEFINITIONS
from .daily_digest_retrieval import retrieve_digest_context
from .openai_summary import OpenAISummaryService
from .slack_reporter import SlackReporter

STOPWORDS = {
    "오늘",
    "내일",
    "어제",
    "관련",
    "대한",
    "이번",
    "통해",
    "위해",
    "기자",
    "보도",
    "기사",
    "정부",
    "뉴스",
    "발표",
    "있는",
    "한다",
    "했다",
    "한다는",
    "있는지",
    "대한민국",
    "한국",
    "세계",
    "글로벌",
}
TOKEN_PATTERN = re.compile(r"[A-Za-z0-9가-힣%./+-]{2,}")
SOURCE_PRIORITY = {definition.name: definition.priority for definition in SOURCE_DEFINITIONS}
ALIASES = {
    "하이닉스": "sk하이닉스",
    "sk하이닉스": "sk하이닉스",
    "美": "미국",
}


@dataclass(slots=True)
class DailyIssueRecord:
    issue_id: int
    topic: str
    title: str
    source_name: str
    original_url: str | None
    published_at: datetime
    summary: str
    raw_content: str
    importance: str
    key_points: list[str]
    research_value: str
    tracking_keywords: list[str]


@dataclass(slots=True)
class IssueCluster:
    topic: str
    issues: list[DailyIssueRecord] = field(default_factory=list)
    title_tokens: set[str] = field(default_factory=set)
    entity_tokens: set[str] = field(default_factory=set)

    def add(self, issue: DailyIssueRecord) -> None:
        self.issues.append(issue)
        self.title_tokens |= tokenize(issue.title)
        self.entity_tokens |= extract_entity_tokens(issue)

    @property
    def representative(self) -> DailyIssueRecord:
        return sorted(
            self.issues,
            key=lambda issue: (
                SOURCE_PRIORITY.get(issue.source_name, 0),
                issue.published_at,
            ),
            reverse=True,
        )[0]

    @property
    def unique_source_count(self) -> int:
        return len({issue.source_name for issue in self.issues})

    @property
    def max_importance(self) -> str:
        order = {"낮음": 0, "보통": 1, "높음": 2, "긴급": 3}
        return max((issue.importance for issue in self.issues), key=lambda item: order.get(item, 0), default="보통")


def build_daily_summary(db: Session, *, summary_date: date) -> DailySummary:
    channel = get_or_create_daily_summary_channel(db)
    records = _load_daily_issue_records(db, summary_date=summary_date)
    payload = build_daily_payload(db=db, summary_date=summary_date, records=records)
    message_text = format_daily_summary_message(payload)
    daily_summary = db.scalar(select(DailySummary).where(DailySummary.summary_date == payload["summary_date"]))
    if daily_summary is None:
        daily_summary = DailySummary(
            summary_date=payload["summary_date"],
            channel_id=channel.id,
            status="ready",
            message_text=message_text,
            payload_json=json.dumps(payload, ensure_ascii=False),
        )
        db.add(daily_summary)
        db.flush()
    else:
        daily_summary.channel_id = channel.id
        daily_summary.status = "ready"
        daily_summary.message_text = message_text
        daily_summary.payload_json = json.dumps(payload, ensure_ascii=False)
    return daily_summary


def send_daily_summary(db: Session, *, summary_date: date) -> DailySummary | None:
    if not settings.daily_summary_enabled:
        return None

    daily_summary = build_daily_summary(db, summary_date=summary_date)
    webhook_url = settings.daily_summary_webhook_url or settings.slack_webhook_url
    if not webhook_url:
        daily_summary.status = "failed"
        return daily_summary

    result = SlackReporter().send_text(webhook_url, daily_summary.message_text)
    daily_summary.status = "sent" if result.success else "failed"
    return daily_summary


def get_latest_daily_summary(db: Session) -> DailySummary | None:
    return db.scalar(
        select(DailySummary).options(joinedload(DailySummary.channel)).order_by(DailySummary.summary_date.desc())
    )


def build_daily_payload(*, db: Session, summary_date: date, records: list[DailyIssueRecord]) -> dict:
    topic_clusters: dict[str, list[IssueCluster]] = defaultdict(list)
    for record in records:
        _append_to_clusters(topic_clusters[record.topic], record)

    topics_payload = []
    llm_topics = []
    for topic, clusters in sorted(topic_clusters.items(), key=lambda item: item[0]):
        top_keywords = _rank_keywords_for_topic(clusters)
        if not top_keywords:
            continue
        llm_topics.append(
            {
                "topic": topic,
                "keywords": [
                    _build_keyword_context(db, summary_date=summary_date, topic=topic, keyword_item=item)
                    for item in top_keywords
                ],
            }
        )
        topics_payload.append(
            {
                "topic": topic,
                "keywords": [
                    {
                        "keyword": item["keyword"],
                        "score": round(item["score"], 2),
                        "representative_article_url": item["representative"].original_url,
                        "representative_article_title": item["representative"].title,
                        "description": "",
                        "context_issue_ids": [],
                        "context_count": 0,
                        "retrieval_method": "rule_db",
                        "explanation_version": "v2-rag",
                    }
                    for item in top_keywords
                ],
            }
        )

    descriptions = _describe_keywords(summary_date=summary_date, topics=llm_topics)
    for topic_payload in topics_payload:
        topic_name = topic_payload["topic"]
        for keyword_payload in topic_payload["keywords"]:
            keyword = keyword_payload["keyword"]
            llm_keyword = next(
                (
                    item
                    for topic_item in llm_topics
                    if topic_item["topic"] == topic_name
                    for item in topic_item["keywords"]
                    if item["keyword"] == keyword
                ),
                None,
            )
            if llm_keyword is not None:
                keyword_payload["context_issue_ids"] = llm_keyword["context_issue_ids"]
                keyword_payload["context_count"] = llm_keyword["context_count"]
                keyword_payload["retrieval_method"] = llm_keyword["retrieval_method"]
            keyword_payload["description"] = descriptions.get(topic_name, {}).get(
                keyword,
                f"{summary_date.isoformat()} {topic_name} 기사에서 {keyword} 관련 보도가 집중되었습니다.",
            )

    return {
        "summary_date": summary_date.isoformat(),
        "topics": topics_payload,
        "meta": {
            "basis": "event-cluster-count",
            "topic_weighting": False,
            "top_n_per_topic": 3,
        },
    }


def format_daily_summary_message(payload: dict) -> str:
    lines = [f"{payload['summary_date']} 일자 키워드 요약"]
    if not payload["topics"]:
        lines.append("")
        lines.append("집계된 토픽이 없습니다.")
        return "\n".join(lines)
    for topic_payload in payload["topics"]:
        lines.append("")
        lines.append(f"[{topic_payload['topic']}]")
        for keyword_payload in topic_payload["keywords"]:
            lines.append(f"- {keyword_payload['keyword']} — {keyword_payload['description']}")
            if keyword_payload["representative_article_url"]:
                lines.append(f"  링크: {keyword_payload['representative_article_url']}")
    return "\n".join(lines)


def parse_daily_payload(payload_json: str) -> dict:
    return json.loads(payload_json)


def get_or_create_daily_summary_channel(db: Session) -> ReportChannel:
    channel = db.scalar(select(ReportChannel).where(ReportChannel.name == settings.daily_summary_channel))
    if channel is not None:
        channel.destination = settings.daily_summary_channel
        return channel

    channel = ReportChannel(
        name=settings.daily_summary_channel,
        channel_type="slack",
        destination=settings.daily_summary_channel,
        is_active=True,
    )
    db.add(channel)
    db.flush()
    return channel


def _load_daily_issue_records(db: Session, *, summary_date: date) -> list[DailyIssueRecord]:
    start_dt = datetime.combine(summary_date, time.min)
    end_dt = datetime.combine(summary_date, time.max)
    issues = (
        db.execute(
            select(Issue)
            .options(joinedload(Issue.summaries), joinedload(Issue.source))
            .where(Issue.published_at >= start_dt, Issue.published_at <= end_dt)
            .order_by(Issue.published_at.asc(), Issue.created_at.asc())
        )
        .unique()
        .scalars()
        .all()
    )

    records = []
    for issue in issues:
        if not issue.category:
            continue
        latest_summary = sorted(issue.summaries, key=lambda item: item.created_at or datetime.min)[-1] if issue.summaries else None
        records.append(
            DailyIssueRecord(
                issue_id=issue.id,
                topic=issue.category,
                title=issue.title,
                source_name=issue.press_name or (issue.source.name if issue.source else "출처 미상"),
                original_url=issue.original_url,
                published_at=issue.published_at or issue.collected_at,
                summary=latest_summary.summary_text if latest_summary else preview_text(issue.raw_content),
                raw_content=issue.raw_content or "",
                importance=latest_summary.importance if latest_summary and latest_summary.importance else "보통",
                key_points=_parse_json_list(latest_summary.key_points_json if latest_summary else None),
                research_value=latest_summary.research_value if latest_summary and latest_summary.research_value else "",
                tracking_keywords=_parse_json_list(
                    latest_summary.tracking_keywords_json if latest_summary else None
                ),
            )
        )
    return records


def _append_to_clusters(clusters: list[IssueCluster], issue: DailyIssueRecord) -> None:
    issue_title_tokens = tokenize(issue.title)
    issue_entities = extract_entity_tokens(issue)
    for cluster in clusters:
        rep = cluster.representative
        if abs((issue.published_at - rep.published_at).total_seconds()) > 86400:
            continue
        title_similarity = _jaccard(issue_title_tokens, cluster.title_tokens)
        entity_overlap = len(issue_entities & cluster.entity_tokens)
        if title_similarity >= 0.6 or entity_overlap >= 2:
            cluster.add(issue)
            return

    cluster = IssueCluster(topic=issue.topic)
    cluster.add(issue)
    clusters.append(cluster)


def _rank_keywords_for_topic(clusters: list[IssueCluster]) -> list[dict]:
    bucket: dict[str, dict] = {}
    for cluster in clusters:
        candidates = cluster.representative.tracking_keywords or _extract_keyword_candidates(cluster.representative)
        for keyword in candidates[:5]:
            normalized = normalize_keyword(keyword)
            if not normalized:
                continue
            entry = bucket.setdefault(
                normalized,
                {
                    "keyword": normalized,
                    "score": 0.0,
                    "clusters": [],
                },
            )
            entry["score"] += 1 + _source_diversity_bonus(cluster) + _importance_bonus(cluster.max_importance)
            entry["clusters"].append(cluster)

    ranked = sorted(
        bucket.values(),
        key=lambda item: (
            item["score"],
            len(item["clusters"]),
            SOURCE_PRIORITY.get(item["clusters"][0].representative.source_name, 0) if item["clusters"] else 0,
        ),
        reverse=True,
    )
    result = []
    for item in ranked[:3]:
        best_cluster = sorted(
            item["clusters"],
            key=lambda cluster: (
                SOURCE_PRIORITY.get(cluster.representative.source_name, 0),
                cluster.representative.published_at,
            ),
            reverse=True,
        )[0]
        result.append(
            {
                "keyword": item["keyword"],
                "score": item["score"],
                "clusters": item["clusters"],
                "representative": best_cluster.representative,
            }
        )
    return result


def _describe_keywords(*, summary_date: date, topics: list[dict]) -> dict[str, dict[str, str]]:
    if not topics or not settings.openai_api_key:
        return {}
    try:
        return OpenAISummaryService().describe_daily_keywords(
            summary_date=summary_date.isoformat(),
            topics=topics,
        )
    except Exception:
        return {}


def _extract_keyword_candidates(issue: DailyIssueRecord) -> list[str]:
    text = " ".join([issue.title, issue.summary, preview_text(issue.raw_content, max_length=300)])
    candidates = []
    for token in TOKEN_PATTERN.findall(text):
        normalized = normalize_keyword(token)
        if normalized and normalized not in candidates:
            candidates.append(normalized)
    return candidates[:8]


def tokenize(text: str) -> set[str]:
    return {normalize_keyword(token) for token in TOKEN_PATTERN.findall(text) if normalize_keyword(token)}


def extract_entity_tokens(issue: DailyIssueRecord) -> set[str]:
    text = " ".join([issue.title, issue.summary, preview_text(issue.raw_content, max_length=300)])
    entities = set()
    for token in TOKEN_PATTERN.findall(text):
        normalized = normalize_keyword(token)
        if not normalized:
            continue
        if any(char.isdigit() for char in normalized) or len(normalized) >= 3:
            entities.add(normalized)
    return entities


def normalize_keyword(token: str) -> str:
    normalized = ALIASES.get(token, token).strip().lower()
    normalized = normalized.replace("㈜", "").replace("(", " ").replace(")", " ")
    normalized = re.sub(r"[^0-9a-z가-힣%./+-]+", "", normalized)
    if len(normalized) < 2 or normalized in STOPWORDS:
        return ""
    return normalized


def _parse_json_list(raw: str | None) -> list[str]:
    if not raw:
        return []
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError:
        return []
    if not isinstance(payload, list):
        return []
    return [str(item).strip() for item in payload if str(item).strip()]


def _jaccard(left: set[str], right: set[str]) -> float:
    if not left or not right:
        return 0.0
    union = left | right
    if not union:
        return 0.0
    return len(left & right) / len(union)


def _source_diversity_bonus(cluster: IssueCluster) -> float:
    return min(max(cluster.unique_source_count - 1, 0), 3) * 0.15


def _importance_bonus(importance: str) -> float:
    mapping = {"낮음": 0.0, "보통": 0.1, "높음": 0.3, "긴급": 0.5}
    return mapping.get(importance, 0.0)


def preview_text(content: str | None, max_length: int = 220) -> str:
    if not content:
        return ""
    text = " ".join(content.split())
    return text[: max_length - 1] + "…" if len(text) > max_length else text


def _build_keyword_context(db: Session, *, summary_date: date, topic: str, keyword_item: dict) -> dict:
    prioritized_issue_ids = {issue.issue_id for cluster in keyword_item["clusters"] for issue in cluster.issues}
    try:
        docs, retrieval_method = retrieve_digest_context(
            db,
            summary_date=summary_date,
            topic=topic,
            keyword=keyword_item["keyword"],
            prioritized_issue_ids=prioritized_issue_ids,
        )
    except Exception:
        docs, retrieval_method = [], "rule_db"
    return {
        "keyword": keyword_item["keyword"],
        "titles": [doc.title for doc in docs[:3]],
        "summaries": [doc.summary for doc in docs[:2]],
        "documents": [
            {
                "issue_id": doc.issue_id,
                "title": doc.title,
                "summary": doc.summary,
                "key_points": doc.key_points,
                "importance": doc.importance,
                "source": doc.source_name,
                "url": doc.original_url,
            }
            for doc in docs
        ],
        "context_issue_ids": [doc.issue_id for doc in docs],
        "context_count": len(docs),
        "retrieval_method": retrieval_method,
    }
