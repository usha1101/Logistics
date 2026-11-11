from datetime import datetime, timedelta, timezone
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models.network import NetworkNode, NodeType
from app.models.order import (
    Customer,
    Order,
    OrderItem,
    OrderPriority,
    OrderStatus,
)
from app.models.vehicle import Vehicle, VehicleStatus, VehicleType
from app.models.warehouse import Warehouse, WarehouseStatus, WarehouseType


@pytest.fixture
def order_api_fixtures(db_session: Session):
    node = NetworkNode(
        name="Peenya Distribution Hub",
        node_type=NodeType.WAREHOUSE.value,
        latitude=13.028,
        longitude=77.519,
        region="North-West",
        address="Peenya Industrial Area",
        is_active=True,
    )
    db_session.add(node)
    db_session.commit()

    warehouse = Warehouse(
        network_node_id=node.id,
        warehouse_code="WH-PEENYA-TEST",
        warehouse_type=WarehouseType.DISTRIBUTION_CENTER.value,
        total_capacity=15000.0,
        used_capacity=3000.0,
        status=WarehouseStatus.OPERATIONAL.value,
    )
    db_session.add(warehouse)
    db_session.commit()

    customer = Customer(
        customer_code="CUST-API-01",
        name="Apex Industrial Logistics",
        email="orders@apexind.com",
        phone="+91-80-5566-7788",
        address_line="22/4 Outer Ring Road",
        city="Bengaluru",
        state="Karnataka",
        postal_code="560037",
        latitude=12.97,
        longitude=77.65,
        is_active=True,
    )
    db_session.add(customer)
    db_session.commit()

    # Vehicles: 1 available with 500 kg capacity, 1 small van with 50 kg capacity, 1 broken down
    v_main = Vehicle(
        vehicle_code="V-MAIN-01",
        registration_number="KA-01-MN-01",
        vehicle_type=VehicleType.DELIVERY_VAN.value,
        capacity_kg=500.0,
        current_load_kg=0.0,
        status=VehicleStatus.AVAILABLE.value,
        is_active=True,
    )
    v_small = Vehicle(
        vehicle_code="V-SMALL-01",
        registration_number="KA-01-SM-01",
        vehicle_type=VehicleType.ELECTRIC_VAN.value,
        capacity_kg=50.0,
        current_load_kg=0.0,
        status=VehicleStatus.AVAILABLE.value,
        is_active=True,
    )
    v_broken = Vehicle(
        vehicle_code="V-BROKEN-01",
        registration_number="KA-01-BR-01",
        vehicle_type=VehicleType.HEAVY_TRUCK.value,
        capacity_kg=2000.0,
        current_load_kg=0.0,
        status=VehicleStatus.BREAKDOWN.value,
        is_active=True,
    )
    db_session.add_all([v_main, v_small, v_broken])
    db_session.commit()

    now = datetime.now(timezone.utc)
    # Order 1: Pending CREATED, unassigned
    o1 = Order(
        order_number="ORD-API-001",
        customer_id=customer.id,
        warehouse_id=warehouse.id,
        status=OrderStatus.CREATED.value,
        priority=OrderPriority.NORMAL.value,
        expected_delivery_at=now + timedelta(hours=24),
        delivery_address="Outer Ring Road, Bellandur",
        delivery_latitude=12.93,
        delivery_longitude=77.68,
        total_weight_kg=100.0,
        total_amount=15000.0,
    )
    # Order 2: Overdue, in processing
    o2 = Order(
        order_number="ORD-API-002",
        customer_id=customer.id,
        warehouse_id=warehouse.id,
        status=OrderStatus.PROCESSING.value,
        priority=OrderPriority.URGENT.value,
        expected_delivery_at=now - timedelta(hours=5),
        delivery_address="Outer Ring Road, Marathahalli",
        delivery_latitude=12.95,
        delivery_longitude=77.70,
        total_weight_kg=60.0,
        total_amount=8000.0,
    )
    db_session.add_all([o1, o2])
    db_session.commit()

    return {
        "warehouse_id": warehouse.id,
        "customer_id": customer.id,
        "v_main_id": v_main.id,
        "v_small_id": v_small.id,
        "v_broken_id": v_broken.id,
        "o1_id": o1.id,
        "o2_id": o2.id,
    }


