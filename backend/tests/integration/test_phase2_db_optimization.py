from datetime import datetime, timezone
import pytest
from sqlalchemy.orm import Session

from app.models.order import Customer, Order, OrderPriority, OrderStatus
from app.models.simulation import SimulationTelemetry
from app.models.vehicle import Vehicle, VehicleStatus, VehicleType
from app.models.warehouse import InventoryItem, Warehouse, WarehouseType


def test_vehicle_soft_delete_and_restore(db_session: Session):
    """Verify Vehicle model supports soft_delete() and restore() lifecycle."""
    vehicle = Vehicle(
        vehicle_code="TEST-VEH-001",
        registration_number="KA-01-AB-1234",
        vehicle_type=VehicleType.DELIVERY_VAN.value,
        capacity_kg=1500.0,
        status=VehicleStatus.AVAILABLE.value,
    )
    db_session.add(vehicle)
    db_session.commit()
    db_session.refresh(vehicle)

    # Initial state
    assert vehicle.is_deleted is False
    assert vehicle.deleted_at is None

    # Soft delete
    vehicle.soft_delete()
    db_session.commit()
    db_session.refresh(vehicle)

    assert vehicle.is_deleted is True
    assert isinstance(vehicle.deleted_at, datetime)

    # Restore
    vehicle.restore()
    db_session.commit()
    db_session.refresh(vehicle)

    assert vehicle.is_deleted is False
    assert vehicle.deleted_at is None


def test_warehouse_soft_delete_and_restore(db_session: Session):
    """Verify Warehouse model supports soft_delete() and restore()."""
    # Create required network node first
    from app.models.network import NetworkNode, NodeType
    node = NetworkNode(
        name="Test Warehouse Node",
        node_type=NodeType.WAREHOUSE.value,
        latitude=12.9716,
        longitude=77.5946,
    )
    db_session.add(node)
    db_session.commit()

    warehouse = Warehouse(
        network_node_id=node.id,
        warehouse_code="WH-TEST-001",
        warehouse_type=WarehouseType.DISTRIBUTION_CENTER.value,
        total_capacity=10000.0,
        used_capacity=100.0,
    )
    db_session.add(warehouse)
    db_session.commit()
    db_session.refresh(warehouse)

    assert warehouse.is_deleted is False
    assert warehouse.deleted_at is None

    warehouse.soft_delete()
    db_session.commit()
    db_session.refresh(warehouse)

    assert warehouse.is_deleted is True
    assert warehouse.deleted_at is not None

    warehouse.restore()
    db_session.commit()
    db_session.refresh(warehouse)

    assert warehouse.is_deleted is False
    assert warehouse.deleted_at is None


def test_customer_and_order_soft_delete(db_session: Session):
    """Verify Customer and Order models support soft_delete() and restore()."""
    customer = Customer(
        customer_code="CUST-TEST-001",
        name="Acme Corp Logistics",
        phone="+919876543210",
        address_line="123 MG Road",
        city="Bengaluru",
        state="Karnataka",
        postal_code="560001",
        latitude=12.9716,
        longitude=77.5946,
    )
    db_session.add(customer)
    db_session.commit()

    # Create network node and warehouse for order
    from app.models.network import NetworkNode, NodeType
    node = NetworkNode(
        name="Test Node for Order",
        node_type=NodeType.WAREHOUSE.value,
        latitude=12.9716,
        longitude=77.5946,
    )
    db_session.add(node)
    db_session.commit()

    warehouse = Warehouse(
        network_node_id=node.id,
        warehouse_code="WH-ORD-TEST-001",
        warehouse_type=WarehouseType.FULFILLMENT_CENTER.value,
        total_capacity=5000.0,
    )
    db_session.add(warehouse)
    db_session.commit()

    order = Order(
        order_number="ORD-TEST-001",
        customer_id=customer.id,
        warehouse_id=warehouse.id,
        status=OrderStatus.CREATED.value,
        priority=OrderPriority.HIGH.value,
        expected_delivery_at=datetime.now(timezone.utc),
        delivery_address="456 Indiranagar",
        delivery_latitude=12.9784,
        delivery_longitude=77.6408,
    )
    db_session.add(order)
    db_session.commit()

    # Verify Customer soft delete
    customer.soft_delete()
    assert customer.is_deleted is True
    customer.restore()
    assert customer.is_deleted is False

    # Verify Order soft delete
    order.soft_delete()
    assert order.is_deleted is True
    assert order.deleted_at is not None
    order.restore()
    assert order.is_deleted is False
    assert order.deleted_at is None


def test_compound_indexes_metadata():
    """Verify all Phase 2 high-throughput compound indexes are registered on models."""
    order_indexes = {idx.name for idx in Order.__table__.indexes}
    assert "ix_orders_customer_created" in order_indexes
    assert "ix_orders_status_created" in order_indexes
    assert "ix_orders_assigned_vehicle_status" in order_indexes
    assert "ix_orders_deleted_status" in order_indexes

    vehicle_indexes = {idx.name for idx in Vehicle.__table__.indexes}
    assert "ix_vehicles_status_deleted" in vehicle_indexes
    assert "ix_vehicles_type_status" in vehicle_indexes

    warehouse_indexes = {idx.name for idx in Warehouse.__table__.indexes}
    assert "ix_warehouses_type_deleted" in warehouse_indexes

    inventory_indexes = {idx.name for idx in InventoryItem.__table__.indexes}
    assert "ix_inventory_items_wh_quantity" in inventory_indexes

    telemetry_indexes = {idx.name for idx in SimulationTelemetry.__table__.indexes}
    assert "ix_sim_telemetry_sim_recorded" in telemetry_indexes
