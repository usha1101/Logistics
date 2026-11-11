from datetime import datetime, timedelta, timezone
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models.agent import (
    AgentExecution,
    AgentExecutionStatus,
    AgentRecommendation,
    AgentRun,
    AgentRunStatus,
    RecommendationPriority,
    RecommendationValidationStatus,
)
from app.models.disruption import (
    AffectedResourceType,
    Disruption,
    DisruptionImpact,
    DisruptionSeverity,
    DisruptionStatus,
    DisruptionType,
)
from app.models.network import NetworkNode, NodeType
from app.models.order import Customer, Order, OrderPriority, OrderStatus
from app.models.recovery import (
    OptimizationStrategy,
    RecoveryAction,
    RecoveryActionStatus,
    RecoveryComparison,
    RecoveryPlan,
    RecoveryPlanStatus,
)
from app.models.simulation import (
    Simulation,
    SimulationStatus,
    SimulationTelemetry,
    SimulationVehicleState,
    SimulationVehicleStatus,
)
from app.models.vehicle import (
    LocationSource,
    Vehicle,
    VehicleLocation,
    VehicleStatus,
    VehicleStatusHistory,
    VehicleType,
)
from app.models.warehouse import (
    InventoryItem,
    InventoryMovement,
    MovementType,
    Warehouse,
    WarehouseStatus,
    WarehouseType,
)


