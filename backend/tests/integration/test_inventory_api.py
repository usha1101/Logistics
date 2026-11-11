import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models.network import NetworkNode, NodeType
from app.models.warehouse import (
    InventoryItem,
    InventoryMovement,
    MovementType,
    StockStatus,
    Warehouse,
    WarehouseStatus,
    WarehouseType,
)


@pytest.fixture
def inventory_setup(db_session: Session):
    node = NetworkNode(
        name="Electronic City Hub",
        node_type=NodeType.WAREHOUSE.value,
        latitude=12.84,
        longitude=77.67,
        region="South",
        address="Phase 1 Electronic City",
        is_active=True,
    )
    db_session.add(node)
    db_session.commit()

    warehouse = Warehouse(
        network_node_id=node.id,
        warehouse_code="WH-TEST-01",
        warehouse_type=WarehouseType.FULFILLMENT_CENTER.value,
        total_capacity=1000.0,
        used_capacity=100.0,
        status=WarehouseStatus.OPERATIONAL.value,
        manager_name="Pooja Sharma",
    )
    db_session.add(warehouse)
    db_session.commit()

    item1 = InventoryItem(
        warehouse_id=warehouse.id,
        sku="SKU-TEST-01",
        product_name="Sensors Pack",
        category="Electronics",
        quantity=50,
        reorder_level=20,
        unit="units",
        unit_volume=2.0,
    )
    item2 = InventoryItem(
        warehouse_id=warehouse.id,
        sku="SKU-TEST-02",
        product_name="Packaging Tape",
        category="Packaging",
        quantity=5,
        reorder_level=10,
        unit="rolls",
        unit_volume=0.5,
    )
    item3 = InventoryItem(
        warehouse_id=warehouse.id,
        sku="SKU-TEST-03",
        product_name="Pallets",
        category="Packaging",
        quantity=0,
        reorder_level=5,
        unit="pieces",
        unit_volume=5.0,
    )
    db_session.add_all([item1, item2, item3])
    db_session.commit()

    return {
        "warehouse_id": warehouse.id,
        "item1_id": item1.id,
        "item2_id": item2.id,
        "item3_id": item3.id,
    }


def test_get_inventory_item(client: TestClient, inventory_setup, warehouse_manager_headers):
    item_id = inventory_setup["item1_id"]
    res = client.get(f"/api/v1/inventory/{item_id}", headers=warehouse_manager_headers)
    assert res.status_code == 200
    data = res.json()
    assert data["id"] == item_id
    assert data["sku"] == "SKU-TEST-01"
    assert data["quantity"] == 50
    assert data["status"] == StockStatus.IN_STOCK.value


def test_get_inventory_item_not_found(client: TestClient, inventory_setup, warehouse_manager_headers):
    res = client.get("/api/v1/inventory/nonexistent-id", headers=warehouse_manager_headers)
    assert res.status_code == 404
    assert res.json()["error"]["code"] == "NOT_FOUND"


def test_get_low_stock_items(client: TestClient, inventory_setup, warehouse_manager_headers):
    res = client.get("/api/v1/inventory/low-stock", headers=warehouse_manager_headers)
    assert res.status_code == 200
    data = res.json()
    # item2 (qty 5 <= reorder 10) and item3 (qty 0 <= reorder 5)
    skus = [item["sku"] for item in data["items"]]
    assert "SKU-TEST-02" in skus
    assert "SKU-TEST-03" in skus
    assert "SKU-TEST-01" not in skus


def test_get_low_stock_items_filter_by_warehouse(client: TestClient, inventory_setup, warehouse_manager_headers):
    wh_id = inventory_setup["warehouse_id"]
    res = client.get(f"/api/v1/inventory/low-stock?warehouse_id={wh_id}", headers=warehouse_manager_headers)
    assert res.status_code == 200
    data = res.json()
    assert data["total"] == 2


def test_patch_inventory_item_metadata(client: TestClient, inventory_setup, warehouse_manager_headers):
    item_id = inventory_setup["item1_id"]
    patch_payload = {
        "product_name": "Updated Sensors Pack",
        "category": "Industrial Electronics",
        "reorder_level": 30,
        "quantity": 9999,  # Should be ignored by schema / cannot directly modify quantity
    }
    res = client.patch(
        f"/api/v1/inventory/{item_id}",
        json=patch_payload,
        headers=warehouse_manager_headers,
    )
    assert res.status_code == 200
    data = res.json()
    assert data["product_name"] == "Updated Sensors Pack"
    assert data["category"] == "Industrial Electronics"
    assert data["reorder_level"] == 30
    assert data["quantity"] == 50  # Must remain unchanged


