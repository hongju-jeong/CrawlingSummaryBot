from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ...config import settings
from ...database import get_db
from ...repository import get_issue_detail, get_issue_preview, list_issues
from ...schemas import IssueDetailResponse, IssueListResponse, ReportPreviewResponse

router = APIRouter(prefix=settings.api_prefix, tags=["issues"])


@router.get("/issues", response_model=IssueListResponse, summary="수집된 이슈 목록 조회")
def read_issues(db: Session = Depends(get_db)) -> IssueListResponse:
    items = list_issues(db)
    return IssueListResponse(items=items, total=len(items))


@router.get(
    "/issues/{issue_id}/preview",
    response_model=ReportPreviewResponse,
    summary="이슈 자동 보고 미리보기 조회",
)
def read_issue_preview(issue_id: int, db: Session = Depends(get_db)) -> ReportPreviewResponse:
    preview = get_issue_preview(db, issue_id)
    if preview is None:
        raise HTTPException(status_code=404, detail="Issue not found")
    return ReportPreviewResponse(**preview)


@router.get(
    "/issues/{issue_id}",
    response_model=IssueDetailResponse,
    summary="이슈 원문 상세 조회",
)
def read_issue_detail(issue_id: int, db: Session = Depends(get_db)) -> IssueDetailResponse:
    issue = get_issue_detail(db, issue_id)
    if issue is None:
        raise HTTPException(status_code=404, detail="Issue not found")
    return IssueDetailResponse(**issue)
