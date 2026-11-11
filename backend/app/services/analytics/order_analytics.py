from datetime import datetime, timezone
from typing import Dict, List, Optional
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.disruption import AffectedResourceType, Disruption, DisruptionImpact
from app.models.order import Order, OrderPriority, OrderStatus
from app.schemas.analytics import MetricAvailabilityStatus, OrderAnalyticsResponse
from app.services.analytics.filters import (
    apply_date_filter,
    apply_simulation_scope,
    build_filter_meta,
    normalize_utc,
)


def compute_order_analytics(
    db: Session,
    start_date: Optional[datetime] = None,
    end_date: Optional[datetime] = None,
    warehouse_id: Optional[str] = None,
    priority: Optional[str] = None,
    status: Optional[str] = None,
    simulation_id: Optional[str] = None,
    include_simulations: bool = False,
) -> OrderAnalyticsResponse:
    filter_meta = build_filter_meta(start_date, end_date, simulation_id, include_simulations)
    now = datetime.now(timezone.utc)

    base_stmt = select(Order)
    base_stmt = apply_date_filter(base_stmt, Order.created_at, start_date, end_date)
    if warehouse_id:
        base_stmt = base_stmt.where(Order.warehouse_id == warehouse_id)
    if priority:
        base_stmt = base_stmt.where(Order.priority == priority)
    if status:
        base_stmt = base_stmt.where(Order.status == status)

    orders: List[Order] = list(db.execute(base_stmt).scalars().all())
    total_orders = len(orders)

    orders_by_status: Dict[str, int] = {s.value: 0 for s in OrderStatus}
    orders_by_priority: Dict[str, int] = {p.value: 0 for p in OrderPriority}

    delivered_orders = 0
    cancelled_orders = 0
    in_transit_orders = 0
    overdue_orders = 0
    on_time_delivered_orders = 0
    late_delivered_orders = 0
    total_weight = 0.0
    total_value = 0.0
    delivery_durations: List[float] = []

    for o in orders:
        st = o.status
        pr = o.priority
        orders_by_status[st] = orders_by_status.get(st, 0) + 1
        orders_by_priority[pr] = orders_by_priority.get(pr, 0) + 1

        total_weight += float(o.total_weight_kg or 0.0)
        total_value += float(o.total_amount or 0.0)

        exp_dt = normalize_utc(o.expected_delivery_at)
        deliv_dt = normalize_utc(o.delivered_at)
        ord_dt = normalize_utc(o.order_date) or normalize_utc(o.created_at)

        if st == OrderStatus.DELIVERED.value:
            delivered_orders += 1
            if deliv_dt and exp_dt:
                if deliv_dt <= exp_dt:
                    on_time_delivered_orders += 1
                else:
                    late_delivered_orders += 1
            else:
                on_time_delivered_orders += 1

            if deliv_dt and ord_dt and deliv_dt >= ord_dt:
                duration_min = (deliv_dt - ord_dt).total_seconds() / 60.0
                delivery_durations.append(duration_min)
        elif st == OrderStatus.CANCELLED.value:
            cancelled_orders += 1
        else:
            if st in (OrderStatus.DISPATCHED.value, OrderStatus.IN_TRANSIT.value):
                in_transit_orders += 1
            if exp_dt and exp_dt < now:
                overdue_orders += 1

    eligible_orders = max(0, total_orders - cancelled_orders)
    delivery_success_rate = (
        round((delivered_orders / eligible_orders) * 100.0, 2) if eligible_orders > 0 else 0.0
    )
    on_time_delivery_rate = (
        round((on_time_delivered_orders / delivered_orders) * 100.0, 2)
        if delivered_orders > 0
        else 0.0
    )

    avg_delivery_duration: Optional[float] = (
        round(sum(delivery_durations) / len(delivery_durations), 2)
        if delivery_durations
        else None
    )

    # Estimated delayed orders & average estimated delay from DisruptionImpact
    impact_stmt = (
        select(DisruptionImpact.affected_resource_id, DisruptionImpact.estimated_delay_minutes)
        .join(Disruption, DisruptionImpact.disruption_id == Disruption.id)
        .where(DisruptionImpact.affected_resource_type == AffectedResourceType.ORDER.value)
    )
    impact_stmt = apply_date_filter(impact_stmt, Disruption.created_at, start_date, end_date)
    impact_stmt = apply_simulation_scope(
        impact_stmt, Disruption.simulation_id, simulation_id, include_simulations
    )
    if warehouse_id or priority or status:
        order_ids = {o.id for o in orders}
        if order_ids:
            impact_stmt = impact_stmt.where(DisruptionImpact.affected_resource_id.in_(order_ids))
        else:
            impact_stmt = impact_stmt.where(False)

    impact_rows = db.execute(impact_stmt).all()
    delayed_order_ids = {
        row[0] for row in impact_rows if (row[1] or 0) > 0
    }
    estimated_delays = [float(row[1]) for row in impact_rows if row[1] is not None and row[1] > 0]
    estimated_delayed_orders = len(delayed_order_ids)
    avg_estimated_delay: Optional[float] = (
        round(sum(estimated_delays) / len(estimated_delays), 2)
        if estimated_delays
        else None
    )

    unavailable_metrics: List[str] = []
    if avg_delivery_duration is None:
        unavailable_metrics.append("average_delivery_duration_minutes")
    if avg_estimated_delay is None:
        unavailable_metrics.append("average_estimated_delay_minutes")

    metric_classifications = {
        "total_orders": MetricAvailabilityStatus.ACTUAL.value,
        "delivered_orders": MetricAvailabilityStatus.ACTUAL.value,
        "overdue_orders": MetricAvailabilityStatus.ACTUAL.value,
        "estimated_delayed_orders": MetricAvailabilityStatus.ESTIMATED.value,
        "delivery_success_rate": MetricAvailabilityStatus.ACTUAL.value,
        "on_time_delivery_rate": MetricAvailabilityStatus.ACTUAL.value,
        "average_delivery_duration_minutes": (
            MetricAvailabilityStatus.ACTUAL.value
            if avg_delivery_duration is not None
            else MetricAvailabilityStatus.UNAVAILABLE.value
        ),
        "average_estimated_delay_minutes": (
            MetricAvailabilityStatus.ESTIMATED.value
            if avg_estimated_delay is not None
            else MetricAvailabilityStatus.UNAVAILABLE.value
        ),
    }

    return OrderAnalyticsResponse(
        total_orders=total_orders,
        orders_by_status=orders_by_status,
        orders_by_priority=orders_by_priority,
        delivered_orders=delivered_orders,
        cancelled_orders=cancelled_orders,
        in_transit_orders=in_transit_orders,
        overdue_orders=overdue_orders,
        estimated_delayed_orders=estimated_delayed_orders,
        eligible_orders=eligible_orders,
        on_time_delivered_orders=on_time_delivered_orders,
        late_delivered_orders=late_delivered_orders,
        delivery_success_rate=delivery_success_rate,
        on_time_delivery_rate=on_time_delivery_rate,
        average_delivery_duration_minutes=avg_delivery_duration,
        average_estimated_delay_minutes=avg_estimated_delay,
        total_order_weight_kg=round(total_weight, 2),
        total_order_value=round(total_value, 2),
        metric_classifications=metric_classifications,
        unavailable_metrics=unavailable_metrics,
        filter_meta=filter_meta,
    )

