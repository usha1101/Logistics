import pytest
from datetime import datetime, timezone
from fastapi.testclient import TestClient
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
from app.scripts.seed_demo_disruptions import seed_demo_disruptions


@pytest.fixture
def disruption_setup(db_session: Session):
    # Setup node, warehouse, vehicles, customers, orders, edges
    node_wh = NetworkNode(name="Disruption WH Hub", node_type=NodeType.WAREHOUSE.value, latitude=12.9698, longitude=77.7499)
    node_cust = NetworkNode(name="Disruption Cust Hub", node_type=NodeType.CUSTOMER.value, latitude=12.9352, longitude=77.6245)
    db_session.add_all([node_wh, node_cust])
    db_session.flush()

    edge = NetworkEdge(
        source_node_id=node_wh.id,
        target_node_id=node_cust.id,
        distance_km=14.2,
        estimated_travel_minutes=35,
        road_type="HIGHWAY",
        is_active=True,
    )
    wh = Warehouse(warehouse_code="WH-DISR-01", network_node_id=node_wh.id, total_capacity=8000.0)
    v1 = Vehicle(
        vehicle_code="VEH-DISR-01",
        registration_number="KA-01-DS-1001",
        vehicle_type=VehicleType.HEAVY_TRUCK.value,
        status=VehicleStatus.IN_TRANSIT.value,
        capacity_kg=2500.0,
        current_load_kg=1200.0,
        home_warehouse_id=wh.id,
    )
    v2 = Vehicle(
        vehicle_code="VEH-DISR-02",
        registration_number="KA-01-DS-1002",
        vehicle_type=VehicleType.DELIVERY_VAN.value,
        status=VehicleStatus.AVAILABLE.value,
        capacity_kg=1000.0,
        current_load_kg=0.0,
        home_warehouse_id=wh.id,
    )
    cust = Customer(
        customer_code="CUST-DISR-01",
        name="Global Retailers",
        phone="9876543210",
        address_line="Koramangala Ring Road",
        city="Bengaluru",
        state="Karnataka",
        postal_code="560034",
        latitude=12.9352,
        longitude=77.6245,
    )
    db_session.add_all([edge, wh, v1, v2, cust])
    db_session.flush()

    now = datetime.now(timezone.utc)
    order1 = Order(
        order_number="ORD-DISR-001",
        customer_id=cust.id,
        warehouse_id=wh.id,
        assigned_vehicle_id=v1.id,
        status=OrderStatus.IN_TRANSIT.value,
        priority=OrderPriority.URGENT.value,
        expected_delivery_at=now,
        delivery_address="Koramangala Ring Road",
        delivery_latitude=12.9352,
        delivery_longitude=77.6245,
    )
    order2 = Order(
        order_number="ORD-DISR-002",
        customer_id=cust.id,
        warehouse_id=wh.id,
        status=OrderStatus.CREATED.value,
        priority=OrderPriority.NORMAL.value,
        expected_delivery_at=now,
        delivery_address="Koramangala Ring Road",
        delivery_latitude=12.9352,
        delivery_longitude=77.6245,
    )
    db_session.add_all([order1, order2])
    db_session.commit()

    return {
        "node_wh": node_wh,
        "node_cust": node_cust,
        "edge": edge,
        "warehouse": wh,
        "v1": v1,
        "v2": v2,
        "cust": cust,
        "order1": order1,
        "order2": order2,
    }


def test_create_disruption_dispatcher(client: TestClient, disruption_setup, ops_headers):
    payload = {
        "disruption_type": "TRAFFIC_CONGESTION",
        "title": "Severe Traffic on Outer Ring Road",
        "description": "Gridlock due to water logging",
        "affected_network_edge_id": disruption_setup["edge"].id,
        "parameters": {"speed_reduction_pct": 60.0, "delay_minutes": 50.0},
    }
    response = client.post("/api/v1/disruptions", json=payload, headers=ops_headers)
    assert response.status_code == 201
    data = response.json()
    assert data["disruption_type"] == "TRAFFIC_CONGESTION"
    assert data["severity"] == "HIGH"
    assert data["status"] == "DETECTED"
    assert data["affected_network_edge_id"] == disruption_setup["edge"].id
    assert "events" in data
    assert len(data["events"]) >= 1


