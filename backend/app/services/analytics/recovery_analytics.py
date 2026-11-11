from datetime import datetime
from typing import Dict, List, Optional
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.recovery import (
    OptimizationStrategy,
    RecoveryAction,
    RecoveryActionStatus,
    RecoveryComparison,
    RecoveryPlan,
    RecoveryPlanStatus,
)
from app.schemas.analytics import MetricAvailabilityStatus, RecoveryAnalyticsResponse
from app.services.analytics.filters import (
    apply_date_filter,
    apply_simulation_scope,
    build_filter_meta,
    normalize_utc,
)


def compute_recovery_analytics(
    db: Session,
    start_date: Optional[datetime] = None,
    end_date: Optional[datetime] = None,
    status: Optional[str] = None,
    strategy: Optional[str] = None,
    simulation_id: Optional[str] = None,
    include_simulations: bool = False,
) -> RecoveryAnalyticsResponse:
    filter_meta = build_filter_meta(start_date, end_date, simulation_id, include_simulations)

    stmt = select(RecoveryPlan)
    stmt = apply_date_filter(stmt, RecoveryPlan.created_at, start_date, end_date)
    stmt = apply_simulation_scope(
        stmt, RecoveryPlan.simulation_id, simulation_id, include_simulations
    )
    if status:
        stmt = stmt.where(RecoveryPlan.status == status)
    if strategy:
        stmt = stmt.where(RecoveryPlan.optimization_strategy == strategy)

    plans: List[RecoveryPlan] = list(db.execute(stmt).scalars().all())
    total_plans = len(plans)

    plans_by_status: Dict[str, int] = {s.value: 0 for s in RecoveryPlanStatus}
    plans_by_strategy: Dict[str, int] = {s.value: 0 for s in OptimizationStrategy}

    total_affected_orders = 0
    total_reassigned_proposed = 0
    total_recovered_orders = 0
    execution_durations_min: List[float] = []
    estimated_distance_sum = 0.0
    estimated_cost_sum = 0.0

    plan_ids = [p.id for p in plans]

    for p in plans:
        st = p.status
        plans_by_status[st] = plans_by_status.get(st, 0) + 1
        strat = p.optimization_strategy
        plans_by_strategy[strat] = plans_by_strategy.get(strat, 0) + 1

        total_affected_orders += int(p.affected_order_count or 0)
        total_reassigned_proposed += int(p.reassigned_order_count or 0)
        estimated_distance_sum += float(p.estimated_total_distance_km or 0.0)
        estimated_cost_sum += float(p.estimated_recovery_cost or 0.0)

        if st == RecoveryPlanStatus.EXECUTED.value:
            total_recovered_orders += int(p.reassigned_order_count or 0)

        c_dt = normalize_utc(p.created_at)
        e_dt = normalize_utc(p.executed_at)
        if c_dt and e_dt and e_dt >= c_dt:
            execution_durations_min.append((e_dt - c_dt).total_seconds() / 60.0)

    actions: List[RecoveryAction] = []
    comparisons: List[RecoveryComparison] = []
    if plan_ids:
        act_stmt = select(RecoveryAction).where(RecoveryAction.recovery_plan_id.in_(plan_ids))
        actions = list(db.execute(act_stmt).scalars().all())

        comp_stmt = select(RecoveryComparison).where(
            RecoveryComparison.recovery_plan_id.in_(plan_ids)
        )
        comparisons = list(db.execute(comp_stmt).scalars().all())

    total_actions = len(actions)
    executed_actions = sum(
        1 for a in actions if a.status == RecoveryActionStatus.EXECUTED.value
    )
    failed_actions = sum(
        1 for a in actions if a.status == RecoveryActionStatus.FAILED.value
    )
    pending_actions = sum(
        1 for a in actions if a.status == RecoveryActionStatus.PENDING.value
    )

    # Also count recovered orders from partially executed plans via executed REASSIGN_VEHICLE actions
    partially_executed_plan_ids = {
        p.id for p in plans if p.status == RecoveryPlanStatus.PARTIALLY_EXECUTED.value
    }
    if partially_executed_plan_ids:
        partial_reassigned = sum(
            1
            for a in actions
            if a.recovery_plan_id in partially_executed_plan_ids
            and a.status == RecoveryActionStatus.EXECUTED.value
            and a.action_type == "REASSIGN_VEHICLE"
        )
        total_recovered_orders += partial_reassigned

    delay_reduction = 0.0
    distance_change_from_comp = 0.0
    cost_change_from_comp = 0.0
    has_dist_comp = False
    has_cost_comp = False

    for c in comparisons:
        m_name = (c.metric_name or "").lower()
        if "delay" in m_name:
            delay_reduction += float(c.improvement_value or 0.0)
        elif "distance" in m_name:
            has_dist_comp = True
            distance_change_from_comp += float(c.proposed_value or 0.0) - float(
                c.baseline_value or 0.0
            )
        elif "cost" in m_name:
            has_cost_comp = True
            cost_change_from_comp += float(c.proposed_value or 0.0) - float(
                c.baseline_value or 0.0
            )

    optimized_plans = plans_by_status.get(RecoveryPlanStatus.OPTIMIZED.value, 0)
    pending_approval_plans = plans_by_status.get(
        RecoveryPlanStatus.PENDING_APPROVAL.value, 0
    )
    approved_plans = plans_by_status.get(RecoveryPlanStatus.APPROVED.value, 0)
    rejected_plans = plans_by_status.get(RecoveryPlanStatus.REJECTED.value, 0)
    executed_plans = plans_by_status.get(RecoveryPlanStatus.EXECUTED.value, 0)
    partially_executed_plans = plans_by_status.get(
        RecoveryPlanStatus.PARTIALLY_EXECUTED.value, 0
    )
    failed_plans = plans_by_status.get(RecoveryPlanStatus.FAILED.value, 0)
    infeasible_plans = plans_by_status.get(RecoveryPlanStatus.VALIDATION_FAILED.value, 0)

    recovery_success_rate = (
        round((executed_plans / total_plans) * 100.0, 2) if total_plans > 0 else 0.0
    )

    avg_exec_time: Optional[float] = (
        round(sum(execution_durations_min) / len(execution_durations_min), 2)
        if execution_durations_min
        else None
    )

    est_distance_change = (
        round(distance_change_from_comp, 2)
        if has_dist_comp
        else round(estimated_distance_sum, 2)
    )
    est_cost_change = (
        round(cost_change_from_comp, 2)
        if has_cost_comp
        else round(estimated_cost_sum, 2)
    )

    unavailable_metrics: List[str] = []
    if avg_exec_time is None:
        unavailable_metrics.append("average_recovery_execution_time_minutes")

    metric_classifications = {
        "total_recovery_plans": MetricAvailabilityStatus.ACTUAL.value,
        "executed_plans": MetricAvailabilityStatus.ACTUAL.value,
        "total_recovered_orders": MetricAvailabilityStatus.ACTUAL.value,
        "total_reassigned_orders_proposed": MetricAvailabilityStatus.ESTIMATED.value,
        "recovery_success_rate": MetricAvailabilityStatus.ACTUAL.value,
        "average_recovery_execution_time_minutes": (
            MetricAvailabilityStatus.ACTUAL.value
            if avg_exec_time is not None
            else MetricAvailabilityStatus.UNAVAILABLE.value
        ),
        "estimated_delay_reduction_minutes": MetricAvailabilityStatus.ESTIMATED.value,
        "estimated_distance_change_km": MetricAvailabilityStatus.ESTIMATED.value,
        "estimated_cost_change": MetricAvailabilityStatus.ESTIMATED.value,
    }

    return RecoveryAnalyticsResponse(
        total_recovery_plans=total_plans,
        optimized_plans=optimized_plans,
        pending_approval_plans=pending_approval_plans,
        approved_plans=approved_plans,
        rejected_plans=rejected_plans,
        executed_plans=executed_plans,
        partially_executed_plans=partially_executed_plans,
        failed_plans=failed_plans,
        infeasible_plans=infeasible_plans,
        plans_by_status=plans_by_status,
        plans_by_strategy=plans_by_strategy,
        total_affected_orders_in_plans=total_affected_orders,
        total_reassigned_orders_proposed=total_reassigned_proposed,
        total_recovered_orders=total_recovered_orders,
        total_recovery_actions=total_actions,
        executed_actions=executed_actions,
        failed_actions=failed_actions,
        pending_actions=pending_actions,
        recovery_success_rate=recovery_success_rate,
        average_recovery_execution_time_minutes=avg_exec_time,
        estimated_delay_reduction_minutes=round(delay_reduction, 2),
        estimated_distance_change_km=est_distance_change,
        estimated_cost_change=est_cost_change,
        metric_classifications=metric_classifications,
        unavailable_metrics=unavailable_metrics,
        filter_meta=filter_meta,
    )

