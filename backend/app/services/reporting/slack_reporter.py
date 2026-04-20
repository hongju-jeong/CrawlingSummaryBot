from dataclasses import dataclass

import httpx

from ...config import settings


@dataclass
class SlackSendResult:
    success: bool
    status_code: int | None
    response_body: str | None
    error_message: str | None


class SlackReporter:
    def __init__(self) -> None:
        self.default_webhook_url = settings.slack_webhook_url
        self.timeout = settings.crawler_timeout_seconds

    def send_summary(
        self,
        summary_text: str,
        *,
        topic: str,
        importance: str | None,
        key_points: list[str] | None,
        research_value: str | None,
        tracking_keywords: list[str] | None,
        source_name: str,
        article_url: str | None,
    ) -> SlackSendResult:
        webhook_url = self._resolve_webhook_url(topic)
        if not webhook_url:
            return SlackSendResult(
                success=False,
                status_code=None,
                response_body=None,
                error_message=f"Slack webhook URL is not configured for topic '{topic}'.",
            )

        try:
            message = format_article_message(
                topic=topic,
                summary_text=summary_text,
                importance=importance,
                key_points=key_points or [],
                research_value=research_value,
                tracking_keywords=tracking_keywords or [],
                source_name=source_name,
                article_url=article_url,
            )
            return self.send_text(webhook_url, message)
        except Exception as error:
            return SlackSendResult(
                success=False,
                status_code=None,
                response_body=None,
                error_message=str(error),
            )

    def send_text(self, webhook_url: str, text: str) -> SlackSendResult:
        try:
            with httpx.Client(timeout=self.timeout) as client:
                response = client.post(webhook_url, json={"text": text})
                ok = 200 <= response.status_code < 300
                return SlackSendResult(
                    success=ok,
                    status_code=response.status_code,
                    response_body=response.text,
                    error_message=None if ok else f"Slack webhook returned {response.status_code}",
                )
        except Exception as error:
            return SlackSendResult(
                success=False,
                status_code=None,
                response_body=None,
                error_message=str(error),
            )

    def _resolve_webhook_url(self, topic: str) -> str | None:
        return settings.topic_webhooks.get(topic) or self.default_webhook_url


def format_article_message(
    *,
    topic: str,
    summary_text: str,
    importance: str | None,
    key_points: list[str],
    research_value: str | None,
    tracking_keywords: list[str],
    source_name: str,
    article_url: str | None,
) -> str:
    if importance in {"높음", "긴급"}:
        lines = [f"[{topic}][{importance}] {summary_text}"]
        if key_points:
            lines.append("핵심 포인트: " + " / ".join(key_points[:3]))
        if research_value:
            lines.append(f"리서치 포인트: {research_value}")
        if tracking_keywords:
            lines.append("추적 키워드: " + ", ".join(tracking_keywords[:4]))
    else:
        lines = [f"[{topic}] {summary_text}"]
    lines.append(f"출처: {source_name}")
    if article_url:
        lines.append(f"링크: {article_url}")
    return "\n".join(lines)
