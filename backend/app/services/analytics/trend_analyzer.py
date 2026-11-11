from collections import defaultdict
from datetime import datetime
from typing import Dict, List, Optional
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.agent import AgentExecution, AgentExecutionStatus, AgentRun, AgentRunStatus
from app.models.disruption import Disruption, DisruptionStatus
from app.models.order import Order, OrderStatus
from app.models.recovery import RecoveryPlan, RecoveryPlanStatus
from app.models.vehicle import VehicleStatus, VehicleStatusHistory
from app.models.warehouse import InventoryMovement, MovementType
from app.schemas.analytics import TrendGrouping, TrendPoint, TrendSeriesResponse
from app.services.analytics.filters import (
    apply_date_filter,
    apply_simulation_scope,
    build_filter_meta,
    normalize_utc,
)


def _format_bucket(dt: Optional[datetime], grouping: TrendGrouping) -> str:
    norm = normalize_utc(dt)
    if norm is None:
        return "UNKNOWN"
    if grouping == TrendGrouping.DAY:
        return norm.strftime("%Y-%m-%d")
    if grouping == TrendGrouping.WEEK:
        iso_year, iso_week, _ = norm.isocalendar()
        return f"{iso_year}-W{iso_week:02d}"
    return norm.strftime("%Y-%m")


def compute_order_trends(
    db: Session,
    grouping: TrendGrouping = TrendGrouping.DAY,
    start_date: Optional[datetime] = None,
    end_date: Optional[datetime] = None,
    warehouse_id: Optional[str] = None,
    simulation_id: Optional[str] = None,
    include_simulations: bool = False,
) -> TrendSeriesResponse:
    filter_meta = build_filter_meta(start_date, end_date, simulation_id, include_simulations)

    stmt = select(Order)
    stmt = apply_date_filter(stmt, Order.created_at, start_date, end_date)
    if warehouse_id:
        stmt = stmt.where(Order.warehouse_id == warehouse_id)

    orders: List[Order] = list(db.execute(stmt).scalars().all())

    buckets: Dict[str, List[Order]] = defaultdict(list)
    for o in orders:
        b = _format_bucket(o.created_at or o.order_date, grouping)
        buckets[b].append(o)

    points: List[TrendPoint] = []
    for period in sorted(buckets.keys()):
        b_orders = buckets[period]
        total = len(b_orders)
        delivered = sum(1 for o in b_orders if o.status == OrderStatus.DELIVERED.value)
        cancelled = sum(1 for o in b_orders if o.status == OrderStatus.CANCELLED.value)
        eligible = max(0, total - cancelled)
        success_rate = round((delivered / eligible) * 100.0, 2) if eligible > 0 else 0.0

        points.append(
            TrendPoint(
                period=period,
                value=float(total),
                count=total,
                secondary_value=success_rate,
                breakdown={
                    "orders_created": total,
                    "orders_delivered": delivered,
                    "orders_cancelled": cancelled,
                    "delivery_success_rate": success_rate,
                },
            )
        )

    return TrendSeriesResponse(
        domain="ORDERS",
        metric_name="orders_and_delivery_success_rate",
        grouping=grouping,
        unit="orders",
        data_points=points,
        total_points=len(points),
        is_historical=True,
        notes="Aggregated from actual Order records by creation timestamp.",
        filter_meta=filter_meta,
    )


