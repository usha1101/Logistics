import pytest
from datetime import datetime, timezone
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models.agent import AgentRun, AgentRunStatus
from app.models.disruption import Disruption, DisruptionSeverity, DisruptionStatus, DisruptionType
from app.models.network import NetworkNode, NodeType
from app.models.vehicle import Vehicle, VehicleStatus, VehicleType
from app.models.warehouse import Warehouse


@pytest.fixture
def agent_test_disruption(db_session: Session):
    node = NetworkNode(name="Agent Node Hub", node_type=NodeType.WAREHOUSE.value, latitude=12.97, longitude=77.59)
    db_session.add(node)
    db_session.flush()

    wh = Warehouse(warehouse_code="WH-AGT-01", network_node_id=node.id, total_capacity=5000.0)
    v = Vehicle(
        vehicle_code="VEH-AGT-01",
        registration_number="KA-01-AG-1001",
        vehicle_type=VehicleType.MEDIUM_TRUCK.value,
        status=VehicleStatus.AVAILABLE.value,
        capacity_kg=2000.0,
        current_load_kg=0.0,
        home_warehouse_id=wh.id,
    )
    db_session.add_all([wh, v])
    db_session.flush()

    disr = Disruption(
        disruption_code="DISR-AGT-TEST-001",
        disruption_type=DisruptionType.TRAFFIC_CONGESTION.value,
        title="Agent Traffic Disruption",
        severity=DisruptionSeverity.HIGH.value,
        status=DisruptionStatus.ACTIVE.value,
        affected_warehouse_id=wh.id,
    )
    db_session.add(disr)
    db_session.commit()
    db_session.refresh(disr)
    return disr


# ============================================================================
# Integration Tests: AI Status & Configuration Endpoints (3 tests)
# ============================================================================

def test_get_ai_status(client: TestClient, analyst_headers):
    res = client.get("/api/v1/agents/status", headers=analyst_headers)
    assert res.status_code == 200
    data = res.json()
    assert "gemini_configured" in data
    assert "groq_configured" in data
    assert "primary_provider" in data
    assert "api_key" not in str(data) # Security: secrets never exposed


def test_ai_status_unauthorized(client: TestClient):
    res = client.get("/api/v1/agents/status")
    assert res.status_code == 401


def test_analyze_disruption_analyst_forbidden(client: TestClient, agent_test_disruption, analyst_headers):
    # Analyst cannot initiate multi-agent analysis
    res = client.post(f"/api/v1/agents/analyze/{agent_test_disruption.id}", headers=analyst_headers)
    assert res.status_code == 403


# ============================================================================
# Integration Tests: Full Analysis Workflow (8 tests)
# ============================================================================

def test_analyze_disruption_success(client: TestClient, agent_test_disruption, ops_headers):
    res = client.post(f"/api/v1/agents/analyze/{agent_test_disruption.id}", headers=ops_headers)
    assert res.status_code == 201
    data = res.json()
    assert data["disruption_id"] == agent_test_disruption.id
    assert data["status"] == "COMPLETED"
    assert len(data["executions"]) >= 5
    assert len(data["recommendations"]) >= 1


def test_analyze_nonexistent_disruption_404(client: TestClient, ops_headers):
    res = client.post("/api/v1/agents/analyze/00000000-0000-0000-0000-000000000000", headers=ops_headers)
    assert res.status_code == 404


def test_get_agent_runs_list(client: TestClient, agent_test_disruption, ops_headers, analyst_headers):
    # Trigger run first
    client.post(f"/api/v1/agents/analyze/{agent_test_disruption.id}", headers=ops_headers)

    res = client.get("/api/v1/agents/runs", headers=analyst_headers)
    assert res.status_code == 200
    data = res.json()
    assert data["total"] >= 1
    assert "items" in data


def test_get_agent_run_detail(client: TestClient, agent_test_disruption, ops_headers, analyst_headers):
    post_res = client.post(f"/api/v1/agents/analyze/{agent_test_disruption.id}", headers=ops_headers)
    run_id = post_res.json()["id"]

    res = client.get(f"/api/v1/agents/runs/{run_id}", headers=analyst_headers)
    assert res.status_code == 200
    data = res.json()
    assert data["id"] == run_id
    assert len(data["executions"]) >= 5


def test_get_agent_run_executions(client: TestClient, agent_test_disruption, ops_headers, analyst_headers):
    post_res = client.post(f"/api/v1/agents/analyze/{agent_test_disruption.id}", headers=ops_headers)
    run_id = post_res.json()["id"]

    res = client.get(f"/api/v1/agents/runs/{run_id}/executions", headers=analyst_headers)
    assert res.status_code == 200
    execs = res.json()
    assert len(execs) >= 5
    agent_names = [e["agent_name"] for e in execs]
    assert "DISRUPTION_ANALYSIS" in agent_names
    assert "FLEET_INTELLIGENCE" in agent_names
    assert "ROUTING_INTELLIGENCE" in agent_names
    assert "WAREHOUSE_INTELLIGENCE" in agent_names
    assert "ORDER_PRIORITY" in agent_names


def test_get_agent_run_recommendations(client: TestClient, agent_test_disruption, ops_headers, analyst_headers):
    post_res = client.post(f"/api/v1/agents/analyze/{agent_test_disruption.id}", headers=ops_headers)
    run_id = post_res.json()["id"]

    res = client.get(f"/api/v1/agents/runs/{run_id}/recommendations", headers=analyst_headers)
    assert res.status_code == 200
    recs = res.json()
    assert len(recs) >= 1
    for r in recs:
        assert r["execution_status"] == "RECOMMENDED_ONLY" # Stage 10 rule: NEVER automatically executed


def test_retry_agent_run(client: TestClient, agent_test_disruption, ops_headers):
    post_res = client.post(f"/api/v1/agents/analyze/{agent_test_disruption.id}", headers=ops_headers)
    run_id = post_res.json()["id"]

    retry_res = client.post(f"/api/v1/agents/runs/{run_id}/retry", headers=ops_headers)
    assert retry_res.status_code == 200
    retry_data = retry_res.json()
    assert retry_data["status"] == "COMPLETED"
    assert retry_data["id"] != run_id # Creates a new traceable run


def test_get_unknown_agent_run_404(client: TestClient, analyst_headers):
    res = client.get("/api/v1/agents/runs/00000000-0000-0000-0000-000000000000", headers=analyst_headers)
    assert res.status_code == 404

