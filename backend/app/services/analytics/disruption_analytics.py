from datetime import datetime
from typing import Dict, List, Optional, Set
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.disruption import (
    AffectedResourceType,
    Disruption,
    DisruptionImpact,
    DisruptionSeverity,
    DisruptionStatus,
    DisruptionType,
)
from app.schemas.analytics import DisruptionAnalyticsResponse, MetricAvailabilityStatus
from app.services.analytics.filters import (
    apply_date_filter,
    apply_simulation_scope,
    build_filter_meta,
    normalize_utc,
)


def compute_disruption_analytics(
    db: Session,
    start_date: Optional[datetime] = None,
    end_date: Optional[datetime] = None,
    disruption_type: Optional[str] = None,
    severity: Optional[str] = None,
    status: Optional[str] = None,
    simulation_id: Optional[str] = None,
    include_simulations: bool = False,
) -> DisruptionAnalyticsResponse:
    filter_meta = build_filter_meta(start_date, end_date, simulation_id, include_simulations)

    stmt = select(Disruption)
    stmt = apply_date_filter(stmt, Disruption.created_at, start_date, end_date)
    stmt = apply_simulation_scope(stmt, Disruption.simulation_id, simulation_id, include_simulations)
    if disruption_type:
        stmt = stmt.where(Disruption.disruption_type == disruption_type)
    if severity:
        stmt = stmt.where(Disruption.severity == severity)
    if status:
        stmt = stmt.where(Disruption.status == status)

    disruptions: List[Disruption] = list(db.execute(stmt).scalars().all())
    total_disruptions = len(disruptions)

    by_status: Dict[str, int] = {s.value: 0 for s in DisruptionStatus}
    by_severity: Dict[str, int] = {s.value: 0 for s in DisruptionSeverity}
    by_type: Dict[str, int] = {t.value: 0 for t in DisruptionType}

    resolution_durations: List[float] = []
    affected_vehicles: Set[str] = set()
    affected_orders: Set[str] = set()
    affected_warehouses: Set[str] = set()
    affected_edges: Set[str] = set()

    disruption_ids = [d.id for d in disruptions]

    for d in disruptions:
        by_status[d.status] = by_status.get(d.status, 0) + 1
        by_severity[d.severity] = by_severity.get(d.severity, 0) + 1
        by_type[d.disruption_type] = by_type.get(d.disruption_type, 0) + 1

        if d.affected_vehicle_id:
            affected_vehicles.add(d.affected_vehicle_id)
        if d.affected_order_id:
            affected_orders.add(d.affected_order_id)
        if d.affected_warehouse_id:
            affected_warehouses.add(d.affected_warehouse_id)
        if d.affected_network_edge_id:
            affected_edges.add(d.affected_network_edge_id)

        s_dt = normalize_utc(d.start_time)
        e_dt = normalize_utc(d.actual_end_time)
        if s_dt and e_dt and e_dt >= s_dt:
            resolution_durations.append((e_dt - s_dt).total_seconds() / 60.0)

    estimated_total_delay = 0.0
    if disruption_ids:
        imp_stmt = select(DisruptionImpact).where(
            DisruptionImpact.disruption_id.in_(disruption_ids)
        )
        impacts: List[DisruptionImpact] = list(db.execute(imp_stmt).scalars().all())
        for imp in impacts:
            rt = imp.affected_resource_type
            rid = imp.affected_resource_id
            if rt == AffectedResourceType.VEHICLE.value:
                affected_vehicles.add(rid)
            elif rt == AffectedResourceType.ORDER.value:
                affected_orders.add(rid)
            elif rt == AffectedResourceType.WAREHOUSE.value:
                affected_warehouses.add(rid)
            elif rt == AffectedResourceType.NETWORK_EDGE.value:
                affected_edges.add(rid)
            if imp.estimated_delay_minutes:
                estimated_total_delay += float(imp.estimated_delay_minutes)

    active_disruptions = (
        by_status.get(DisruptionStatus.DETECTED.value, 0)
        + by_status.get(DisruptionStatus.ACTIVE.value, 0)
        + by_status.get(DisruptionStatus.MONITORING.value, 0)
    )
    resolved_disruptions = by_status.get(DisruptionStatus.RESOLVED.value, 0)
    cancelled_disruptions = by_status.get(DisruptionStatus.CANCELLED.value, 0)

    avg_resolution_time: Optional[float] = (
        round(sum(resolution_durations) / len(resolution_durations), 2)
        if resolution_durations
        else None
    )

    unavailable_metrics: List[str] = []
    if avg_resolution_time is None:
        unavailable_metrics.append("average_resolution_time_minutes")

    metric_classifications = {
        "total_disruptions": MetricAvailabilityStatus.ACTUAL.value,
        "active_disruptions": MetricAvailabilityStatus.ACTUAL.value,
        "resolved_disruptions": MetricAvailabilityStatus.ACTUAL.value,
        "average_resolution_time_minutes": (
            MetricAvailabilityStatus.ACTUAL.value
            if avg_resolution_time is not None
            else MetricAvailabilityStatus.UNAVAILABLE.value
        ),
        "estimated_total_delay_minutes": MetricAvailabilityStatus.ESTIMATED.value,
    }

    return DisruptionAnalyticsResponse(
        total_disruptions=total_disruptions,
        active_disruptions=active_disruptions,
        resolved_disruptions=resolved_disruptions,
        cancelled_disruptions=cancelled_disruptions,
        disruptions_by_status=by_status,
        disruptions_by_severity=by_severity,
        disruptions_by_type=by_type,
        affected_vehicles_count=len(affected_vehicles),
        affected_orders_count=len(affected_orders),
        affected_warehouses_count=len(affected_warehouses),
        affected_edges_count=len(affected_edges),
        average_resolution_time_minutes=avg_resolution_time,
        estimated_total_delay_minutes=round(estimated_total_delay, 2),
        metric_classifications=metric_classifications,
        unavailable_metrics=unavailable_metrics,
        filter_meta=filter_meta,
    )

