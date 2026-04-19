from collections import defaultdict
import json

from ...config import settings
from ..crawling.source_types import (
    TOPICS,
    TOPIC_ECONOMY,
    TOPIC_ENTERTAINMENT,
    TOPIC_INDUSTRY,
    TOPIC_INTERNATIONAL,
    TOPIC_POLITICS,
    TOPIC_SOCIAL,
    TOPIC_TECH,
)

TOPIC_KEYWORDS: dict[str, tuple[str, ...]] = {
    TOPIC_POLITICS: (
        "대통령",
        "국회",
        "정당",
        "총리",
        "장관",
        "선거",
        "외교부",
        "청와대",
        "탄핵",
        "의회",
        "government",
        "president",
        "minister",
        "parliament",
        "election",
    ),
    TOPIC_ECONOMY: (
        "금리",
        "물가",
        "환율",
        "증시",
        "주가",
        "경기",
        "경제",
        "무역",
        "수출",
        "수입",
        "inflation",
        "interest rate",
        "economy",
        "stocks",
        "market",
    ),
    TOPIC_INTERNATIONAL: (
        "미국",
        "중국",
        "일본",
        "러시아",
        "우크라이나",
        "이란",
        "가자",
        "유럽",
        "세계",
        "국제",
        "war",
        "global",
        "world",
        "foreign",
        "diplomacy",
    ),
    TOPIC_INDUSTRY: (
        "기업",
        "실적",
        "매출",
        "공장",
        "반도체",
        "투자",
        "인수",
        "합병",
        "ira",
        "manufacturing",
        "company",
        "earnings",
        "factory",
        "chip",
        "merger",
    ),
    TOPIC_TECH: (
        "ai",
        "인공지능",
        "오픈ai",
        "테크",
        "기술",
        "클라우드",
        "로봇",
        "반도체 설계",
        "software",
        "model",
        "llm",
        "chip design",
    ),
    TOPIC_SOCIAL: (
        "사건",
        "사고",
        "범죄",
        "화재",
        "병원",
        "복지",
        "교육",
        "기후",
        "재난",
        "법원",
        "court",
        "crime",
        "school",
        "health",
        "disaster",
    ),
    TOPIC_ENTERTAINMENT: (
        "연예",
        "가수",
        "배우",
        "드라마",
        "영화",
        "아이돌",
        "공연",
        "넷플릭스",
        "music",
        "actor",
        "drama",
        "movie",
        "celebrity",
    ),
}


def classify_topic(*, title: str, raw_content: str, source_name: str, topic_hint: str | None = None) -> tuple[str, float]:
    if topic_hint in TOPICS:
        return topic_hint, 0.92

    text = f"{title} {raw_content[:1500]} {source_name}".lower()
    scores: dict[str, int] = defaultdict(int)
    for topic, keywords in TOPIC_KEYWORDS.items():
        for keyword in keywords:
            if keyword.lower() in text:
                scores[topic] += 1

    if scores:
        topic, score = max(scores.items(), key=lambda item: item[1])
        if score >= 2:
            return topic, min(0.6 + score * 0.08, 0.9)

    if settings.openai_api_key:
        llm_topic = classify_topic_with_llm(title=title, raw_content=raw_content, source_name=source_name)
        if llm_topic in TOPICS:
            return llm_topic, 0.78

    return TOPIC_SOCIAL, 0.35


def classify_topic_with_llm(*, title: str, raw_content: str, source_name: str) -> str | None:
    from openai import OpenAI

    client = OpenAI(api_key=settings.openai_api_key)
    response = client.responses.create(
        model=settings.openai_model,
        reasoning={"effort": settings.openai_reasoning_effort},
        instructions=(
            "Classify the input into exactly one topic from this set: "
            + ", ".join(TOPICS)
            + "."
        ),
        input=[
            {
                "role": "developer",
                "content": (
                    "Return strict JSON only with one key named topic. "
                    'Example: {"topic":"정치"}'
                ),
            },
            {
                "role": "user",
                "content": (
                    f"출처: {source_name}\n"
                    f"제목: {title}\n"
                    f"본문:\n{raw_content[:2500]}"
                ),
            },
        ],
    )
    try:
        payload = json.loads(response.output_text.strip())
    except json.JSONDecodeError:
        return None
    topic = payload.get("topic")
    if topic in TOPICS:
        return topic
    return None