def test_order_summary_metrics(client: TestClient, order_api_fixtures, analyst_headers):
    res = client.get("/api/v1/orders/summary", headers=analyst_headers)
    assert res.status_code == 200
    data = res.json()
    assert data["total_orders"] == 2
    assert data["created_orders"] == 1
    assert data["processing_orders"] == 1
    assert data["overdue_orders"] == 1
    assert data["unassigned_orders"] == 2
    assert data["total_order_value"] == 23000.0
    assert data["total_order_weight_kg"] == 160.0


def test_operational_queues_pending_overdue_unassigned(client: TestClient, order_api_fixtures, analyst_headers):
    # 1. Pending (both are pending)
    res_pending = client.get("/api/v1/orders/pending", headers=analyst_headers)
    assert res_pending.status_code == 200
    assert res_pending.json()["total"] == 2

    # 2. Overdue (only o2 is overdue)
    res_overdue = client.get("/api/v1/orders/overdue", headers=analyst_headers)
    assert res_overdue.status_code == 200
    assert res_overdue.json()["total"] == 1
    assert res_overdue.json()["items"][0]["order_number"] == "ORD-API-002"

    # 3. Unassigned (both are unassigned)
    res_unassigned = client.get("/api/v1/orders/unassigned", headers=analyst_headers)
    assert res_unassigned.status_code == 200
    assert res_unassigned.json()["total"] == 2


def test_list_orders_filtering_and_pagination(client: TestClient, order_api_fixtures, analyst_headers):
    # Filter by priority=URGENT
    res = client.get("/api/v1/orders?priority=URGENT", headers=analyst_headers)
    assert res.status_code == 200
    assert res.json()["total"] == 1
    assert res.json()["items"][0]["order_number"] == "ORD-API-002"

    # Filter by is_overdue=true
    res_overdue = client.get("/api/v1/orders?is_overdue=true", headers=analyst_headers)
    assert res_overdue.status_code == 200
    assert res_overdue.json()["total"] == 1


def test_create_order_with_items_and_totals(client: TestClient, order_api_fixtures, admin_headers):
    now = datetime.now(timezone.utc)
    payload = {
        "order_number": "ORD-NEW-101",
        "customer_id": order_api_fixtures["customer_id"],
        "warehouse_id": order_api_fixtures["warehouse_id"],
        "priority": "HIGH",
        "expected_delivery_at": (now + timedelta(hours=18)).isoformat(),
        "delivery_address": "Tech Zone, Whitefield",
        "delivery_latitude": 12.9698,
        "delivery_longitude": 77.7499,
        "notes": "Fragile electronic parts",
        "items": [
            {"product_code": "SKU-A", "product_name": "Inverter", "quantity": 2, "unit_price": 5000.0, "unit_weight_kg": 10.0},
            {"product_code": "SKU-B", "product_name": "Cable Roll", "quantity": 5, "unit_price": 200.0, "unit_weight_kg": 2.0},
        ],
    }
    res = client.post("/api/v1/orders", json=payload, headers=admin_headers)
    assert res.status_code == 201
    data = res.json()
    assert data["order_number"] == "ORD-NEW-101"
    # Total amount = (2 * 5000) + (5 * 200) = 11000.0
    assert data["total_amount"] == 11000.0
    # Total weight = (2 * 10) + (5 * 2) = 30.0
    assert data["total_weight_kg"] == 30.0
    assert data["status"] == "CREATED"


