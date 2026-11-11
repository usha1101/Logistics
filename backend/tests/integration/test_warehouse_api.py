from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models.network import NetworkNode, NodeType
from app.models.warehouse import InventoryItem, Warehouse, WarehouseStatus, WarehouseType


def setup_warehouse_fixtures(db_session: Session):
    node_wh1 = NetworkNode(
        name="Hub Whitefield",
        node_type=NodeType.WAREHOUSE.value,
        latitude=12.96,
        longitude=77.74,
        region="East",
        address="Whitefield Tech Zone",
        is_active=True,
    )
    node_wh2 = NetworkNode(
        name="Hub Peenya",
        node_type=NodeType.WAREHOUSE.value,
        latitude=13.02,
        longitude=77.51,
        region="North-West",
        address="Peenya Industrial Area",
        is_active=True,
    )
    node_cust = NetworkNode(
        name="Retail Cust 1",
        node_type=NodeType.CUSTOMER.value,
        latitude=12.93,
        longitude=77.62,
        region="South",
        is_active=True,
    )
    db_session.add_all([node_wh1, node_wh2, node_cust])
    db_session.commit()

    wh1 = Warehouse(
        network_node_id=node_wh1.id,
        warehouse_code="WH-EAST-01",
        warehouse_type=WarehouseType.DISTRIBUTION_CENTER.value,
        total_capacity=10000.0,
        used_capacity=2500.0,
        status=WarehouseStatus.OPERATIONAL.value,
        manager_name="Rajesh S",
    )
    wh2 = Warehouse(
        network_node_id=node_wh2.id,
        warehouse_code="WH-NORTH-02",
        warehouse_type=WarehouseType.STORAGE_FACILITY.value,
        total_capacity=8000.0,
        used_capacity=4000.0,
        status=WarehouseStatus.DEGRADED.value,
        manager_name="Anil K",
    )
    db_session.add_all([wh1, wh2])
    db_session.commit()

    item1 = InventoryItem(warehouse_id=wh1.id, sku="SKU-101", product_name="Batteries", quantity=100, reorder_level=20)
    item2 = InventoryItem(warehouse_id=wh1.id, sku="SKU-102", product_name="Sensors", quantity=10, reorder_level=15)
    item3 = InventoryItem(warehouse_id=wh1.id, sku="SKU-103", product_name="Boxes", quantity=0, reorder_level=10)
    db_session.add_all([item1, item2, item3])
    db_session.commit()

    return {
        "node_wh1": node_wh1,
        "node_wh2": node_wh2,
        "node_cust": node_cust,
        "wh1": wh1,
        "wh2": wh2,
        "item1": item1,
    }


def test_list_warehouses_and_filtering(
    client: TestClient, db_session: Session, analyst_headers: dict
):
    setup_warehouse_fixtures(db_session)

    # List all
    res_all = client.get("/api/v1/warehouses", headers=analyst_headers)
    assert res_all.status_code == 200
    data = res_all.json()
    assert data["total"] == 2
    assert len(data["items"]) == 2

    # Filter by status=DEGRADED
    res_deg = client.get("/api/v1/warehouses?status=DEGRADED", headers=analyst_headers)
    assert res_deg.status_code == 200
    assert res_deg.json()["total"] == 1
    assert res_deg.json()["items"][0]["warehouse_code"] == "WH-NORTH-02"

    # Filter by region=East
    res_east = client.get("/api/v1/warehouses?region=East", headers=analyst_headers)
    assert res_east.status_code == 200
    assert res_east.json()["total"] == 1
    assert res_east.json()["items"][0]["warehouse_code"] == "WH-EAST-01"


def test_create_warehouse_success_and_validations(
    client: TestClient, db_session: Session, warehouse_manager_headers: dict
):
    node_avail = NetworkNode(
        name="New WH Node",
        node_type=NodeType.WAREHOUSE.value,
        latitude=12.85,
        longitude=77.66,
    )
    node_cust = NetworkNode(
        name="Cust Node Invalid",
        node_type=NodeType.CUSTOMER.value,
        latitude=12.86,
        longitude=77.67,
    )
    db_session.add_all([node_avail, node_cust])
    db_session.commit()

    # 1. Success creation by Warehouse Manager
    create_payload = {
        "network_node_id": node_avail.id,
        "warehouse_code": "WH-NEW-01",
        "warehouse_type": "FULFILLMENT_CENTER",
        "total_capacity": 6000.0,
        "manager_name": "Priya N",
    }
    res_create = client.post(
        "/api/v1/warehouses", json=create_payload, headers=warehouse_manager_headers
    )
    assert res_create.status_code == 201
    created = res_create.json()
    assert created["warehouse_code"] == "WH-NEW-01"
    assert created["total_capacity"] == 6000.0
    assert created["utilization_percentage"] == 0.0

    # 2. Cannot link CUSTOMER node as warehouse (400)
    res_invalid_node = client.post(
        "/api/v1/warehouses",
        json={
            "network_node_id": node_cust.id,
            "warehouse_code": "WH-FAIL-01",
            "total_capacity": 5000.0,
        },
        headers=warehouse_manager_headers,
    )
    assert res_invalid_node.status_code == 400
    assert "node must be of type 'WAREHOUSE'" in res_invalid_node.json()["error"]["message"]

    # 3. Duplicate network_node_id rejected (409)
    res_dup_node = client.post(
        "/api/v1/warehouses",
        json={
            "network_node_id": node_avail.id,
            "warehouse_code": "WH-ANOTHER",
            "total_capacity": 5000.0,
        },
        headers=warehouse_manager_headers,
    )
    assert res_dup_node.status_code == 409
    assert "already associated" in res_dup_node.json()["error"]["message"]

    # 4. Duplicate warehouse_code rejected (409)
    node_third = NetworkNode(
        name="Third Node",
        node_type=NodeType.WAREHOUSE.value,
        latitude=12.87,
        longitude=77.68,
    )
    db_session.add(node_third)
    db_session.commit()

    res_dup_code = client.post(
        "/api/v1/warehouses",
        json={
            "network_node_id": node_third.id,
            "warehouse_code": "WH-NEW-01",  # duplicate
            "total_capacity": 5000.0,
        },
        headers=warehouse_manager_headers,
    )
    assert res_dup_code.status_code == 409
    assert "already registered" in res_dup_code.json()["error"]["message"]


