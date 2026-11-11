import pytest
from sqlalchemy.exc import IntegrityError, OperationalError
from sqlalchemy.orm import Session

from app.models.network import NetworkNode, NodeType
from app.models.warehouse import (
    InventoryItem,
    Warehouse,
    WarehouseStatus,
    WarehouseType,
)


def test_warehouse_creation_and_node_linkage(db_session: Session):
    node = NetworkNode(
        name="Test WH Node",
        node_type=NodeType.WAREHOUSE.value,
        latitude=12.95,
        longitude=77.65,
    )
    db_session.add(node)
    db_session.commit()

    warehouse = Warehouse(
        network_node_id=node.id,
        warehouse_code="WH-TEST-01",
        warehouse_type=WarehouseType.DISTRIBUTION_CENTER.value,
        total_capacity=5000.0,
        used_capacity=100.0,
        status=WarehouseStatus.OPERATIONAL.value,
        manager_name="Kiran Kumar",
    )
    db_session.add(warehouse)
    db_session.commit()
    db_session.refresh(warehouse)

    assert warehouse.id is not None
    assert warehouse.network_node_id == node.id
    assert warehouse.warehouse_code == "WH-TEST-01"
    assert warehouse.total_capacity == 5000.0
    assert warehouse.used_capacity == 100.0
    assert warehouse.network_node.name == "Test WH Node"


def test_duplicate_warehouse_code_rejected(db_session: Session):
    node1 = NetworkNode(name="Node 1", node_type=NodeType.WAREHOUSE.value, latitude=12.0, longitude=77.0)
    node2 = NetworkNode(name="Node 2", node_type=NodeType.WAREHOUSE.value, latitude=12.1, longitude=77.1)
    db_session.add_all([node1, node2])
    db_session.commit()

    wh1 = Warehouse(network_node_id=node1.id, warehouse_code="WH-DUP", total_capacity=1000.0)
    wh2 = Warehouse(network_node_id=node2.id, warehouse_code="WH-DUP", total_capacity=2000.0)

    db_session.add(wh1)
    db_session.commit()

    db_session.add(wh2)
    with pytest.raises(IntegrityError):
        db_session.commit()
    db_session.rollback()


def test_duplicate_network_node_linkage_rejected(db_session: Session):
    node = NetworkNode(name="Single Node", node_type=NodeType.WAREHOUSE.value, latitude=12.0, longitude=77.0)
    db_session.add(node)
    db_session.commit()

    wh1 = Warehouse(network_node_id=node.id, warehouse_code="WH-A", total_capacity=1000.0)
    wh2 = Warehouse(network_node_id=node.id, warehouse_code="WH-B", total_capacity=2000.0)

    db_session.add(wh1)
    db_session.commit()

    db_session.add(wh2)
    with pytest.raises(IntegrityError):
        db_session.commit()
    db_session.rollback()


def test_invalid_capacity_rejected(db_session: Session):
    node = NetworkNode(name="WH Node Cap", node_type=NodeType.WAREHOUSE.value, latitude=12.0, longitude=77.0)
    db_session.add(node)
    db_session.commit()

    # Total capacity <= 0 rejected
    with pytest.raises(ValueError, match="total_capacity"):
        Warehouse(network_node_id=node.id, warehouse_code="WH-NEG", total_capacity=-500.0)

    # Negative used capacity rejected
    with pytest.raises(ValueError, match="used_capacity"):
        Warehouse(network_node_id=node.id, warehouse_code="WH-NEG2", total_capacity=1000.0, used_capacity=-10.0)

    # Used capacity exceeding total capacity rejected
    with pytest.raises(ValueError, match="cannot exceed total_capacity"):
        Warehouse(network_node_id=node.id, warehouse_code="WH-EXCEED", total_capacity=500.0, used_capacity=600.0)


def test_inventory_item_creation_and_status(db_session: Session):
    node = NetworkNode(name="WH Node Inv", node_type=NodeType.WAREHOUSE.value, latitude=12.0, longitude=77.0)
    db_session.add(node)
    db_session.commit()

    wh = Warehouse(network_node_id=node.id, warehouse_code="WH-INV", total_capacity=5000.0)
    db_session.add(wh)
    db_session.commit()

    # Normal in stock item
    item_in_stock = InventoryItem(
        warehouse_id=wh.id,
        sku="SKU-NORMAL",
        product_name="Product A",
        quantity=50,
        reorder_level=20,
    )
    # Low stock item
    item_low_stock = InventoryItem(
        warehouse_id=wh.id,
        sku="SKU-LOW",
        product_name="Product B",
        quantity=15,
        reorder_level=20,
    )
    # Out of stock item
    item_out_of_stock = InventoryItem(
        warehouse_id=wh.id,
        sku="SKU-OUT",
        product_name="Product C",
        quantity=0,
        reorder_level=20,
    )

    db_session.add_all([item_in_stock, item_low_stock, item_out_of_stock])
    db_session.commit()

    assert item_in_stock.status == "IN_STOCK"
    assert item_low_stock.status == "LOW_STOCK"
    assert item_out_of_stock.status == "OUT_OF_STOCK"


def test_sku_uniqueness_within_warehouse_and_across_warehouses(db_session: Session):
    node1 = NetworkNode(name="W1", node_type=NodeType.WAREHOUSE.value, latitude=12.0, longitude=77.0)
    node2 = NetworkNode(name="W2", node_type=NodeType.WAREHOUSE.value, latitude=12.1, longitude=77.1)
    db_session.add_all([node1, node2])
    db_session.commit()

    wh1 = Warehouse(network_node_id=node1.id, warehouse_code="WH-1", total_capacity=1000.0)
    wh2 = Warehouse(network_node_id=node2.id, warehouse_code="WH-2", total_capacity=1000.0)
    db_session.add_all([wh1, wh2])
    db_session.commit()

    # Same SKU in different warehouses is ALLOWED
    item1 = InventoryItem(warehouse_id=wh1.id, sku="COMMON-SKU", product_name="Item 1")
    item2 = InventoryItem(warehouse_id=wh2.id, sku="COMMON-SKU", product_name="Item 2")
    db_session.add_all([item1, item2])
    db_session.commit()
    assert item1.id != item2.id

    # Same SKU in same warehouse is REJECTED
    duplicate_item = InventoryItem(warehouse_id=wh1.id, sku="COMMON-SKU", product_name="Item Duplicate")
    db_session.add(duplicate_item)
    with pytest.raises(IntegrityError):
        db_session.commit()
    db_session.rollback()


def test_negative_quantity_and_reorder_level_rejected(db_session: Session):
    node = NetworkNode(name="W-Neg", node_type=NodeType.WAREHOUSE.value, latitude=12.0, longitude=77.0)
    db_session.add(node)
    db_session.commit()
    wh = Warehouse(network_node_id=node.id, warehouse_code="WH-NEG-INV", total_capacity=1000.0)
    db_session.add(wh)
    db_session.commit()

    with pytest.raises(ValueError, match="quantity"):
        InventoryItem(warehouse_id=wh.id, sku="SKU-NEG", product_name="P", quantity=-5)

    with pytest.raises(ValueError, match="reorder_level"):
        InventoryItem(warehouse_id=wh.id, sku="SKU-NEG2", product_name="P", reorder_level=-1)