def test_stock_movement_receipt(client: TestClient, inventory_setup, warehouse_manager_headers, db_session: Session):
    item_id = inventory_setup["item1_id"]
    wh_id = inventory_setup["warehouse_id"]

    movement_payload = {
        "movement_type": "STOCK_RECEIVED",
        "quantity": 25,
        "reference": "PO-2026-901",
        "notes": "Weekly supplier replenishment",
    }
    res = client.post(
        f"/api/v1/inventory/{item_id}/movements",
        json=movement_payload,
        headers=warehouse_manager_headers,
    )
    assert res.status_code == 201
    data = res.json()
    assert data["movement_type"] == MovementType.STOCK_RECEIVED.value
    assert data["quantity"] == 25
    assert data["previous_quantity"] == 50
    assert data["new_quantity"] == 75
    assert data["created_by_user_id"] is not None

    # Check item in DB
    item = db_session.get(InventoryItem, item_id)
    assert item.quantity == 75

    # Check warehouse used capacity: 100 + (25 * 2.0) = 150.0
    wh = db_session.get(Warehouse, wh_id)
    assert wh.used_capacity == 150.0


def test_stock_movement_dispatch(client: TestClient, inventory_setup, warehouse_manager_headers, db_session: Session):
    item_id = inventory_setup["item1_id"]
    wh_id = inventory_setup["warehouse_id"]

    # Initial used_capacity is 100.0, qty is 50, unit_volume is 2.0
    movement_payload = {
        "movement_type": "STOCK_DISPATCHED",
        "quantity": 10,
        "reference": "SO-2026-101",
        "notes": "Dispatched for customer order",
    }
    res = client.post(
        f"/api/v1/inventory/{item_id}/movements",
        json=movement_payload,
        headers=warehouse_manager_headers,
    )
    assert res.status_code == 201
    data = res.json()
    assert data["previous_quantity"] == 50
    assert data["new_quantity"] == 40

    item = db_session.get(InventoryItem, item_id)
    assert item.quantity == 40

    wh = db_session.get(Warehouse, wh_id)
    assert wh.used_capacity == 80.0  # 100 - (10 * 2.0)


def test_stock_dispatch_insufficient_stock_rejected(client: TestClient, inventory_setup, warehouse_manager_headers, db_session: Session):
    item_id = inventory_setup["item1_id"]
    wh_id = inventory_setup["warehouse_id"]

    movement_payload = {
        "movement_type": "STOCK_DISPATCHED",
        "quantity": 999,
        "reference": "SO-OVERLIMIT",
    }
    res = client.post(
        f"/api/v1/inventory/{item_id}/movements",
        json=movement_payload,
        headers=warehouse_manager_headers,
    )
    assert res.status_code == 400
    assert "Insufficient stock" in res.json()["error"]["message"]

    # Verify rollback/unchanged
    item = db_session.get(InventoryItem, item_id)
    assert item.quantity == 50

    wh = db_session.get(Warehouse, wh_id)
    assert wh.used_capacity == 100.0


def test_stock_receipt_exceeding_capacity_rejected(client: TestClient, inventory_setup, warehouse_manager_headers, db_session: Session):
    item_id = inventory_setup["item1_id"]
    wh_id = inventory_setup["warehouse_id"]

    # Total capacity = 1000.0, used = 100.0. Remaining = 900.0.
    # Unit volume = 2.0 -> max additional units = 450.
    # Requesting 500 units requires 1000 volume -> exceeds 900 available.
    movement_payload = {
        "movement_type": "STOCK_RECEIVED",
        "quantity": 500,
        "reference": "PO-BULK-OVERFLOW",
    }
    res = client.post(
        f"/api/v1/inventory/{item_id}/movements",
        json=movement_payload,
        headers=warehouse_manager_headers,
    )
    assert res.status_code == 400
    assert "exceeding available warehouse capacity" in res.json()["error"]["message"]

    # Verify atomic state
    item = db_session.get(InventoryItem, item_id)
    assert item.quantity == 50
    wh = db_session.get(Warehouse, wh_id)
    assert wh.used_capacity == 100.0


