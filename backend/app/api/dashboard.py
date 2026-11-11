from datetime import datetime, timezone
from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.deps import require_roles
from app.database.session import get_db
from app.models.disruption import (
    AffectedResourceType,
    Disruption,
    DisruptionImpact,
    DisruptionSeverity,
    DisruptionStatus,
)
from app.models.network import NetworkEdge, NetworkNode, NodeType
from app.models.order import Order, OrderStatus
from app.models.simulation import Simulation
from app.models.user import User, UserRole
from app.models.vehicle import Vehicle, VehicleStatus
from app.models.warehouse import Warehouse, WarehouseStatus
from app.schemas.dashboard import (
    DashboardSummaryResponse,
    DisruptionKPIs,
    NetworkKPIs,
    OperationalKPIs,
    PerformanceKPIs,
    SimulationKPIs,
)
from app.services.analytics import (
    compute_agent_analytics,
    compute_disruption_analytics,
    compute_fleet_analytics,
    compute_order_analytics,
    compute_overview_analytics,
    compute_recovery_analytics,
    compute_simulation_analytics,
    compute_warehouse_analytics,
)

router = APIRouter(prefix="/dashboard", tags=["Command Centre Dashboard"])

DASHBOARD_PERMITTED_ROLES = (
    UserRole.ADMIN,
    UserRole.OPERATIONS_MANAGER,
    UserRole.ANALYST,
)


