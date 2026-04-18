import asyncio
from concurrent.futures import ProcessPoolExecutor, as_completed
from datetime import datetime, timezone

import httpx

from ..config import settings
from .gnews_api_crawler import GNewsAPICrawler
from .html_source_crawler import HTMLSourceCrawler
from .source_registry import SourceDefinition, get_source_definitions
from .source_types import CrawledArticle, TOPIC_PRIORITY
from .x_experimental_crawler import XExperimentalCrawler


class MultiSourcePollingCrawler:
    def crawl_latest(self, limit_per_source: int) -> list[CrawledArticle]:
        groups = [group for group in settings.crawler_enabled_source_groups if get_source_definitions(group)]
        if not groups:
            return []

        max_workers = min(settings.crawler_processes, len(groups))
        if max_workers <= 1:
            articles = asyncio.run(_crawl_group_async(groups[0], limit_per_source))
            return _prioritize_articles(articles)

        articles: list[CrawledArticle] = []
        with ProcessPoolExecutor(max_workers=max_workers) as executor:
            futures = [executor.submit(_crawl_group_sync, group, limit_per_source) for group in groups]
            for future in as_completed(futures):
                try:
                    articles.extend(future.result())
                except Exception:
                    continue
        return _prioritize_articles(articles)


def _crawl_group_sync(group: str, limit_per_source: int) -> list[CrawledArticle]:
    return asyncio.run(_crawl_group_async(group, limit_per_source))


async def _crawl_group_async(group: str, limit_per_source: int) -> list[CrawledArticle]:
    source_definitions = get_source_definitions(group)
    if not source_definitions:
        return []

    headers = {"User-Agent": settings.crawler_user_agent}
    limits = httpx.Limits(max_connections=settings.crawler_concurrency_per_process)
    host_limiters: dict[str, asyncio.Semaphore] = {}
    async with httpx.AsyncClient(headers=headers, timeout=settings.crawler_timeout_seconds, limits=limits) as client:
        tasks = [
            _crawl_source(
                definition,
                client=client,
                limit_per_source=limit_per_source,
                host_limiters=host_limiters,
            )
            for definition in source_definitions
        ]
        results = await asyncio.gather(*tasks, return_exceptions=True)

    articles: list[CrawledArticle] = []
    for result in results:
        if isinstance(result, list):
            articles.extend(result)
    return articles


async def _crawl_source(
    source: SourceDefinition,
    *,
    client: httpx.AsyncClient,
    limit_per_source: int,
    host_limiters: dict[str, asyncio.Semaphore],
) -> list[CrawledArticle]:
    if source.source_type == "html":
        return await HTMLSourceCrawler().crawl_source(
            source,
            limit=limit_per_source,
            client=client,
            host_limiters=host_limiters,
        )
    if source.source_type == "api":
        return await GNewsAPICrawler().crawl_source(source, limit=limit_per_source, client=client)
    if source.source_type == "experimental_x":
        return await XExperimentalCrawler().crawl_source(source, limit=limit_per_source)
    return []


def _prioritize_articles(articles: list[CrawledArticle]) -> list[CrawledArticle]:
    seen: set[str] = set()
    unique_articles: list[CrawledArticle] = []
    for article in sorted(
        articles,
        key=lambda item: (
            TOPIC_PRIORITY.get(item.topic_hint or "", 0) + item.priority_score,
            _as_timestamp(item.published_at),
        ),
        reverse=True,
    ):
        if article.article_url in seen:
            continue
        seen.add(article.article_url)
        unique_articles.append(article)
    return unique_articles


def _as_timestamp(value: datetime | None) -> int:
    if value is None:
        return 0
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return int(value.timestamp())
