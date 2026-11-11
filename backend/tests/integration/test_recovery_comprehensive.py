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
    RecoveryPlan,
    RecoveryPlanStatus,
)
from app.models.user import UserRole
from app.models.vehicle import Vehicle, VehicleStatus, VehicleType
from app.models.warehouse import Warehouse, WarehouseStatus, WarehouseType


@pytest.fixture
def comprehensive_recovery_setup(db_session: Session):
    n1 = NetworkNode(
        name="Comp Hub Node 1",
        node_type=NodeType.WAREHOUSE.value,
        latitude=12.95,
        longitude=77.58,
        region="South",
        address="South Hub Road",
        is_active=True,
    )
    n2 = NetworkNode(
        name="Comp Customer Node 2",
        node_type=NodeType.CUSTOMER.value,
        latitude=12.96,
        longitude=77.60,
        region="South",
        address="Customer South Road",
        is_active=True,
    )
    n3 = NetworkNode(
        name="Comp Hub Node 3",
        node_type=NodeType.WAREHOUSE.value,
        latitude=12.98,
        longitude=77.62,
        region="East",
        address="East Hub Road",
        is_active=True,
    )
    db_session.add_all([n1, n2, n3])
    db_session.commit()

    edge1 = NetworkEdge(source_node_id=n1.id, target_node_id=n2.id, distance_km=5.0, estimated_travel_minutes=10, is_active=True)
    edge2 = NetworkEdge(source_node_id=n2.id, target_node_id=n3.id, distance_km=6.0, estimated_travel_minutes=12, is_active=True)
    edge3 = NetworkEdge(source_node_id=n1.id, target_node_id=n3.id, distance_km=10.0, estimated_travel_minutes=18, is_active=True)
    db_session.add_all([edge1, edge2, edge3])
    db_session.commit()

    wh = Warehouse(
        network_node_id=n1.id,
        warehouse_code="WH-COMP-01",
        warehouse_type=WarehouseType.DISTRIBUTION_CENTER.value,
        total_capacity=15000.0,
        used_capacity=500.0,
        status=WarehouseStatus.OPERATIONAL.value,
    )
    db_session.add(wh)
    db_session.commit()

    cust = Customer(
        customer_code="CUST-COMP-01",
        name="Comp Retailer",
        phone="+91-80-77665544",
        address_line="Retail Block 1",
        city="Bengaluru",
        state="Karnataka",
        postal_code="560001",
        latitude=12.96,
        longitude=77.60,
        is_active=True,
    )
    db_session.add(cust)
    db_session.commit()

    # Broken vehicle with 2 orders
    v_broken = Vehicle(
        vehicle_code="V-BROKEN",
        registration_number="KA-01-BRK-01",
        vehicle_type=VehicleType.DELIVERY_VAN.value,
        status=VehicleStatus.BREAKDOWN.value,
        capacity_kg=800.0,
        current_load_kg=350.0,
        is_active=True,
    )
    # Available replacement vehicle
    v_rep = Vehicle(
        vehicle_code="V-REPLACEMENT",
        registration_number="KA-01-REP-01",
        vehicle_type=VehicleType.DELIVERY_VAN.value,
        status=VehicleStatus.AVAILABLE.value,
        capacity_kg=1200.0,
        current_load_kg=0.0,
        is_active=True,
    )
    db_session.add_all([v_broken, v_rep])
    db_session.commit()

    disr = Disruption(
        disruption_code="DIS-COMP-001",
        disruption_type=DisruptionType.VEHICLE_BREAKDOWN.value,
        severity=DisruptionSeverity.CRITICAL.value,
        status=DisruptionStatus.ACTIVE.value,
        title="Engine Failure on Major Route",
        affected_vehicle_id=v_broken.id,
    )
    db_session.add(disr)
    db_session.commit()

    now = datetime.now(timezone.utc)
    o1 = Order(
        order_number="ORD-COMP-01",
        customer_id=cust.id,
        warehouse_id=wh.id,
        status=OrderStatus.IN_TRANSIT.value,
        priority=OrderPriority.HIGH.value,
        expected_delivery_at=now + timedelta(hours=3),
        delivery_address="Retail Block 1",
        delivery_latitude=12.96,
        delivery_longitude=77.60,
        total_weight_kg=150.0,
        total_amount=2000.0,
        assigned_vehicle_id=v_broken.id,
    )
    o2 = Order(
        order_number="ORD-COMP-02",
        customer_id=cust.id,
        warehouse_id=wh.id,
        status=OrderStatus.IN_TRANSIT.value,
        priority=OrderPriority.URGENT.value,
        expected_delivery_at=now + timedelta(hours=2),
        delivery_address="Retail Block 1",
        delivery_latitude=12.96,
        delivery_longitude=77.60,
        total_weight_kg=200.0,
        total_amount=3000.0,
        assigned_vehicle_id=v_broken.id,
    )
    db_session.add_all([o1, o2])
    db_session.commit()

    return {
        "n1": n1,
        "n2": n2,
        "n3": n3,
        "wh": wh,
        "cust": cust,
        "v_broken": v_broken,
        "v_rep": v_rep,
        "disr": disr,
        "o1": o1,
        "o2": o2,
    }


