import json
from dataclasses import dataclass

from openai import OpenAI

from ...config import settings
from ..crawling.source_types import TOPICS


@dataclass(slots=True)
class OpenAIArticleAnalysis:
    topic: str
    summary: str
    importance: str
    key_points: list[str]
    research_value: str
    tracking_keywords: list[str]


class OpenAISummaryService:
    def __init__(self) -> None:
        self.client = OpenAI(api_key=settings.openai_api_key)
        self._embedding_client = None

    def analyze_article(self, *, title: str, press_name: str, raw_content: str) -> OpenAIArticleAnalysis:
        response = self.client.responses.create(
            model=settings.openai_model,
            reasoning={"effort": settings.openai_reasoning_effort},
            instructions=(
                "You are a news classification and summarization assistant. "
                "Read the article and choose exactly one topic from this set: "
                + ", ".join(TOPICS)
                + ". Treat sports news as part of the 연예 category. "
                "Then summarize the article in Korean in 3-4 concise sentences. "
                "Also assign an importance level from this set: 낮음, 보통, 높음, 긴급. "
                "Return 2-3 concise key points, one short research_value sentence explaining "
                "why this article is worth tracking, and 2-4 tracking_keywords. "
                "Keep factual accuracy, avoid speculation, and do not mention that you are an AI."
            ),
            input=[
                {
                    "role": "developer",
                    "content": (
                        "Return strict JSON only with keys "
                        "topic, summary, importance, key_points, research_value, tracking_keywords. "
                        'Example: {"topic":"경제","summary":"...","importance":"높음",'
                        '"key_points":["...","..."],"research_value":"...",'
                        '"tracking_keywords":["...","..."]}'
                    ),
                },
                {
                    "role": "user",
                    "content": (
                        f"언론사: {press_name}\n"
                        f"제목: {title}\n"
                        f"본문:\n{raw_content}"
                    ),
                },
            ],
        )
        payload = json.loads(response.output_text.strip())
        topic = payload.get("topic")
        summary = (payload.get("summary") or "").strip()
        importance = (payload.get("importance") or "").strip()
        key_points = [str(item).strip() for item in (payload.get("key_points") or []) if str(item).strip()]
        research_value = (payload.get("research_value") or "").strip()
        tracking_keywords = [
            str(item).strip() for item in (payload.get("tracking_keywords") or []) if str(item).strip()
        ]
        if topic not in TOPICS:
            raise ValueError("OpenAI returned an invalid topic.")
        if not summary:
            raise ValueError("OpenAI returned an empty summary.")
        if importance not in {"낮음", "보통", "높음", "긴급"}:
            raise ValueError("OpenAI returned an invalid importance level.")
        return OpenAIArticleAnalysis(
            topic=topic,
            summary=summary,
            importance=importance,
            key_points=key_points[:3],
            research_value=research_value,
            tracking_keywords=tracking_keywords[:4],
        )

    def describe_daily_keywords(self, *, summary_date: str, topics: list[dict]) -> dict[str, dict[str, str]]:
        response = self.client.responses.create(
            model=settings.openai_model,
            reasoning={"effort": settings.openai_reasoning_effort},
            instructions=(
                "You are a Korean newsroom research assistant. "
                "For each topic and keyword, write a short factual Korean explanation sentence "
                "describing why that keyword drew attention that day. "
                "Use the provided retrieved article context to ground the explanation. "
                "Prefer cross-article common context over a single headline. "
                "If the retrieved documents disagree, stay conservative and describe only the overlap. "
                "Do not invent facts."
            ),
            input=[
                {
                    "role": "developer",
                    "content": (
                        "Return strict JSON only. "
                        'Format: {"정치":{"키워드":"설명"},"경제":{"키워드":"설명"}}'
                    ),
                },
                {
                    "role": "user",
                    "content": json.dumps(
                        {
                            "summary_date": summary_date,
                            "topics": topics,
                        },
                        ensure_ascii=False,
                    ),
                },
            ],
        )
        payload = json.loads(response.output_text.strip())
        if not isinstance(payload, dict):
            raise ValueError("OpenAI returned an invalid daily keyword description payload.")
        normalized: dict[str, dict[str, str]] = {}
        for topic, keyword_map in payload.items():
            if not isinstance(keyword_map, dict):
                continue
            normalized[str(topic)] = {
                str(keyword): str(description).strip()
                for keyword, description in keyword_map.items()
                if str(description).strip()
            }
        return normalized

    def embed_text(self, text: str) -> list[float]:
        if self._embedding_client is None:
            from langchain_openai import OpenAIEmbeddings

            self._embedding_client = OpenAIEmbeddings(
                api_key=settings.openai_api_key,
                model=settings.openai_embedding_model,
            )
        return [float(item) for item in self._embedding_client.embed_query(text)]
