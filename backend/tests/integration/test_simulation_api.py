import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models.network import NetworkEdge, NetworkNode, NodeType
from app.models.simulation import SimulationStatus, SimulationVehicleStatus
from app.models.vehicle import Vehicle, VehicleStatus, VehicleType
from app.services.simulation.manager import simulation_manager


@pytest.fixture
def sim_setup(db_session: Session):
    # 1. Network Nodes
    n1 = NetworkNode(
        id="node-sim-wh1",
        name="Whitefield Hub",
        node_type=NodeType.WAREHOUSE.value,
        latitude=12.9698,
        longitude=77.7499,
        region="East Bengaluru",
        address="Whitefield EPIP",
        is_active=True,
    )
    n2 = NetworkNode(
        id="node-sim-cust1",
        name="Marathahalli Outpost",
        node_type=NodeType.CUSTOMER.value,
        latitude=12.9591,
        longitude=77.6974,
        region="East Bengaluru",
        address="Outer Ring Road",
        is_active=True,
    )
    # 2. Network Edge
    e1 = NetworkEdge(
        id="edge-sim-wh1-cust1",
        source_node_id=n1.id,
        target_node_id=n2.id,
        distance_km=8.5,
        estimated_travel_minutes=22,
        road_type="ARTERIAL",
        is_active=True,
    )

    # 3. Vehicles
    v_active = Vehicle(
        id="veh-sim-active-01",
        vehicle_code="VEH-SIM-001",
        registration_number="KA-01-SM-1001",
        vehicle_type=VehicleType.DELIVERY_VAN.value,
        capacity_kg=1500.0,
        current_load_kg=0.0,
        status=VehicleStatus.AVAILABLE.value,
        current_latitude=12.9698,
        current_longitude=77.7499,
        is_active=True,
    )
    v_maint = Vehicle(
        id="veh-sim-maint-02",
        vehicle_code="VEH-SIM-002",
        registration_number="KA-01-SM-1002",
        vehicle_type=VehicleType.HEAVY_TRUCK.value,
        capacity_kg=5000.0,
        current_load_kg=0.0,
        status=VehicleStatus.MAINTENANCE.value,
        is_active=True,
    )

    db_session.add_all([n1, n2, e1, v_active, v_maint])
    db_session.commit()

    return {
        "n1_id": n1.id,
        "n2_id": n2.id,
        "v_active_id": v_active.id,
        "v_maint_id": v_maint.id,
    }


def test_create_and_list_simulations(client: TestClient, sim_setup, ops_headers):
    # 1. Create Simulation
    payload = {
        "name": "Morning Peak Dispatch Simulation",
        "seed": 101,
        "simulation_speed_multiplier": 2.0,
        "configuration": {"weather": "clear", "traffic_factor": 1.1},
    }
    create_res = client.post("/api/v1/simulations", json=payload, headers=ops_headers)
    assert create_res.status_code == 201
    sim_data = create_res.json()
    assert sim_data["name"] == "Morning Peak Dispatch Simulation"
    assert sim_data["status"] == "CREATED"
    assert sim_data["simulation_speed_multiplier"] == 2.0
    sim_id = sim_data["id"]

    # 2. List Simulations
    list_res = client.get("/api/v1/simulations", headers=ops_headers)
    assert list_res.status_code == 200
    list_data = list_res.json()
    assert list_data["total"] >= 1
    assert any(s["id"] == sim_id for s in list_data["items"])

    # 3. Get Single Simulation
    get_res = client.get(f"/api/v1/simulations/{sim_id}", headers=ops_headers)
    assert get_res.status_code == 200
    assert get_res.json()["id"] == sim_id