def _seed_full_operational_and_simulated_data(db: Session):
    now = datetime.now(timezone.utc)
    wh_node = NetworkNode(
        name="BLR Central Hub",
        node_type=NodeType.WAREHOUSE.value,
        latitude=12.9716,
        longitude=77.5946,
        is_active=True,
    )
    cust_node = NetworkNode(
        name="Indiranagar Client",
        node_type=NodeType.CUSTOMER.value,
        latitude=12.9784,
        longitude=77.6408,
        is_active=True,
    )
    db.add_all([wh_node, cust_node])
    db.commit()

    wh = Warehouse(
        network_node_id=wh_node.id,
        warehouse_code="WH-INT-01",
        warehouse_type=WarehouseType.DISTRIBUTION_CENTER.value,
        total_capacity=2000.0,
        used_capacity=800.0,
        status=WarehouseStatus.OPERATIONAL.value,
    )
    cust = Customer(
        customer_code="CUST-INT-01",
        name="Indiranagar Retail",
        email="retail@indiranagar.io",
        phone="9988776655",
        address_line="100 Feet Road",
        city="Bengaluru",
        state="Karnataka",
        postal_code="560038",
        latitude=12.9784,
        longitude=77.6408,
    )
    db.add_all([wh, cust])
    db.commit()

    item1 = InventoryItem(
        warehouse_id=wh.id,
        sku="SKU-INT-1",
        product_name="Smart Sensor",
        category="IoT",
        quantity=80,
        reorder_level=20,
        unit="pcs",
    )
    item2 = InventoryItem(
        warehouse_id=wh.id,
        sku="SKU-INT-2",
        product_name="Battery Pack",
        category="Power",
        quantity=5,
        reorder_level=15,
        unit="pcs",
    )
    db.add_all([item1, item2])
    db.commit()

    mov = InventoryMovement(
        inventory_item_id=item1.id,
        movement_type=MovementType.STOCK_RECEIVED.value,
        quantity=80,
        previous_quantity=0,
        new_quantity=80,
    )
    v1 = Vehicle(
        vehicle_code="VEH-INT-1",
        registration_number="KA01INT0001",
        vehicle_type=VehicleType.MEDIUM_TRUCK.value,
        capacity_kg=1000.0,
        current_load_kg=400.0,
        status=VehicleStatus.IN_TRANSIT.value,
        home_warehouse_id=wh.id,
        is_active=True,
    )
    db.add_all([mov, v1])
    db.commit()

    vsh = VehicleStatusHistory(
        vehicle_id=v1.id,
        previous_status=VehicleStatus.AVAILABLE.value,
        new_status=VehicleStatus.IN_TRANSIT.value,
    )
    loc1 = VehicleLocation(
        vehicle_id=v1.id,
        latitude=12.9716,
        longitude=77.5946,
        speed_kmph=42.0,
        recorded_at=now - timedelta(minutes=25),
        source=LocationSource.GPS.value,
    )
    loc2 = VehicleLocation(
        vehicle_id=v1.id,
        latitude=12.9784,
        longitude=77.6408,
        speed_kmph=38.0,
        recorded_at=now - timedelta(minutes=5),
        source=LocationSource.GPS.value,
    )
    o1 = Order(
        order_number="ORD-INT-1",
        customer_id=cust.id,
        warehouse_id=wh.id,
        assigned_vehicle_id=v1.id,
        status=OrderStatus.DELIVERED.value,
        priority=OrderPriority.HIGH.value,
        order_date=now - timedelta(hours=2),
        expected_delivery_at=now - timedelta(minutes=30),
        delivered_at=now - timedelta(minutes=60),
        delivery_address="100 Feet Road",
        delivery_latitude=12.9784,
        delivery_longitude=77.6408,
        total_weight_kg=120.0,
        total_amount=1500.0,
    )
    o2 = Order(
        order_number="ORD-INT-2",
        customer_id=cust.id,
        warehouse_id=wh.id,
        assigned_vehicle_id=v1.id,
        status=OrderStatus.IN_TRANSIT.value,
        priority=OrderPriority.URGENT.value,
        order_date=now - timedelta(hours=3),
        expected_delivery_at=now - timedelta(minutes=20),
        delivery_address="100 Feet Road",
        delivery_latitude=12.9784,
        delivery_longitude=77.6408,
        total_weight_kg=280.0,
        total_amount=3200.0,
    )
    db.add_all([vsh, loc1, loc2, o1, o2])
    db.commit()

    dis = Disruption(
        disruption_code="DIS-INT-1",
        disruption_type=DisruptionType.TRAFFIC_CONGESTION.value,
        severity=DisruptionSeverity.HIGH.value,
        status=DisruptionStatus.ACTIVE.value,
        title="Ring Road Congestion",
        affected_vehicle_id=v1.id,
        affected_order_id=o2.id,
    )
    db.add(dis)
    db.commit()

    imp = DisruptionImpact(
        disruption_id=dis.id,
        affected_resource_type=AffectedResourceType.ORDER.value,
        affected_resource_id=o2.id,
        severity=DisruptionSeverity.HIGH.value,
        estimated_delay_minutes=35.0,
    )
    run = AgentRun(
        disruption_id=dis.id,
        status=AgentRunStatus.COMPLETED.value,
        primary_provider="GEMINI",
        execution_duration_ms=310.0,
    )
    db.add_all([imp, run])
    db.commit()

    ex = AgentExecution(
        agent_run_id=run.id,
        agent_name="DisruptionAnalysisAgent",
        status=AgentExecutionStatus.COMPLETED.value,
        provider="GEMINI",
        model="gemini-2.5-flash",
        confidence_score=0.92,
        execution_duration_ms=150.0,
    )
    rec = AgentRecommendation(
        agent_run_id=run.id,
        source_agent="DisruptionAnalysisAgent",
        recommendation_type="REROUTE_VEHICLE",
        priority=RecommendationPriority.HIGH.value,
        title="Reroute around congestion",
        description="Use alternate edge",
        validation_status=RecommendationValidationStatus.VALIDATED.value,
    )
    plan = RecoveryPlan(
        recovery_code="REC-INT-1",
        disruption_id=dis.id,
        agent_run_id=run.id,
        status=RecoveryPlanStatus.EXECUTED.value,
        optimization_strategy=OptimizationStrategy.PRIORITY_BASED_RECOVERY.value,
        affected_order_count=1,
        reassigned_order_count=1,
        assigned_vehicle_count=1,
        estimated_total_distance_km=12.4,
        estimated_total_delay_minutes=10.0,
        estimated_recovery_cost=120.0,
        executed_at=now,
    )
    db.add_all([ex, rec, plan])
    db.commit()

    act = RecoveryAction(
        recovery_plan_id=plan.id,
        action_type="REASSIGN_VEHICLE",
        target_resource_type="ORDER",
        target_resource_id=o2.id,
        status=RecoveryActionStatus.EXECUTED.value,
    )
    comp = RecoveryComparison(
        recovery_plan_id=plan.id,
        metric_name="total_delivery_delay",
        baseline_value=35.0,
        proposed_value=10.0,
        improvement_value=25.0,
        improvement_percentage=71.43,
        unit="minutes",
    )
    sim = Simulation(
        id="SIM-INT-01",
        name="Integration Twin Run",
        seed=99,
        status=SimulationStatus.RUNNING.value,
        started_at=now - timedelta(minutes=10),
    )
    db.add_all([act, comp, sim])
    db.commit()

    svs = SimulationVehicleState(
        simulation_id=sim.id,
        vehicle_id=v1.id,
        origin_node_id=wh_node.id,
        destination_node_id=cust_node.id,
        route_node_ids=[wh_node.id, cust_node.id],
        current_latitude=12.9750,
        current_longitude=77.6100,
        status=SimulationVehicleStatus.EN_ROUTE.value,
        progress_percentage=50.0,
    )
    st1 = SimulationTelemetry(
        simulation_id=sim.id,
        vehicle_id=v1.id,
        latitude=12.9716,
        longitude=77.5946,
        speed_kmph=40.0,
    )
    st2 = SimulationTelemetry(
        simulation_id=sim.id,
        vehicle_id=v1.id,
        latitude=12.9750,
        longitude=77.6100,
        speed_kmph=40.0,
    )
    db.add_all([svs, st1, st2])
    db.commit()
    return {"warehouse_id": wh.id, "vehicle_id": v1.id, "disruption_id": dis.id, "plan_id": plan.id, "sim_id": sim.id}


