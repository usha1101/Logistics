import pytest
from datetime import datetime, timezone
from sqlalchemy.orm import Session

from app.models.disruption import (
    AffectedResourceType,
    Disruption,
    DisruptionSeverity,
    DisruptionStatus,
    DisruptionType,
)
from app.models.network import NetworkEdge, NetworkNode, NodeType
from app.models.order import Customer, Order, OrderPriority, OrderStatus
from app.models.simulation import Simulation, SimulationStatus, SimulationVehicleState, SimulationVehicleStatus
from app.models.vehicle import Vehicle, VehicleStatus, VehicleType
from app.models.warehouse import Warehouse, WarehouseStatus
from app.schemas.disruption import DisruptionCreate
from app.services.disruptions.engine import DisruptionEngine
from app.services.disruptions.exceptions import (
    DisruptionNotFoundError,
    InvalidDisruptionTransitionError,
    TargetResourceValidationError,
)
from app.services.disruptions.impact_analyzer import DisruptionImpactAnalyzer
from app.services.disruptions.severity import calculate_severity


def test_severity_calculation_edge_cases():
    # Boundary thresholds
    assert calculate_severity(DisruptionType.TRAFFIC_CONGESTION, {"speed_reduction_pct": 70.0, "delay_minutes": 0}) == DisruptionSeverity.CRITICAL
    assert calculate_severity(DisruptionType.TRAFFIC_CONGESTION, {"speed_reduction_pct": 40.0, "delay_minutes": 0}) == DisruptionSeverity.HIGH
    assert calculate_severity(DisruptionType.TRAFFIC_CONGESTION, {"speed_reduction_pct": 20.0, "delay_minutes": 0}) == DisruptionSeverity.MEDIUM
    assert calculate_severity(DisruptionType.TRAFFIC_CONGESTION, {"speed_reduction_pct": 19.9, "delay_minutes": 0}) == DisruptionSeverity.LOW

    # Warehouse thresholds
    assert calculate_severity(DisruptionType.WAREHOUSE_SHUTDOWN, {"capacity_utilization_pct": 80.0}) == DisruptionSeverity.CRITICAL
    assert calculate_severity(DisruptionType.WAREHOUSE_SHUTDOWN, {"capacity_utilization_pct": 50.0}) == DisruptionSeverity.HIGH
    assert calculate_severity(DisruptionType.WAREHOUSE_SHUTDOWN, {"capacity_utilization_pct": 49.9, "active_orders": 1}) == DisruptionSeverity.MEDIUM
    assert calculate_severity(DisruptionType.WAREHOUSE_SHUTDOWN, {"capacity_utilization_pct": 0.0, "active_orders": 0}) == DisruptionSeverity.LOW


def test_impact_analysis_vehicle_breakdown(db_session: Session):
    # Setup node, warehouse, vehicle, customer, orders
    node = NetworkNode(name="Test Hub", node_type=NodeType.WAREHOUSE.value, latitude=12.97, longitude=77.59)
    db_session.add(node)
    db_session.flush()

    wh = Warehouse(warehouse_code="WH-IMP-01", network_node_id=node.id, total_capacity=5000.0)
    db_session.add(wh)
    db_session.flush()

    vehicle = Vehicle(
        vehicle_code="VEH-IMP-01",
        registration_number="KA-05-AB-1234",
        vehicle_type=VehicleType.MEDIUM_TRUCK.value,
        status=VehicleStatus.IN_TRANSIT.value,
        capacity_kg=2000.0,
        current_load_kg=850.0,
        home_warehouse_id=wh.id,
    )
    db_session.add(vehicle)
    db_session.flush()

    customer = Customer(
        customer_code="CUST-IMP-01",
        name="Acme Corp",
        phone="1234567890",
        address_line="MG Road",
        city="Bengaluru",
        state="Karnataka",
        postal_code="560001",
        latitude=12.9716,
        longitude=77.5946,
    )
    db_session.add(customer)
    db_session.flush()

    now = datetime.now(timezone.utc)
    order1 = Order(
        order_number="ORD-IMP-001",
        customer_id=customer.id,
        warehouse_id=wh.id,
        assigned_vehicle_id=vehicle.id,
        status=OrderStatus.IN_TRANSIT.value,
        priority=OrderPriority.URGENT.value,
        expected_delivery_at=now,
        delivery_address="Indiranagar 100ft Road",
        delivery_latitude=12.9783,
        delivery_longitude=77.6408,
    )
    order2 = Order(
        order_number="ORD-IMP-002",
        customer_id=customer.id,
        warehouse_id=wh.id,
        assigned_vehicle_id=vehicle.id,
        status=OrderStatus.DISPATCHED.value,
        priority=OrderPriority.NORMAL.value,
        expected_delivery_at=now,
        delivery_address="Koramangala 4th Block",
        delivery_latitude=12.9352,
        delivery_longitude=77.6245,
    )
    db_session.add_all([order1, order2])
    db_session.commit()

    # Create disruption
    engine = DisruptionEngine(db_session)
    payload = DisruptionCreate(
        disruption_type=DisruptionType.VEHICLE_BREAKDOWN,
        title="Vehicle Breakdown on Highway",
        affected_vehicle_id=vehicle.id,
        parameters={"delay_minutes": 150.0},
    )
    disruption = engine.create_disruption(payload)
    assert disruption.severity == DisruptionSeverity.CRITICAL.value

    # Analyze impact
    report = engine.get_impact_analysis(disruption.id)
    assert report.affected_vehicles_count == 1
    assert report.affected_orders_count == 2
    assert report.urgent_orders_count == 1
    assert report.at_risk_orders_count >= 1
    assert report.total_estimated_delay_minutes == 150.0


