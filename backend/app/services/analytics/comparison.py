from datetime import datetime
from typing import List, Optional
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.recovery import RecoveryComparison, RecoveryPlan
from app.schemas.analytics import (
    ComparisonDirection,
    ComparisonMetricItem,
    MetricAvailabilityStatus,
    PerformanceComparisonResponse,
)
from app.services.analytics.filters import (
    apply_date_filter,
    apply_simulation_scope,
    build_filter_meta,
)
from app.services.analytics.fleet_analytics import compute_fleet_analytics


def _build_metric_item(
    metric_name: str,
    label: str,
    before_val: Optional[float],
    after_val: Optional[float],
    direction: ComparisonDirection,
    unit: str,
    classification: str,
) -> ComparisonMetricItem:
    abs_diff: Optional[float] = None
    pct_change: Optional[float] = None
    is_improved: Optional[bool] = None

    if before_val is not None and after_val is not None:
        abs_diff = round(after_val - before_val, 2)
        if before_val != 0:
            pct_change = round(((after_val - before_val) / abs(before_val)) * 100.0, 2)
        if direction == ComparisonDirection.LOWER_IS_BETTER:
            is_improved = after_val <= before_val
        elif direction == ComparisonDirection.HIGHER_IS_BETTER:
            is_improved = after_val >= before_val

    return ComparisonMetricItem(
        metric_name=metric_name,
        label=label,
        before_value=round(before_val, 2) if before_val is not None else None,
        after_value=round(after_val, 2) if after_val is not None else None,
        absolute_difference=abs_diff,
        percentage_change=pct_change,
        improvement_direction=direction,
        is_improved=is_improved,
        unit=unit,
        data_classification=classification,
    )


