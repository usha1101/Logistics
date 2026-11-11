from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.deps import require_roles
from app.database.session import get_db
from app.models.report import ReportMetadata
from app.models.user import User, UserRole
from app.schemas.analytics import (
    AgentAnalyticsResponse,
    AnalyticsHealthResponse,
    DisruptionAnalyticsResponse,
    FleetAnalyticsResponse,
    OrderAnalyticsResponse,
    OverviewAnalyticsResponse,
    PerformanceComparisonResponse,
    RecoveryAnalyticsResponse,
    SimulationAnalyticsResponse,
    TrendGrouping,
    TrendSeriesResponse,
    WarehouseAnalyticsResponse,
)
from app.services.analytics import (
    InvalidAnalyticsFilterError,
    InvalidDateRangeError,
    compute_agent_analytics,
    compute_agent_trends,
    compute_disruption_analytics,
    compute_disruption_trends,
    compute_fleet_analytics,
    compute_fleet_trends,
    compute_order_analytics,
    compute_order_trends,
    compute_overview_analytics,
    compute_performance_comparisons,
    compute_recovery_analytics,
    compute_recovery_trends,
    compute_simulation_analytics,
    compute_warehouse_analytics,
    compute_warehouse_trends,
)
from app.services.reports import ensure_reports_directory

router = APIRouter(prefix="/analytics", tags=["Analytics & Performance Monitoring"])

CORE_ANALYTICS_ROLES = (
    UserRole.ADMIN,
    UserRole.OPERATIONS_MANAGER,
    UserRole.ANALYST,
)

FLEET_ANALYTICS_ROLES = (
    UserRole.ADMIN,
    UserRole.OPERATIONS_MANAGER,
    UserRole.FLEET_MANAGER,
    UserRole.ANALYST,
)

WAREHOUSE_ANALYTICS_ROLES = (
    UserRole.ADMIN,
    UserRole.OPERATIONS_MANAGER,
    UserRole.WAREHOUSE_MANAGER,
    "WAREHOUSE_OPERATOR",
    UserRole.ANALYST,
)

ORDER_ANALYTICS_ROLES = (
    UserRole.ADMIN,
    UserRole.OPERATIONS_MANAGER,
    UserRole.FLEET_MANAGER,
    UserRole.WAREHOUSE_MANAGER,
    "WAREHOUSE_OPERATOR",
    UserRole.ANALYST,
)


def _handle_analytics_error(exc: Exception) -> None:
    if isinstance(exc, (InvalidDateRangeError, InvalidAnalyticsFilterError)):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc
    raise exc


@router.get(
    "/overview",
    response_model=OverviewAnalyticsResponse,
    summary="Get unified overview analytics across all logistics domains",
)
def get_overview_analytics(
    start_date: Optional[datetime] = Query(default=None),
    end_date: Optional[datetime] = Query(default=None),
    simulation_id: Optional[str] = Query(default=None),
    include_simulations: bool = Query(default=False),
    current_user: User = Depends(require_roles(*CORE_ANALYTICS_ROLES)),
    db: Session = Depends(get_db),
) -> OverviewAnalyticsResponse:
    try:
        return compute_overview_analytics(
            db=db,
            start_date=start_date,
            end_date=end_date,
            simulation_id=simulation_id,
            include_simulations=include_simulations,
        )
    except Exception as exc:
        _handle_analytics_error(exc)
        raise


@router.get(
    "/orders",
    response_model=OrderAnalyticsResponse,
    summary="Get order fulfillment, SLA, and delay analytics",
)
def get_orders_analytics(
    start_date: Optional[datetime] = Query(default=None),
    end_date: Optional[datetime] = Query(default=None),
    warehouse_id: Optional[str] = Query(default=None),
    priority: Optional[str] = Query(default=None),
    order_status: Optional[str] = Query(default=None, alias="status"),
    simulation_id: Optional[str] = Query(default=None),
    include_simulations: bool = Query(default=False),
    current_user: User = Depends(require_roles(*ORDER_ANALYTICS_ROLES)),
    db: Session = Depends(get_db),
) -> OrderAnalyticsResponse:
    try:
        return compute_order_analytics(
            db=db,
            start_date=start_date,
            end_date=end_date,
            warehouse_id=warehouse_id,
            priority=priority,
            status=order_status,
            simulation_id=simulation_id,
            include_simulations=include_simulations,
        )
    except Exception as exc:
        _handle_analytics_error(exc)
        raise


