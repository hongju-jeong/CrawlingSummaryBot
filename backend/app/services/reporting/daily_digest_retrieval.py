import hashlib
import json
import math
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta

from langchain_core.documents import Document
from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from ...config import settings
from ...models import Issue, IssueEmbedding, IssueSummary
from .openai_summary import OpenAISummaryService

try:
    import faiss  # type: ignore
    import numpy as np

    FAISS_AVAILABLE = True
except Exception:
    faiss = None
    np = None
    FAISS_AVAILABLE = False


@dataclass(slots=True)
class DigestContextDoc:
    issue_id: int
    title: str
    summary: str
    key_points: list[str]
    importance: str
    source_name: str
    original_url: str | None
    published_at: datetime
    similarity_score: float
    metadata: dict[str, object]

    def to_document(self) -> Document:
        content_parts = [self.title, self.summary]
        if self.key_points:
            content_parts.append("핵심 포인트: " + " / ".join(self.key_points))
        return Document(
            page_content="\n".join(part for part in content_parts if part),
            metadata={
                "issue_id": self.issue_id,
                "importance": self.importance,
                "source_name": self.source_name,
                "original_url": self.original_url,
                "published_at": self.published_at.isoformat(),
                **self.metadata,
            },
        )


def build_issue_embedding_text(
    *,
    title: str,
    topic: str,
    summary: str,
    key_points: list[str],
    research_value: str | None,
    tracking_keywords: list[str],
) -> str:
    parts = [
        f"토픽: {topic}",
        f"제목: {title}",
        f"요약: {summary}",
    ]
    if key_points:
        parts.append("핵심 포인트: " + " / ".join(key_points))
    if research_value:
        parts.append(f"리서치 포인트: {research_value}")
    if tracking_keywords:
        parts.append("추적 키워드: " + ", ".join(tracking_keywords))
    return "\n".join(parts)


def upsert_issue_embedding(
    db: Session,
    *,
    issue: Issue,
    summary: IssueSummary,
    key_points: list[str],
    research_value: str,
    tracking_keywords: list[str],
) -> None:
    if not settings.openai_api_key or not settings.daily_summary_rag_enabled:
        return

    embedding_text = build_issue_embedding_text(
        title=issue.title,
        topic=issue.category,
        summary=summary.summary_text,
        key_points=key_points,
        research_value=research_value,
        tracking_keywords=tracking_keywords,
    )
    content_hash = hashlib.sha256(embedding_text.encode("utf-8")).hexdigest()
    row = db.scalar(select(IssueEmbedding).where(IssueEmbedding.issue_id == issue.id))
    if row is not None and row.content_hash == content_hash:
        return

    vector = OpenAISummaryService().embed_text(embedding_text)
    payload = json.dumps(vector)
    if row is None:
        row = IssueEmbedding(
            issue_id=issue.id,
            embedding_model=settings.openai_embedding_model,
            content_hash=content_hash,
            embedding_json=payload,
        )
        db.add(row)
    else:
        row.embedding_model = settings.openai_embedding_model
        row.content_hash = content_hash
        row.embedding_json = payload


