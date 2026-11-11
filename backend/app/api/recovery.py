from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, require_roles
from app.database.session import get_db
from app.models.recovery import (
    RecoveryAction,
    RecoveryAssignment,
    RecoveryAuditLog,
    RecoveryComparison,
    RecoveryPlan,
    RecoveryPlanStatus,
)
from app.models.user import User, UserRole
from app.schemas.recovery import (
    PaginatedRecoveryPlansResponse,
    RecoveryActionRead,
    RecoveryAssignmentRead,
    RecoveryAuditLogRead,
    RecoveryComparisonRead,
    RecoveryKPISummary,
    RecoveryPlanApproveRequest,
    RecoveryPlanGenerateRequest,
    RecoveryPlanRead,
    RecoveryPlanRejectRequest,
    RecoveryPlanValidationReport,
)
from app.services.recovery.exceptions import (
    InfeasibleOptimizationError,
    InvalidPlanStatusTransitionError,
    PlanValidationFailedError,
    RecoveryEngineError,
    RecoveryExecutionError,
    RecoveryPlanNotFoundError,
    StalePlanStateError,
)
from app.services.recovery.orchestrator import RecoveryOrchestrator

router = APIRouter(prefix="/recovery", tags=["Intelligent Recovery Engine"])


@router.post(
    "/plans/generate",
    response_model=RecoveryPlanRead,
    status_code=status.HTTP_201_CREATED,
    summary="Generate a mathematically optimized recovery plan using OR-Tools and NetworkX",
)
def generate_recovery_plan(
    payload: RecoveryPlanGenerateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(UserRole.OPERATIONS_MANAGER, UserRole.FLEET_MANAGER, UserRole.WAREHOUSE_MANAGER)),
):
    orchestrator = RecoveryOrchestrator(db)
    try:
        plan = orchestrator.generate_plan(payload, user_id=current_user.id)
        return plan
    except RecoveryPlanNotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except InfeasibleOptimizationError as e:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.get(
    "/plans",
    response_model=PaginatedRecoveryPlansResponse,
    summary="List recovery plans with optional filters and pagination",
)
def list_recovery_plans(
    disruption_id: Optional[str] = Query(None, description="Filter by disruption ID"),
    status_filter: Optional[str] = Query(None, alias="status", description="Filter by plan status"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    query = select(RecoveryPlan)
    if disruption_id:
        query = query.where(RecoveryPlan.disruption_id == disruption_id)
    if status_filter:
        query = query.where(RecoveryPlan.status == status_filter)

    total = db.scalar(select(func.count()).select_from(query.subquery())) or 0
    total_pages = (total + page_size - 1) // page_size if total > 0 else 1

    items = db.scalars(
        query.order_by(RecoveryPlan.created_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    ).all()

    return PaginatedRecoveryPlansResponse(
        items=items,
        total=total,
        page=page,
        page_size=page_size,
        total_pages=total_pages,
    )


@router.get(
    "/summary",
    response_model=RecoveryKPISummary,
    summary="Get aggregated recovery KPIs across all plans",
)
def get_recovery_summary(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    orchestrator = RecoveryOrchestrator(db)
    return orchestrator.get_summary_kpis()


@router.get(
    "/plans/{plan_id}",
    response_model=RecoveryPlanRead,
    summary="Get complete recovery plan details",
)
def get_recovery_plan(
    plan_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    plan = db.get(RecoveryPlan, plan_id)
    if not plan:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Recovery plan '{plan_id}' not found.")
    return plan


@router.get(
    "/plans/{plan_id}/assignments",
    response_model=List[RecoveryAssignmentRead],
    summary="Get proposed order assignments for a plan",
)
def get_recovery_assignments(
    plan_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    plan = db.get(RecoveryPlan, plan_id)
    if not plan:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Recovery plan '{plan_id}' not found.")
    return plan.assignments


@router.get(
    "/plans/{plan_id}/comparison",
    response_model=List[RecoveryComparisonRead],
    summary="Get baseline vs proposed performance comparisons",
)
def get_recovery_comparison(
    plan_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    plan = db.get(RecoveryPlan, plan_id)
    if not plan:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Recovery plan '{plan_id}' not found.")
    return plan.comparisons


@router.post(
    "/plans/{plan_id}/validate",
    response_model=RecoveryPlanValidationReport,
    summary="Run deterministic validation against live database constraints",
)
def validate_recovery_plan(
    plan_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(UserRole.OPERATIONS_MANAGER, UserRole.FLEET_MANAGER, UserRole.WAREHOUSE_MANAGER)),
):
    plan = db.get(RecoveryPlan, plan_id)
    if not plan:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Recovery plan '{plan_id}' not found.")

    orchestrator = RecoveryOrchestrator(db)
    return orchestrator.validator.validate_plan(plan)


@router.post(
    "/plans/{plan_id}/approve",
    response_model=RecoveryPlanRead,
    summary="Human approval of a validated recovery plan",
)
def approve_recovery_plan(
    plan_id: str,
    payload: Optional[RecoveryPlanApproveRequest] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(UserRole.OPERATIONS_MANAGER, UserRole.FLEET_MANAGER, UserRole.ADMIN)),
):
    orchestrator = RecoveryOrchestrator(db)
    try:
        plan = orchestrator.approve_plan(plan_id, user_id=current_user.id, payload=payload)
        return plan
    except RecoveryPlanNotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except (InvalidPlanStatusTransitionError, PlanValidationFailedError) as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.post(
    "/plans/{plan_id}/reject",
    response_model=RecoveryPlanRead,
    summary="Reject a recovery plan with an audit reason",
)
def reject_recovery_plan(
    plan_id: str,
    payload: RecoveryPlanRejectRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(UserRole.OPERATIONS_MANAGER, UserRole.FLEET_MANAGER, UserRole.ADMIN)),
):
    orchestrator = RecoveryOrchestrator(db)
    try:
        plan = orchestrator.reject_plan(plan_id, payload=payload, user_id=current_user.id)
        return plan
    except RecoveryPlanNotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except InvalidPlanStatusTransitionError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.post(
    "/plans/{plan_id}/execute",
    response_model=RecoveryPlanRead,
    summary="Execute an approved recovery plan in an atomic transaction",
)
def execute_recovery_plan(
    plan_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(UserRole.OPERATIONS_MANAGER, UserRole.FLEET_MANAGER, UserRole.ADMIN)),
):
    orchestrator = RecoveryOrchestrator(db)
    try:
        plan = orchestrator.execute_plan(plan_id, user_id=current_user.id)
        return plan
    except RecoveryPlanNotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except StalePlanStateError as e:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(e))
    except (InvalidPlanStatusTransitionError, PlanValidationFailedError) as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except RecoveryExecutionError as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))


@router.get(
    "/plans/{plan_id}/actions",
    response_model=List[RecoveryActionRead],
    summary="Get execution action history for a recovery plan",
)
def get_recovery_actions(
    plan_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    plan = db.get(RecoveryPlan, plan_id)
    if not plan:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Recovery plan '{plan_id}' not found.")
    return plan.actions


@router.get(
    "/plans/{plan_id}/audit",
    response_model=List[RecoveryAuditLogRead],
    summary="Get immutable audit logs for a recovery plan",
)
@router.get(
    "/plans/{plan_id}/audit-logs",
    response_model=List[RecoveryAuditLogRead],
    summary="Get immutable audit logs for a recovery plan",
)
def get_recovery_audit_logs(
    plan_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    plan = db.get(RecoveryPlan, plan_id)
    if not plan:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Recovery plan '{plan_id}' not found.")
    return plan.audit_logs