def test_stock_adjustment_increase_and_decrease(client: TestClient, inventory_setup, warehouse_manager_headers, db_session: Session):
    item_id = inventory_setup["item1_id"]

    # 1. Increase adjustment
    res_inc = client.post(
        f"/api/v1/inventory/{item_id}/movements",
        json={
            "movement_type": "STOCK_ADJUSTMENT",
            "adjustment_type": "INCREASE",
            "quantity": 5,
            "reference": "AUDIT-INC",
            "notes": "Found extra items during inventory count",
        },
        headers=warehouse_manager_headers,
    )
    assert res_inc.status_code == 201
    assert res_inc.json()["previous_quantity"] == 50
    assert res_inc.json()["new_quantity"] == 55

    # 2. Decrease adjustment
    res_dec = client.post(
        f"/api/v1/inventory/{item_id}/movements",
        json={
            "movement_type": "STOCK_ADJUSTMENT",
            "adjustment_type": "DECREASE",
            "quantity": 15,
            "reference": "AUDIT-DEC",
            "notes": "Damaged goods written off",
        },
        headers=warehouse_manager_headers,
    )
    assert res_dec.status_code == 201
    assert res_dec.json()["previous_quantity"] == 55
    assert res_dec.json()["new_quantity"] == 40


def test_stock_adjustment_missing_type_fails(client: TestClient, inventory_setup, warehouse_manager_headers):
    item_id = inventory_setup["item1_id"]
    res = client.post(
        f"/api/v1/inventory/{item_id}/movements",
        json={
            "movement_type": "STOCK_ADJUSTMENT",
            "quantity": 5,
        },
        headers=warehouse_manager_headers,
    )
    assert res.status_code == 422


def test_stock_movement_audit_history(client: TestClient, inventory_setup, warehouse_manager_headers):
    item_id = inventory_setup["item1_id"]

    # Create 2 movements
    client.post(
        f"/api/v1/inventory/{item_id}/movements",
        json={"movement_type": "STOCK_RECEIVED", "quantity": 10, "reference": "M1"},
        headers=warehouse_manager_headers,
    )
    client.post(
        f"/api/v1/inventory/{item_id}/movements",
        json={"movement_type": "STOCK_DISPATCHED", "quantity": 5, "reference": "M2"},
        headers=warehouse_manager_headers,
    )

    res = client.get(f"/api/v1/inventory/{item_id}/movements", headers=warehouse_manager_headers)
    assert res.status_code == 200
    data = res.json()
    assert data["total"] == 2
    assert len(data["items"]) == 2
    # Verify latest first
    assert data["items"][0]["reference"] == "M2"
    assert data["items"][1]["reference"] == "M1"


def test_inventory_rbac_permissions(
    client: TestClient,
    inventory_setup,
    admin_headers,
    warehouse_manager_headers,
    fleet_manager_headers,
    analyst_headers,
):
    item_id = inventory_setup["item1_id"]

    # Analyst can read
    res = client.get(f"/api/v1/inventory/{item_id}", headers=analyst_headers)
    assert res.status_code == 200

    # Analyst cannot execute movements
    res = client.post(
        f"/api/v1/inventory/{item_id}/movements",
        json={"movement_type": "STOCK_RECEIVED", "quantity": 5},
        headers=analyst_headers,
    )
    assert res.status_code == 403
    assert res.json()["error"]["code"] == "FORBIDDEN"

    # Fleet manager cannot execute movements
    res = client.post(
        f"/api/v1/inventory/{item_id}/movements",
        json={"movement_type": "STOCK_RECEIVED", "quantity": 5},
        headers=fleet_manager_headers,
    )
    assert res.status_code == 403

    # Fleet manager cannot patch metadata
    res = client.patch(
        f"/api/v1/inventory/{item_id}",
        json={"product_name": "Hacked Name"},
        headers=fleet_manager_headers,
    )
    assert res.status_code == 403

    # Admin CAN execute movements
    res = client.post(
        f"/api/v1/inventory/{item_id}/movements",
        json={"movement_type": "STOCK_RECEIVED", "quantity": 5, "reference": "ADMIN-RESTOCK"},
        headers=admin_headers,
    )
    assert res.status_code == 201
