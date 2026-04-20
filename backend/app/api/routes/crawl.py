import json
import queue
import threading

import httpx
from fastapi import APIRouter, Body, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from ...config import settings
from ...database import SessionLocal, get_db
from ...schemas import CrawlJobSummaryResponse, LatestNewsCrawlRequest
from ...services.crawling.multi_source_crawler import MultiSourcePollingCrawler
from ...services.crawling.naver_latest_crawler import NaverLatestNewsCrawler
from ...services.ingestion.issue_ingestion import save_crawled_articles
from ...services.runtime.crawl_control import is_cancelled, registry
from ...services.runtime.runtime_profile import get_effective_crawler_processes
from ...services.runtime.scheduler import activate_auto_crawl_schedule

router = APIRouter(prefix=settings.api_prefix, tags=["crawl"])


@router.post(
    "/crawl/latest",
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
    activate_auto_crawl_schedule()
    return CrawlJobSummaryResponse(
        source="multi-source",
        sources=sorted({article.source_name for article in articles}),
        requested_count=payload.limit,
        collected_count=result.collected_count,
        saved_count=result.saved_count,
        skipped_count=result.skipped_count,
        failed_count=result.failed_count,
    )


@router.get(
    "/crawl/latest/stream",
    summary="다중 소스 최신 소식 스트리밍 수집",
    description="크롤링 프로세스 수와 기사별 요약/전송 단계를 실시간으로 스트리밍합니다.",
)
def stream_latest_sources(limit: int = Query(default=settings.crawler_limit_per_source, ge=1, le=20)) -> StreamingResponse:
    run = registry.start()
    if run is None:
        raise HTTPException(status_code=409, detail="A crawl run is already active.")

    def event_stream():
        event_queue: queue.Queue[dict | None] = queue.Queue()
        groups = [
            group
            for group in settings.crawler_enabled_source_groups
            if group != "x-experimental" or settings.x_experimental_enabled
        ]
        active_groups = [group for group in groups if group in settings.crawler_enabled_source_groups]
        process_count = min(get_effective_crawler_processes(), len(active_groups)) if active_groups else 0

        def on_event(event_type: str, payload: dict) -> None:
            event_queue.put({"type": event_type, **payload})

        def run_worker() -> None:
            db = SessionLocal()
            try:
                event_queue.put(
                    {
                        "type": "run_started",
                        "run_id": run.run_id,
                        "process_count": process_count,
                        "source_groups": active_groups,
                        "limit_per_source": limit,
                    }
                )
                crawler = MultiSourcePollingCrawler()
                articles = crawler.crawl_latest(limit, cancel_token=run.cancel_token)
                if is_cancelled(run.cancel_token):
                    event_queue.put(
                        {
                            "type": "run_cancelled",
                            "collected_count": len(articles),
                        }
                    )
                    return
                event_queue.put(
                    {
                        "type": "crawl_completed",
                        "discovered_count": len(articles),
                        "sources": sorted({article.source_name for article in articles}),
                    }
                )
                result = save_crawled_articles(
                    db,
                    articles,
                    event_callback=on_event,
                    cancel_token=run.cancel_token,
                )
                if not is_cancelled(run.cancel_token):
                    activate_auto_crawl_schedule()
                final_type = "run_cancelled" if is_cancelled(run.cancel_token) else "run_completed"
                event_queue.put(
                    {
                        "type": final_type,
                        "collected_count": len(articles),
                        "saved_count": result.saved_count,
                        "skipped_count": result.skipped_count,
                        "failed_count": result.failed_count,
                    }
                )
            except Exception as error:
                event_queue.put({"type": "run_failed", "error": str(error)})
            finally:
                db.close()
                registry.finish(run.run_id)
                event_queue.put(None)

        threading.Thread(target=run_worker, name="crawl-stream-ingest", daemon=True).start()
        while True:
            event = event_queue.get()
            if event is None:
                break
            yield to_ndjson(event)

    return StreamingResponse(event_stream(), media_type="application/x-ndjson")


@router.post(
    "/crawl/naver-news/latest",
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
    activate_auto_crawl_schedule()
    return CrawlJobSummaryResponse(
        source=settings.crawler_source_name,
        sources=[settings.crawler_source_name],
        requested_count=payload.limit,
        collected_count=result.collected_count,
        saved_count=result.saved_count,
        skipped_count=result.skipped_count,
        failed_count=result.failed_count,
    )


@router.post(
    "/crawl/latest/stop",
    summary="실행 중인 최신 소식 수집 중단",
)
def stop_latest_sources() -> dict:
    stopped = registry.stop()
    return {"stopped": stopped}


def to_ndjson(payload: dict) -> bytes:
    return (json.dumps(payload, ensure_ascii=False) + "\n").encode("utf-8")