def test_create_order_duplicate_number_rejected(client: TestClient, order_api_fixtures, admin_headers):
    now = datetime.now(timezone.utc)
    payload = {
        "order_number": "ORD-API-001",  # Existing
        "customer_id": order_api_fixtures["customer_id"],
        "warehouse_id": order_api_fixtures["warehouse_id"],
        "expected_delivery_at": (now + timedelta(hours=12)).isoformat(),
        "delivery_address": "Some place",
        "delivery_latitude": 12.9,
        "delivery_longitude": 77.6,
    }
    res = client.post("/api/v1/orders", json=payload, headers=admin_headers)
    assert res.status_code == 409
    assert res.json()["error"]["code"] == "CONFLICT"


def test_get_order_by_id_and_patch(client: TestClient, order_api_fixtures, admin_headers):
    o1_id = order_api_fixtures["o1_id"]
    res = client.get(f"/api/v1/orders/{o1_id}", headers=admin_headers)
    assert res.status_code == 200
    assert res.json()["order_number"] == "ORD-API-001"

    # Patch notes and priority
    res_patch = client.patch(
        f"/api/v1/orders/{o1_id}",
        json={"priority": "URGENT", "notes": "Updated instructions"},
        headers=admin_headers,
    )
    assert res_patch.status_code == 200
    assert res_patch.json()["priority"] == "URGENT"
    assert res_patch.json()["notes"] == "Updated instructions"


def test_add_order_item_and_recalculate_totals(client: TestClient, order_api_fixtures, admin_headers):
    o1_id = order_api_fixtures["o1_id"]

    # Initial totals on o1: weight = 100.0, amount = 15000.0
    item_payload = {
        "product_code": "SKU-EXTRA",
        "product_name": "Diagnostic Tool",
        "quantity": 2,
        "unit_price": 2500.0,
        "unit_weight_kg": 5.0,
    }
    res = client.post(f"/api/v1/orders/{o1_id}/items", json=item_payload, headers=admin_headers)
    assert res.status_code == 201
    assert res.json()["subtotal"] == 5000.0
    assert res.json()["total_weight_kg"] == 10.0

    # Verify order total recalculation
    res_order = client.get(f"/api/v1/orders/{o1_id}", headers=admin_headers)
    assert res_order.status_code == 200
    assert res_order.json()["total_amount"] == 5000.0  # Item replaces initial dummy items or recalculated
    assert res_order.json()["total_weight_kg"] == 10.0


def test_order_status_transitions_and_history(client: TestClient, order_api_fixtures, admin_headers):
    o1_id = order_api_fixtures["o1_id"]  # Status is CREATED

    # 1. Valid transition: CREATED -> CONFIRMED
    res_conf = client.patch(
        f"/api/v1/orders/{o1_id}/status",
        json={"status": "CONFIRMED", "reason": "Payment verified"},
        headers=admin_headers,
    )
    assert res_conf.status_code == 200
    assert res_conf.json()["status"] == "CONFIRMED"

    # 2. Invalid transition: CONFIRMED -> DELIVERED (Must go through PROCESSING -> READY_FOR_DISPATCH -> DISPATCHED -> IN_TRANSIT)
    res_bad = client.patch(
        f"/api/v1/orders/{o1_id}/status",
        json={"status": "DELIVERED"},
        headers=admin_headers,
    )
    assert res_bad.status_code == 400
    assert "Invalid order status transition" in res_bad.json()["error"]["message"]

    # 3. Check status history endpoint
    res_hist = client.get(f"/api/v1/orders/{o1_id}/history", headers=admin_headers)
    assert res_hist.status_code == 200
    assert len(res_hist.json()) >= 1
    assert res_hist.json()[0]["new_status"] == "CONFIRMED"


