import ast
import json
from pathlib import Path
from typing import Annotated, Any

from pydantic import ValidationInfo, field_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "AI Issue Monitoring API"
    api_prefix: str = "/api"
    cors_origins: list[str] = ["http://localhost:5173", "http://127.0.0.1:5173"]
    database_url: str = "sqlite:///./app.db"
    crawler_timeout_seconds: float = 10.0
    crawler_max_items_per_run: int = 20
    crawler_limit_per_source: int = 5
    crawler_schedule_enabled: bool = True
    crawler_interval_minutes: int = 10
    crawler_processes: int = 4
    crawler_concurrency_per_process: int = 8
    crawler_host_concurrency: int = 2
    crawler_retry_count: int = 2
    crawler_respect_robots: bool = True
    crawler_robots_cache_ttl_seconds: int = 3600
    crawler_robots_user_agent: str = "*"
    report_worker_threads: int = 4
    crawler_user_agent: str = (
        "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/135.0.0.0 Safari/537.36"
    )
    crawler_source_name: str = "Naver News Main"
    crawler_source_base_url: str = "https://news.naver.com/"
    crawler_enabled_source_groups: list[str] = ["kr-news", "global-news", "news-api", "x-experimental"]
    default_report_channel: str = "Slack"
    default_report_destination: str = "#exec-briefing"
    slack_webhook_url: str | None = None
    topic_webhooks: Annotated[dict[str, str], NoDecode] = {}
    topic_channels: Annotated[dict[str, str], NoDecode] = {}
    slack_auto_send: bool = True
    openai_api_key: str | None = None
    openai_model: str = "gpt-5.4-mini"
    openai_reasoning_effort: str = "low"
    gnews_api_key: str | None = None
    gnews_base_url: str = "https://gnews.io/api/v4/top-headlines"
    x_experimental_enabled: bool = False
    x_accounts: list[str] = []
    x_max_posts_per_account: int = 3

    model_config = SettingsConfigDict(
        env_prefix="APP_",
        env_file=".env",
        extra="ignore",
    )

    @field_validator("topic_webhooks", "topic_channels", mode="before")
    @classmethod
    def parse_mapping(cls, value: Any, info: ValidationInfo) -> dict[str, str]:
        if value in (None, "", {}):
            return {}
        if isinstance(value, dict):
            return {str(key): str(item) for key, item in value.items()}
        if isinstance(value, str):
            if value.strip() == "{":
                key = f"{cls.model_config.get('env_prefix', '')}{info.field_name.upper()}"
                value = cls._read_multiline_mapping_from_env_file(key) or value
            for parser in (json.loads, ast.literal_eval):
                try:
                    parsed = parser(value)
                except (ValueError, SyntaxError, json.JSONDecodeError):
                    continue
                if isinstance(parsed, dict):
                    return {str(key): str(item) for key, item in parsed.items()}
        raise ValueError("Expected a JSON or Python-style mapping string.")

    @classmethod
    def _read_multiline_mapping_from_env_file(cls, env_key: str) -> str | None:
        env_file = cls.model_config.get("env_file")
        if not env_file:
            return None
        path = Path(env_file)
        if not path.exists():
            return None

        lines = path.read_text(encoding="utf-8").splitlines()
        prefix = f"{env_key}="
        for index, line in enumerate(lines):
            if not line.startswith(prefix):
                continue
            value = line.split("=", 1)[1].strip()
            if not value.startswith("{"):
                return value

            collected = [value]
            balance = value.count("{") - value.count("}")
            cursor = index + 1
            while balance > 0 and cursor < len(lines):
                next_line = lines[cursor].strip()
                collected.append(next_line)
                balance += next_line.count("{") - next_line.count("}")
                cursor += 1
            return "\n".join(collected)
        return None


settings = Settings()