def test_create_disruption_unauthorized_analyst(client: TestClient, disruption_setup, analyst_headers):
    payload = {
        "disruption_type": "DEMAND_SURGE",
        "title": "Analyst Not Allowed to Create",
    }
    response = client.post("/api/v1/disruptions", json=payload, headers=analyst_headers)
    assert response.status_code == 403


def test_list_and_filter_disruptions(client: TestClient, disruption_setup, ops_headers, analyst_headers):
    # Create two disruptions
    client.post("/api/v1/disruptions", json={
        "disruption_type": "DEMAND_SURGE",
        "title": "Demand Surge 1",
        "parameters": {"surge_multiplier": 2.5, "extra_orders": 30},
    }, headers=ops_headers)

    client.post("/api/v1/disruptions", json={
        "disruption_type": "TRAFFIC_CONGESTION",
        "title": "Traffic 1",
        "parameters": {"speed_reduction_pct": 10.0, "delay_minutes": 5.0},
    }, headers=ops_headers)

    # Analyst can read
    res = client.get("/api/v1/disruptions", headers=analyst_headers)
    assert res.status_code == 200
    data = res.json()
    assert data["total"] >= 2
    assert "items" in data

    # Filter by disruption_type
    res_type = client.get("/api/v1/disruptions?disruption_type=DEMAND_SURGE", headers=analyst_headers)
    assert res_type.status_code == 200
    for item in res_type.json()["items"]:
        assert item["disruption_type"] == "DEMAND_SURGE"


def test_disruption_lifecycle_transitions(client: TestClient, disruption_setup, ops_headers):
    # 1. Create
    res = client.post("/api/v1/disruptions", json={
        "disruption_type": "DELIVERY_DELAY",
        "title": "Courier Delay",
        "affected_order_id": disruption_setup["order1"].id,
        "parameters": {"delay_minutes": 65.0},
    }, headers=ops_headers)
    print("CREATE RESPONSE:", res.status_code, res.json())
    assert res.status_code == 201
    d_id = res.json()["id"]
    assert res.json()["status"] == "DETECTED"

    # 2. Activate
    res_act = client.post(f"/api/v1/disruptions/{d_id}/activate", headers=ops_headers)
    assert res_act.status_code == 200
    assert res_act.json()["status"] == "ACTIVE"

    # 3. Monitor
    res_mon = client.post(f"/api/v1/disruptions/{d_id}/monitor", headers=ops_headers)
    assert res_mon.status_code == 200
    assert res_mon.json()["status"] == "MONITORING"

    # 4. Resolve
    res_res = client.post(f"/api/v1/disruptions/{d_id}/resolve", json={"notes": "Package recovered"}, headers=ops_headers)
    assert res_res.status_code == 200
    assert res_res.json()["status"] == "RESOLVED"
    assert res_res.json()["actual_end_time"] is not None

    # 5. Invalid transition: cannot re-activate resolved
    res_invalid = client.post(f"/api/v1/disruptions/{d_id}/activate", headers=ops_headers)
    assert res_invalid.status_code == 400


def test_disruption_patch_and_cancel(client: TestClient, disruption_setup, ops_headers):
    res = client.post("/api/v1/disruptions", json={
        "disruption_type": "DEMAND_SURGE",
        "title": "Initial Title",
    }, headers=ops_headers)
    d_id = res.json()["id"]

    # PATCH
    patch_res = client.patch(f"/api/v1/disruptions/{d_id}", json={
        "title": "Updated Surge Title",
        "severity": "CRITICAL",
    }, headers=ops_headers)
    assert patch_res.status_code == 200
    assert patch_res.json()["title"] == "Updated Surge Title"
    assert patch_res.json()["severity"] == "CRITICAL"

    # CANCEL
    cancel_res = client.post(f"/api/v1/disruptions/{d_id}/cancel", json={"reason": "Incorrect report"}, headers=ops_headers)
    assert cancel_res.status_code == 200
    assert cancel_res.json()["status"] == "CANCELLED"