def compute_performance_comparisons(
    db: Session,
    disruption_id: Optional[str] = None,
    recovery_plan_id: Optional[str] = None,
    simulation_id: Optional[str] = None,
    include_simulations: bool = False,
    start_date: Optional[datetime] = None,
    end_date: Optional[datetime] = None,
) -> PerformanceComparisonResponse:
    filter_meta = build_filter_meta(start_date, end_date, simulation_id, include_simulations)

    stmt = select(RecoveryPlan)
    stmt = apply_date_filter(stmt, RecoveryPlan.created_at, start_date, end_date)
    if recovery_plan_id:
        stmt = stmt.where(RecoveryPlan.id == recovery_plan_id)
    elif disruption_id:
        stmt = stmt.where(RecoveryPlan.disruption_id == disruption_id)
    else:
        stmt = apply_simulation_scope(
            stmt, RecoveryPlan.simulation_id, simulation_id, include_simulations
        )

    plans: List[RecoveryPlan] = list(db.execute(stmt).scalars().all())
    plan_ids = [p.id for p in plans]

    comparisons: List[RecoveryComparison] = []
    if plan_ids:
        comparisons = list(
            db.execute(
                select(RecoveryComparison).where(
                    RecoveryComparison.recovery_plan_id.in_(plan_ids)
                )
            ).scalars().all()
        )

    notes: List[str] = []
    if not plans:
        notes.append(
            "No recovery plans found for the selected scope; baseline and recovery metrics are null."
        )
        metrics = [
            _build_metric_item(
                "estimated_delay_minutes",
                "Estimated Delivery Delay",
                None,
                None,
                ComparisonDirection.LOWER_IS_BETTER,
                "minutes",
                MetricAvailabilityStatus.UNAVAILABLE.value,
            ),
            _build_metric_item(
                "estimated_distance_km",
                "Estimated Recovery Route Distance",
                None,
                None,
                ComparisonDirection.LOWER_IS_BETTER,
                "km",
                MetricAvailabilityStatus.UNAVAILABLE.value,
            ),
            _build_metric_item(
                "estimated_recovery_cost",
                "Estimated Recovery Cost",
                None,
                None,
                ComparisonDirection.LOWER_IS_BETTER,
                "currency",
                MetricAvailabilityStatus.UNAVAILABLE.value,
            ),
            _build_metric_item(
                "orders_recovered",
                "Orders Recovered vs Affected",
                None,
                None,
                ComparisonDirection.HIGHER_IS_BETTER,
                "orders",
                MetricAvailabilityStatus.UNAVAILABLE.value,
            ),
            _build_metric_item(
                "fleet_utilization_percentage",
                "Fleet Capacity Utilization",
                None,
                None,
                ComparisonDirection.HIGHER_IS_BETTER,
                "percentage",
                MetricAvailabilityStatus.UNAVAILABLE.value,
            ),
        ]
        return PerformanceComparisonResponse(
            comparison_scope="RECOVERY_BEFORE_VS_AFTER",
            disruption_id=disruption_id,
            recovery_plan_id=recovery_plan_id,
            simulation_id=simulation_id,
            total_comparisons_evaluated=0,
            metrics=metrics,
            notes=notes,
            filter_meta=filter_meta,
        )

    # 1. Delay comparison
    delay_comps = [c for c in comparisons if "delay" in (c.metric_name or "").lower()]
    before_delay = (
        sum(float(c.baseline_value) for c in delay_comps) if delay_comps else None
    )
    after_delay = (
        sum(float(c.proposed_value) for c in delay_comps)
        if delay_comps
        else sum(float(p.estimated_total_delay_minutes or 0.0) for p in plans)
    )

    # 2. Distance comparison
    dist_comps = [c for c in comparisons if "distance" in (c.metric_name or "").lower()]
    before_dist = (
        sum(float(c.baseline_value) for c in dist_comps) if dist_comps else None
    )
    after_dist = (
        sum(float(c.proposed_value) for c in dist_comps)
        if dist_comps
        else sum(float(p.estimated_total_distance_km or 0.0) for p in plans)
    )
    if before_dist is None:
        notes.append(
            "Pre-disruption baseline distance was not persisted in RecoveryComparison; before_value is null."
        )

    # 3. Cost comparison
    cost_comps = [c for c in comparisons if "cost" in (c.metric_name or "").lower()]
    before_cost = (
        sum(float(c.baseline_value) for c in cost_comps) if cost_comps else None
    )
    after_cost = (
        sum(float(c.proposed_value) for c in cost_comps)
        if cost_comps
        else sum(float(p.estimated_recovery_cost or 0.0) for p in plans)
    )
    if before_cost is None:
        notes.append(
            "Pre-disruption baseline cost was not persisted in RecoveryComparison; before_value is null."
        )

    # 4. Orders recovered vs affected
    affected_orders = float(sum(int(p.affected_order_count or 0) for p in plans))
    reassigned_orders = float(sum(int(p.reassigned_order_count or 0) for p in plans))

    # 5. Active vehicles engaged
    veh_comps = [c for c in comparisons if "vehicle" in (c.metric_name or "").lower()]
    before_veh = (
        sum(float(c.baseline_value) for c in veh_comps) if veh_comps else None
    )
    after_veh = (
        sum(float(c.proposed_value) for c in veh_comps)
        if veh_comps
        else float(sum(int(p.assigned_vehicle_count or 0) for p in plans))
    )

    # 6. Fleet utilization before vs after
    util_comps = [c for c in comparisons if "utilization" in (c.metric_name or "").lower()]
    fleet_now = compute_fleet_analytics(db=db, simulation_id=simulation_id, include_simulations=include_simulations)
    before_util = (
        sum(float(c.baseline_value) for c in util_comps) / len(util_comps)
        if util_comps
        else None
    )
    after_util = (
        sum(float(c.proposed_value) for c in util_comps) / len(util_comps)
        if util_comps
        else fleet_now.fleet_capacity_utilization_percentage
    )
    if before_util is None:
        notes.append(
            "Pre-recovery fleet capacity utilization snapshot was not persisted; before_value is null."
        )

    metrics = [
        _build_metric_item(
            "estimated_delay_minutes",
            "Estimated Delivery Delay",
            before_delay,
            after_delay,
            ComparisonDirection.LOWER_IS_BETTER,
            "minutes",
            MetricAvailabilityStatus.ESTIMATED.value,
        ),
        _build_metric_item(
            "estimated_distance_km",
            "Estimated Recovery Route Distance",
            before_dist,
            after_dist,
            ComparisonDirection.LOWER_IS_BETTER,
            "km",
            MetricAvailabilityStatus.ESTIMATED.value,
        ),
        _build_metric_item(
            "estimated_recovery_cost",
            "Estimated Recovery Cost",
            before_cost,
            after_cost,
            ComparisonDirection.LOWER_IS_BETTER,
            "currency",
            MetricAvailabilityStatus.ESTIMATED.value,
        ),
        _build_metric_item(
            "orders_recovered",
            "Orders Reassigned vs Affected",
            affected_orders,
            reassigned_orders,
            ComparisonDirection.HIGHER_IS_BETTER,
            "orders",
            MetricAvailabilityStatus.ACTUAL.value,
        ),
        _build_metric_item(
            "active_vehicles_engaged",
            "Active Vehicles Engaged",
            before_veh,
            after_veh,
            ComparisonDirection.HIGHER_IS_BETTER,
            "vehicles",
            MetricAvailabilityStatus.ESTIMATED.value,
        ),
        _build_metric_item(
            "fleet_utilization_percentage",
            "Fleet Capacity Utilization",
            before_util,
            after_util,
            ComparisonDirection.HIGHER_IS_BETTER,
            "percentage",
            MetricAvailabilityStatus.ACTUAL.value
            if before_util is not None
            else MetricAvailabilityStatus.ESTIMATED.value,
        ),
    ]

    return PerformanceComparisonResponse(
        comparison_scope="RECOVERY_BEFORE_VS_AFTER",
        disruption_id=disruption_id,
        recovery_plan_id=recovery_plan_id,
        simulation_id=simulation_id,
        total_comparisons_evaluated=len(plans),
        metrics=metrics,
        notes=notes,
        filter_meta=filter_meta,
    )