@router.get(
    "/orders/trends",
    response_model=TrendSeriesResponse,
    summary="Get historical order creation and delivery success trends",
)
def get_orders_trends(
    grouping: TrendGrouping = Query(default=TrendGrouping.DAY),
    start_date: Optional[datetime] = Query(default=None),
    end_date: Optional[datetime] = Query(default=None),
    warehouse_id: Optional[str] = Query(default=None),
    simulation_id: Optional[str] = Query(default=None),
    include_simulations: bool = Query(default=False),
    current_user: User = Depends(require_roles(*ORDER_ANALYTICS_ROLES)),
    db: Session = Depends(get_db),
) -> TrendSeriesResponse:
    try:
        return compute_order_trends(
            db=db,
            grouping=grouping,
            start_date=start_date,
            end_date=end_date,
            warehouse_id=warehouse_id,
            simulation_id=simulation_id,
            include_simulations=include_simulations,
        )
    except Exception as exc:
        _handle_analytics_error(exc)
        raise


@router.get(
    "/fleet",
    response_model=FleetAnalyticsResponse,
    summary="Get fleet capacity, load utilization, and telemetry distance analytics",
)
def get_fleet_analytics(
    start_date: Optional[datetime] = Query(default=None),
    end_date: Optional[datetime] = Query(default=None),
    vehicle_id: Optional[str] = Query(default=None),
    warehouse_id: Optional[str] = Query(default=None),
    vehicle_status: Optional[str] = Query(default=None, alias="status"),
    simulation_id: Optional[str] = Query(default=None),
    include_simulations: bool = Query(default=False),
    current_user: User = Depends(require_roles(*FLEET_ANALYTICS_ROLES)),
    db: Session = Depends(get_db),
) -> FleetAnalyticsResponse:
    try:
        return compute_fleet_analytics(
            db=db,
            start_date=start_date,
            end_date=end_date,
            vehicle_id=vehicle_id,
            warehouse_id=warehouse_id,
            status=vehicle_status,
            simulation_id=simulation_id,
            include_simulations=include_simulations,
        )
    except Exception as exc:
        _handle_analytics_error(exc)
        raise


@router.get(
    "/fleet/trends",
    response_model=TrendSeriesResponse,
    summary="Get historical fleet status transition trends",
)
def get_fleet_trends(
    grouping: TrendGrouping = Query(default=TrendGrouping.DAY),
    start_date: Optional[datetime] = Query(default=None),
    end_date: Optional[datetime] = Query(default=None),
    vehicle_id: Optional[str] = Query(default=None),
    simulation_id: Optional[str] = Query(default=None),
    include_simulations: bool = Query(default=False),
    current_user: User = Depends(require_roles(*FLEET_ANALYTICS_ROLES)),
    db: Session = Depends(get_db),
) -> TrendSeriesResponse:
    try:
        return compute_fleet_trends(
            db=db,
            grouping=grouping,
            start_date=start_date,
            end_date=end_date,
            vehicle_id=vehicle_id,
            simulation_id=simulation_id,
            include_simulations=include_simulations,
        )
    except Exception as exc:
        _handle_analytics_error(exc)
        raise


@router.get(
    "/warehouses",
    response_model=WarehouseAnalyticsResponse,
    summary="Get warehouse storage utilization and inventory health analytics",
)
def get_warehouses_analytics(
    start_date: Optional[datetime] = Query(default=None),
    end_date: Optional[datetime] = Query(default=None),
    warehouse_id: Optional[str] = Query(default=None),
    warehouse_status: Optional[str] = Query(default=None, alias="status"),
    simulation_id: Optional[str] = Query(default=None),
    include_simulations: bool = Query(default=False),
    current_user: User = Depends(require_roles(*WAREHOUSE_ANALYTICS_ROLES)),
    db: Session = Depends(get_db),
) -> WarehouseAnalyticsResponse:
    try:
        return compute_warehouse_analytics(
            db=db,
            start_date=start_date,
            end_date=end_date,
            warehouse_id=warehouse_id,
            status=warehouse_status,
            simulation_id=simulation_id,
            include_simulations=include_simulations,
        )
    except Exception as exc:
        _handle_analytics_error(exc)
        raise


@router.get(
    "/warehouses/trends",
    response_model=TrendSeriesResponse,
    summary="Get historical warehouse inventory movement trends",
)
def get_warehouses_trends(
    grouping: TrendGrouping = Query(default=TrendGrouping.DAY),
    start_date: Optional[datetime] = Query(default=None),
    end_date: Optional[datetime] = Query(default=None),
    warehouse_id: Optional[str] = Query(default=None),
    simulation_id: Optional[str] = Query(default=None),
    include_simulations: bool = Query(default=False),
    current_user: User = Depends(require_roles(*WAREHOUSE_ANALYTICS_ROLES)),
    db: Session = Depends(get_db),
) -> TrendSeriesResponse:
    try:
        return compute_warehouse_trends(
            db=db,
            grouping=grouping,
            start_date=start_date,
            end_date=end_date,
            warehouse_id=warehouse_id,
            simulation_id=simulation_id,
            include_simulations=include_simulations,
        )
    except Exception as exc:
        _handle_analytics_error(exc)
        raise


