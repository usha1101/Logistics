from typing import Any, Literal, Optional
from pydantic import BaseModel, Field


class ErrorDetail(BaseModel):
    code: str = Field(..., description="Machine-readable error code")
    message: str = Field(..., description="Human-readable error description")
    details: Optional[Any] = Field(None, description="Optional granular validation or error details")


class ErrorResponse(BaseModel):
    error: ErrorDetail
    request_id: str = Field(..., description="Unique per-request tracing identifier")


class DatabaseHealth(BaseModel):
    connected: bool


class HealthResponse(BaseModel):
    status: Literal["ok", "degraded"]
    app: str
    version: str
    environment: str
    database: DatabaseHealth
    server_time_utc: str
    data_source: Literal["SIMULATED"] = "SIMULATED"

