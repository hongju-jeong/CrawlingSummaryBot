from dataclasses import dataclass
from datetime import datetime
from urllib.parse import urljoin
import re

import httpx
from bs4 import BeautifulSoup
from zoneinfo import ZoneInfo

from ..config import settings

SEOUL_TZ = ZoneInfo("Asia/Seoul")
ARTICLE_LINK_PATTERN = re.compile(r"^https://n\.news\.naver\.com/article/\d+/\d+$")


@dataclass
class CrawledArticle:
    title: str
    article_url: str
    press_name: str
    published_at: datetime | None
    raw_content: str


class NaverLatestNewsCrawler:
    def __init__(self) -> None:
        self.headers = {"User-Agent": settings.crawler_user_agent}
        self.timeout = settings.crawler_timeout_seconds

    def crawl_latest_news(self, limit: int) -> list[CrawledArticle]:
        latest_links = self._fetch_latest_article_links(limit)
        articles: list[CrawledArticle] = []
        for article_url in latest_links:
            article = self._fetch_article(article_url)
            if article is not None:
                articles.append(article)
        return articles

    def _fetch_latest_article_links(self, limit: int) -> list[str]:
        with httpx.Client(headers=self.headers, timeout=self.timeout, follow_redirects=True) as client:
            response = client.get(settings.crawler_source_base_url)
            response.raise_for_status()

        soup = BeautifulSoup(response.text, "html.parser")
        links: list[str] = []
        seen: set[str] = set()

        for anchor in soup.select("a[href]"):
            href = (anchor.get("href") or "").strip()
            if href.startswith("/"):
                href = urljoin(settings.crawler_source_base_url, href)
            if not ARTICLE_LINK_PATTERN.match(href):
                continue
            if href in seen:
                continue
            seen.add(href)
            links.append(href)
            if len(links) >= limit:
                break

        return links

    def _fetch_article(self, article_url: str) -> CrawledArticle | None:
        with httpx.Client(headers=self.headers, timeout=self.timeout, follow_redirects=True) as client:
            response = client.get(article_url)
            response.raise_for_status()

        soup = BeautifulSoup(response.text, "html.parser")
        title = self._extract_title(soup)
        raw_content = self._extract_content(soup)
        if not title or not raw_content:
            return None

        press_name = self._extract_press_name(soup)
        published_at = self._extract_published_at(soup)
        return CrawledArticle(
            title=title,
            article_url=article_url,
            press_name=press_name,
            published_at=published_at,
            raw_content=raw_content,
        )

    @staticmethod
    def _extract_title(soup: BeautifulSoup) -> str:
        element = soup.select_one(".media_end_head_title")
        if element is None:
            return ""
        return " ".join(element.get_text(" ", strip=True).split())

    @staticmethod
    def _extract_press_name(soup: BeautifulSoup) -> str:
        element = soup.select_one(".media_end_head_top_press")
        if element is not None:
            return " ".join(element.get_text(" ", strip=True).split())
        meta = soup.select_one("meta[property='og:article:author']")
        if meta and meta.get("content"):
            return meta["content"].split("|")[0].strip()
        return settings.crawler_source_name

    @staticmethod
    def _extract_published_at(soup: BeautifulSoup) -> datetime | None:
        element = soup.select_one("._ARTICLE_DATE_TIME")
        date_string = element.get("data-date-time") if element is not None else None
        if not date_string:
            return None
        try:
            return datetime.strptime(date_string, "%Y-%m-%d %H:%M:%S").replace(tzinfo=SEOUL_TZ)
        except ValueError:
            return None

    @staticmethod
    def _extract_content(soup: BeautifulSoup) -> str:
        article = soup.select_one("#dic_area")
        if article is None:
            return ""

        for selector in [
            "script",
            "style",
            ".byline_s",
            ".media_end_summary",
            ".promotion",
            ".copyright",
        ]:
            for node in article.select(selector):
                node.decompose()

        text = " ".join(article.get_text(" ", strip=True).split())
        return text
