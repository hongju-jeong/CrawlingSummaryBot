from contextlib import asynccontextmanager
import json

import httpx
from fastapi import Body, Depends, FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from .config import settings
from .database import SessionLocal, get_db, init_db
from .repository import get_issue_detail, get_issue_preview, list_delivery_logs, list_issues
from .schemas import (
    CrawlJobSummaryResponse,
    DeliveryLogListResponse,
    HealthResponse,
    IssueDetailResponse,
    IssueListResponse,
    LatestNewsCrawlRequest,
    ReportPreviewResponse,
)
from .services.issue_ingestion import save_crawled_articles
from .services.multi_source_crawler import MultiSourcePollingCrawler
from .services.naver_latest_crawler import NaverLatestNewsCrawler
from .services.scheduler import start_scheduler, stop_scheduler


@asynccontextmanager
async def lifespan(_: FastAPI):
    init_db()
    start_scheduler()
    try:
        yield
    finally:
        stop_scheduler()


app = FastAPI(
    title=settings.app_name,
    lifespan=lifespan,
)

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


@app.post(
    f"{settings.api_prefix}/crawl/latest",
    response_model=CrawlJobSummaryResponse,
    summary="다중 소스 최신 소식 수동 수집",
    description="국내외 뉴스 사이트, 공식 API, 실험적 X 소스를 병렬 수집해 DB에 저장합니다.",
)
def crawl_latest_sources(
    request: LatestNewsCrawlRequest | None = Body(default=None),
    db: Session = Depends(get_db),
) -> CrawlJobSummaryResponse:
    payload = request or LatestNewsCrawlRequest(limit=settings.crawler_limit_per_source)
    crawler = MultiSourcePollingCrawler()
    articles = crawler.crawl_latest(payload.limit)
    result = save_crawled_articles(db, articles)
    return CrawlJobSummaryResponse(
        source="multi-source",
        sources=sorted({article.source_name for article in articles}),
        requested_count=payload.limit,
        collected_count=result.collected_count,
        saved_count=result.saved_count,
        skipped_count=result.skipped_count,
        failed_count=result.failed_count,
    )


@app.get(
    f"{settings.api_prefix}/crawl/latest/stream",
    summary="다중 소스 최신 소식 스트리밍 수집",
    description="크롤링 프로세스 수와 기사별 요약/전송 단계를 실시간으로 스트리밍합니다.",
)
def stream_latest_sources(limit: int = Query(default=settings.crawler_limit_per_source, ge=1, le=20)) -> StreamingResponse:
    def event_stream():
        groups = [group for group in settings.crawler_enabled_source_groups if group != "x-experimental" or settings.x_experimental_enabled]
        active_groups = [group for group in groups if group in settings.crawler_enabled_source_groups]
        process_count = min(settings.crawler_processes, len(active_groups)) if active_groups else 0
        yield to_ndjson(
            {
                "type": "run_started",
                "process_count": process_count,
                "source_groups": active_groups,
                "limit_per_source": limit,
            }
        )

        crawler = MultiSourcePollingCrawler()
        try:
            articles = crawler.crawl_latest(limit)
        except Exception as error:
            yield to_ndjson({"type": "run_failed", "error": str(error)})
            return

        yield to_ndjson(
            {
                "type": "crawl_completed",
                "discovered_count": len(articles),
                "sources": sorted({article.source_name for article in articles}),
            }
        )

        db = SessionLocal()
        totals = {
            "saved_count": 0,
            "skipped_count": 0,
            "failed_count": 0,
        }
        try:
            for article in articles:
                buffered_events: list[dict] = []

                def on_event(event_type: str, payload: dict) -> None:
                    buffered_events.append({"type": event_type, **payload})

                result = save_crawled_articles(db, [article], event_callback=on_event)
                totals["saved_count"] += result.saved_count
                totals["skipped_count"] += result.skipped_count
                totals["failed_count"] += result.failed_count
                for event in buffered_events:
                    yield to_ndjson(event)

            yield to_ndjson(
                {
                    "type": "run_completed",
                    "collected_count": len(articles),
                    "saved_count": totals["saved_count"],
                    "skipped_count": totals["skipped_count"],
                    "failed_count": totals["failed_count"],
                }
            )
        finally:
            db.close()

    return StreamingResponse(event_stream(), media_type="application/x-ndjson")


@app.post(
    f"{settings.api_prefix}/crawl/naver-news/latest",
    response_model=CrawlJobSummaryResponse,
    summary="네이버 최신 뉴스 수동 수집",
    description="네이버 뉴스 메인에서 최신 기사 목록과 본문을 수집해 DB에 저장합니다.",
)
def crawl_latest_news(
    request: LatestNewsCrawlRequest | None = Body(default=None),
    db: Session = Depends(get_db),
) -> CrawlJobSummaryResponse:
    payload = request or LatestNewsCrawlRequest(limit=settings.crawler_max_items_per_run)
    crawler = NaverLatestNewsCrawler()
    try:
        articles = crawler.crawl_latest_news(payload.limit)
    except httpx.HTTPError as error:
        raise HTTPException(status_code=502, detail=f"Failed to fetch Naver News: {error}") from error
    result = save_crawled_articles(db, articles)
    return CrawlJobSummaryResponse(
        source=settings.crawler_source_name,
        sources=[settings.crawler_source_name],
        requested_count=payload.limit,
        collected_count=result.collected_count,
        saved_count=result.saved_count,
        skipped_count=result.skipped_count,
        failed_count=result.failed_count,
    )


@app.get(
    f"{settings.api_prefix}/issues",
    response_model=IssueListResponse,
    summary="수집된 이슈 목록 조회",
)
def read_issues(db: Session = Depends(get_db)) -> IssueListResponse:
    items = list_issues(db)
    return IssueListResponse(items=items, total=len(items))


@app.get(
    f"{settings.api_prefix}/issues/{{issue_id}}/preview",
    response_model=ReportPreviewResponse,
    summary="이슈 자동 보고 미리보기 조회",
)
def read_issue_preview(issue_id: int, db: Session = Depends(get_db)) -> ReportPreviewResponse:
    preview = get_issue_preview(db, issue_id)
    if preview is None:
        raise HTTPException(status_code=404, detail="Issue not found")
    return ReportPreviewResponse(**preview)


@app.get(
    f"{settings.api_prefix}/issues/{{issue_id}}",
    response_model=IssueDetailResponse,
    summary="이슈 원문 상세 조회",
)
def read_issue_detail(issue_id: int, db: Session = Depends(get_db)) -> IssueDetailResponse:
    issue = get_issue_detail(db, issue_id)
    if issue is None:
        raise HTTPException(status_code=404, detail="Issue not found")
    return IssueDetailResponse(**issue)


@app.get(f"{settings.api_prefix}/delivery-logs", response_model=DeliveryLogListResponse)
def read_delivery_logs(db: Session = Depends(get_db)) -> DeliveryLogListResponse:
    items = list_delivery_logs(db)
    return DeliveryLogListResponse(items=items, total=len(items))


def to_ndjson(payload: dict) -> bytes:
    return (json.dumps(payload, ensure_ascii=False) + "\n").encode("utf-8")