def compute_fleet_trends(
    db: Session,
    grouping: TrendGrouping = TrendGrouping.DAY,
    start_date: Optional[datetime] = None,
    end_date: Optional[datetime] = None,
    vehicle_id: Optional[str] = None,
    simulation_id: Optional[str] = None,
    include_simulations: bool = False,
) -> TrendSeriesResponse:
    filter_meta = build_filter_meta(start_date, end_date, simulation_id, include_simulations)

    stmt = select(VehicleStatusHistory)
    stmt = apply_date_filter(stmt, VehicleStatusHistory.changed_at, start_date, end_date)
    if vehicle_id:
        stmt = stmt.where(VehicleStatusHistory.vehicle_id == vehicle_id)

    history: List[VehicleStatusHistory] = list(db.execute(stmt).scalars().all())

    if not history:
        return TrendSeriesResponse(
            domain="FLEET",
            metric_name="fleet_status_activity",
            grouping=grouping,
            unit="transitions",
            data_points=[],
            total_points=0,
            is_historical=False,
            notes=(
                "Historical fleet load utilization snapshots are not persisted over time; "
                "no vehicle status history events found in the requested date range."
            ),
            filter_meta=filter_meta,
        )

    buckets: Dict[str, List[VehicleStatusHistory]] = defaultdict(list)
    for h in history:
        b = _format_bucket(h.changed_at, grouping)
        buckets[b].append(h)

    points: List[TrendPoint] = []
    for period in sorted(buckets.keys()):
        b_hist = buckets[period]
        total = len(b_hist)
        in_transit = sum(
            1 for h in b_hist if h.new_status == VehicleStatus.IN_TRANSIT.value
        )
        breakdown_cnt = sum(
            1 for h in b_hist if h.new_status == VehicleStatus.BREAKDOWN.value
        )
        active_ratio = round((in_transit / total) * 100.0, 2) if total > 0 else 0.0
        points.append(
            TrendPoint(
                period=period,
                value=active_ratio,
                count=total,
                secondary_value=float(in_transit),
                breakdown={
                    "status_transitions": total,
                    "in_transit_transitions": in_transit,
                    "breakdown_transitions": breakdown_cnt,
                    "in_transit_transition_rate": active_ratio,
                },
            )
        )

    return TrendSeriesResponse(
        domain="FLEET",
        metric_name="fleet_status_activity",
        grouping=grouping,
        unit="percentage",
        data_points=points,
        total_points=len(points),
        is_historical=True,
        notes=(
            "Computed from persisted VehicleStatusHistory transitions. "
            "Continuous historical load capacity snapshots are not persisted over time."
        ),
        filter_meta=filter_meta,
    )


def compute_warehouse_trends(
    db: Session,
    grouping: TrendGrouping = TrendGrouping.DAY,
    start_date: Optional[datetime] = None,
    end_date: Optional[datetime] = None,
    warehouse_id: Optional[str] = None,
    simulation_id: Optional[str] = None,
    include_simulations: bool = False,
) -> TrendSeriesResponse:
    filter_meta = build_filter_meta(start_date, end_date, simulation_id, include_simulations)

    stmt = select(InventoryMovement)
    stmt = apply_date_filter(stmt, InventoryMovement.created_at, start_date, end_date)
    if warehouse_id:
        from app.models.warehouse import InventoryItem

        stmt = stmt.join(
            InventoryItem, InventoryMovement.inventory_item_id == InventoryItem.id
        ).where(InventoryItem.warehouse_id == warehouse_id)

    movements: List[InventoryMovement] = list(db.execute(stmt).scalars().all())

    if not movements:
        return TrendSeriesResponse(
            domain="WAREHOUSES",
            metric_name="inventory_movement_volume",
            grouping=grouping,
            unit="units",
            data_points=[],
            total_points=0,
            is_historical=False,
            notes=(
                "Historical warehouse storage capacity snapshots are not persisted outside "
                "InventoryMovement audit logs; no movements found in the requested window."
            ),
            filter_meta=filter_meta,
        )

    buckets: Dict[str, List[InventoryMovement]] = defaultdict(list)
    for m in movements:
        b = _format_bucket(m.created_at, grouping)
        buckets[b].append(m)

    points: List[TrendPoint] = []
    for period in sorted(buckets.keys()):
        b_movs = buckets[period]
        inbound = sum(
            abs(int(m.quantity or 0))
            for m in b_movs
            if m.movement_type == MovementType.STOCK_RECEIVED.value
        )
        outbound = sum(
            abs(int(m.quantity or 0))
            for m in b_movs
            if m.movement_type == MovementType.STOCK_DISPATCHED.value
        )
        adjust = sum(
            abs(int(m.quantity or 0))
            for m in b_movs
            if m.movement_type == MovementType.STOCK_ADJUSTMENT.value
        )
        total_vol = inbound + outbound + adjust

        points.append(
            TrendPoint(
                period=period,
                value=float(total_vol),
                count=len(b_movs),
                secondary_value=float(outbound),
                breakdown={
                    "movement_count": len(b_movs),
                    "inbound_quantity": inbound,
                    "outbound_quantity": outbound,
                    "adjustment_quantity": adjust,
                },
            )
        )

    return TrendSeriesResponse(
        domain="WAREHOUSES",
        metric_name="inventory_movement_volume",
        grouping=grouping,
        unit="units",
        data_points=points,
        total_points=len(points),
        is_historical=True,
        notes="Aggregated from persisted InventoryMovement audit trail records.",
        filter_meta=filter_meta,
    )


