from datetime import datetime
from typing import Any

import httpx

from ...config import settings
from ..runtime.crawl_control import is_cancelled
from .source_registry import SourceDefinition
from .source_types import CrawledArticle


class GNewsAPICrawler:
    async def crawl_source(
        self,
        source: SourceDefinition,
        *,
        limit: int,
        client: httpx.AsyncClient,
        cancel_token: Any | None = None,
    ) -> list[CrawledArticle]:
        if not settings.gnews_api_key or is_cancelled(cancel_token):
            return []

        response = await client.get(
            settings.gnews_base_url,
            params={
                "token": settings.gnews_api_key,
                "lang": "en",
                "max": limit,
            },
            follow_redirects=True,
            timeout=settings.crawler_timeout_seconds,
        )
        response.raise_for_status()
        payload = response.json()
        articles: list[CrawledArticle] = []
        for item in payload.get("articles", []):
            if is_cancelled(cancel_token):
                break
            title = (item.get("title") or "").strip()
            article_url = (item.get("url") or "").strip()
            raw_content = (item.get("content") or item.get("description") or "").strip()
            if not title or not article_url or not raw_content:
                continue
            published_at = self._parse_datetime(item.get("publishedAt"))
            articles.append(
                CrawledArticle(
                    title=title,
                    article_url=article_url,
                    press_name=((item.get("source") or {}).get("name") or source.name).strip(),
                    published_at=published_at,
                    raw_content=" ".join(raw_content.split()),
                    source_name=source.name,
                    source_type=source.source_type,
                    region=source.region,
                    priority_score=source.priority,
                )
            )
        return articles

    @staticmethod
    def _parse_datetime(value: str | None) -> datetime | None:
        if not value:
            return None
        try:
            return datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            return None
