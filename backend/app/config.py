from pydantic_settings import BaseSettings, SettingsConfigDict


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


settings = Settings()
