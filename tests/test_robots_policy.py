import asyncio

import httpx

from backend.app.services.crawling.html_source_crawler import HTMLSourceCrawler
from backend.app.services.crawling.robots_policy import RobotsPolicyCache
from backend.app.services.crawling.source_registry import SourceDefinition


def test_robots_policy_disallows_blocked_paths():
    async def run() -> None:
        def handler(request: httpx.Request) -> httpx.Response:
            if request.url.path == "/robots.txt":
                return httpx.Response(
                    200,
                    text="User-agent: *\nDisallow: /blocked\nCrawl-delay: 1",
                )
            return httpx.Response(404, text="")

        transport = httpx.MockTransport(handler)
        async with httpx.AsyncClient(transport=transport, base_url="https://example.com") as client:
            cache = RobotsPolicyCache()
            host_limiters: dict[str, asyncio.Semaphore] = {}
            assert await cache.can_fetch(
                "https://example.com/article/1",
                client=client,
                host_limiters=host_limiters,
            ) is True
            assert await cache.can_fetch(
                "https://example.com/blocked/2",
                client=client,
                host_limiters=host_limiters,
            ) is False

    asyncio.run(run())


def test_html_crawler_skips_links_blocked_by_robots():
    async def run() -> None:
        source = SourceDefinition(
            name="Test News",
            group="kr-news",
            source_type="html",
            base_url="https://example.com/",
            start_url="https://example.com/",
            region="KR",
            priority=100,
            article_contains=("/article/", "/blocked/"),
            title_selectors=("h1",),
        )

        home_html = """
        <html>
          <body>
            <a href="/article/1">allowed</a>
            <a href="/blocked/2">blocked</a>
          </body>
        </html>
        """
        article_html = """
        <html>
          <body>
            <h1>허용 기사</h1>
            <article><p>본문입니다.</p></article>
          </body>
        </html>
        """

        def handler(request: httpx.Request) -> httpx.Response:
            if request.url.path == "/robots.txt":
                return httpx.Response(200, text="User-agent: *\nDisallow: /blocked")
            if request.url.path == "/":
                return httpx.Response(200, text=home_html)
            if request.url.path == "/article/1":
                return httpx.Response(200, text=article_html)
            if request.url.path == "/blocked/2":
                return httpx.Response(200, text=article_html)
            return httpx.Response(404, text="")

        transport = httpx.MockTransport(handler)
        async with httpx.AsyncClient(transport=transport, base_url="https://example.com") as client:
            articles = await HTMLSourceCrawler().crawl_source(
                source,
                limit=10,
                client=client,
                host_limiters={},
                robots_cache=RobotsPolicyCache(),
            )

        assert len(articles) == 1
        assert articles[0].article_url == "https://example.com/article/1"

    asyncio.run(run())
