from dataclasses import dataclass

import httpx

from ..config import settings


@dataclass
class SlackSendResult:
    success: bool
    status_code: int | None
    response_body: str | None
    error_message: str | None


class SlackReporter:
    def __init__(self) -> None:
        self.webhook_url = settings.slack_webhook_url
        self.timeout = settings.crawler_timeout_seconds

    def send_summary(self, summary_text: str) -> SlackSendResult:
        if not self.webhook_url:
            return SlackSendResult(
                success=False,
                status_code=None,
                response_body=None,
                error_message="Slack webhook URL is not configured.",
            )

        try:
            with httpx.Client(timeout=self.timeout) as client:
                response = client.post(self.webhook_url, json={"text": summary_text})
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
