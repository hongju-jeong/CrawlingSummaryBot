from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from .config import settings
from .repository import get_issue_preview, list_delivery_logs, list_issues
from .schemas import (
    DeliveryLogListResponse,
    HealthResponse,
    IssueListResponse,
    ReportPreviewResponse,
)

app = FastAPI(title=settings.app_name)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health", response_model=HealthResponse)
def health_check() -> HealthResponse:
    return HealthResponse(status="ok")


@app.get(f"{settings.api_prefix}/issues", response_model=IssueListResponse)
def read_issues() -> IssueListResponse:
    items = list_issues()
    return IssueListResponse(items=items, total=len(items))


@app.get(
    f"{settings.api_prefix}/issues/{{issue_id}}/preview",
    response_model=ReportPreviewResponse,
)
def read_issue_preview(issue_id: int) -> ReportPreviewResponse:
    preview = get_issue_preview(issue_id)
    if preview is None:
        raise HTTPException(status_code=404, detail="Issue not found")
    return ReportPreviewResponse(**preview)


@app.get(f"{settings.api_prefix}/delivery-logs", response_model=DeliveryLogListResponse)
def read_delivery_logs() -> DeliveryLogListResponse:
    items = list_delivery_logs()
    return DeliveryLogListResponse(items=items, total=len(items))