def test_delivery_before_dispatch_rejected(client: TestClient, order_api_fixtures, admin_headers):
    o1_id = order_api_fixtures["o1_id"]

    # Transition to PROCESSING
    client.patch(f"/api/v1/orders/{o1_id}/status", json={"status": "CONFIRMED"}, headers=admin_headers)
    client.patch(f"/api/v1/orders/{o1_id}/status", json={"status": "PROCESSING"}, headers=admin_headers)
    client.patch(f"/api/v1/orders/{o1_id}/status", json={"status": "READY_FOR_DISPATCH"}, headers=admin_headers)
    client.patch(f"/api/v1/orders/{o1_id}/status", json={"status": "DISPATCHED"}, headers=admin_headers)
    client.patch(f"/api/v1/orders/{o1_id}/status", json={"status": "IN_TRANSIT"}, headers=admin_headers)

    # Deliver order
    res_del = client.patch(
        f"/api/v1/orders/{o1_id}/status",
        json={"status": "DELIVERED", "reason": "Customer signature obtained"},
        headers=admin_headers,
    )
    assert res_del.status_code == 200
    assert res_del.json()["status"] == "DELIVERED"
    assert res_del.json()["delivered_at"] is not None


def test_vehicle_assignment_and_capacity_checks(
    client: TestClient, order_api_fixtures, admin_headers, db_session: Session
):
    o1_id = order_api_fixtures["o1_id"]  # Weight = 100.0 kg
    v_main_id = order_api_fixtures["v_main_id"]  # Cap = 500.0 kg
    v_small_id = order_api_fixtures["v_small_id"]  # Cap = 50.0 kg
    v_broken_id = order_api_fixtures["v_broken_id"]  # BREAKDOWN

    # 1. Assign to small van -> fails (100 kg > 50 kg)
    res_cap = client.patch(
        f"/api/v1/orders/{o1_id}/assignment",
        json={"vehicle_id": v_small_id},
        headers=admin_headers,
    )
    assert res_cap.status_code == 400
    assert "insufficient capacity" in res_cap.json()["error"]["message"]

    # 2. Assign to broken vehicle -> fails
    res_broken = client.patch(
        f"/api/v1/orders/{o1_id}/assignment",
        json={"vehicle_id": v_broken_id},
        headers=admin_headers,
    )
    assert res_broken.status_code == 400
    assert "does not permit assignment" in res_broken.json()["error"]["message"]

    # 3. Assign to main van -> succeeds
    res_ok = client.patch(
        f"/api/v1/orders/{o1_id}/assignment",
        json={"vehicle_id": v_main_id, "reason": "Route 1 allocation"},
        headers=admin_headers,
    )
    assert res_ok.status_code == 200
    assert res_ok.json()["assigned_vehicle_id"] == v_main_id

    # Verify vehicle load updated to 100.0
    v = db_session.get(Vehicle, v_main_id)
    assert v.current_load_kg == 100.0

    # 4. Check assignment history endpoint
    res_assign_hist = client.get(f"/api/v1/orders/{o1_id}/assignment-history", headers=admin_headers)
    assert res_assign_hist.status_code == 200
    assert len(res_assign_hist.json()) >= 1
    assert res_assign_hist.json()[0]["new_vehicle_id"] == v_main_id

    # 5. Unassign vehicle -> vehicle load freed
    res_unassign = client.patch(
        f"/api/v1/orders/{o1_id}/assignment",
        json={"vehicle_id": None, "reason": "Order cancelled from route"},
        headers=admin_headers,
    )
    assert res_unassign.status_code == 200
    assert res_unassign.json()["assigned_vehicle_id"] is None
    v = db_session.get(Vehicle, v_main_id)
    assert v.current_load_kg == 0.0


