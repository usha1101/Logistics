from datetime import datetime
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, ConfigDict, Field
from app.models.report import ReportStatus, ReportType


class ReportGenerateRequest(BaseModel):
    report_type: ReportType
    title: Optional[str] = Field(default=None, max_length=255)
    start_date: Optional[datetime] = None
    end_date: Optional[datetime] = None
    simulation_id: Optional[str] = None
    include_simulations: bool = False
    include_charts: bool = True
    filters: Optional[Dict[str, Any]] = None


class ReportMetadataRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    report_code: str
    report_type: str
    title: str
    status: str
    requested_by_user_id: Optional[str] = None
    simulation_id: Optional[str] = None
    include_simulations: bool = False
    start_date: Optional[datetime] = None
    end_date: Optional[datetime] = None
    filters: Optional[Dict[str, Any]] = None
    summary_metrics: Optional[Dict[str, Any]] = None
    include_charts: bool = True
    file_reference: Optional[str] = None
    file_name: Optional[str] = None
    file_size: Optional[int] = None
    generated_at: Optional[datetime] = None
    expires_at: Optional[datetime] = None
    error_message: Optional[str] = None
    created_at: datetime


class PaginatedReportsResponse(BaseModel):
    items: List[ReportMetadataRead]
    total: int
    skip: int
    limit: int


class ReportTypeInfo(BaseModel):
    report_type: str
    title: str
    description: str
    included_sections: List[str]


class ReportTypesListResponse(BaseModel):
    report_types: List[ReportTypeInfo]
    total: int