@router.get(
    "/disruptions",
    response_model=DisruptionAnalyticsResponse,
    summary="Get disruption impact, severity, and resolution analytics",
)
def get_disruptions_analytics(
    start_date: Optional[datetime] = Query(default=None),
    end_date: Optional[datetime] = Query(default=None),
    disruption_type: Optional[str] = Query(default=None),
    severity: Optional[str] = Query(default=None),
    disruption_status: Optional[str] = Query(default=None, alias="status"),
    simulation_id: Optional[str] = Query(default=None),
    include_simulations: bool = Query(default=False),
    current_user: User = Depends(require_roles(*CORE_ANALYTICS_ROLES)),
    db: Session = Depends(get_db),
) -> DisruptionAnalyticsResponse:
    try:
        return compute_disruption_analytics(
            db=db,
            start_date=start_date,
            end_date=end_date,
            disruption_type=disruption_type,
            severity=severity,
            status=disruption_status,
            simulation_id=simulation_id,
            include_simulations=include_simulations,
        )
    except Exception as exc:
        _handle_analytics_error(exc)
        raise


@router.get(
    "/disruptions/trends",
    response_model=TrendSeriesResponse,
    summary="Get historical disruption occurrence and resolution trends",
)
def get_disruptions_trends(
    grouping: TrendGrouping = Query(default=TrendGrouping.DAY),
    start_date: Optional[datetime] = Query(default=None),
    end_date: Optional[datetime] = Query(default=None),
    simulation_id: Optional[str] = Query(default=None),
    include_simulations: bool = Query(default=False),
    current_user: User = Depends(require_roles(*CORE_ANALYTICS_ROLES)),
    db: Session = Depends(get_db),
) -> TrendSeriesResponse:
    try:
        return compute_disruption_trends(
            db=db,
            grouping=grouping,
            start_date=start_date,
            end_date=end_date,
            simulation_id=simulation_id,
            include_simulations=include_simulations,
        )
    except Exception as exc:
        _handle_analytics_error(exc)
        raise


@router.get(
    "/agents",
    response_model=AgentAnalyticsResponse,
    summary="Get multi-agent AI intelligence and recommendation analytics",
)
def get_agents_analytics(
    start_date: Optional[datetime] = Query(default=None),
    end_date: Optional[datetime] = Query(default=None),
    run_status: Optional[str] = Query(default=None, alias="status"),
    provider: Optional[str] = Query(default=None),
    simulation_id: Optional[str] = Query(default=None),
    include_simulations: bool = Query(default=False),
    current_user: User = Depends(require_roles(*CORE_ANALYTICS_ROLES)),
    db: Session = Depends(get_db),
) -> AgentAnalyticsResponse:
    try:
        return compute_agent_analytics(
            db=db,
            start_date=start_date,
            end_date=end_date,
            status=run_status,
            provider=provider,
            simulation_id=simulation_id,
            include_simulations=include_simulations,
        )
    except Exception as exc:
        _handle_analytics_error(exc)
        raise


@router.get(
    "/agents/trends",
    response_model=TrendSeriesResponse,
    summary="Get historical agent execution success rate trends",
)
def get_agents_trends(
    grouping: TrendGrouping = Query(default=TrendGrouping.DAY),
    start_date: Optional[datetime] = Query(default=None),
    end_date: Optional[datetime] = Query(default=None),
    simulation_id: Optional[str] = Query(default=None),
    include_simulations: bool = Query(default=False),
    current_user: User = Depends(require_roles(*CORE_ANALYTICS_ROLES)),
    db: Session = Depends(get_db),
) -> TrendSeriesResponse:
    try:
        return compute_agent_trends(
            db=db,
            grouping=grouping,
            start_date=start_date,
            end_date=end_date,
            simulation_id=simulation_id,
            include_simulations=include_simulations,
        )
    except Exception as exc:
        _handle_analytics_error(exc)
        raise