def test_disruption_impact_analysis_endpoint(client: TestClient, disruption_setup, ops_headers, analyst_headers):
    res = client.post("/api/v1/disruptions", json={
        "disruption_type": "VEHICLE_BREAKDOWN",
        "title": "Vehicle 1 Breakdown",
        "affected_vehicle_id": disruption_setup["v1"].id,
        "parameters": {"delay_minutes": 120.0},
    }, headers=ops_headers)
    d_id = res.json()["id"]

    impact_res = client.get(f"/api/v1/disruptions/{d_id}/impact", headers=analyst_headers)
    assert impact_res.status_code == 200
    data = impact_res.json()
    assert data["disruption_id"] == d_id
    assert data["affected_vehicles_count"] == 1
    assert data["affected_orders_count"] >= 1
    assert data["total_estimated_delay_minutes"] == 120.0
    assert len(data["affected_vehicles"]) == 1
    assert data["affected_vehicles"][0]["vehicle_id"] == disruption_setup["v1"].id


def test_disruption_events_audit_endpoint(client: TestClient, disruption_setup, ops_headers, analyst_headers):
    res = client.post("/api/v1/disruptions", json={
        "disruption_type": "WAREHOUSE_SHUTDOWN",
        "title": "Power Cut",
        "affected_warehouse_id": disruption_setup["warehouse"].id,
    }, headers=ops_headers)
    d_id = res.json()["id"]

    client.post(f"/api/v1/disruptions/{d_id}/activate", headers=ops_headers)

    events_res = client.get(f"/api/v1/disruptions/{d_id}/events", headers=analyst_headers)
    assert events_res.status_code == 200
    data = events_res.json()
    assert data["total"] >= 2
    types = [e["event_type"] for e in data["items"]]
    assert "DISRUPTION_CREATED" in types
    assert "DISRUPTION_ACTIVATED" in types


def test_active_disruptions_endpoint(client: TestClient, disruption_setup, ops_headers, analyst_headers):
    # Create and activate one
    res = client.post("/api/v1/disruptions", json={
        "disruption_type": "TRAFFIC_CONGESTION",
        "title": "Active Congestion",
    }, headers=ops_headers)
    d_id = res.json()["id"]
    client.post(f"/api/v1/disruptions/{d_id}/activate", headers=ops_headers)

    active_res = client.get("/api/v1/disruptions/active", headers=analyst_headers)
    assert active_res.status_code == 200
    ids = [d["id"] for d in active_res.json()["items"]]
    assert d_id in ids


def test_dashboard_summary_includes_disruptions(client: TestClient, disruption_setup, ops_headers):
    # Activate a disruption to reflect in dashboard KPIs
    res = client.post("/api/v1/disruptions", json={
        "disruption_type": "VEHICLE_BREAKDOWN",
        "title": "Dashboard Metric Breakdown",
        "severity": "CRITICAL",
        "affected_vehicle_id": disruption_setup["v1"].id,
    }, headers=ops_headers)
    d_id = res.json()["id"]
    client.post(f"/api/v1/disruptions/{d_id}/activate", headers=ops_headers)

    dash_res = client.get("/api/v1/dashboard/summary", headers=ops_headers)
    assert dash_res.status_code == 200
    dash_data = dash_res.json()
    assert "disruptions" in dash_data
    assert dash_data["disruptions"]["active_disruptions"] >= 1
    assert dash_data["disruptions"]["critical_disruptions"] >= 1


def test_seed_demo_disruptions_idempotency(db_session: Session):
    r1 = seed_demo_disruptions(db_session)
    count1 = len(r1)
    assert count1 >= 4

    r2 = seed_demo_disruptions(db_session)
    count2 = len(r2)
    assert count2 == count1