def test_analytics_overview_endpoint(client: TestClient, db_session: Session, analyst_headers: dict):
    _seed_full_operational_and_simulated_data(db_session)
    res = client.get("/api/v1/analytics/overview", headers=analyst_headers)
    assert res.status_code == 200
    data = res.json()
    assert data["total_orders"] == 2
    assert data["delivered_orders"] == 1
    assert data["overdue_orders"] == 1
    assert data["estimated_delayed_orders"] == 1
    assert data["delivery_success_rate"] == 50.0
    assert data["on_time_delivery_rate"] == 100.0
    assert data["total_vehicles"] == 1
    assert data["fleet_utilization_rate"] == 40.0
    assert data["warehouse_utilization_rate"] == 40.0
    assert data["active_disruptions"] == 1
    assert data["total_agent_runs"] == 1
    assert data["executed_recovery_plans"] == 1
    assert data["active_simulations"] == 1


def test_analytics_orders_and_trends_endpoints(
    client: TestClient, db_session: Session, warehouse_manager_headers: dict
):
    seeded = _seed_full_operational_and_simulated_data(db_session)
    res = client.get(
        f"/api/v1/analytics/orders?warehouse_id={seeded['warehouse_id']}",
        headers=warehouse_manager_headers,
    )
    assert res.status_code == 200
    data = res.json()
    assert data["total_orders"] == 2
    assert data["average_delivery_duration_minutes"] == 60.0
    assert data["average_estimated_delay_minutes"] == 35.0

    tr_res = client.get(
        "/api/v1/analytics/orders/trends?grouping=DAY",
        headers=warehouse_manager_headers,
    )
    assert tr_res.status_code == 200
    tr = tr_res.json()
    assert tr["domain"] == "ORDERS"
    assert tr["total_points"] == 1
    assert tr["data_points"][0]["breakdown"]["orders_created"] == 2


