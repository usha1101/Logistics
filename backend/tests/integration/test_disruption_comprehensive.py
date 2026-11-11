import pytest
from datetime import datetime, timezone
from fastapi.testclient import TestClient

from app.models.disruption import (
    AffectedResourceType,
    DisruptionSeverity,
    DisruptionStatus,
    DisruptionType,
)
from app.models.network import NetworkNode, NodeType
from app.models.order import Customer, Order, OrderPriority, OrderStatus
from app.models.simulation import Simulation, SimulationStatus, SimulationVehicleState, SimulationVehicleStatus
from app.models.vehicle import Vehicle, VehicleStatus, VehicleType
from app.models.warehouse import Warehouse
from app.schemas.disruption import DisruptionCreate
from app.services.disruptions.engine import DisruptionEngine
from app.services.disruptions.exceptions import (
    DisruptionNotFoundError,
    InvalidDisruptionTransitionError,
    TargetResourceValidationError,
)
from app.services.disruptions.severity import calculate_severity


# ============================================================================
# Unit Tests: Deterministic Severity Calculator (10 tests)
# ============================================================================

def test_severity_breakdown_high_load():
    res = calculate_severity(DisruptionType.VEHICLE_BREAKDOWN, {"current_load_kg": 750.0})
    assert res == DisruptionSeverity.HIGH

def test_severity_breakdown_critical_urgent():
    res = calculate_severity(DisruptionType.VEHICLE_BREAKDOWN, {"current_load_kg": 100.0, "has_urgent_orders": True})
    assert res == DisruptionSeverity.CRITICAL

def test_severity_breakdown_idle_empty():
    res = calculate_severity(DisruptionType.VEHICLE_BREAKDOWN, {"current_load_kg": 0.0, "is_idle": True})
    assert res == DisruptionSeverity.LOW

def test_severity_breakdown_default_medium():
    res = calculate_severity(DisruptionType.VEHICLE_BREAKDOWN, {"current_load_kg": 250.0, "is_idle": False})
    assert res == DisruptionSeverity.MEDIUM

def test_severity_traffic_critical_speed():
    res = calculate_severity(DisruptionType.TRAFFIC_CONGESTION, {"speed_reduction_pct": 75.0})
    assert res == DisruptionSeverity.CRITICAL

def test_severity_traffic_high_delay():
    res = calculate_severity(DisruptionType.TRAFFIC_CONGESTION, {"delay_minutes": 35.0})
    assert res == DisruptionSeverity.HIGH

def test_severity_traffic_low():
    res = calculate_severity(DisruptionType.TRAFFIC_CONGESTION, {"speed_reduction_pct": 5.0, "delay_minutes": 5.0})
    assert res == DisruptionSeverity.LOW

def test_severity_warehouse_critical_utilization():
    res = calculate_severity(DisruptionType.WAREHOUSE_SHUTDOWN, {"capacity_utilization_pct": 92.0})
    assert res == DisruptionSeverity.CRITICAL

def test_severity_warehouse_medium_active():
    res = calculate_severity(DisruptionType.WAREHOUSE_SHUTDOWN, {"capacity_utilization_pct": 10.0, "active_orders": 3})
    assert res == DisruptionSeverity.MEDIUM

def test_severity_demand_surge_high():
    res = calculate_severity(DisruptionType.DEMAND_SURGE, {"surge_multiplier": 2.1, "extra_orders": 26})
    assert res == DisruptionSeverity.HIGH


# ============================================================================
# Unit Tests: State Machine & Transition Rules (6 tests)
# ============================================================================

def test_engine_cannot_activate_from_active(db_session):
    engine = DisruptionEngine(db_session)
    p = DisruptionCreate(disruption_type=DisruptionType.DEMAND_SURGE, title="Surge Test")
    d = engine.create_disruption(p)
    engine.activate_disruption(d.id)
    with pytest.raises(InvalidDisruptionTransitionError):
        engine.activate_disruption(d.id)

def test_engine_cannot_monitor_from_detected(db_session):
    engine = DisruptionEngine(db_session)
    p = DisruptionCreate(disruption_type=DisruptionType.DEMAND_SURGE, title="Surge Test")
    d = engine.create_disruption(p)
    with pytest.raises(InvalidDisruptionTransitionError):
        engine.set_monitoring(d.id)

def test_engine_cannot_resolve_from_detected(db_session):
    engine = DisruptionEngine(db_session)
    p = DisruptionCreate(disruption_type=DisruptionType.DEMAND_SURGE, title="Surge Test")
    d = engine.create_disruption(p)
    with pytest.raises(InvalidDisruptionTransitionError):
        engine.resolve_disruption(d.id)

def test_engine_cannot_update_terminal_cancelled(db_session):
    engine = DisruptionEngine(db_session)
    p = DisruptionCreate(disruption_type=DisruptionType.DEMAND_SURGE, title="Surge Test")
    d = engine.create_disruption(p)
    engine.cancel_disruption(d.id)
    from app.schemas.disruption import DisruptionUpdate
    with pytest.raises(InvalidDisruptionTransitionError):
        engine.update_disruption(d.id, DisruptionUpdate(title="New Title"))

