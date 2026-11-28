from typing import Literal

from fastapi import APIRouter
from pydantic import BaseModel

router = APIRouter(tags=["health"])


class HealthResponse(BaseModel):
    status: Literal["ok"] = "ok"


@router.get("/health", response_model=HealthResponse)
def health() -> HealthResponse:
    """API 프로세스 응답 여부를 확인합니다. DB·AI 서버 상태는 포함하지 않습니다."""
    return HealthResponse()