def test_order_rbac_permissions(
    client: TestClient,
    order_api_fixtures,
    warehouse_manager_headers,
    fleet_manager_headers,
    analyst_headers,
):
    o1_id = order_api_fixtures["o1_id"]
    v_main_id = order_api_fixtures["v_main_id"]

    # 1. Analyst cannot create orders (403)
    res_analyst = client.post(
        "/api/v1/orders",
        json={"order_number": "ORD-FORBID", "customer_id": "c", "warehouse_id": "w", "expected_delivery_at": "2026-11-12T00:00:00Z", "delivery_address": "a", "delivery_latitude": 12.0, "delivery_longitude": 77.0},
        headers=analyst_headers,
    )
    assert res_analyst.status_code == 403

    # 2. Warehouse Manager can advance to CONFIRMED (200)
    res_wh = client.patch(
        f"/api/v1/orders/{o1_id}/status",
        json={"status": "CONFIRMED"},
        headers=warehouse_manager_headers,
    )
    assert res_wh.status_code == 200

    # 3. Warehouse Manager cannot deliver order (403)
    res_wh_del = client.patch(
        f"/api/v1/orders/{o1_id}/status",
        json={"status": "DELIVERED"},
        headers=warehouse_manager_headers,
    )
    assert res_wh_del.status_code == 403

    # 4. Fleet Manager CAN assign vehicle (200)
    res_fm_assign = client.patch(
        f"/api/v1/orders/{o1_id}/assignment",
        json={"vehicle_id": v_main_id},
        headers=fleet_manager_headers,
    )
    assert res_fm_assign.status_code == 200


def test_order_filters_by_customer_warehouse_and_vehicle(client: TestClient, order_api_fixtures, admin_headers):
    cust_id = order_api_fixtures["customer_id"]
    wh_id = order_api_fixtures["warehouse_id"]

    # Filter by customer
    res_cust = client.get(f"/api/v1/orders?customer_id={cust_id}", headers=admin_headers)
    assert res_cust.status_code == 200
    assert res_cust.json()["total"] == 2

    # Filter by warehouse
    res_wh = client.get(f"/api/v1/orders?warehouse_id={wh_id}", headers=admin_headers)
    assert res_wh.status_code == 200
    assert res_wh.json()["total"] == 2


def test_cannot_add_items_to_processing_or_terminal_order(client: TestClient, order_api_fixtures, admin_headers):
    o2_id = order_api_fixtures["o2_id"]  # Status is PROCESSING
    item_payload = {
        "product_code": "PROD-LATE",
        "product_name": "Too Late Item",
        "quantity": 1,
        "unit_price": 500.0,
        "unit_weight_kg": 2.0,
    }
    res = client.post(f"/api/v1/orders/{o2_id}/items", json=item_payload, headers=admin_headers)
    assert res.status_code == 400
    assert "Cannot add items to order with status" in res.json()["error"]["message"]


def test_order_hold_and_resume_transitions(client: TestClient, order_api_fixtures, admin_headers):
    o1_id = order_api_fixtures["o1_id"]

    # CREATED -> CONFIRMED
    client.patch(f"/api/v1/orders/{o1_id}/status", json={"status": "CONFIRMED"}, headers=admin_headers)

    # CONFIRMED -> ON_HOLD
    res_hold = client.patch(
        f"/api/v1/orders/{o1_id}/status",
        json={"status": "ON_HOLD", "reason": "Awaiting customer address confirmation"},
        headers=admin_headers,
    )
    assert res_hold.status_code == 200
    assert res_hold.json()["status"] == "ON_HOLD"

    # ON_HOLD -> PROCESSING (Resume)
    res_resume = client.patch(
        f"/api/v1/orders/{o1_id}/status",
        json={"status": "PROCESSING", "reason": "Address confirmed, resumed packing"},
        headers=admin_headers,
    )
    assert res_resume.status_code == 200
    assert res_resume.json()["status"] == "PROCESSING"


