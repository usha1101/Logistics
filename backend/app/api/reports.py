from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from app.api.deps import require_roles
from app.database.session import get_db
from app.models.user import User, UserRole
from app.schemas.report import (
    PaginatedReportsResponse,
    ReportGenerateRequest,
    ReportMetadataRead,
    ReportTypesListResponse,
)
from app.services.analytics import (
    InvalidAnalyticsFilterError,
    InvalidDateRangeError,
    ReportGenerationError,
    ReportNotFoundError,
)
from app.services.reports import (
    generate_pdf_report,
    get_report_by_id,
    get_report_types_catalog,
    list_reports,
    resolve_safe_report_path,
)

router = APIRouter(prefix="/reports", tags=["Reporting & PDF Export"])

REPORT_PERMITTED_ROLES = (
    UserRole.ADMIN,
    UserRole.OPERATIONS_MANAGER,
    UserRole.ANALYST,
)


@router.post(
    "/generate",
    response_model=ReportMetadataRead,
    status_code=status.HTTP_201_CREATED,
    summary="Generate a downloadable PDF analytics report",
)
def create_report(
    payload: ReportGenerateRequest,
    current_user: User = Depends(require_roles(*REPORT_PERMITTED_ROLES)),
    db: Session = Depends(get_db),
) -> ReportMetadataRead:
    try:
        report = generate_pdf_report(db=db, req=payload, user_id=current_user.id)
        return ReportMetadataRead.model_validate(report)
    except (InvalidDateRangeError, InvalidAnalyticsFilterError) as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc
    except ReportGenerationError as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(exc),
        ) from exc


@router.get(
    "",
    response_model=PaginatedReportsResponse,
    summary="List generated reports with pagination and filtering",
)
def get_reports_list(
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=20, ge=1, le=100),
    report_type: Optional[str] = Query(default=None),
    report_status: Optional[str] = Query(default=None, alias="status"),
    current_user: User = Depends(require_roles(*REPORT_PERMITTED_ROLES)),
    db: Session = Depends(get_db),
) -> PaginatedReportsResponse:
    items, total = list_reports(
        db=db,
        skip=skip,
        limit=limit,
        report_type=report_type,
        status=report_status,
    )
    return PaginatedReportsResponse(
        items=[ReportMetadataRead.model_validate(it) for it in items],
        total=total,
        skip=skip,
        limit=limit,
    )


@router.get(
    "/types",
    response_model=ReportTypesListResponse,
    summary="List supported PDF report types and included sections",
)
def get_supported_report_types(
    current_user: User = Depends(require_roles(*REPORT_PERMITTED_ROLES)),
) -> ReportTypesListResponse:
    return get_report_types_catalog()


@router.get(
    "/{report_id}",
    response_model=ReportMetadataRead,
    summary="Get metadata for a specific generated report",
)
def get_report_metadata(
    report_id: str,
    current_user: User = Depends(require_roles(*REPORT_PERMITTED_ROLES)),
    db: Session = Depends(get_db),
) -> ReportMetadataRead:
    try:
        report = get_report_by_id(db=db, report_id=report_id)
        return ReportMetadataRead.model_validate(report)
    except ReportNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc


@router.get(
    "/{report_id}/download",
    summary="Download the generated PDF file for a report",
)
def download_report_pdf(
    report_id: str,
    current_user: User = Depends(require_roles(*REPORT_PERMITTED_ROLES)),
    db: Session = Depends(get_db),
) -> FileResponse:
    try:
        report = get_report_by_id(db=db, report_id=report_id)
        if not report.file_reference:
            raise ReportNotFoundError("Report PDF file reference is missing.")
        pdf_path = resolve_safe_report_path(report.file_reference)
        if not pdf_path.exists() or not pdf_path.is_file():
            raise ReportNotFoundError("Generated PDF file not found on disk.")
        return FileResponse(
            path=str(pdf_path),
            media_type="application/pdf",
            filename=report.file_reference,
        )
    except ReportNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc

