from datetime import datetime, timedelta, timezone
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models.disruption import (
    Disruption,
    DisruptionSeverity,
    DisruptionStatus,
    DisruptionType,
)
from app.models.network import NetworkEdge, NetworkNode, NodeType
from app.models.order import Customer, Order, OrderPriority, OrderStatus
from app.models.recovery import (
    OptimizationStrategy,
    RecoveryAction,
    RecoveryActionStatus,
    RecoveryAssignment,
    RecoveryAuditLog,
    RecoveryComparison,
    RecoveryPlan,
    RecoveryPlanStatus,
)
from app.models.simulation import Simulation, SimulationStatus
from app.models.user import User, UserRole
from app.models.vehicle import Vehicle, VehicleStatus, VehicleType
from app.models.warehouse import Warehouse, WarehouseStatus, WarehouseType


@pytest.fixture
def recovery_env(db_session: Session):
    node1 = NetworkNode(
        name="Recovery Hub North",
        node_type=NodeType.WAREHOUSE.value,
        latitude=12.9716,
        longitude=77.5946,
        region="North",
        address="Hub Road North",
        is_active=True,
    )
    node2 = NetworkNode(
        name="Recovery Node South",
        node_type=NodeType.CUSTOMER.value,
        latitude=12.9352,
        longitude=77.6245,
        region="South",
        address="Customer Road South",
        is_active=True,
    )
    node3 = NetworkNode(
        name="Recovery Node East",
        node_type=NodeType.CUSTOMER.value,
        latitude=12.9784,
        longitude=77.6408,
        region="East",
        address="Customer Road East",
        is_active=True,
    )
    db_session.add_all([node1, node2, node3])
    db_session.commit()

    edge1 = NetworkEdge(
        source_node_id=node1.id,
        target_node_id=node2.id,
        distance_km=10.0,
        estimated_travel_minutes=20,
        is_active=True,
    )
    edge2 = NetworkEdge(
        source_node_id=node2.id,
        target_node_id=node3.id,
        distance_km=8.0,
        estimated_travel_minutes=15,
        is_active=True,
    )
    edge3 = NetworkEdge(
        source_node_id=node1.id,
        target_node_id=node3.id,
        distance_km=14.0,
        estimated_travel_minutes=25,
        is_active=True,
    )
    db_session.add_all([edge1, edge2, edge3])
    db_session.commit()

    wh = Warehouse(
        network_node_id=node1.id,
        warehouse_code="WH-REC-NORTH",
        warehouse_type=WarehouseType.DISTRIBUTION_CENTER.value,
        total_capacity=20000.0,
        used_capacity=1000.0,
        status=WarehouseStatus.OPERATIONAL.value,
    )
    db_session.add(wh)
    db_session.commit()

    cust = Customer(
        customer_code="CUST-REC-01",
        name="Recovery Test Corp",
        phone="+91-80-88776655",
        address_line="South Tech Zone",
        city="Bengaluru",
        state="Karnataka",
        postal_code="560034",
        latitude=12.9352,
        longitude=77.6245,
        is_active=True,
    )
    db_session.add(cust)
    db_session.commit()

    v1 = Vehicle(
        vehicle_code="KA-REC-01",
        registration_number="KA-01-REC-001",
        vehicle_type=VehicleType.DELIVERY_VAN.value,
        status=VehicleStatus.BREAKDOWN.value,
        capacity_kg=1000.0,
        current_load_kg=300.0,
        is_active=True,
    )
    v2 = Vehicle(
        vehicle_code="KA-REC-02",
        registration_number="KA-01-REC-002",
        vehicle_type=VehicleType.DELIVERY_VAN.value,
        status=VehicleStatus.AVAILABLE.value,
        capacity_kg=1500.0,
        current_load_kg=0.0,
        is_active=True,
    )
    db_session.add_all([v1, v2])
    db_session.commit()

    disr = Disruption(
        disruption_code="DIS-REC-001",
        disruption_type=DisruptionType.VEHICLE_BREAKDOWN.value,
        severity=DisruptionSeverity.CRITICAL.value,
        status=DisruptionStatus.ACTIVE.value,
        title="Van Breakdown along Route",
        affected_vehicle_id=v1.id,
    )
    db_session.add(disr)
    db_session.commit()

    now = datetime.now(timezone.utc)
    ord1 = Order(
        order_number="ORD-REC-001",
        customer_id=cust.id,
        warehouse_id=wh.id,
        status=OrderStatus.IN_TRANSIT.value,
        priority=OrderPriority.HIGH.value,
        expected_delivery_at=now + timedelta(hours=4),
        delivery_address="South Tech Zone",
        delivery_latitude=12.9352,
        delivery_longitude=77.6245,
        total_weight_kg=150.0,
        total_amount=3500.0,
        assigned_vehicle_id=v1.id,
    )
    ord2 = Order(
        order_number="ORD-REC-002",
        customer_id=cust.id,
        warehouse_id=wh.id,
        status=OrderStatus.IN_TRANSIT.value,
        priority=OrderPriority.URGENT.value,
        expected_delivery_at=now + timedelta(hours=2),
        delivery_address="South Tech Zone",
        delivery_latitude=12.9352,
        delivery_longitude=77.6245,
        total_weight_kg=150.0,
        total_amount=4000.0,
        assigned_vehicle_id=v1.id,
    )
    db_session.add_all([ord1, ord2])
    db_session.commit()

    return {
        "node1": node1,
        "node2": node2,
        "node3": node3,
        "wh": wh,
        "cust": cust,
        "v1": v1,
        "v2": v2,
        "disr": disr,
        "ord1": ord1,
        "ord2": ord2,
    }