class TestRecoveryComprehensive:
    def test_generate_plan_with_single_vehicle_strategy(
        self, client: TestClient, admin_headers, comprehensive_recovery_setup
    ):
        setup = comprehensive_recovery_setup
        res = client.post(
            "/api/v1/recovery/plans/generate",
            json={
                "disruption_id": setup["disr"].id,
                "optimization_strategy": OptimizationStrategy.SINGLE_VEHICLE_RECOVERY.value,
            },
            headers=admin_headers,
        )
        assert res.status_code == 201
        data = res.json()
        assert data["optimization_strategy"] == OptimizationStrategy.SINGLE_VEHICLE_RECOVERY.value
        assert len(data["assignments"]) == 2

    def test_generate_plan_with_alternative_route_strategy(
        self, client: TestClient, admin_headers, comprehensive_recovery_setup
    ):
        setup = comprehensive_recovery_setup
        res = client.post(
            "/api/v1/recovery/plans/generate",
            json={
                "disruption_id": setup["disr"].id,
                "optimization_strategy": OptimizationStrategy.ALTERNATIVE_ROUTE_RECOVERY.value,
            },
            headers=admin_headers,
        )
        assert res.status_code == 201
        data = res.json()
        assert data["optimization_strategy"] == OptimizationStrategy.ALTERNATIVE_ROUTE_RECOVERY.value

    def test_filter_plans_by_disruption_id(
        self, client: TestClient, admin_headers, comprehensive_recovery_setup
    ):
        setup = comprehensive_recovery_setup
        client.post(
            "/api/v1/recovery/plans/generate",
            json={"disruption_id": setup["disr"].id},
            headers=admin_headers,
        )

        res = client.get(f"/api/v1/recovery/plans?disruption_id={setup['disr'].id}", headers=admin_headers)
        assert res.status_code == 200
        data = res.json()
        assert data["total"] >= 1
        for p in data["items"]:
            assert p["disruption_id"] == setup["disr"].id

    def test_ops_manager_can_approve_and_execute(
        self, client: TestClient, ops_manager_headers, admin_headers, comprehensive_recovery_setup
    ):
        setup = comprehensive_recovery_setup
        gen = client.post(
            "/api/v1/recovery/plans/generate",
            json={"disruption_id": setup["disr"].id},
            headers=admin_headers,
        ).json()
        plan_id = gen["id"]

        # Operations Manager can approve
        appr_res = client.post(
            f"/api/v1/recovery/plans/{plan_id}/approve",
            json={"notes": "Approved by Ops Manager"},
            headers=ops_manager_headers,
        )
        assert appr_res.status_code == 200
        assert appr_res.json()["status"] == RecoveryPlanStatus.APPROVED.value

        # Operations Manager can execute
        exec_res = client.post(f"/api/v1/recovery/plans/{plan_id}/execute", headers=ops_manager_headers)
        assert exec_res.status_code == 200
        assert exec_res.json()["status"] == RecoveryPlanStatus.EXECUTED.value

    def test_fleet_manager_can_approve_and_execute(
        self, client: TestClient, fleet_manager_headers, admin_headers, comprehensive_recovery_setup
    ):
        setup = comprehensive_recovery_setup
        gen = client.post(
            "/api/v1/recovery/plans/generate",
            json={"disruption_id": setup["disr"].id},
            headers=admin_headers,
        ).json()
        plan_id = gen["id"]

        # Fleet Manager can approve
        appr_res = client.post(
            f"/api/v1/recovery/plans/{plan_id}/approve",
            json={"notes": "Approved by Fleet Manager"},
            headers=fleet_manager_headers,
        )
        assert appr_res.status_code == 200

        # Fleet Manager can execute
        exec_res = client.post(f"/api/v1/recovery/plans/{plan_id}/execute", headers=fleet_manager_headers)
        assert exec_res.status_code == 200

    def test_warehouse_manager_cannot_approve(
        self, client: TestClient, warehouse_manager_headers, admin_headers, comprehensive_recovery_setup
    ):
        setup = comprehensive_recovery_setup
        gen = client.post(
            "/api/v1/recovery/plans/generate",
            json={"disruption_id": setup["disr"].id},
            headers=admin_headers,
        ).json()
        plan_id = gen["id"]

        # Warehouse Manager cannot approve plans
        res = client.post(
            f"/api/v1/recovery/plans/{plan_id}/approve",
            json={"notes": "Wh mgr attempt"},
            headers=warehouse_manager_headers,
        )
        assert res.status_code == 403

    def test_reject_with_too_short_reason_returns_422(
        self, client: TestClient, admin_headers, comprehensive_recovery_setup
    ):
        setup = comprehensive_recovery_setup
        gen = client.post(
            "/api/v1/recovery/plans/generate",
            json={"disruption_id": setup["disr"].id},
            headers=admin_headers,
        ).json()
        plan_id = gen["id"]

        # Length < 3
        res = client.post(f"/api/v1/recovery/plans/{plan_id}/reject", json={"reason": "no"}, headers=admin_headers)
        assert res.status_code == 422

    def test_comparison_endpoint_non_existent_plan_404(self, client: TestClient, admin_headers):
        res = client.get("/api/v1/recovery/plans/non-existent-id/comparison", headers=admin_headers)
        assert res.status_code == 404

    def test_assignments_endpoint_non_existent_plan_404(self, client: TestClient, admin_headers):
        res = client.get("/api/v1/recovery/plans/non-existent-id/assignments", headers=admin_headers)
        assert res.status_code == 404

    def test_actions_endpoint_non_existent_plan_404(self, client: TestClient, admin_headers):
        res = client.get("/api/v1/recovery/plans/non-existent-id/actions", headers=admin_headers)
        assert res.status_code == 404

    def test_audit_logs_endpoint_non_existent_plan_404(self, client: TestClient, admin_headers):
        res = client.get("/api/v1/recovery/plans/non-existent-id/audit-logs", headers=admin_headers)
        assert res.status_code == 404

    def test_audit_log_entries_detail_tracking(
        self, client: TestClient, admin_headers, comprehensive_recovery_setup
    ):
        setup = comprehensive_recovery_setup
        gen = client.post(
            "/api/v1/recovery/plans/generate",
            json={"disruption_id": setup["disr"].id},
            headers=admin_headers,
        ).json()
        plan_id = gen["id"]

        client.post(f"/api/v1/recovery/plans/{plan_id}/approve", json={"notes": "Special approval note"}, headers=admin_headers)
        client.post(f"/api/v1/recovery/plans/{plan_id}/execute", headers=admin_headers)

        res = client.get(f"/api/v1/recovery/plans/{plan_id}/audit-logs", headers=admin_headers)
        assert res.status_code == 200
        logs = res.json()
        actions = [log["action"] for log in logs]
        assert "PLAN_GENERATED" in actions
        assert "PLAN_APPROVED" in actions
        assert "PLAN_EXECUTED" in actions

        # Verify notes are saved in approval audit details
        approved_log = next(log for log in logs if log["action"] == "PLAN_APPROVED")
        assert approved_log["details"]["notes"] == "Special approval note"

    def test_action_payload_contains_reassignment_details(
        self, client: TestClient, admin_headers, comprehensive_recovery_setup
    ):
        setup = comprehensive_recovery_setup
        gen = client.post(
            "/api/v1/recovery/plans/generate",
            json={"disruption_id": setup["disr"].id},
            headers=admin_headers,
        ).json()
        plan_id = gen["id"]

        client.post(f"/api/v1/recovery/plans/{plan_id}/approve", json={"notes": "Approve"}, headers=admin_headers)
        client.post(f"/api/v1/recovery/plans/{plan_id}/execute", headers=admin_headers)

        res = client.get(f"/api/v1/recovery/plans/{plan_id}/actions", headers=admin_headers)
        assert res.status_code == 200
        actions = res.json()
        for act in actions:
            assert act["action_type"] == "REASSIGN_ORDER_VEHICLE"
            assert "new_vehicle_id" in act["action_payload"]
            assert act["status"] == "EXECUTED"
            assert act["execution_result"] is not None
            assert act["executed_at"] is not None

    def test_infeasible_optimization_when_no_vehicles_available(
        self, client: TestClient, admin_headers, comprehensive_recovery_setup, db_session: Session
    ):
        setup = comprehensive_recovery_setup
        # Mark all replacement vehicles offline
        setup["v_rep"].status = VehicleStatus.OFFLINE.value
        db_session.commit()

        res = client.post(
            "/api/v1/recovery/plans/generate",
            json={"disruption_id": setup["disr"].id},
            headers=admin_headers,
        )
        assert res.status_code == 422
        assert "No available replacement vehicles" in res.json().get("error", {}).get("message", "")