def test_order_failed_delivery_and_recovery(client: TestClient, order_api_fixtures, admin_headers):
    o1_id = order_api_fixtures["o1_id"]

    # Transition to IN_TRANSIT
    client.patch(f"/api/v1/orders/{o1_id}/status", json={"status": "CONFIRMED"}, headers=admin_headers)
    client.patch(f"/api/v1/orders/{o1_id}/status", json={"status": "PROCESSING"}, headers=admin_headers)
    client.patch(f"/api/v1/orders/{o1_id}/status", json={"status": "READY_FOR_DISPATCH"}, headers=admin_headers)
    client.patch(f"/api/v1/orders/{o1_id}/status", json={"status": "DISPATCHED"}, headers=admin_headers)
    client.patch(f"/api/v1/orders/{o1_id}/status", json={"status": "IN_TRANSIT"}, headers=admin_headers)

    # IN_TRANSIT -> FAILED_DELIVERY
    res_fail = client.patch(
        f"/api/v1/orders/{o1_id}/status",
        json={"status": "FAILED_DELIVERY", "reason": "Customer gate locked"},
        headers=admin_headers,
    )
    assert res_fail.status_code == 200
    assert res_fail.json()["status"] == "FAILED_DELIVERY"

    # Recovery: FAILED_DELIVERY -> PROCESSING
    res_recover = client.patch(
        f"/api/v1/orders/{o1_id}/status",
        json={"status": "PROCESSING", "reason": "Scheduled for re-attempt"},
        headers=admin_headers,
    )
    assert res_recover.status_code == 200
    assert res_recover.json()["status"] == "PROCESSING"


def test_order_cancellation_releases_vehicle_load(
    client: TestClient, order_api_fixtures, admin_headers, db_session: Session
):
    o1_id = order_api_fixtures["o1_id"]  # 100 kg
    v_main_id = order_api_fixtures["v_main_id"]

    # Assign vehicle
    client.patch(f"/api/v1/orders/{o1_id}/assignment", json={"vehicle_id": v_main_id}, headers=admin_headers)
    v = db_session.get(Vehicle, v_main_id)
    assert v.current_load_kg == 100.0

    # Cancel order
    res_cancel = client.patch(
        f"/api/v1/orders/{o1_id}/status",
        json={"status": "CANCELLED", "reason": "Customer cancelled order"},
        headers=admin_headers,
    )
    assert res_cancel.status_code == 200
    assert res_cancel.json()["status"] == "CANCELLED"

    # Check vehicle load released
    db_session.refresh(v)
    assert v.current_load_kg == 0.0


def test_vehicle_reassignment_transfers_load(
    client: TestClient, order_api_fixtures, admin_headers, db_session: Session
):
    o1_id = order_api_fixtures["o1_id"]  # 100 kg
    v_main_id = order_api_fixtures["v_main_id"]  # 500 kg capacity

    # Create another available vehicle with 800 kg capacity
    v_other = Vehicle(
        vehicle_code="V-REASSIGN-01",
        registration_number="KA-01-RE-01",
        vehicle_type=VehicleType.HEAVY_TRUCK.value,
        capacity_kg=800.0,
        current_load_kg=0.0,
        status=VehicleStatus.AVAILABLE.value,
        is_active=True,
    )
    db_session.add(v_other)
    db_session.commit()

    # 1. Assign to v_main
    client.patch(f"/api/v1/orders/{o1_id}/assignment", json={"vehicle_id": v_main_id}, headers=admin_headers)
    v1 = db_session.get(Vehicle, v_main_id)
    assert v1.current_load_kg == 100.0

    # 2. Reassign to v_other
    res_re = client.patch(
        f"/api/v1/orders/{o1_id}/assignment",
        json={"vehicle_id": v_other.id, "reason": "Optimized to larger hauler"},
        headers=admin_headers,
    )
    assert res_re.status_code == 200
    assert res_re.json()["assigned_vehicle_id"] == v_other.id

    # Verify load transferred: v1 released (0), v_other loaded (100)
    db_session.refresh(v1)
    db_session.refresh(v_other)
    assert v1.current_load_kg == 0.0
    assert v_other.current_load_kg == 100.0


def test_order_same_status_update_is_noop(client: TestClient, order_api_fixtures, admin_headers):
    o1_id = order_api_fixtures["o1_id"]
    res = client.patch(f"/api/v1/orders/{o1_id}/status", json={"status": "CREATED"}, headers=admin_headers)
    assert res.status_code == 200
    assert res.json()["status"] == "CREATED"


def test_order_summary_empty_database_no_division_by_zero(client: TestClient, admin_headers):
    res = client.get("/api/v1/orders/summary", headers=admin_headers)
    assert res.status_code == 200
    data = res.json()
    assert data["total_orders"] >= 0

