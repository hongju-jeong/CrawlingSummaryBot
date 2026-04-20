from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from ...config import settings
from ...database import get_db
from ...repository import get_daily_summary_payload, get_latest_daily_summary_payload
from ...services.reporting.daily_summary import send_daily_summary
from ...schemas import DailySummaryLatestResponse

router = APIRouter(prefix=settings.api_prefix, tags=["daily-summaries"])


@router.get(
    "/daily-summaries/latest",
    response_model=DailySummaryLatestResponse,
    summary="최근 일일 키워드 다이제스트 조회",
)
def read_latest_daily_summary(db: Session = Depends(get_db)) -> DailySummaryLatestResponse:
    payload = get_latest_daily_summary_payload(db)
    if payload is None:
        raise HTTPException(status_code=404, detail="Daily summary not found")
    return DailySummaryLatestResponse(**payload)


@router.post(
    "/daily-summaries/run",
    response_model=DailySummaryLatestResponse,
    summary="일일 키워드 다이제스트 수동 생성 및 전송",
)
def run_daily_summary(
    summary_date: date = Query(..., description="집계 대상 날짜. 예: 2026-04-21"),
    db: Session = Depends(get_db),
) -> DailySummaryLatestResponse:
    daily_summary = send_daily_summary(db, summary_date=summary_date)
    if daily_summary is None:
        raise HTTPException(status_code=400, detail="Daily summary is disabled")
    db.commit()
    payload = get_daily_summary_payload(db, summary_date.isoformat())
    if payload is None:
        raise HTTPException(status_code=500, detail="Daily summary was created but could not be loaded")
    return DailySummaryLatestResponse(**payload)
