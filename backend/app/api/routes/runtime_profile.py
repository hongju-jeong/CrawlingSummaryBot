from fastapi import APIRouter

from ...config import settings
from ...schemas import RuntimeProfileResponse
from ...services.runtime.runtime_profile import get_runtime_profile

router = APIRouter(prefix=settings.api_prefix, tags=["runtime"])


@router.get("/runtime-profile", response_model=RuntimeProfileResponse)
def read_runtime_profile() -> RuntimeProfileResponse:
    return RuntimeProfileResponse(**get_runtime_profile())
