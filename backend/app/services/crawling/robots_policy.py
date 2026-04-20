import asyncio
from dataclasses import dataclass
from time import monotonic
from urllib.parse import urlparse
from urllib.robotparser import RobotFileParser

import httpx

from ...config import settings


@dataclass(slots=True)
class RobotsPolicy:
    parser: RobotFileParser
    fetched_at: float
    crawl_delay: float | None
    deny_all: bool = False

    def can_fetch(self, user_agent: str, url: str) -> bool:
        if self.deny_all:
            return False
        return self.parser.can_fetch(user_agent, url)


class RobotsPolicyCache:
    def __init__(self) -> None:
        self._cache: dict[str, RobotsPolicy] = {}
        self._policy_locks: dict[str, asyncio.Lock] = {}
        self._throttle_locks: dict[str, asyncio.Lock] = {}
        self._next_allowed_at: dict[str, float] = {}

    async def can_fetch(
        self,
        url: str,
        *,
        client: httpx.AsyncClient,
        host_limiters: dict[str, asyncio.Semaphore],
    ) -> bool:
        if not settings.crawler_respect_robots:
            return True
        policy = await self._get_policy(url, client=client, host_limiters=host_limiters)
        return policy.can_fetch(settings.crawler_robots_user_agent, url)

    async def wait_for_slot(
        self,
        url: str,
        *,
        client: httpx.AsyncClient,
        host_limiters: dict[str, asyncio.Semaphore],
    ) -> None:
        if not settings.crawler_respect_robots:
            return
        policy = await self._get_policy(url, client=client, host_limiters=host_limiters)
        if not policy.crawl_delay:
            return

        host = urlparse(url).netloc
        lock = self._throttle_locks.setdefault(host, asyncio.Lock())
        async with lock:
            now = monotonic()
            next_allowed_at = self._next_allowed_at.get(host, now)
            wait_seconds = max(0.0, next_allowed_at - now)
            if wait_seconds > 0:
                await asyncio.sleep(wait_seconds)
            self._next_allowed_at[host] = monotonic() + policy.crawl_delay

    async def _get_policy(
        self,
        url: str,
        *,
        client: httpx.AsyncClient,
        host_limiters: dict[str, asyncio.Semaphore],
    ) -> RobotsPolicy:
        host = urlparse(url).netloc
        cached = self._cache.get(host)
        if cached and (monotonic() - cached.fetched_at) < settings.crawler_robots_cache_ttl_seconds:
            return cached

        lock = self._policy_locks.setdefault(host, asyncio.Lock())
        async with lock:
            cached = self._cache.get(host)
            if cached and (monotonic() - cached.fetched_at) < settings.crawler_robots_cache_ttl_seconds:
                return cached

            policy = await self._fetch_policy(url, client=client, host_limiters=host_limiters)
            self._cache[host] = policy
            return policy

    async def _fetch_policy(
        self,
        url: str,
        *,
        client: httpx.AsyncClient,
        host_limiters: dict[str, asyncio.Semaphore],
    ) -> RobotsPolicy:
        parsed = urlparse(url)
        robots_url = f"{parsed.scheme}://{parsed.netloc}/robots.txt"
        host = parsed.netloc
        limiter = host_limiters.setdefault(host, asyncio.Semaphore(settings.crawler_host_concurrency))

        try:
            async with limiter:
                response = await client.get(
                    robots_url,
                    headers={"User-Agent": settings.crawler_user_agent},
                    timeout=settings.crawler_timeout_seconds,
                    follow_redirects=True,
                )
        except httpx.HTTPError:
            return self._allow_all_policy()

        if response.status_code in {401, 403}:
            return self._deny_all_policy(robots_url)
        if response.status_code == 404:
            return self._allow_all_policy(robots_url)
        if response.status_code < 200 or response.status_code >= 300:
            return self._allow_all_policy(robots_url)

        parser = RobotFileParser()
        parser.set_url(robots_url)
        parser.parse(response.text.splitlines())
        crawl_delay = self._resolve_crawl_delay(parser)
        return RobotsPolicy(parser=parser, fetched_at=monotonic(), crawl_delay=crawl_delay, deny_all=False)

    @staticmethod
    def _resolve_crawl_delay(parser: RobotFileParser) -> float | None:
        for user_agent in (settings.crawler_robots_user_agent, "*"):
            try:
                delay = parser.crawl_delay(user_agent)
            except Exception:
                delay = None
            if delay is not None:
                return float(delay)
        return None

    @staticmethod
    def _allow_all_policy(robots_url: str = "") -> RobotsPolicy:
        parser = RobotFileParser()
        if robots_url:
            parser.set_url(robots_url)
        parser.parse(["User-agent: *", "Allow: /"])
        return RobotsPolicy(parser=parser, fetched_at=monotonic(), crawl_delay=None, deny_all=False)

    @staticmethod
    def _deny_all_policy(robots_url: str = "") -> RobotsPolicy:
        parser = RobotFileParser()
        if robots_url:
            parser.set_url(robots_url)
        parser.parse(["User-agent: *", "Disallow: /"])
        return RobotsPolicy(parser=parser, fetched_at=monotonic(), crawl_delay=None, deny_all=True)