@router.get(
    "/summary",
    response_model=DashboardSummaryResponse,
    summary="Get unified Command Centre operational and network KPIs",
)
def get_dashboard_summary(
    current_user: User = Depends(require_roles(*DASHBOARD_PERMITTED_ROLES)),
    db: Session = Depends(get_db),
) -> DashboardSummaryResponse:
    # 1. Query network KPIs from database
    total_warehouses = (
        db.execute(
            select(func.count())
            .select_from(NetworkNode)
            .where(
                NetworkNode.node_type == NodeType.WAREHOUSE.value,
                NetworkNode.is_active.is_(True),
            )
        ).scalar()
        or 0
    )

    total_customers = (
        db.execute(
            select(func.count())
            .select_from(NetworkNode)
            .where(
                NetworkNode.node_type == NodeType.CUSTOMER.value,
                NetworkNode.is_active.is_(True),
            )
        ).scalar()
        or 0
    )

    total_connections = (
        db.execute(
            select(func.count())
            .select_from(NetworkEdge)
            .where(NetworkEdge.is_active.is_(True))
        ).scalar()
        or 0
    )

    # 2. Query warehouse specific metrics
    operational_warehouses = (
        db.execute(
            select(func.count())
            .select_from(Warehouse)
            .where(Warehouse.status == WarehouseStatus.OPERATIONAL.value)
        ).scalar()
        or 0
    )
    total_cap = (
        db.execute(select(func.coalesce(func.sum(Warehouse.total_capacity), 0.0))).scalar()
        or 0.0
    )
    used_cap = (
        db.execute(select(func.coalesce(func.sum(Warehouse.used_capacity), 0.0))).scalar()
        or 0.0
    )

    # 3. Query fleet vehicle metrics
    total_vehicles = db.execute(select(func.count()).select_from(Vehicle)).scalar() or 0
    active_vehicles = (
        db.execute(select(func.count()).select_from(Vehicle).where(Vehicle.is_active == True)).scalar()
        or 0
    )
    in_transit_vehicles = (
        db.execute(
            select(func.count())
            .select_from(Vehicle)
            .where(Vehicle.status == VehicleStatus.IN_TRANSIT.value, Vehicle.is_active == True)
        ).scalar()
        or 0
    )
    total_vehicle_cap = (
        db.execute(select(func.coalesce(func.sum(Vehicle.capacity_kg), 0.0))).scalar() or 0.0
    )
    current_vehicle_load = (
        db.execute(select(func.coalesce(func.sum(Vehicle.current_load_kg), 0.0))).scalar() or 0.0
    )
    fleet_utilization = (
        round((current_vehicle_load / total_vehicle_cap) * 100.0, 2)
        if total_vehicle_cap > 0
        else None
    )

    # 4. Query order metrics
    now = datetime.now(timezone.utc)
    total_orders = db.execute(select(func.count()).select_from(Order)).scalar() or 0
    pending_orders = (
        db.execute(
            select(func.count())
            .select_from(Order)
            .where(
                Order.status.in_(
                    [
                        OrderStatus.CREATED.value,
                        OrderStatus.CONFIRMED.value,
                        OrderStatus.PROCESSING.value,
                        OrderStatus.READY_FOR_DISPATCH.value,
                    ]
                )
            )
        ).scalar()
        or 0
    )
    in_transit_orders = (
        db.execute(
            select(func.count())
            .select_from(Order)
            .where(
                Order.status.in_(
                    [
                        OrderStatus.DISPATCHED.value,
                        OrderStatus.IN_TRANSIT.value,
                    ]
                )
            )
        ).scalar()
        or 0
    )
    delivered_orders = (
        db.execute(
            select(func.count())
            .select_from(Order)
            .where(Order.status == OrderStatus.DELIVERED.value)
        ).scalar()
        or 0
    )
    delayed_orders = (
        db.execute(
            select(func.count())
            .select_from(Order)
            .where(
                Order.status.notin_([OrderStatus.DELIVERED.value, OrderStatus.CANCELLED.value]),
                Order.expected_delivery_at < now,
            )
        ).scalar()
        or 0
    )

    # Calculate on-time delivery rate if delivered orders exist
    on_time_delivery_rate = None
    if delivered_orders > 0:
        delivered_list = list(
            db.execute(select(Order).where(Order.status == OrderStatus.DELIVERED.value)).scalars().all()
        )
        on_time_count = sum(
            1 for o in delivered_list if o.delivered_at and o.expected_delivery_at and o.delivered_at <= o.expected_delivery_at
        )
        on_time_delivery_rate = round((on_time_count / delivered_orders) * 100.0, 2)

    # 5. Query simulation KPIs from database
    active_simulations = (
        db.execute(
            select(func.count())
            .select_from(Simulation)
            .where(Simulation.status == "RUNNING")
        ).scalar()
        or 0
    )

    completed_simulations = (
        db.execute(
            select(func.count())
            .select_from(Simulation)
            .where(Simulation.status == "COMPLETED")
        ).scalar()
        or 0
    )

    # 5b. Query disruption KPIs from database
    total_disruptions = db.scalar(select(func.count()).select_from(Disruption)) or 0
    active_disruptions = (
        db.scalar(
            select(func.count())
            .select_from(Disruption)
            .where(Disruption.status.in_([DisruptionStatus.ACTIVE.value, DisruptionStatus.MONITORING.value]))
        )
        or 0
    )
    critical_disruptions = (
        db.scalar(
            select(func.count())
            .select_from(Disruption)
            .where(
                Disruption.status.in_([DisruptionStatus.ACTIVE.value, DisruptionStatus.MONITORING.value]),
                Disruption.severity == DisruptionSeverity.CRITICAL.value,
            )
        )
        or 0
    )
    affected_vehicles_count = (
        db.scalar(
            select(func.count(func.distinct(DisruptionImpact.affected_resource_id)))
            .select_from(DisruptionImpact)
            .join(Disruption, DisruptionImpact.disruption_id == Disruption.id)
            .where(
                Disruption.status.in_([DisruptionStatus.ACTIVE.value, DisruptionStatus.MONITORING.value]),
                DisruptionImpact.affected_resource_type == AffectedResourceType.VEHICLE.value,
            )
        )
        or 0
    )
    affected_orders_count = (
        db.scalar(
            select(func.count(func.distinct(DisruptionImpact.affected_resource_id)))
            .select_from(DisruptionImpact)
            .join(Disruption, DisruptionImpact.disruption_id == Disruption.id)
            .where(
                Disruption.status.in_([DisruptionStatus.ACTIVE.value, DisruptionStatus.MONITORING.value]),
                DisruptionImpact.affected_resource_type == AffectedResourceType.ORDER.value,
            )
        )
        or 0
    )

    # 5c. Compute Stage 12 domain analytics summaries
    overview_data = compute_overview_analytics(db=db, include_simulations=True)
    order_data = compute_order_analytics(db=db, include_simulations=True)
    fleet_data = compute_fleet_analytics(db=db, include_simulations=True)
    warehouse_data = compute_warehouse_analytics(db=db, include_simulations=True)
    disruption_data = compute_disruption_analytics(db=db, include_simulations=True)
    agent_data = compute_agent_analytics(db=db, include_simulations=True)
    recovery_data = compute_recovery_analytics(db=db, include_simulations=True)
    simulation_data = compute_simulation_analytics(db=db)

    # 6. Assemble response
    return DashboardSummaryResponse(
        network=NetworkKPIs(
            total_warehouses=total_warehouses,
            total_customers=total_customers,
            total_network_connections=total_connections,
            operational_warehouses=operational_warehouses,
            total_storage_capacity=round(total_cap, 2),
            used_storage_capacity=round(used_cap, 2),
        ),
        operations=OperationalKPIs(
            total_vehicles=total_vehicles,
            active_vehicles=active_vehicles,
            in_transit_vehicles=in_transit_vehicles,
            total_orders=total_orders,
            pending_orders=pending_orders,
            in_transit_orders=in_transit_orders,
            delivered_orders=delivered_orders,
            delayed_orders=delayed_orders,
        ),
        simulations=SimulationKPIs(
            active_simulations=active_simulations,
            completed_simulations=completed_simulations,
        ),
        disruptions=DisruptionKPIs(
            total_disruptions=total_disruptions,
            active_disruptions=active_disruptions,
            critical_disruptions=critical_disruptions,
            affected_vehicles_count=affected_vehicles_count,
            affected_orders_count=affected_orders_count,
        ),
        performance=PerformanceKPIs(
            on_time_delivery_rate=on_time_delivery_rate,
            fleet_utilization=fleet_utilization,
            average_delivery_time_minutes=order_data.average_delivery_duration_minutes,
        ),
        overview_summary=overview_data.model_dump(mode="json"),
        order_summary=order_data.model_dump(mode="json"),
        fleet_summary=fleet_data.model_dump(mode="json"),
        warehouse_summary=warehouse_data.model_dump(mode="json"),
        disruption_summary=disruption_data.model_dump(mode="json"),
        agent_summary=agent_data.model_dump(mode="json"),
        recovery_summary=recovery_data.model_dump(mode="json"),
        simulation_summary=simulation_data.model_dump(mode="json"),
        generated_at=now.isoformat(),
        data_source="SIMULATED",
    )