def test_analytics_fleet_and_trends_endpoints(
    client: TestClient, db_session: Session, fleet_manager_headers: dict
):
    _seed_full_operational_and_simulated_data(db_session)
    res = client.get("/api/v1/analytics/fleet", headers=fleet_manager_headers)
    assert res.status_code == 200
    data = res.json()
    assert data["total_vehicles"] == 1
    assert data["in_transit_vehicles"] == 1
    assert data["fleet_capacity_utilization_percentage"] == 40.0
    assert data["total_distance_travelled_km"] is not None and data["total_distance_travelled_km"] > 4.0

    tr_res = client.get("/api/v1/analytics/fleet/trends?grouping=WEEK", headers=fleet_manager_headers)
    assert tr_res.status_code == 200
    assert tr_res.json()["domain"] == "FLEET"
    assert tr_res.json()["total_points"] == 1


def test_analytics_warehouses_and_trends_endpoints(
    client: TestClient, db_session: Session, warehouse_manager_headers: dict
):
    _seed_full_operational_and_simulated_data(db_session)
    res = client.get("/api/v1/analytics/warehouses", headers=warehouse_manager_headers)
    assert res.status_code == 200
    data = res.json()
    assert data["total_warehouses"] == 1
    assert data["in_stock_items"] == 1
    assert data["low_stock_items"] == 1
    assert data["inbound_quantity_total"] == 80

    tr_res = client.get(
        "/api/v1/analytics/warehouses/trends?grouping=MONTH",
        headers=warehouse_manager_headers,
    )
    assert tr_res.status_code == 200
    assert tr_res.json()["domain"] == "WAREHOUSES"
    assert tr_res.json()["total_points"] == 1


def test_analytics_disruptions_and_trends_endpoints(
    client: TestClient, db_session: Session, ops_headers: dict
):
    _seed_full_operational_and_simulated_data(db_session)
    res = client.get("/api/v1/analytics/disruptions", headers=ops_headers)
    assert res.status_code == 200
    data = res.json()
    assert data["total_disruptions"] == 1
    assert data["active_disruptions"] == 1
    assert data["estimated_total_delay_minutes"] == 35.0

    tr_res = client.get("/api/v1/analytics/disruptions/trends", headers=ops_headers)
    assert tr_res.status_code == 200
    assert tr_res.json()["total_points"] == 1


def test_analytics_agents_and_trends_endpoints(
    client: TestClient, db_session: Session, analyst_headers: dict
):
    _seed_full_operational_and_simulated_data(db_session)
    res = client.get("/api/v1/analytics/agents", headers=analyst_headers)
    assert res.status_code == 200
    data = res.json()
    assert data["total_agent_runs"] == 1
    assert data["validated_recommendations"] == 1
    assert data["agent_success_rate"] == 100.0
    assert data["token_usage_total"] is None

    tr_res = client.get("/api/v1/analytics/agents/trends", headers=analyst_headers)
    assert tr_res.status_code == 200
    assert tr_res.json()["total_points"] == 1


def test_analytics_recovery_and_trends_endpoints(
    client: TestClient, db_session: Session, admin_headers: dict
):
    _seed_full_operational_and_simulated_data(db_session)
    res = client.get("/api/v1/analytics/recovery", headers=admin_headers)
    assert res.status_code == 200
    data = res.json()
    assert data["total_recovery_plans"] == 1
    assert data["executed_plans"] == 1
    assert data["total_recovered_orders"] == 1
    assert data["recovery_success_rate"] == 100.0

    tr_res = client.get("/api/v1/analytics/recovery/trends", headers=admin_headers)
    assert tr_res.status_code == 200
    assert tr_res.json()["total_points"] == 1


def test_analytics_simulations_endpoint(
    client: TestClient, db_session: Session, analyst_headers: dict
):
    seeded = _seed_full_operational_and_simulated_data(db_session)
    res = client.get(
        f"/api/v1/analytics/simulations?simulation_id={seeded['sim_id']}",
        headers=analyst_headers,
    )
    assert res.status_code == 200
    data = res.json()
    assert data["total_simulations"] == 1
    assert data["running_simulations"] == 1
    assert data["total_simulated_vehicles"] == 1
    assert data["total_simulated_distance_km"] is not None