def compute_disruption_trends(
    db: Session,
    grouping: TrendGrouping = TrendGrouping.DAY,
    start_date: Optional[datetime] = None,
    end_date: Optional[datetime] = None,
    simulation_id: Optional[str] = None,
    include_simulations: bool = False,
) -> TrendSeriesResponse:
    filter_meta = build_filter_meta(start_date, end_date, simulation_id, include_simulations)

    stmt = select(Disruption)
    stmt = apply_date_filter(stmt, Disruption.created_at, start_date, end_date)
    stmt = apply_simulation_scope(stmt, Disruption.simulation_id, simulation_id, include_simulations)

    disruptions: List[Disruption] = list(db.execute(stmt).scalars().all())
    buckets: Dict[str, List[Disruption]] = defaultdict(list)
    for d in disruptions:
        b = _format_bucket(d.created_at, grouping)
        buckets[b].append(d)

    points: List[TrendPoint] = []
    for period in sorted(buckets.keys()):
        b_dis = buckets[period]
        total = len(b_dis)
        resolved = sum(1 for d in b_dis if d.status == DisruptionStatus.RESOLVED.value)
        active = sum(
            1
            for d in b_dis
            if d.status
            in (
                DisruptionStatus.DETECTED.value,
                DisruptionStatus.ACTIVE.value,
                DisruptionStatus.MONITORING.value,
            )
        )
        points.append(
            TrendPoint(
                period=period,
                value=float(total),
                count=total,
                secondary_value=float(resolved),
                breakdown={
                    "total_disruptions": total,
                    "active_disruptions": active,
                    "resolved_disruptions": resolved,
                },
            )
        )

    return TrendSeriesResponse(
        domain="DISRUPTIONS",
        metric_name="disruptions_over_time",
        grouping=grouping,
        unit="disruptions",
        data_points=points,
        total_points=len(points),
        is_historical=True,
        notes="Aggregated from persisted Disruption records.",
        filter_meta=filter_meta,
    )


