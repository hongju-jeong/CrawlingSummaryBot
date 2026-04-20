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
            lines = [
                f"[{topic}] {summary_text}",
                f"출처: {source_name}",
            ]
            if article_url:
                lines.append(f"링크: {article_url}")
            message = "\n".join(lines)
            with httpx.Client(timeout=self.timeout) as client:
                response = client.post(webhook_url, json={"text": message})
                ok = response.status_code >= 200 and response.status_code < 300
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