def test_analytics_comparisons_endpoint(
    client: TestClient, db_session: Session, analyst_headers: dict
):
    seeded = _seed_full_operational_and_simulated_data(db_session)
    res = client.get(
        f"/api/v1/analytics/comparisons?recovery_plan_id={seeded['plan_id']}",
        headers=analyst_headers,
    )
    assert res.status_code == 200
    data = res.json()
    assert data["total_comparisons_evaluated"] == 1
    delay_m = next(m for m in data["metrics"] if m["metric_name"] == "estimated_delay_minutes")
    assert delay_m["before_value"] == 35.0
    assert delay_m["after_value"] == 10.0
    assert delay_m["is_improved"] is True


def test_analytics_health_endpoint(client: TestClient, analyst_headers: dict):
    res = client.get("/api/v1/analytics/health", headers=analyst_headers)
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "HEALTHY"
    assert data["reportlab_available"] is True
    assert data["reports_storage_ready"] is True


def test_analytics_invalid_date_range_returns_400(client: TestClient, analyst_headers: dict):
    res = client.get(
        "/api/v1/analytics/overview?start_date=2026-11-15T00:00:00Z&end_date=2026-11-10T00:00:00Z",
        headers=analyst_headers,
    )
    assert res.status_code == 400
    assert res.json()["error"]["code"] == "BAD_REQUEST"


def test_analytics_rbac_restrictions(
    client: TestClient,
    fleet_manager_headers: dict,
    warehouse_manager_headers: dict,
    analyst_headers: dict,
):
    # Unauthenticated -> 401
    assert client.get("/api/v1/analytics/overview").status_code == 401

    # Fleet manager can access fleet and orders, but NOT overview, warehouses, disruptions, agents, recovery
    assert client.get("/api/v1/analytics/fleet", headers=fleet_manager_headers).status_code == 200
    assert client.get("/api/v1/analytics/orders", headers=fleet_manager_headers).status_code == 200
    assert client.get("/api/v1/analytics/overview", headers=fleet_manager_headers).status_code == 403
    assert client.get("/api/v1/analytics/warehouses", headers=fleet_manager_headers).status_code == 403
    assert client.get("/api/v1/analytics/disruptions", headers=fleet_manager_headers).status_code == 403
    assert client.get("/api/v1/analytics/agents", headers=fleet_manager_headers).status_code == 403
    assert client.get("/api/v1/analytics/recovery", headers=fleet_manager_headers).status_code == 403

    # Warehouse manager can access warehouses and orders, but NOT overview or fleet
    assert client.get("/api/v1/analytics/warehouses", headers=warehouse_manager_headers).status_code == 200
    assert client.get("/api/v1/analytics/orders", headers=warehouse_manager_headers).status_code == 200
    assert client.get("/api/v1/analytics/overview", headers=warehouse_manager_headers).status_code == 403
    assert client.get("/api/v1/analytics/fleet", headers=warehouse_manager_headers).status_code == 403

    # Analyst can access all analytics endpoints
    for path in (
        "/api/v1/analytics/overview",
        "/api/v1/analytics/orders",
        "/api/v1/analytics/fleet",
        "/api/v1/analytics/warehouses",
        "/api/v1/analytics/disruptions",
        "/api/v1/analytics/agents",
        "/api/v1/analytics/recovery",
        "/api/v1/analytics/simulations",
        "/api/v1/analytics/comparisons",
        "/api/v1/analytics/health",
    ):
        assert client.get(path, headers=analyst_headers).status_code == 200


def test_dashboard_summary_includes_stage12_analytics_sections(
    client: TestClient, db_session: Session, analyst_headers: dict
):
    _seed_full_operational_and_simulated_data(db_session)
    res = client.get("/api/v1/dashboard/summary", headers=analyst_headers)
    assert res.status_code == 200
    data = res.json()
    for section in (
        "overview_summary",
        "order_summary",
        "fleet_summary",
        "warehouse_summary",
        "disruption_summary",
        "agent_summary",
        "recovery_summary",
        "simulation_summary",
    ):
        assert section in data
        assert data[section] is not None
    assert data["performance"]["average_delivery_time_minutes"] == 60.0

