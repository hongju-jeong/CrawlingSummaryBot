from datetime import datetime

from pydantic import BaseModel, Field


class IssueListItem(BaseModel):
    id: int
    title: str
    source: str
    category: str
    time: str
    report_status: str


class IssueListResponse(BaseModel):
    items: list[IssueListItem]
    total: int


class ReportPreviewResponse(BaseModel):
    issue_id: int
    title: str
    source: str
    category: str
    channel: str
    destination: str
    summary: str
    preview_message: str


class IssueDetailResponse(BaseModel):
    issue_id: int
    title: str
    source: str
    category: str
    original_url: str | None = None
    published_at: datetime | None = None
    raw_content: str


class DeliveryLogItem(BaseModel):
    id: int
    title: str
    category: str
    channel: str
    time: str
    status: str
    delivered_at: datetime | None = None


class DeliveryLogListResponse(BaseModel):
    items: list[DeliveryLogItem]
    total: int


class HealthResponse(BaseModel):
    status: str


class LatestNewsCrawlRequest(BaseModel):
    limit: int = Field(default=20, ge=1, le=100)


class CrawlJobSummaryResponse(BaseModel):
    source: str
    sources: list[str] = []
    requested_count: int
    collected_count: int
    saved_count: int
    skipped_count: int
    failed_count: int


class RuntimeSystemProfile(BaseModel):
    logical_cores: int
    physical_cores: int
    memory_gb: float | None = None


class RuntimeTuningProfile(BaseModel):
    crawler_processes: int
    crawler_concurrency_per_process: int
    crawler_host_concurrency: int
    report_worker_threads: int


class RuntimeProfileResponse(BaseModel):
    system: RuntimeSystemProfile
    recommended: RuntimeTuningProfile
    configured: RuntimeTuningProfile
    effective: RuntimeTuningProfile
    explicit: dict[str, bool]