def retrieve_digest_context(
    db: Session,
    *,
    summary_date: date,
    topic: str,
    keyword: str,
    prioritized_issue_ids: set[int] | None = None,
    query_vector: list[float] | None = None,
) -> tuple[list[DigestContextDoc], str]:
    start_dt = datetime.combine(summary_date - timedelta(days=max(settings.daily_summary_rag_lookback_days - 1, 0)), time.min)
    end_dt = datetime.combine(summary_date, time.max)
    rows = (
        db.execute(
            select(Issue, IssueSummary, IssueEmbedding)
            .join(IssueSummary, IssueSummary.issue_id == Issue.id)
            .outerjoin(IssueEmbedding, IssueEmbedding.issue_id == Issue.id)
            .where(
                Issue.category == topic,
                Issue.published_at >= start_dt,
                Issue.published_at <= end_dt,
            )
            .order_by(Issue.published_at.desc(), Issue.created_at.desc())
        )
        .all()
    )
    if not rows:
        return [], "rule_db"

    retrieval_method = "rule_db"
    if query_vector is None and settings.daily_summary_rag_enabled and settings.openai_api_key:
        try:
            query_vector = OpenAISummaryService().embed_text(f"{topic} {keyword}")
            retrieval_method = "embedding"
        except Exception:
            query_vector = None
    elif query_vector is not None:
        retrieval_method = "embedding"

    docs: list[DigestContextDoc] = []
    faiss_docs: list[DigestContextDoc] = []
    faiss_vectors: list[list[float]] = []
    for issue, summary, embedding in rows:
        key_points = _parse_json_list(summary.key_points_json)
        tracking_keywords = _parse_json_list(summary.tracking_keywords_json)
        keyword_hit_score = _keyword_hit_score(keyword, issue=issue, summary=summary.summary_text, tracking_keywords=tracking_keywords)
        priority_boost = 0.45 if prioritized_issue_ids and issue.id in prioritized_issue_ids else 0.0
        importance_boost = {"낮음": 0.0, "보통": 0.05, "높음": 0.15, "긴급": 0.25}.get(summary.importance or "보통", 0.0)
        recency_boost = 0.1 if issue.published_at and issue.published_at.date() == summary_date else 0.0
        doc = DigestContextDoc(
            issue_id=issue.id,
            title=issue.title,
            summary=summary.summary_text,
            key_points=key_points,
            importance=summary.importance or "보통",
            source_name=issue.press_name or "출처 미상",
            original_url=issue.original_url,
            published_at=issue.published_at or issue.created_at,
            similarity_score=keyword_hit_score + priority_boost + importance_boost + recency_boost,
            metadata={
                "tracking_keywords": tracking_keywords,
                "research_value": summary.research_value,
            },
        )
        docs.append(doc)
        if query_vector is not None and embedding is not None:
            vector = _parse_vector(embedding.embedding_json)
            if vector:
                if FAISS_AVAILABLE:
                    faiss_docs.append(doc)
                    faiss_vectors.append(vector)
                else:
                    doc.similarity_score += max(_cosine_similarity(query_vector, vector), 0.0)

    if query_vector is not None and faiss_docs and FAISS_AVAILABLE:
        try:
            similarity_scores = _faiss_similarity_scores(query_vector, faiss_vectors)
            for doc, score in zip(faiss_docs, similarity_scores, strict=True):
                doc.similarity_score += max(score, 0.0)
            retrieval_method = "faiss"
        except Exception:
            for doc, vector in zip(faiss_docs, faiss_vectors, strict=True):
                doc.similarity_score += max(_cosine_similarity(query_vector, vector), 0.0)
    ranked = sorted(docs, key=lambda item: (item.similarity_score, item.published_at), reverse=True)
    return ranked[: settings.daily_summary_rag_top_k], retrieval_method


def _keyword_hit_score(keyword: str, *, issue: Issue, summary: str, tracking_keywords: list[str]) -> float:
    normalized = keyword.lower()
    score = 0.0
    if normalized in (issue.title or "").lower():
        score += 0.8
    if normalized in (summary or "").lower():
        score += 0.6
    if any(normalized == item.lower() for item in tracking_keywords):
        score += 0.7
    if normalized in (issue.raw_content or "").lower():
        score += 0.3
    return score


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


def _parse_vector(raw: str) -> list[float]:
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError:
        return []
    if not isinstance(payload, list):
        return []
    return [float(item) for item in payload]


def _cosine_similarity(left: list[float], right: list[float]) -> float:
    if not left or not right or len(left) != len(right):
        return 0.0
    left_norm = math.sqrt(sum(item * item for item in left))
    right_norm = math.sqrt(sum(item * item for item in right))
    if left_norm == 0 or right_norm == 0:
        return 0.0
    return sum(l * r for l, r in zip(left, right, strict=True)) / (left_norm * right_norm)


def _faiss_similarity_scores(query_vector: list[float], vectors: list[list[float]]) -> list[float]:
    if not FAISS_AVAILABLE or not vectors:
        raise RuntimeError("FAISS is not available.")
    if not query_vector or any(len(vector) != len(query_vector) for vector in vectors):
        raise ValueError("All vectors must match the query vector dimension.")

    matrix = np.array(vectors, dtype="float32")
    query = np.array([query_vector], dtype="float32")

    faiss.normalize_L2(matrix)
    faiss.normalize_L2(query)

    index = faiss.IndexFlatIP(matrix.shape[1])
    index.add(matrix)
    scores, indices = index.search(query, len(vectors))

    result = [0.0] * len(vectors)
    for rank, row_index in enumerate(indices[0]):
        if row_index < 0:
            continue
        result[int(row_index)] = float(scores[0][rank])
    return result
