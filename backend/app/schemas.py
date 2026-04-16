from datetime import datetime

from pydantic import BaseModel


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
    channel: str
    destination: str
    summary: str
    preview_message: str


class DeliveryLogItem(BaseModel):
    id: int
    title: str
    channel: str
    time: str
    status: str
    delivered_at: datetime | None = None


class DeliveryLogListResponse(BaseModel):
    items: list[DeliveryLogItem]
    total: int


class HealthResponse(BaseModel):
    status: str