def compute_agent_trends(
    db: Session,
    grouping: TrendGrouping = TrendGrouping.DAY,
    start_date: Optional[datetime] = None,
    end_date: Optional[datetime] = None,
    simulation_id: Optional[str] = None,
    include_simulations: bool = False,
) -> TrendSeriesResponse:
    filter_meta = build_filter_meta(start_date, end_date, simulation_id, include_simulations)

    stmt = select(AgentRun)
    stmt = apply_date_filter(stmt, AgentRun.created_at, start_date, end_date)
    stmt = apply_simulation_scope(stmt, AgentRun.simulation_id, simulation_id, include_simulations)

    runs: List[AgentRun] = list(db.execute(stmt).scalars().all())
    run_ids = [r.id for r in runs]
    execs_by_run: Dict[str, List[AgentExecution]] = defaultdict(list)
    if run_ids:
        ex_list = list(
            db.execute(
                select(AgentExecution).where(AgentExecution.agent_run_id.in_(run_ids))
            ).scalars().all()
        )
        for ex in ex_list:
            execs_by_run[ex.agent_run_id].append(ex)

    buckets: Dict[str, List[AgentRun]] = defaultdict(list)
    for r in runs:
        b = _format_bucket(r.created_at, grouping)
        buckets[b].append(r)

    points: List[TrendPoint] = []
    for period in sorted(buckets.keys()):
        b_runs = buckets[period]
        total_runs = len(b_runs)
        b_execs: List[AgentExecution] = []
        for r in b_runs:
            b_execs.extend(execs_by_run.get(r.id, []))

        total_execs = len(b_execs)
        comp_execs = sum(
            1 for ex in b_execs if ex.status == AgentExecutionStatus.COMPLETED.value
        )
        comp_runs = sum(
            1
            for r in b_runs
            if r.status
            in (AgentRunStatus.COMPLETED.value, AgentRunStatus.PARTIALLY_COMPLETED.value)
        )
        if total_execs > 0:
            success_rate = round((comp_execs / total_execs) * 100.0, 2)
        else:
            success_rate = round((comp_runs / total_runs) * 100.0, 2) if total_runs > 0 else 0.0

        points.append(
            TrendPoint(
                period=period,
                value=success_rate,
                count=total_runs,
                secondary_value=float(total_execs),
                breakdown={
                    "agent_runs": total_runs,
                    "agent_executions": total_execs,
                    "completed_executions": comp_execs,
                    "agent_execution_success_rate": success_rate,
                },
            )
        )

    return TrendSeriesResponse(
        domain="AGENTS",
        metric_name="agent_execution_success_rate",
        grouping=grouping,
        unit="percentage",
        data_points=points,
        total_points=len(points),
        is_historical=True,
        notes="Aggregated from persisted AgentRun and AgentExecution records.",
        filter_meta=filter_meta,
    )


def compute_recovery_trends(
    db: Session,
    grouping: TrendGrouping = TrendGrouping.DAY,
    start_date: Optional[datetime] = None,
    end_date: Optional[datetime] = None,
    simulation_id: Optional[str] = None,
    include_simulations: bool = False,
) -> TrendSeriesResponse:
    filter_meta = build_filter_meta(start_date, end_date, simulation_id, include_simulations)

    stmt = select(RecoveryPlan)
    stmt = apply_date_filter(stmt, RecoveryPlan.created_at, start_date, end_date)
    stmt = apply_simulation_scope(
        stmt, RecoveryPlan.simulation_id, simulation_id, include_simulations
    )

    plans: List[RecoveryPlan] = list(db.execute(stmt).scalars().all())
    buckets: Dict[str, List[RecoveryPlan]] = defaultdict(list)
    for p in plans:
        b = _format_bucket(p.created_at, grouping)
        buckets[b].append(p)

    points: List[TrendPoint] = []
    for period in sorted(buckets.keys()):
        b_plans = buckets[period]
        total = len(b_plans)
        executed = sum(
            1 for p in b_plans if p.status == RecoveryPlanStatus.EXECUTED.value
        )
        recovered_orders = sum(
            int(p.reassigned_order_count or 0)
            for p in b_plans
            if p.status == RecoveryPlanStatus.EXECUTED.value
        )
        success_rate = round((executed / total) * 100.0, 2) if total > 0 else 0.0

        points.append(
            TrendPoint(
                period=period,
                value=success_rate,
                count=total,
                secondary_value=float(recovered_orders),
                breakdown={
                    "total_plans": total,
                    "executed_plans": executed,
                    "recovered_orders": recovered_orders,
                    "recovery_success_rate": success_rate,
                },
            )
        )

    return TrendSeriesResponse(
        domain="RECOVERY",
        metric_name="recovery_success_rate",
        grouping=grouping,
        unit="percentage",
        data_points=points,
        total_points=len(points),
        is_historical=True,
        notes="Aggregated from persisted RecoveryPlan records.",
        filter_meta=filter_meta,
    )
