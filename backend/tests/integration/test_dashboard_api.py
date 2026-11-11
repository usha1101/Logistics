from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.core.security import create_access_token
from app.models.network import NetworkEdge, NetworkNode, NodeType
from app.models.simulation import Simulation
from app.models.user import User, UserRole


def test_dashboard_summary_unauthenticated_rejected(client: TestClient):
    response = client.get("/api/v1/dashboard/summary")
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "UNAUTHORIZED"


def test_dashboard_summary_metrics_and_accuracy(
    client: TestClient, db_session: Session, analyst_headers: dict
):
    # Setup test nodes
    wh1 = NetworkNode(name="W1", node_type=NodeType.WAREHOUSE.value, latitude=12.1, longitude=77.1, is_active=True)
    wh2 = NetworkNode(name="W2", node_type=NodeType.WAREHOUSE.value, latitude=12.2, longitude=77.2, is_active=True)
    wh_inactive = NetworkNode(name="W3", node_type=NodeType.WAREHOUSE.value, latitude=12.3, longitude=77.3, is_active=False)

    cust1 = NetworkNode(name="C1", node_type=NodeType.CUSTOMER.value, latitude=12.4, longitude=77.4, is_active=True)
    cust2 = NetworkNode(name="C2", node_type=NodeType.CUSTOMER.value, latitude=12.5, longitude=77.5, is_active=True)
    cust3 = NetworkNode(name="C3", node_type=NodeType.CUSTOMER.value, latitude=12.6, longitude=77.6, is_active=True)

    db_session.add_all([wh1, wh2, wh_inactive, cust1, cust2, cust3])
    db_session.commit()

    # Setup test edges
    edge1 = NetworkEdge(source_node_id=wh1.id, target_node_id=cust1.id, distance_km=5.0, estimated_travel_minutes=12, is_active=True)
    edge2 = NetworkEdge(source_node_id=wh1.id, target_node_id=cust2.id, distance_km=8.0, estimated_travel_minutes=20, is_active=True)
    edge_inactive = NetworkEdge(source_node_id=wh2.id, target_node_id=cust3.id, distance_km=10.0, estimated_travel_minutes=25, is_active=False)
    db_session.add_all([edge1, edge2, edge_inactive])

    # Setup test simulations
    sim_running = Simulation(id="SIM-RUNNING-1", seed=42, status="RUNNING")
    sim_completed1 = Simulation(id="SIM-COMPLETED-1", seed=43, status="COMPLETED")
    sim_completed2 = Simulation(id="SIM-COMPLETED-2", seed=44, status="COMPLETED")
    sim_stopped = Simulation(id="SIM-STOPPED-1", seed=45, status="STOPPED")
    db_session.add_all([sim_running, sim_completed1, sim_completed2, sim_stopped])
    db_session.commit()

    # Call dashboard endpoint
    response = client.get("/api/v1/dashboard/summary", headers=analyst_headers)
    assert response.status_code == 200
    data = response.json()

    # 1. Network KPIs (only active counted)
    assert data["network"]["total_warehouses"] == 2
    assert data["network"]["total_customers"] == 3
    assert data["network"]["total_network_connections"] == 2

    # 2. Simulation KPIs
    assert data["simulations"]["active_simulations"] == 1
    assert data["simulations"]["completed_simulations"] == 2

    # 3. Operational KPIs: Ensure NOT fabricated (must be 0 or null)
    ops = data["operations"]
    assert ops["total_vehicles"] == 0
    assert ops["active_vehicles"] == 0
    assert ops["total_orders"] == 0
    assert ops["pending_orders"] == 0
    assert ops["in_transit_orders"] == 0
    assert ops["delivered_orders"] == 0
    assert ops["delayed_orders"] == 0

    # 4. Performance KPIs: None / null
    perf = data["performance"]
    assert perf["on_time_delivery_rate"] is None
    assert perf["fleet_utilization"] is None
    assert perf["average_delivery_time_minutes"] is None

    # 5. Metadata
    assert data["data_source"] == "SIMULATED"
    assert "generated_at" in data
    assert "notes" in data


def test_dashboard_role_authorization(client: TestClient, db_session: Session):
    # Fleet Manager user
    fleet_user = User(
        username="fleet_mgr_dash",
        email="fleet_dash@logipulse.io",
        full_name="Fleet Mgr",
        role=UserRole.FLEET_MANAGER.value,
        hashed_password="hash",
        is_active=True,
    )
    # Operations Manager user
    ops_user = User(
        username="ops_mgr_dash",
        email="ops_dash@logipulse.io",
        full_name="Ops Mgr",
        role=UserRole.OPERATIONS_MANAGER.value,
        hashed_password="hash",
        is_active=True,
    )
    db_session.add_all([fleet_user, ops_user])
    db_session.commit()

    fleet_token = create_access_token(fleet_user.id, fleet_user.username, fleet_user.role)
    ops_token = create_access_token(ops_user.id, ops_user.username, ops_user.role)

    # Operations Manager is permitted (200)
    res_ops = client.get(
        "/api/v1/dashboard/summary",
        headers={"Authorization": f"Bearer {ops_token}"},
    )
    assert res_ops.status_code == 200

    # Fleet Manager is forbidden at Stage 3 (403)
    res_fleet = client.get(
        "/api/v1/dashboard/summary",
        headers={"Authorization": f"Bearer {fleet_token}"},
    )
    assert res_fleet.status_code == 403
    assert res_fleet.json()["error"]["code"] == "FORBIDDEN"