def test_get_and_update_warehouse(
    client: TestClient, db_session: Session, warehouse_manager_headers: dict, analyst_headers: dict
):
    fixtures = setup_warehouse_fixtures(db_session)
    wh_id = fixtures["wh1"].id

    # 1. Get warehouse details
    res_get = client.get(f"/api/v1/warehouses/{wh_id}", headers=analyst_headers)
    assert res_get.status_code == 200
    data = res_get.json()
    assert data["warehouse_code"] == "WH-EAST-01"
    assert data["network_node"]["name"] == "Hub Whitefield"
    assert data["available_capacity"] == 7500.0
    assert data["utilization_percentage"] == 25.0

    # 2. Update warehouse
    update_payload = {
        "status": "MAINTENANCE",
        "manager_name": "New Manager",
        "total_capacity": 12000.0,
    }
    res_update = client.patch(
        f"/api/v1/warehouses/{wh_id}",
        json=update_payload,
        headers=warehouse_manager_headers,
    )
    assert res_update.status_code == 200
    updated = res_update.json()
    assert updated["status"] == "MAINTENANCE"
    assert updated["manager_name"] == "New Manager"
    assert updated["total_capacity"] == 12000.0

    # 3. Reducing total_capacity below current used_capacity rejected (400)
    res_invalid_cap = client.patch(
        f"/api/v1/warehouses/{wh_id}",
        json={"total_capacity": 1000.0},  # used is 2500.0
        headers=warehouse_manager_headers,
    )
    assert res_invalid_cap.status_code == 400
    assert "cannot be less than currently used capacity" in res_invalid_cap.json()["error"]["message"]

    # 4. Non-existent warehouse returns 404
    res_404 = client.get("/api/v1/warehouses/missing-wh-id", headers=analyst_headers)
    assert res_404.status_code == 404


def test_list_warehouse_inventory(
    client: TestClient, db_session: Session, analyst_headers: dict
):
    fixtures = setup_warehouse_fixtures(db_session)
    wh_id = fixtures["wh1"].id

    res_inv = client.get(f"/api/v1/warehouses/{wh_id}/inventory", headers=analyst_headers)
    assert res_inv.status_code == 200
    data = res_inv.json()
    assert data["total"] == 3
    skus = [item["sku"] for item in data["items"]]
    assert "SKU-101" in skus
    assert "SKU-102" in skus
    assert "SKU-103" in skus


def test_warehouse_summary_metrics(
    client: TestClient, db_session: Session, analyst_headers: dict
):
    fixtures = setup_warehouse_fixtures(db_session)

    res = client.get("/api/v1/warehouses/summary", headers=analyst_headers)
    assert res.status_code == 200
    data = res.json()

    assert data["total_warehouses"] == 2
    assert data["operational_warehouses"] == 1
    assert data["degraded_warehouses"] == 1
    assert data["closed_warehouses"] == 0
    assert data["total_storage_capacity"] == 18000.0
    assert data["used_storage_capacity"] == 6500.0
    assert data["available_storage_capacity"] == 11500.0
    assert data["average_utilization_percentage"] == round((6500.0 / 18000.0) * 100, 2)
    assert data["total_inventory_records"] == 3
    assert data["low_stock_items"] == 1
    assert data["out_of_stock_items"] == 1
    assert data["data_source"] == "SIMULATED"


def test_warehouse_summary_empty_database_no_division_by_zero(
    client: TestClient, analyst_headers: dict
):
    # Call summary when database has zero warehouses
    res = client.get("/api/v1/warehouses/summary", headers=analyst_headers)
    assert res.status_code == 200
    data = res.json()
    assert data["total_warehouses"] == 0
    assert data["total_storage_capacity"] == 0.0
    assert data["average_utilization_percentage"] is None

