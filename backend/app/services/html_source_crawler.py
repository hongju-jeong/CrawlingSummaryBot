import asyncio
from collections.abc import Iterable
from datetime import datetime
from email.utils import parsedate_to_datetime
import json
from urllib.parse import urljoin, urlparse

import httpx
from bs4 import BeautifulSoup

from ..config import settings
from .runtime_profile import get_effective_crawler_host_concurrency
from .source_registry import SourceDefinition
from .source_types import CrawledArticle


class HTMLSourceCrawler:
    def __init__(self) -> None:
        self.headers = {"User-Agent": settings.crawler_user_agent}
        self.timeout = settings.crawler_timeout_seconds

    async def crawl_source(
        self,
        source: SourceDefinition,
        *,
        limit: int,
        client: httpx.AsyncClient,
        host_limiters: dict[str, asyncio.Semaphore],
    ) -> list[CrawledArticle]:
        html = await self._fetch_text(client, source.start_url, host_limiters)
        if not html:
            return []

        links = self._extract_article_links(source, html, limit=limit)
        tasks = [
            self._fetch_article(source, article_url=article_url, client=client, host_limiters=host_limiters)
            for article_url in links
        ]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        articles: list[CrawledArticle] = []
        for result in results:
            if isinstance(result, CrawledArticle):
                articles.append(result)
        return articles

    async def _fetch_article(
        self,
        source: SourceDefinition,
        *,
        article_url: str,
        client: httpx.AsyncClient,
        host_limiters: dict[str, asyncio.Semaphore],
    ) -> CrawledArticle | None:
        html = await self._fetch_text(client, article_url, host_limiters)
        if not html:
            return None

        soup = BeautifulSoup(html, "html.parser")
        title = self._extract_first_text(soup, source.title_selectors) or self._extract_meta(
            soup, "og:title"
        )
        raw_content = self._extract_content(soup, source.content_selectors)
        if not title or not raw_content:
            return None

        press_name = self._extract_press_name(soup, source)
        published_at = self._extract_published_at(soup)
        return CrawledArticle(
            title=" ".join(title.split()),
            article_url=article_url,
            press_name=" ".join(press_name.split()),
            published_at=published_at,
            raw_content=raw_content,
            source_name=source.name,
            source_type=source.source_type,
            region=source.region,
            priority_score=source.priority,
        )

    async def _fetch_text(
        self,
        client: httpx.AsyncClient,
        url: str,
        host_limiters: dict[str, asyncio.Semaphore],
    ) -> str:
        host = urlparse(url).netloc
        limiter = host_limiters.setdefault(host, asyncio.Semaphore(get_effective_crawler_host_concurrency()))
        for attempt in range(settings.crawler_retry_count + 1):
            try:
                async with limiter:
                    response = await client.get(url, headers=self.headers, timeout=self.timeout, follow_redirects=True)
                response.raise_for_status()
                return response.text
            except httpx.HTTPError:
                if attempt >= settings.crawler_retry_count:
                    return ""
                await asyncio.sleep(min(0.5 * (attempt + 1), 1.5))
        return ""

    def _extract_article_links(self, source: SourceDefinition, html: str, *, limit: int) -> list[str]:
        soup = BeautifulSoup(html, "html.parser")
        anchors: Iterable = (
            soup.select(", ".join(source.latest_link_selectors))
            if source.latest_link_selectors
            else soup.select("a[href]")
        )

        links: list[str] = []
        seen: set[str] = set()
        for anchor in anchors:
            href = (anchor.get("href") or "").strip()
            if not href:
                continue
            full_url = urljoin(source.base_url, href)
            if not self._is_article_link(source, full_url):
                continue
            if full_url in seen:
                continue
            seen.add(full_url)
            links.append(full_url)
            if len(links) >= limit:
                break
        return links

    @staticmethod
    def _is_article_link(source: SourceDefinition, url: str) -> bool:
        if source.article_excludes and any(fragment in url for fragment in source.article_excludes):
            return False
        if source.article_prefixes and any(url.startswith(prefix) for prefix in source.article_prefixes):
            return True
        if source.article_contains and any(fragment in url for fragment in source.article_contains):
            return True
        return False

    @staticmethod
    def _extract_first_text(soup: BeautifulSoup, selectors: tuple[str, ...]) -> str:
        for selector in selectors:
            element = soup.select_one(selector)
            if element is not None:
                text = element.get_text(" ", strip=True)
                if text:
                    return text
        return ""

    @staticmethod
    def _extract_content(soup: BeautifulSoup, selectors: tuple[str, ...]) -> str:
        for selector in selectors:
            nodes = soup.select(selector)
            if not nodes:
                continue
            text = HTMLSourceCrawler._extract_text_from_nodes(nodes)
            if text:
                return text

        fallback = soup.select("article")
        if fallback:
            return HTMLSourceCrawler._extract_text_from_nodes(fallback)
        return ""

    @staticmethod
    def _extract_text_from_nodes(nodes: list[BeautifulSoup] | list) -> str:
        texts: list[str] = []
        for node in nodes:
            for selector in ["script", "style", "figure", "aside", "noscript"]:
                for nested in node.select(selector):
                    nested.decompose()
            text = " ".join(node.get_text(" ", strip=True).split())
            if text:
                texts.append(text)
        deduped: list[str] = []
        seen: set[str] = set()
        for text in texts:
            if text in seen:
                continue
            seen.add(text)
            deduped.append(text)
        return " ".join(deduped)

    @staticmethod
    def _extract_meta(soup: BeautifulSoup, property_name: str) -> str:
        tag = soup.select_one(f"meta[property='{property_name}']")
        if tag is not None and tag.get("content"):
            return str(tag["content"]).strip()
        return ""

    def _extract_press_name(self, soup: BeautifulSoup, source: SourceDefinition) -> str:
        selector_text = self._extract_first_text(soup, source.press_selectors) if source.press_selectors else ""
        meta_candidates = [
            self._extract_meta(soup, "og:site_name"),
            self._extract_meta(soup, "article:publisher"),
            self._extract_meta(soup, "og:article:author"),
        ]
        ldjson_publisher = self._extract_ldjson_publisher(soup)
        for candidate in [selector_text, *meta_candidates, ldjson_publisher, source.name]:
            normalized = self._normalize_press_name(candidate)
            if normalized:
                return normalized
        return source.name

    @staticmethod
    def _normalize_press_name(value: str | None) -> str:
        if not value:
            return ""
        normalized = " ".join(str(value).split())
        if normalized.startswith("http://") or normalized.startswith("https://"):
            return ""
        if "|" in normalized:
            parts = [part.strip() for part in normalized.split("|") if part.strip()]
            if parts:
                normalized = parts[-1]
        if normalized.lower().startswith("daum |"):
            normalized = normalized.split("|", 1)[-1].strip()
        return normalized

    @staticmethod
    def _extract_ldjson_publisher(soup: BeautifulSoup) -> str:
        for script in soup.select("script[type='application/ld+json']"):
            raw = script.string or script.get_text()
            if not raw:
                continue
            try:
                payload = json.loads(raw)
            except json.JSONDecodeError:
                continue
            publisher = HTMLSourceCrawler._find_publisher_name(payload)
            if publisher:
                return publisher
        return ""

    @staticmethod
    def _find_publisher_name(payload: object) -> str:
        if isinstance(payload, dict):
            publisher = payload.get("publisher")
            if isinstance(publisher, dict) and isinstance(publisher.get("name"), str):
                return str(publisher["name"])
            for value in payload.values():
                result = HTMLSourceCrawler._find_publisher_name(value)
                if result:
                    return result
        if isinstance(payload, list):
            for item in payload:
                result = HTMLSourceCrawler._find_publisher_name(item)
                if result:
                    return result
        return ""

    def _extract_published_at(self, soup: BeautifulSoup) -> datetime | None:
        candidates = [
            self._extract_meta(soup, "article:published_time"),
            self._extract_meta(soup, "og:article:published_time"),
        ]
        time_tag = soup.select_one("time[datetime]")
        if time_tag is not None and time_tag.get("datetime"):
            candidates.append(str(time_tag["datetime"]))

        for candidate in candidates:
            if not candidate:
                continue
            parsed = self._parse_datetime(candidate)
            if parsed is not None:
                return parsed
        return None

    @staticmethod
    def _parse_datetime(value: str) -> datetime | None:
        normalized = value.strip()
        try:
            return datetime.fromisoformat(normalized.replace("Z", "+00:00"))
        except ValueError:
            pass
        try:
            return parsedate_to_datetime(normalized)
        except (TypeError, ValueError):
            return None
