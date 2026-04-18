from datetime import datetime, timezone

from ..config import settings
from .source_registry import SourceDefinition
from .source_types import CrawledArticle, TOPIC_POLITICS


class XExperimentalCrawler:
    async def crawl_source(self, source: SourceDefinition, *, limit: int) -> list[CrawledArticle]:
        if not settings.x_experimental_enabled or not settings.x_accounts:
            return []

        try:
            from twscrape import API  # type: ignore
        except Exception:
            return []

        api = API()
        articles: list[CrawledArticle] = []
        per_account_limit = min(limit, settings.x_max_posts_per_account)

        for account in settings.x_accounts:
            try:
                user = await api.user_by_login(account)
                if user is None:
                    continue
                count = 0
                async for tweet in api.user_tweets(user.id, limit=per_account_limit):
                    text = " ".join((tweet.rawContent or "").split())
                    if not text:
                        continue
                    tweet_url = f"https://x.com/{account}/status/{tweet.id}"
                    published_at = getattr(tweet, "date", None) or datetime.now(timezone.utc)
                    articles.append(
                        CrawledArticle(
                            title=text[:140],
                            article_url=tweet_url,
                            press_name=f"X @{account}",
                            published_at=published_at,
                            raw_content=text,
                            source_name=source.name,
                            source_type=source.source_type,
                            region=source.region,
                            topic_hint=TOPIC_POLITICS,
                            priority_score=source.priority,
                        )
                    )
                    count += 1
                    if count >= per_account_limit:
                        break
            except Exception:
                continue

        return articles