@router.get(
    "/recovery",
    response_model=RecoveryAnalyticsResponse,
    summary="Get optimization and recovery engine performance analytics",
)
def get_recovery_analytics(
    start_date: Optional[datetime] = Query(default=None),
    end_date: Optional[datetime] = Query(default=None),
    plan_status: Optional[str] = Query(default=None, alias="status"),
    strategy: Optional[str] = Query(default=None),
    simulation_id: Optional[str] = Query(default=None),
    include_simulations: bool = Query(default=False),
    current_user: User = Depends(require_roles(*CORE_ANALYTICS_ROLES)),
    db: Session = Depends(get_db),
) -> RecoveryAnalyticsResponse:
    try:
        return compute_recovery_analytics(
            db=db,
            start_date=start_date,
            end_date=end_date,
            status=plan_status,
            strategy=strategy,
            simulation_id=simulation_id,
            include_simulations=include_simulations,
        )
    except Exception as exc:
        _handle_analytics_error(exc)
        raise


@router.get(
    "/recovery/trends",
    response_model=TrendSeriesResponse,
    summary="Get historical recovery plan execution success rate trends",
)
def get_recovery_trends(
    grouping: TrendGrouping = Query(default=TrendGrouping.DAY),
    start_date: Optional[datetime] = Query(default=None),
    end_date: Optional[datetime] = Query(default=None),
    simulation_id: Optional[str] = Query(default=None),
    include_simulations: bool = Query(default=False),
    current_user: User = Depends(require_roles(*CORE_ANALYTICS_ROLES)),
    db: Session = Depends(get_db),
) -> TrendSeriesResponse:
    try:
        return compute_recovery_trends(
            db=db,
            grouping=grouping,
            start_date=start_date,
            end_date=end_date,
            simulation_id=simulation_id,
            include_simulations=include_simulations,
        )
    except Exception as exc:
        _handle_analytics_error(exc)
        raise


@router.get(
    "/simulations",
    response_model=SimulationAnalyticsResponse,
    summary="Get digital twin simulation analytics",
)
def get_simulations_analytics(
    start_date: Optional[datetime] = Query(default=None),
    end_date: Optional[datetime] = Query(default=None),
    simulation_id: Optional[str] = Query(default=None),
    sim_status: Optional[str] = Query(default=None, alias="status"),
    current_user: User = Depends(require_roles(*CORE_ANALYTICS_ROLES)),
    db: Session = Depends(get_db),
) -> SimulationAnalyticsResponse:
    try:
        return compute_simulation_analytics(
            db=db,
            start_date=start_date,
            end_date=end_date,
            simulation_id=simulation_id,
            status=sim_status,
        )
    except Exception as exc:
        _handle_analytics_error(exc)
        raise


@router.get(
    "/comparisons",
    response_model=PerformanceComparisonResponse,
    summary="Get before-vs-after disruption recovery performance comparisons",
)
def get_performance_comparisons(
    disruption_id: Optional[str] = Query(default=None),
    recovery_plan_id: Optional[str] = Query(default=None),
    simulation_id: Optional[str] = Query(default=None),
    include_simulations: bool = Query(default=False),
    start_date: Optional[datetime] = Query(default=None),
    end_date: Optional[datetime] = Query(default=None),
    current_user: User = Depends(require_roles(*CORE_ANALYTICS_ROLES)),
    db: Session = Depends(get_db),
) -> PerformanceComparisonResponse:
    try:
        return compute_performance_comparisons(
            db=db,
            disruption_id=disruption_id,
            recovery_plan_id=recovery_plan_id,
            simulation_id=simulation_id,
            include_simulations=include_simulations,
            start_date=start_date,
            end_date=end_date,
        )
    except Exception as exc:
        _handle_analytics_error(exc)
        raise


@router.get(
    "/health",
    response_model=AnalyticsHealthResponse,
    summary="Get analytics and PDF reporting subsystem health",
)
def get_analytics_health(
    current_user: User = Depends(require_roles(*CORE_ANALYTICS_ROLES)),
    db: Session = Depends(get_db),
) -> AnalyticsHealthResponse:
    reportlab_ok = True
    try:
        import reportlab  # noqa: F401
    except ImportError:
        reportlab_ok = False

    storage_dir = ensure_reports_directory()
    storage_ready = storage_dir.exists() and storage_dir.is_dir()

    total_reports = db.scalar(select(func.count(ReportMetadata.id))) or 0

    return AnalyticsHealthResponse(
        status="HEALTHY" if (reportlab_ok and storage_ready) else "DEGRADED",
        analytics_engine="SQLAlchemy Aggregation Engine v1.0",
        pdf_reporting_engine="ReportLab PDF Engine",
        reportlab_available=reportlab_ok,
        reports_storage_ready=storage_ready,
        database_connected=True,
        total_generated_reports=total_reports,
        timestamp=datetime.now(timezone.utc),
    )