def test_engine_disruption_not_found_raises(db_session):
    engine = DisruptionEngine(db_session)
    with pytest.raises(DisruptionNotFoundError):
        engine.activate_disruption("unknown-uuid")

def test_engine_validate_nonexistent_warehouse(db_session):
    engine = DisruptionEngine(db_session)
    p = DisruptionCreate(disruption_type=DisruptionType.WAREHOUSE_SHUTDOWN, title="Bad WH", affected_warehouse_id="non-existent")
    with pytest.raises(TargetResourceValidationError):
        engine.create_disruption(p)


# ============================================================================
# Integration Tests: Disruption API Endpoints & RBAC (12 tests)
# ============================================================================

def test_api_create_422_on_invalid_coords(client: TestClient, ops_headers):
    payload = {
        "disruption_type": "TRAFFIC_CONGESTION",
        "title": "Bad Coords",
        "location_latitude": 95.0, # invalid > 90
    }
    res = client.post("/api/v1/disruptions", json=payload, headers=ops_headers)
    assert res.status_code == 422

def test_api_create_422_on_missing_target_fk(client: TestClient, ops_headers):
    payload = {
        "disruption_type": "VEHICLE_BREAKDOWN",
        "title": "Bad Vehicle ID",
        "affected_vehicle_id": "00000000-0000-0000-0000-000000000000",
    }
    res = client.post("/api/v1/disruptions", json=payload, headers=ops_headers)
    assert res.status_code == 422

def test_api_get_404_for_unknown_disruption(client: TestClient, analyst_headers):
    res = client.get("/api/v1/disruptions/00000000-0000-0000-0000-000000000000", headers=analyst_headers)
    assert res.status_code == 404

def test_api_impact_404_for_unknown_disruption(client: TestClient, analyst_headers):
    res = client.get("/api/v1/disruptions/00000000-0000-0000-0000-000000000000/impact", headers=analyst_headers)
    assert res.status_code == 404

def test_api_events_404_for_unknown_disruption(client: TestClient, analyst_headers):
    res = client.get("/api/v1/disruptions/00000000-0000-0000-0000-000000000000/events", headers=analyst_headers)
    assert res.status_code == 404

def test_api_analyst_cannot_activate(client: TestClient, ops_headers, analyst_headers):
    res = client.post("/api/v1/disruptions", json={"disruption_type": "DEMAND_SURGE", "title": "Surge"}, headers=ops_headers)
    d_id = res.json()["id"]
    res_act = client.post(f"/api/v1/disruptions/{d_id}/activate", headers=analyst_headers)
    assert res_act.status_code == 403

def test_api_analyst_cannot_resolve(client: TestClient, ops_headers, analyst_headers):
    res = client.post("/api/v1/disruptions", json={"disruption_type": "DEMAND_SURGE", "title": "Surge"}, headers=ops_headers)
    d_id = res.json()["id"]
    client.post(f"/api/v1/disruptions/{d_id}/activate", headers=ops_headers)
    res_res = client.post(f"/api/v1/disruptions/{d_id}/resolve", headers=analyst_headers)
    assert res_res.status_code == 403

def test_api_analyst_cannot_cancel(client: TestClient, ops_headers, analyst_headers):
    res = client.post("/api/v1/disruptions", json={"disruption_type": "DEMAND_SURGE", "title": "Surge"}, headers=ops_headers)
    d_id = res.json()["id"]
    res_can = client.post(f"/api/v1/disruptions/{d_id}/cancel", headers=analyst_headers)
    assert res_can.status_code == 403

def test_api_analyst_cannot_patch(client: TestClient, ops_headers, analyst_headers):
    res = client.post("/api/v1/disruptions", json={"disruption_type": "DEMAND_SURGE", "title": "Surge"}, headers=ops_headers)
    d_id = res.json()["id"]
    res_patch = client.patch(f"/api/v1/disruptions/{d_id}", json={"title": "Hacked"}, headers=analyst_headers)
    assert res_patch.status_code == 403

def test_api_pagination_page_size(client: TestClient, analyst_headers):
    res = client.get("/api/v1/disruptions?page=1&page_size=2", headers=analyst_headers)
    assert res.status_code == 200
    data = res.json()
    assert data["page"] == 1
    assert data["page_size"] == 2
    assert len(data["items"]) <= 2

def test_api_active_disruptions_filtering(client: TestClient, ops_headers, analyst_headers):
    res = client.get("/api/v1/disruptions/active", headers=analyst_headers)
    assert res.status_code == 200
    for item in res.json()["items"]:
        assert item["status"] in ["ACTIVE", "MONITORING"]

def test_api_simulation_filter_disruptions(client: TestClient, ops_headers, analyst_headers):
    res = client.get("/api/v1/disruptions?simulation_id=non-existent-sim", headers=analyst_headers)
    assert res.status_code == 200
    assert res.json()["total"] == 0