def test_simulation_isolation_rule(db_session: Session):
    """
    Simulation disruptions MUST update SimulationVehicleState.status to BREAKDOWN,
    but MUST NOT alter real production Vehicle.status or Vehicle.current_load_kg.
    """
    node = NetworkNode(name="Sim Hub", node_type=NodeType.WAREHOUSE.value, latitude=12.97, longitude=77.59)
    db_session.add(node)
    db_session.flush()

    wh = Warehouse(warehouse_code="WH-SIM-01", network_node_id=node.id, total_capacity=5000.0)
    db_session.add(wh)
    db_session.flush()

    vehicle = Vehicle(
        vehicle_code="VEH-SIM-01",
        registration_number="KA-01-SIM-001",
        vehicle_type=VehicleType.ELECTRIC_VAN.value,
        status=VehicleStatus.IN_TRANSIT.value,
        capacity_kg=1000.0,
        current_load_kg=400.0,
    )
    db_session.add(vehicle)
    db_session.flush()

    sim = Simulation(name="Active Test Sim", status=SimulationStatus.RUNNING.value)
    db_session.add(sim)
    db_session.flush()

    sim_state = SimulationVehicleState(
        simulation_id=sim.id,
        vehicle_id=vehicle.id,
        status=SimulationVehicleStatus.EN_ROUTE.value,
        origin_node_id=node.id,
        destination_node_id=node.id,
        route_node_ids=[node.id],
        current_latitude=12.97,
        current_longitude=77.59,
    )
    db_session.add(sim_state)
    db_session.commit()

    engine = DisruptionEngine(db_session)
    payload = DisruptionCreate(
        disruption_type=DisruptionType.VEHICLE_BREAKDOWN,
        title="Simulation Breakdown",
        simulation_id=sim.id,
        affected_vehicle_id=vehicle.id,
    )
    disruption = engine.create_disruption(payload)
    disruption = engine.activate_disruption(disruption.id)

    db_session.refresh(sim_state)
    db_session.refresh(vehicle)

    # Simulation vehicle state MUST be BREAKDOWN
    assert sim_state.status == SimulationVehicleStatus.BREAKDOWN.value

    # Real vehicle state MUST remain strictly intact (ISOLATION RULE)
    assert vehicle.status == VehicleStatus.IN_TRANSIT.value
    assert vehicle.current_load_kg == 400.0

    # Resolve disruption -> restores simulation vehicle to EN_ROUTE
    engine.resolve_disruption(disruption.id)
    db_session.refresh(sim_state)
    assert sim_state.status == SimulationVehicleStatus.EN_ROUTE.value


def test_disruption_cancel_lifecycle(db_session: Session):
    engine = DisruptionEngine(db_session)
    payload = DisruptionCreate(
        disruption_type=DisruptionType.TRAFFIC_CONGESTION,
        title="False Alarm Traffic Spike",
    )
    disruption = engine.create_disruption(payload)
    assert disruption.status == DisruptionStatus.DETECTED.value

    disruption = engine.cancel_disruption(disruption.id)
    assert disruption.status == DisruptionStatus.CANCELLED.value

    with pytest.raises(InvalidDisruptionTransitionError):
        engine.activate_disruption(disruption.id)
