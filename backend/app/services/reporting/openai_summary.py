import json
from dataclasses import dataclass

from openai import OpenAI

from ...config import settings
from ..crawling.source_types import TOPICS


@dataclass(slots=True)
class OpenAIArticleAnalysis:
    topic: str
    summary: str


class OpenAISummaryService:
    def __init__(self) -> None:
        self.client = OpenAI(api_key=settings.openai_api_key)

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
                "Keep factual accuracy, avoid speculation, and do not mention that you are an AI."
            ),
            input=[
                {
                    "role": "developer",
                    "content": (
                        "Return strict JSON only with keys topic and summary. "
                        'Example: {"topic":"경제","summary":"..."}'
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
        if topic not in TOPICS:
            raise ValueError("OpenAI returned an invalid topic.")
        if not summary:
            raise ValueError("OpenAI returned an empty summary.")
        return OpenAIArticleAnalysis(topic=topic, summary=summary)
