from dataclasses import dataclass
from datetime import datetime


TOPIC_POLITICS = "정치"
TOPIC_ECONOMY = "경제"
TOPIC_INTERNATIONAL = "국제"
TOPIC_INDUSTRY = "산업/기업"
TOPIC_TECH = "기술/AI"
TOPIC_SOCIAL = "사회"
TOPIC_ENTERTAINMENT = "연예"

TOPICS = [
    TOPIC_POLITICS,
    TOPIC_ECONOMY,
    TOPIC_INTERNATIONAL,
    TOPIC_INDUSTRY,
    TOPIC_TECH,
    TOPIC_SOCIAL,
    TOPIC_ENTERTAINMENT,
]

TOPIC_PRIORITY = {
    TOPIC_POLITICS: 100,
    TOPIC_ECONOMY: 95,
    TOPIC_INTERNATIONAL: 90,
    TOPIC_INDUSTRY: 80,
    TOPIC_TECH: 75,
    TOPIC_SOCIAL: 60,
    TOPIC_ENTERTAINMENT: 40,
}


@dataclass(slots=True)
class CrawledArticle:
    title: str
    article_url: str
    press_name: str
    published_at: datetime | None
    raw_content: str
    source_name: str
    source_type: str
    region: str | None = None
    topic_hint: str | None = None
    priority_score: int = 0