def test_add_vehicle_to_simulation(client: TestClient, sim_setup, ops_headers):
    # Create simulation
    sim_res = client.post(
        "/api/v1/simulations",
        json={"name": "Vehicle Routing Sim", "simulation_speed_multiplier": 1.0},
        headers=ops_headers,
    )
    sim_id = sim_res.json()["id"]

    # Add valid vehicle
    veh_payload = {
        "vehicle_id": sim_setup["v_active_id"],
        "origin_node_id": sim_setup["n1_id"],
        "destination_node_id": sim_setup["n2_id"],
    }
    add_res = client.post(f"/api/v1/simulations/{sim_id}/vehicles", json=veh_payload, headers=ops_headers)
    assert add_res.status_code == 201
    veh_state = add_res.json()
    assert veh_state["status"] == "QUEUED"
    assert veh_state["vehicle_id"] == sim_setup["v_active_id"]
    assert veh_state["route_node_ids"] == [sim_setup["n1_id"], sim_setup["n2_id"]]
    assert veh_state["progress_percentage"] == 0.0

    # Duplicate vehicle assignment rejected
    dup_res = client.post(f"/api/v1/simulations/{sim_id}/vehicles", json=veh_payload, headers=ops_headers)
    assert dup_res.status_code == 400
    assert "already assigned" in dup_res.json()["error"]["message"].lower()

    # Unavailable vehicle rejected
    bad_veh_payload = {
        "vehicle_id": sim_setup["v_maint_id"],
        "origin_node_id": sim_setup["n1_id"],
        "destination_node_id": sim_setup["n2_id"],
    }
    maint_res = client.post(f"/api/v1/simulations/{sim_id}/vehicles", json=bad_veh_payload, headers=ops_headers)
    assert maint_res.status_code == 400
    assert "unavailable" in maint_res.json()["error"]["message"].lower()

    # List vehicles
    list_v = client.get(f"/api/v1/simulations/{sim_id}/vehicles", headers=ops_headers)
    assert list_v.status_code == 200
    assert len(list_v.json()) == 1

    # Get single vehicle
    get_v = client.get(f"/api/v1/simulations/{sim_id}/vehicles/{sim_setup['v_active_id']}", headers=ops_headers)
    assert get_v.status_code == 200
    assert get_v.json()["vehicle_id"] == sim_setup["v_active_id"]


def test_simulation_lifecycle_api_transitions(client: TestClient, sim_setup, ops_headers):
    # 1. Create
    sim_res = client.post("/api/v1/simulations", json={"name": "Lifecycle API Sim"}, headers=ops_headers)
    sim_id = sim_res.json()["id"]

    # Cannot pause when CREATED
    assert client.post(f"/api/v1/simulations/{sim_id}/pause", headers=ops_headers).status_code == 400

    # 2. Start -> RUNNING
    start_res = client.post(f"/api/v1/simulations/{sim_id}/start", headers=ops_headers)
    assert start_res.status_code == 200
    assert start_res.json()["status"] == "RUNNING"

    # 3. Update speed
    speed_res = client.patch(
        f"/api/v1/simulations/{sim_id}/speed", json={"speed_multiplier": 5.0}, headers=ops_headers
    )
    assert speed_res.status_code == 200
    assert speed_res.json()["simulation_speed_multiplier"] == 5.0

    # 4. Pause -> PAUSED
    pause_res = client.post(f"/api/v1/simulations/{sim_id}/pause", headers=ops_headers)
    assert pause_res.status_code == 200
    assert pause_res.json()["status"] == "PAUSED"

    # 5. Resume -> RUNNING
    resume_res = client.post(f"/api/v1/simulations/{sim_id}/resume", headers=ops_headers)
    assert resume_res.status_code == 200
    assert resume_res.json()["status"] == "RUNNING"

    # 6. Stop -> STOPPED
    stop_res = client.post(f"/api/v1/simulations/{sim_id}/stop", headers=ops_headers)
    assert stop_res.status_code == 200
    assert stop_res.json()["status"] == "STOPPED"

    # 7. Reset -> CREATED
    reset_res = client.post(f"/api/v1/simulations/{sim_id}/reset", headers=ops_headers)
    assert reset_res.status_code == 200
    assert reset_res.json()["status"] == "CREATED"


