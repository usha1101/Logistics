from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, require_roles
from app.database.session import get_db
from app.models.disruption import (
    Disruption,
    DisruptionEvent,
    DisruptionImpact,
    DisruptionSeverity,
    DisruptionStatus,
    DisruptionType,
)
from app.models.user import User, UserRole
from app.schemas.disruption import (
    DisruptionAnalysisReport,
    DisruptionCancelRequest,
    DisruptionCreate,
    DisruptionImpactRead,
    DisruptionRead,
    DisruptionResolveRequest,
    DisruptionSummary,
    DisruptionUpdate,
    PaginatedDisruptionEventsResponse,
    PaginatedDisruptionsResponse,
    PaginatedImpactsResponse,
)
from app.services.disruptions.engine import DisruptionEngine
from app.services.disruptions.exceptions import (
    DisruptionNotFoundError,
    InvalidDisruptionTransitionError,
    TargetResourceValidationError,
)

router = APIRouter(prefix="/disruptions", tags=["Disruptions"])


@router.post(
    "",
    response_model=DisruptionRead,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new logistics disruption",
)
def create_disruption(
    payload: DisruptionCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(UserRole.OPERATIONS_MANAGER, UserRole.FLEET_MANAGER, UserRole.WAREHOUSE_MANAGER)),
):
    engine = DisruptionEngine(db)
    try:
        disruption = engine.create_disruption(payload, user_id=current_user.id)
        return disruption
    except TargetResourceValidationError as e:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.get(
    "",
    response_model=PaginatedDisruptionsResponse,
    summary="List disruptions with optional filters and pagination",
)
def list_disruptions(
    status_filter: Optional[str] = Query(None, alias="status", description="Filter by disruption status"),
    disruption_type: Optional[str] = Query(None, description="Filter by disruption type"),
    severity: Optional[str] = Query(None, description="Filter by severity"),
    simulation_id: Optional[str] = Query(None, description="Filter by simulation ID"),
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(20, ge=1, le=100, description="Items per page"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    query = select(Disruption)

    if status_filter:
        query = query.where(Disruption.status == status_filter)
    if disruption_type:
        query = query.where(Disruption.disruption_type == disruption_type)
    if severity:
        query = query.where(Disruption.severity == severity)
    if simulation_id:
        query = query.where(Disruption.simulation_id == simulation_id)

    total = db.scalar(select(func.count()).select_from(query.subquery())) or 0
    total_pages = (total + page_size - 1) // page_size if total > 0 else 1

    items = db.scalars(
        query.order_by(Disruption.created_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    ).all()

    return PaginatedDisruptionsResponse(
        items=items,
        total=total,
        page=page,
        page_size=page_size,
        total_pages=total_pages,
    )


@router.get(
    "/active",
    response_model=PaginatedDisruptionsResponse,
    summary="List currently active and monitoring disruptions",
)
def list_active_disruptions(
    simulation_id: Optional[str] = Query(None, description="Filter by simulation ID"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    query = select(Disruption).where(
        Disruption.status.in_([DisruptionStatus.ACTIVE.value, DisruptionStatus.MONITORING.value])
    )
    if simulation_id:
        query = query.where(Disruption.simulation_id == simulation_id)

    total = db.scalar(select(func.count()).select_from(query.subquery())) or 0
    total_pages = (total + page_size - 1) // page_size if total > 0 else 1

    items = db.scalars(
        query.order_by(Disruption.created_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    ).all()

    return PaginatedDisruptionsResponse(
        items=items,
        total=total,
        page=page,
        page_size=page_size,
        total_pages=total_pages,
    )


@router.get(
    "/{disruption_id}",
    response_model=DisruptionRead,
    summary="Get complete details of a single disruption",
)
def get_disruption(
    disruption_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    disruption = db.get(Disruption, disruption_id)
    if not disruption:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Disruption '{disruption_id}' not found.",
        )
    return disruption


@router.post(
    "/{disruption_id}/activate",
    response_model=DisruptionRead,
    summary="Activate a detected disruption",
)
def activate_disruption(
    disruption_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(UserRole.OPERATIONS_MANAGER, UserRole.FLEET_MANAGER, UserRole.WAREHOUSE_MANAGER)),
):
    engine = DisruptionEngine(db)
    try:
        disruption = engine.activate_disruption(disruption_id, user_id=current_user.id)
        return disruption
    except DisruptionNotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except InvalidDisruptionTransitionError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.post(
    "/{disruption_id}/monitor",
    response_model=DisruptionRead,
    summary="Put an active disruption into monitoring mode",
)
def set_disruption_monitoring(
    disruption_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(UserRole.OPERATIONS_MANAGER, UserRole.FLEET_MANAGER, UserRole.WAREHOUSE_MANAGER)),
):
    engine = DisruptionEngine(db)
    try:
        disruption = engine.set_monitoring(disruption_id, user_id=current_user.id)
        return disruption
    except DisruptionNotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except InvalidDisruptionTransitionError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.patch(
    "/{disruption_id}",
    response_model=DisruptionRead,
    summary="Update disruption parameters or expected resolution time",
)
def update_disruption(
    disruption_id: str,
    payload: DisruptionUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(UserRole.OPERATIONS_MANAGER, UserRole.FLEET_MANAGER, UserRole.WAREHOUSE_MANAGER)),
):
    engine = DisruptionEngine(db)
    try:
        disruption = engine.update_disruption(disruption_id, payload, user_id=current_user.id)
        return disruption
    except DisruptionNotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except InvalidDisruptionTransitionError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.post(
    "/{disruption_id}/resolve",
    response_model=DisruptionRead,
    summary="Mark an active or monitoring disruption as resolved",
)
def resolve_disruption(
    disruption_id: str,
    payload: Optional[DisruptionResolveRequest] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(UserRole.OPERATIONS_MANAGER, UserRole.FLEET_MANAGER, UserRole.WAREHOUSE_MANAGER)),
):
    engine = DisruptionEngine(db)
    try:
        disruption = engine.resolve_disruption(disruption_id, payload, user_id=current_user.id)
        return disruption
    except DisruptionNotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except InvalidDisruptionTransitionError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.post(
    "/{disruption_id}/cancel",
    response_model=DisruptionRead,
    summary="Cancel a disruption record",
)
def cancel_disruption(
    disruption_id: str,
    payload: Optional[DisruptionCancelRequest] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(UserRole.OPERATIONS_MANAGER, UserRole.FLEET_MANAGER, UserRole.WAREHOUSE_MANAGER)),
):
    engine = DisruptionEngine(db)
    try:
        disruption = engine.cancel_disruption(disruption_id, payload, user_id=current_user.id)
        return disruption
    except DisruptionNotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except InvalidDisruptionTransitionError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.get(
    "/{disruption_id}/impact",
    response_model=DisruptionAnalysisReport,
    summary="Run and retrieve detailed deterministic impact analysis for a disruption",
)
def get_disruption_impact(
    disruption_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    engine = DisruptionEngine(db)
    try:
        report = engine.get_impact_analysis(disruption_id)
        return report
    except DisruptionNotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))


@router.get(
    "/{disruption_id}/events",
    response_model=PaginatedDisruptionEventsResponse,
    summary="Get audit event history for a disruption",
)
def get_disruption_events(
    disruption_id: str,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    disruption = db.get(Disruption, disruption_id)
    if not disruption:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Disruption '{disruption_id}' not found.",
        )

    query = select(DisruptionEvent).where(DisruptionEvent.disruption_id == disruption_id)
    total = db.scalar(select(func.count()).select_from(query.subquery())) or 0
    total_pages = (total + page_size - 1) // page_size if total > 0 else 1

    items = db.scalars(
        query.order_by(DisruptionEvent.created_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    ).all()

    return PaginatedDisruptionEventsResponse(
        items=items,
        total=total,
        page=page,
        page_size=page_size,
        total_pages=total_pages,
    )
