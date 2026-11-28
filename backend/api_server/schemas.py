from datetime import datetime
from typing import Annotated, Any, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, HttpUrl, StringConstraints

AnalysisType = Literal["voice", "sms", "url"]
AnalysisStatus = Literal["pending", "processing", "completed", "failed"]
RiskLevel = Literal["low", "medium", "high", "unknown"]


class SmsRequest(BaseModel):
    text: Annotated[
        str, StringConstraints(strip_whitespace=True, min_length=1, max_length=10000)
    ]


class UrlRequest(BaseModel):
    url: Annotated[HttpUrl, Field(max_length=8192)]


class AcceptedAnalysis(BaseModel):
    id: UUID
    status: Literal["pending"] = "pending"


class AnalysisResult(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    type: AnalysisType
    status: AnalysisStatus
    risk_level: RiskLevel | None = None
    score: float | None = None
    summary: str | None = None
    reasons: list[str] = Field(default_factory=list)
    recommendation: str | None = None
    details: dict[str, Any] = Field(default_factory=dict)
    error: str | None = None
    created_at: datetime
    updated_at: datetime


class HistoryResponse(BaseModel):
    items: list[AnalysisResult]
    total: int
    limit: int
    offset: int


class AIResult(BaseModel):
    id: UUID
    risk_level: RiskLevel
    score: float | None = Field(default=None, ge=0, le=1, allow_inf_nan=False)
    summary: str = Field(min_length=1)
    reasons: list[str]
    details: dict[str, Any]


class ErrorResponse(BaseModel):
    error: str