def test_simulation_step_advances_telemetry_and_events(client: TestClient, sim_setup, ops_headers, db_session):
    # 1. Create and add vehicle
    sim_res = client.post("/api/v1/simulations", json={"name": "Movement Sim"}, headers=ops_headers)
    sim_id = sim_res.json()["id"]
    client.post(
        f"/api/v1/simulations/{sim_id}/vehicles",
        json={
            "vehicle_id": sim_setup["v_active_id"],
            "origin_node_id": sim_setup["n1_id"],
            "destination_node_id": sim_setup["n2_id"],
        },
        headers=ops_headers,
    )

    # 2. Start simulation
    client.post(f"/api/v1/simulations/{sim_id}/start", headers=ops_headers)

    # 3. Step simulation synchronously
    simulation_manager.step_simulation(sim_id, db=db_session, wall_seconds=60.0)

    # 4. Query telemetry
    telem_res = client.get(f"/api/v1/simulations/{sim_id}/telemetry", headers=ops_headers)
    assert telem_res.status_code == 200
    telem_data = telem_res.json()
    assert telem_data["total"] >= 1
    assert telem_data["items"][0]["source"] == "SIMULATION"

    # 5. Query events
    events_res = client.get(f"/api/v1/simulations/{sim_id}/events", headers=ops_headers)
    assert events_res.status_code == 200
    events_data = events_res.json()
    assert events_data["total"] >= 2
    event_types = [e["event_type"] for e in events_data["items"]]
    assert "SIMULATION_STARTED" in event_types
    assert "VEHICLE_DEPARTED" in event_types

    # 6. Query summary KPIs
    sum_res = client.get(f"/api/v1/simulations/{sim_id}/summary", headers=ops_headers)
    assert sum_res.status_code == 200
    summary = sum_res.json()
    assert summary["total_vehicles"] == 1
    assert summary["en_route_vehicles"] == 1
    assert summary["total_telemetry_points"] >= 1


def test_simulation_rbac_control_and_read(
    client: TestClient, sim_setup, ops_headers, analyst_headers, fleet_headers, warehouse_manager_headers
):
    # Operations manager can create
    sim_res = client.post("/api/v1/simulations", json={"name": "RBAC Sim"}, headers=ops_headers)
    assert sim_res.status_code == 201
    sim_id = sim_res.json()["id"]

    # Analyst can read
    assert client.get(f"/api/v1/simulations/{sim_id}", headers=analyst_headers).status_code == 200
    assert client.get(f"/api/v1/simulations/{sim_id}/summary", headers=fleet_headers).status_code == 200
    assert client.get(f"/api/v1/simulations/{sim_id}/events", headers=warehouse_manager_headers).status_code == 200

    # Analyst CANNOT control (start, pause, stop, speed) -> 403 Forbidden
    assert client.post(f"/api/v1/simulations/{sim_id}/start", headers=analyst_headers).status_code == 403
    assert client.post(f"/api/v1/simulations/{sim_id}/pause", headers=analyst_headers).status_code == 403
    assert client.patch(f"/api/v1/simulations/{sim_id}/speed", json={"speed_multiplier": 2.0}, headers=analyst_headers).status_code == 403


def test_simulation_unauthenticated_rejected(client: TestClient):
    assert client.get("/api/v1/simulations").status_code == 401
    assert client.post("/api/v1/simulations", json={"name": "Anon"}).status_code == 401


def test_simulation_websocket_connection(client: TestClient, sim_setup, ops_headers):
    sim_res = client.post("/api/v1/simulations", json={"name": "WS Sim"}, headers=ops_headers)
    sim_id = sim_res.json()["id"]

    with client.websocket_connect(f"/api/v1/simulations/{sim_id}/ws") as websocket:
        websocket.send_text("ping")
        response = websocket.receive_text()
        assert response == "pong"


def test_dashboard_summary_includes_simulation_counts(client: TestClient, sim_setup, ops_headers):
    # Create and start a simulation
    sim_res = client.post("/api/v1/simulations", json={"name": "Dashboard KPI Sim"}, headers=ops_headers)
    sim_id = sim_res.json()["id"]
    client.post(f"/api/v1/simulations/{sim_id}/start", headers=ops_headers)

    dash_res = client.get("/api/v1/dashboard/summary", headers=ops_headers)
    assert dash_res.status_code == 200
    dash_data = dash_res.json()
    assert dash_data["simulations"]["active_simulations"] >= 1


