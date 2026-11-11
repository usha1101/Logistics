from datetime import datetime
from typing import Optional
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.vehicle import Vehicle
from app.schemas.analytics import MetricAvailabilityStatus, OverviewAnalyticsResponse
from app.services.analytics.agent_analytics import compute_agent_analytics
from app.services.analytics.disruption_analytics import compute_disruption_analytics
from app.services.analytics.filters import build_filter_meta
from app.services.analytics.fleet_analytics import compute_fleet_analytics
from app.services.analytics.order_analytics import compute_order_analytics
from app.services.analytics.recovery_analytics import compute_recovery_analytics
from app.services.analytics.simulation_analytics import compute_simulation_analytics
from app.services.analytics.warehouse_analytics import compute_warehouse_analytics


def compute_overview_analytics(
    db: Session,
    start_date: Optional[datetime] = None,
    end_date: Optional[datetime] = None,
    simulation_id: Optional[str] = None,
    include_simulations: bool = False,
) -> OverviewAnalyticsResponse:
    filter_meta = build_filter_meta(start_date, end_date, simulation_id, include_simulations)

    orders = compute_order_analytics(
        db=db,
        start_date=start_date,
        end_date=end_date,
        simulation_id=simulation_id,
        include_simulations=include_simulations,
    )
    fleet = compute_fleet_analytics(
        db=db,
        start_date=start_date,
        end_date=end_date,
        simulation_id=simulation_id,
        include_simulations=include_simulations,
    )
    warehouses = compute_warehouse_analytics(
        db=db,
        start_date=start_date,
        end_date=end_date,
        simulation_id=simulation_id,
        include_simulations=include_simulations,
    )
    disruptions = compute_disruption_analytics(
        db=db,
        start_date=start_date,
        end_date=end_date,
        simulation_id=simulation_id,
        include_simulations=include_simulations,
    )
    agents = compute_agent_analytics(
        db=db,
        start_date=start_date,
        end_date=end_date,
        simulation_id=simulation_id,
        include_simulations=include_simulations,
    )
    recovery = compute_recovery_analytics(
        db=db,
        start_date=start_date,
        end_date=end_date,
        simulation_id=simulation_id,
        include_simulations=include_simulations,
    )
    sims = compute_simulation_analytics(
        db=db,
        start_date=start_date,
        end_date=end_date,
        simulation_id=simulation_id,
    )

    active_vehicles = (
        db.scalar(select(func.count(Vehicle.id)).where(Vehicle.is_active.is_(True))) or 0
    )

    metric_classifications = {
        "total_orders": MetricAvailabilityStatus.ACTUAL.value,
        "overdue_orders": MetricAvailabilityStatus.ACTUAL.value,
        "estimated_delayed_orders": MetricAvailabilityStatus.ESTIMATED.value,
        "delivery_success_rate": MetricAvailabilityStatus.ACTUAL.value,
        "on_time_delivery_rate": MetricAvailabilityStatus.ACTUAL.value,
        "fleet_utilization_rate": MetricAvailabilityStatus.ACTUAL.value,
        "warehouse_utilization_rate": MetricAvailabilityStatus.ACTUAL.value,
        "recovery_success_rate": MetricAvailabilityStatus.ACTUAL.value,
        "active_simulations": MetricAvailabilityStatus.SIMULATED.value,
    }

    return OverviewAnalyticsResponse(
        total_orders=orders.total_orders,
        delivered_orders=orders.delivered_orders,
        in_transit_orders=orders.in_transit_orders,
        overdue_orders=orders.overdue_orders,
        estimated_delayed_orders=orders.estimated_delayed_orders,
        cancelled_orders=orders.cancelled_orders,
        delivery_success_rate=orders.delivery_success_rate,
        on_time_delivery_rate=orders.on_time_delivery_rate,
        total_vehicles=fleet.total_vehicles,
        active_vehicles=active_vehicles,
        fleet_utilization_rate=fleet.fleet_capacity_utilization_percentage,
        total_warehouses=warehouses.total_warehouses,
        warehouse_utilization_rate=warehouses.overall_utilization_percentage,
        active_disruptions=disruptions.active_disruptions,
        resolved_disruptions=disruptions.resolved_disruptions,
        total_agent_runs=agents.total_agent_runs,
        total_recovery_plans=recovery.total_recovery_plans,
        executed_recovery_plans=recovery.executed_plans,
        recovery_success_rate=recovery.recovery_success_rate,
        active_simulations=sims.running_simulations,
        metric_classifications=metric_classifications,
        unavailable_metrics=[],
        filter_meta=filter_meta,
    )