class TestRecoveryOrchestrationAPI:
    def test_generate_recovery_plan_success(self, client: TestClient, admin_headers, recovery_env):
        env = recovery_env
        payload = {
            "disruption_id": env["disr"].id,
            "optimization_strategy": OptimizationStrategy.PRIORITY_BASED_RECOVERY.value,
            "weights": {"distance": 0.3, "travel_time": 0.4, "delay": 0.3},
        }
        res = client.post("/api/v1/recovery/plans/generate", json=payload, headers=admin_headers)
        assert res.status_code == 201
        data = res.json()
        assert data["recovery_code"].startswith("REC-")
        assert data["status"] == RecoveryPlanStatus.PENDING_APPROVAL.value
        assert data["disruption_id"] == env["disr"].id
        assert data["optimization_strategy"] == OptimizationStrategy.PRIORITY_BASED_RECOVERY.value
        assert len(data["assignments"]) == 2
        for assign in data["assignments"]:
            assert assign["proposed_vehicle_id"] == env["v2"].id
            assert assign["previous_vehicle_id"] == env["v1"].id

    def test_generate_plan_invalid_disruption_404(self, client: TestClient, admin_headers):
        payload = {
            "disruption_id": "non-existent-disruption",
            "optimization_strategy": OptimizationStrategy.BALANCED.value if hasattr(OptimizationStrategy, "BALANCED") else "PRIORITY_BASED_RECOVERY",
        }
        res = client.post("/api/v1/recovery/plans/generate", json=payload, headers=admin_headers)
        assert res.status_code == 404

    def test_list_recovery_plans_with_pagination(self, client: TestClient, admin_headers, recovery_env):
        env = recovery_env
        payload = {
            "disruption_id": env["disr"].id,
            "optimization_strategy": OptimizationStrategy.MULTI_VEHICLE_RECOVERY.value,
        }
        client.post("/api/v1/recovery/plans/generate", json=payload, headers=admin_headers)

        res = client.get("/api/v1/recovery/plans?limit=10&page=1", headers=admin_headers)
        assert res.status_code == 200
        data = res.json()
        assert "items" in data
        assert "total" in data
        assert data["total"] >= 1
        assert len(data["items"]) >= 1

    def test_list_plans_filter_by_status(self, client: TestClient, admin_headers, recovery_env):
        res = client.get(
            f"/api/v1/recovery/plans?status={RecoveryPlanStatus.PENDING_APPROVAL.value}",
            headers=admin_headers,
        )
        assert res.status_code == 200
        data = res.json()
        for item in data["items"]:
            assert item["status"] == RecoveryPlanStatus.PENDING_APPROVAL.value

    def test_get_plan_details(self, client: TestClient, admin_headers, recovery_env):
        env = recovery_env
        gen = client.post(
            "/api/v1/recovery/plans/generate",
            json={"disruption_id": env["disr"].id},
            headers=admin_headers,
        ).json()
        plan_id = gen["id"]

        res = client.get(f"/api/v1/recovery/plans/{plan_id}", headers=admin_headers)
        assert res.status_code == 200
        data = res.json()
        assert data["id"] == plan_id
        assert data["recovery_code"] == gen["recovery_code"]

    def test_get_plan_assignments(self, client: TestClient, admin_headers, recovery_env):
        env = recovery_env
        gen = client.post(
            "/api/v1/recovery/plans/generate",
            json={"disruption_id": env["disr"].id},
            headers=admin_headers,
        ).json()
        plan_id = gen["id"]

        res = client.get(f"/api/v1/recovery/plans/{plan_id}/assignments", headers=admin_headers)
        assert res.status_code == 200
        items = res.json()
        assert len(items) == 2
        for it in items:
            assert it["recovery_plan_id"] == plan_id

    def test_get_plan_comparison_metrics(self, client: TestClient, admin_headers, recovery_env):
        env = recovery_env
        gen = client.post(
            "/api/v1/recovery/plans/generate",
            json={"disruption_id": env["disr"].id},
            headers=admin_headers,
        ).json()
        plan_id = gen["id"]

        res = client.get(f"/api/v1/recovery/plans/{plan_id}/comparison", headers=admin_headers)
        assert res.status_code == 200
        comp = res.json()
        assert isinstance(comp, list)
        assert len(comp) > 0
        assert comp[0]["recovery_plan_id"] == plan_id

    def test_validate_plan_endpoint(self, client: TestClient, admin_headers, recovery_env):
        env = recovery_env
        gen = client.post(
            "/api/v1/recovery/plans/generate",
            json={"disruption_id": env["disr"].id},
            headers=admin_headers,
        ).json()
        plan_id = gen["id"]

        res = client.post(f"/api/v1/recovery/plans/{plan_id}/validate", headers=admin_headers)
        assert res.status_code == 200
        report = res.json()
        assert report["plan_id"] == plan_id
        assert report["is_valid"] is True
        assert report["status"] == "VALIDATED"
        assert len(report["violations"]) == 0

    def test_approve_plan_success(self, client: TestClient, admin_headers, recovery_env):
        env = recovery_env
        gen = client.post(
            "/api/v1/recovery/plans/generate",
            json={"disruption_id": env["disr"].id},
            headers=admin_headers,
        ).json()
        plan_id = gen["id"]

        approve_payload = {"notes": "Approved for re-routing van 2"}
        res = client.post(f"/api/v1/recovery/plans/{plan_id}/approve", json=approve_payload, headers=admin_headers)
        assert res.status_code == 200
        data = res.json()
        assert data["status"] == RecoveryPlanStatus.APPROVED.value
        assert data["approved_by_user_id"] is not None

    def test_cannot_execute_unapproved_plan(self, client: TestClient, admin_headers, recovery_env):
        env = recovery_env
        gen = client.post(
            "/api/v1/recovery/plans/generate",
            json={"disruption_id": env["disr"].id},
            headers=admin_headers,
        ).json()
        plan_id = gen["id"]

        # Attempt to execute directly while PENDING_APPROVAL
        res = client.post(f"/api/v1/recovery/plans/{plan_id}/execute", headers=admin_headers)
        assert res.status_code == 400
        err_msg = res.json().get("error", {}).get("message", "")
        assert "APPROVED" in err_msg

    def test_reject_plan_success(self, client: TestClient, admin_headers, recovery_env):
        env = recovery_env
        gen = client.post(
            "/api/v1/recovery/plans/generate",
            json={"disruption_id": env["disr"].id},
            headers=admin_headers,
        ).json()
        plan_id = gen["id"]

        reject_payload = {"reason": "Cost too high for detour"}
        res = client.post(f"/api/v1/recovery/plans/{plan_id}/reject", json=reject_payload, headers=admin_headers)
        assert res.status_code == 200
        data = res.json()
        assert data["status"] == RecoveryPlanStatus.REJECTED.value
        assert data["rejection_reason"] == "Cost too high for detour"

    def test_cannot_approve_already_rejected_plan(self, client: TestClient, admin_headers, recovery_env):
        env = recovery_env
        gen = client.post(
            "/api/v1/recovery/plans/generate",
            json={"disruption_id": env["disr"].id},
            headers=admin_headers,
        ).json()
        plan_id = gen["id"]

        client.post(f"/api/v1/recovery/plans/{plan_id}/reject", json={"reason": "Rejected"}, headers=admin_headers)
        res = client.post(f"/api/v1/recovery/plans/{plan_id}/approve", json={"notes": "Try approve"}, headers=admin_headers)
        assert res.status_code == 400

    def test_full_execution_lifecycle_and_side_effects(
        self, client: TestClient, admin_headers, recovery_env, db_session: Session
    ):
        env = recovery_env
        gen = client.post(
            "/api/v1/recovery/plans/generate",
            json={"disruption_id": env["disr"].id},
            headers=admin_headers,
        ).json()
        plan_id = gen["id"]

        # 1. Validate
        val_res = client.post(f"/api/v1/recovery/plans/{plan_id}/validate", headers=admin_headers)
        assert val_res.status_code == 200
        assert val_res.json()["is_valid"] is True

        # 2. Approve
        appr_res = client.post(f"/api/v1/recovery/plans/{plan_id}/approve", json={"notes": "Ready"}, headers=admin_headers)
        assert appr_res.status_code == 200

        # 3. Execute
        exec_res = client.post(f"/api/v1/recovery/plans/{plan_id}/execute", headers=admin_headers)
        assert exec_res.status_code == 200
        exec_data = exec_res.json()
        assert exec_data["status"] == RecoveryPlanStatus.EXECUTED.value
        assert exec_data["executed_at"] is not None

        # Verify side effects on vehicles and orders
        db_session.refresh(env["v2"])
        assert env["v2"].current_load_kg == 300.0  # ord1 + ord2 = 150 + 150

        db_session.refresh(env["ord1"])
        assert env["ord1"].assigned_vehicle_id == env["v2"].id

        db_session.refresh(env["ord2"])
        assert env["ord2"].assigned_vehicle_id == env["v2"].id

        # 4. Check actions
        act_res = client.get(f"/api/v1/recovery/plans/{plan_id}/actions", headers=admin_headers)
        assert act_res.status_code == 200
        actions = act_res.json()
        assert len(actions) == 2
        for act in actions:
            assert act["status"] == RecoveryActionStatus.EXECUTED.value

        # 5. Check audit logs
        log_res = client.get(f"/api/v1/recovery/plans/{plan_id}/audit-logs", headers=admin_headers)
        assert log_res.status_code == 200
        logs = log_res.json()
        assert len(logs) >= 3  # GENERATED -> APPROVED -> EXECUTING/EXECUTED

    def test_cannot_re_execute_already_executed_plan(self, client: TestClient, admin_headers, recovery_env):
        env = recovery_env
        gen = client.post("/api/v1/recovery/plans/generate", json={"disruption_id": env["disr"].id}, headers=admin_headers).json()
        plan_id = gen["id"]
        client.post(f"/api/v1/recovery/plans/{plan_id}/approve", json={"notes": "Approve"}, headers=admin_headers)
        client.post(f"/api/v1/recovery/plans/{plan_id}/execute", headers=admin_headers)

        # Attempt to execute again
        res = client.post(f"/api/v1/recovery/plans/{plan_id}/execute", headers=admin_headers)
        assert res.status_code == 400
        err_msg = res.json().get("error", {}).get("message", "")
        assert "APPROVED" in err_msg

    def test_stale_plan_rejected_at_execution_when_vehicle_breaks_down(
        self, client: TestClient, admin_headers, recovery_env, db_session: Session
    ):
        env = recovery_env
        gen = client.post("/api/v1/recovery/plans/generate", json={"disruption_id": env["disr"].id}, headers=admin_headers).json()
        plan_id = gen["id"]
        client.post(f"/api/v1/recovery/plans/{plan_id}/approve", json={"notes": "Approve"}, headers=admin_headers)

        # Now vehicle 2 breaks down before execution!
        env["v2"].status = VehicleStatus.BREAKDOWN.value
        db_session.commit()

        # Execute should fail with conflict / stale validation
        res = client.post(f"/api/v1/recovery/plans/{plan_id}/execute", headers=admin_headers)
        assert res.status_code == 409
        err_msg = res.json().get("error", {}).get("message", "")
        assert "Live database state changed" in err_msg or "Violations" in err_msg

    def test_simulation_scoped_recovery_isolation(
        self, client: TestClient, admin_headers, recovery_env, db_session: Session
    ):
        env = recovery_env
        # Create simulation run
        sim = Simulation(
            id="sim-rec-iso-001",
            name="Sim Isolation Test",
            status=SimulationStatus.RUNNING.value,
            simulation_speed_multiplier=1.0,
        )
        db_session.add(sim)
        db_session.commit()

        payload = {
            "disruption_id": env["disr"].id,
            "simulation_id": sim.id,
        }
        gen = client.post("/api/v1/recovery/plans/generate", json=payload, headers=admin_headers).json()
        plan_id = gen["id"]
        assert gen["simulation_id"] == sim.id

        client.post(f"/api/v1/recovery/plans/{plan_id}/approve", json={"notes": "Approve sim plan"}, headers=admin_headers)
        res = client.post(f"/api/v1/recovery/plans/{plan_id}/execute", headers=admin_headers)
        assert res.status_code == 200

        # Verify production vehicle 2 load was NOT mutated!
        db_session.refresh(env["v2"])
        assert env["v2"].current_load_kg == 0.0  # Unchanged!

    def test_recovery_summary_kpi_endpoint(self, client: TestClient, admin_headers, recovery_env):
        res = client.get("/api/v1/recovery/summary", headers=admin_headers)
        assert res.status_code == 200
        kpi = res.json()
        assert "total_recovery_plans" in kpi
        assert "pending_approval_count" in kpi
        assert "approved_count" in kpi
        assert "executed_count" in kpi
        assert "rejected_count" in kpi
        assert "total_orders_recovered" in kpi

    def test_unauthenticated_request_rejected(self, client: TestClient):
        res = client.get("/api/v1/recovery/plans")
        assert res.status_code == 401

    def test_rbac_analyst_cannot_execute_plan(self, client: TestClient, analyst_headers, admin_headers, recovery_env):
        env = recovery_env
        gen = client.post("/api/v1/recovery/plans/generate", json={"disruption_id": env["disr"].id}, headers=admin_headers).json()
        plan_id = gen["id"]
        client.post(f"/api/v1/recovery/plans/{plan_id}/approve", json={"notes": "Approve"}, headers=admin_headers)

        # Analyst cannot execute recovery plan
        res = client.post(f"/api/v1/recovery/plans/{plan_id}/execute", headers=analyst_headers)
        assert res.status_code == 403

    def test_rbac_analyst_can_view_plans(self, client: TestClient, analyst_headers):
        res = client.get("/api/v1/recovery/plans", headers=analyst_headers)
        assert res.status_code == 200

    def test_execute_plan_404_on_missing_plan(self, client: TestClient, admin_headers):
        res = client.post("/api/v1/recovery/plans/missing-plan-id/execute", headers=admin_headers)
        assert res.status_code == 404

    def test_approve_plan_404_on_missing_plan(self, client: TestClient, admin_headers):
        res = client.post("/api/v1/recovery/plans/missing-plan-id/approve", json={}, headers=admin_headers)
        assert res.status_code == 404