def test_simulation_404_not_found_endpoints(client: TestClient, ops_headers):
    fake_id = "non-existent-sim-uuid"
    assert client.get(f"/api/v1/simulations/{fake_id}", headers=ops_headers).status_code == 404
    assert client.post(f"/api/v1/simulations/{fake_id}/start", headers=ops_headers).status_code == 404
    assert client.post(f"/api/v1/simulations/{fake_id}/pause", headers=ops_headers).status_code == 404
    assert client.post(f"/api/v1/simulations/{fake_id}/resume", headers=ops_headers).status_code == 404
    assert client.post(f"/api/v1/simulations/{fake_id}/stop", headers=ops_headers).status_code == 404
    assert client.post(f"/api/v1/simulations/{fake_id}/reset", headers=ops_headers).status_code == 404
    assert client.get(f"/api/v1/simulations/{fake_id}/summary", headers=ops_headers).status_code == 404
    assert client.get(f"/api/v1/simulations/{fake_id}/vehicles", headers=ops_headers).status_code == 404
    assert client.get(f"/api/v1/simulations/{fake_id}/events", headers=ops_headers).status_code == 404
    assert client.get(f"/api/v1/simulations/{fake_id}/telemetry", headers=ops_headers).status_code == 404


def test_simulation_invalid_speed_rejected(client: TestClient, sim_setup, ops_headers):
    sim_res = client.post("/api/v1/simulations", json={"name": "Speed Validation Sim"}, headers=ops_headers)
    sim_id = sim_res.json()["id"]

    # Negative or 0 speed multiplier
    assert client.patch(f"/api/v1/simulations/{sim_id}/speed", json={"speed_multiplier": -1.0}, headers=ops_headers).status_code == 422
    assert client.patch(f"/api/v1/simulations/{sim_id}/speed", json={"speed_multiplier": 0.0}, headers=ops_headers).status_code == 422
    # Excessively high multiplier (> 100)
    assert client.patch(f"/api/v1/simulations/{sim_id}/speed", json={"speed_multiplier": 500.0}, headers=ops_headers).status_code == 422


def test_simulation_auto_completion_on_arrival(client: TestClient, sim_setup, ops_headers, db_session):
    # 1. Create sim with vehicle
    sim_res = client.post("/api/v1/simulations", json={"name": "Completion Sim", "simulation_speed_multiplier": 10.0}, headers=ops_headers)
    sim_id = sim_res.json()["id"]
    client.post(
        f"/api/v1/simulations/{sim_id}/vehicles",
        json={
            "vehicle_id": sim_setup["v_active_id"],
            "origin_node_id": sim_setup["n1_id"],
            "destination_node_id": sim_setup["n2_id"],
        },
        headers=ops_headers,
    )

    # 2. Start simulation
    client.post(f"/api/v1/simulations/{sim_id}/start", headers=ops_headers)

    # 3. Step enough distance to complete route (8.5 km at 450 km/h effective speed -> needs ~70 seconds)
    simulation_manager.step_simulation(sim_id, db=db_session, wall_seconds=80.0)

    # 4. Verify simulation status transitions to COMPLETED
    get_sim = client.get(f"/api/v1/simulations/{sim_id}", headers=ops_headers)
    assert get_sim.status_code == 200
    assert get_sim.json()["status"] == "COMPLETED"

    # 5. Verify vehicle state is ARRIVED
    veh_res = client.get(f"/api/v1/simulations/{sim_id}/vehicles/{sim_setup['v_active_id']}", headers=ops_headers)
    assert veh_res.status_code == 200
    assert veh_res.json()["status"] == "ARRIVED"
    assert veh_res.json()["progress_percentage"] == 100.0
    assert veh_res.json()["actual_arrival_time"] is not None

