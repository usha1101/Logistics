from datetime import datetime, timedelta, timezone
import pytest
from sqlalchemy.exc import IntegrityError, OperationalError
from sqlalchemy.orm import Session

from app.models.network import NetworkNode, NodeType
from app.models.order import (
    Customer,
    Order,
    OrderAssignmentHistory,
    OrderItem,
    OrderPriority,
    OrderStatus,
    OrderStatusHistory,
    PERMITTED_STATUS_TRANSITIONS,
)
from app.models.vehicle import Vehicle, VehicleType
from app.models.warehouse import Warehouse, WarehouseStatus, WarehouseType


@pytest.fixture
def order_model_fixtures(db_session: Session):
    node = NetworkNode(
        name="Hub North",
        node_type=NodeType.WAREHOUSE.value,
        latitude=13.01,
        longitude=77.55,
        region="North",
        address="Yeshwantpur",
        is_active=True,
    )
    db_session.add(node)
    db_session.commit()

    wh = Warehouse(
        network_node_id=node.id,
        warehouse_code="WH-NORTH-TEST",
        warehouse_type=WarehouseType.DISTRIBUTION_CENTER.value,
        total_capacity=10000.0,
        used_capacity=1000.0,
        status=WarehouseStatus.OPERATIONAL.value,
    )
    db_session.add(wh)
    db_session.commit()

    cust = Customer(
        customer_code="CUST-TEST-01",
        name="Acme Corp",
        email="contact@acme.com",
        phone="+91-80-12345678",
        address_line="123 Industrial Road",
        city="Bengaluru",
        state="Karnataka",
        postal_code="560001",
        latitude=12.97,
        longitude=77.59,
        is_active=True,
    )
    db_session.add(cust)
    db_session.commit()

    veh = Vehicle(
        vehicle_code="V-TEST-ORD",
        registration_number="KA-01-ORD-1",
        vehicle_type=VehicleType.DELIVERY_VAN.value,
        capacity_kg=500.0,
    )
    db_session.add(veh)
    db_session.commit()

    return {
        "warehouse_id": wh.id,
        "customer_id": cust.id,
        "vehicle_id": veh.id,
    }


def test_customer_creation_and_properties(db_session: Session, order_model_fixtures):
    cust_id = order_model_fixtures["customer_id"]
    cust = db_session.get(Customer, cust_id)
    assert cust is not None
    assert cust.customer_code == "CUST-TEST-01"
    assert cust.coordinates == [77.59, 12.97]
    assert cust.is_active is True


def test_customer_duplicate_code_rejected(db_session: Session, order_model_fixtures):
    dup = Customer(
        customer_code="CUST-TEST-01",
        name="Another Company",
        phone="123456",
        address_line="Road",
        city="Bengaluru",
        state="KA",
        postal_code="560001",
        latitude=12.0,
        longitude=77.0,
    )
    db_session.add(dup)
    with pytest.raises((IntegrityError, OperationalError)):
        db_session.commit()
    db_session.rollback()


def test_customer_invalid_email_and_coordinates(db_session: Session):
    with pytest.raises(ValueError):
        Customer(
            customer_code="BAD-EMAIL",
            name="Bad",
            email="invalid-email-string",
            phone="12345",
            address_line="A",
            city="B",
            state="C",
            postal_code="123",
            latitude=12.0,
            longitude=77.0,
        )

    with pytest.raises(ValueError):
        Customer(
            customer_code="BAD-LAT",
            name="Bad Lat",
            phone="12345",
            address_line="A",
            city="B",
            state="C",
            postal_code="123",
            latitude=95.0,  # Invalid
            longitude=77.0,
        )


def test_order_creation_and_properties(db_session: Session, order_model_fixtures):
    now = datetime.now(timezone.utc)
    order = Order(
        order_number="ORD-TEST-001",
        customer_id=order_model_fixtures["customer_id"],
        warehouse_id=order_model_fixtures["warehouse_id"],
        status=OrderStatus.CREATED.value,
        priority=OrderPriority.HIGH.value,
        expected_delivery_at=now + timedelta(hours=24),
        delivery_address="456 Tech Park",
        delivery_latitude=12.93,
        delivery_longitude=77.62,
        total_weight_kg=50.0,
        total_amount=5000.0,
    )
    db_session.add(order)
    db_session.commit()

    assert order.id is not None
    assert order.coordinates == [77.62, 12.93]
    assert order.is_overdue is False
    assert order.customer.name == "Acme Corp"


def test_duplicate_order_number_rejected(db_session: Session, order_model_fixtures):
    now = datetime.now(timezone.utc)
    o1 = Order(
        order_number="ORD-DUP",
        customer_id=order_model_fixtures["customer_id"],
        warehouse_id=order_model_fixtures["warehouse_id"],
        expected_delivery_at=now + timedelta(hours=10),
        delivery_address="Address 1",
        delivery_latitude=12.9,
        delivery_longitude=77.6,
    )
    db_session.add(o1)
    db_session.commit()

    o2 = Order(
        order_number="ORD-DUP",
        customer_id=order_model_fixtures["customer_id"],
        warehouse_id=order_model_fixtures["warehouse_id"],
        expected_delivery_at=now + timedelta(hours=10),
        delivery_address="Address 2",
        delivery_latitude=12.9,
        delivery_longitude=77.6,
    )
    db_session.add(o2)
    with pytest.raises((IntegrityError, OperationalError)):
        db_session.commit()
    db_session.rollback()


def test_order_items_calculation_and_validation(db_session: Session, order_model_fixtures):
    now = datetime.now(timezone.utc)
    order = Order(
        order_number="ORD-ITEMS-TEST",
        customer_id=order_model_fixtures["customer_id"],
        warehouse_id=order_model_fixtures["warehouse_id"],
        expected_delivery_at=now + timedelta(hours=12),
        delivery_address="Address Items",
        delivery_latitude=12.9,
        delivery_longitude=77.6,
    )
    db_session.add(order)
    db_session.commit()

    item1 = OrderItem(
        order_id=order.id,
        product_code="PROD-1",
        product_name="Inverter",
        quantity=3,
        unit_price=1000.0,
        unit_weight_kg=5.0,
        subtotal=3000.0,
        total_weight_kg=15.0,
    )
    db_session.add(item1)
    db_session.commit()

    assert item1.id is not None
    assert item1.subtotal == 3000.0
    assert item1.total_weight_kg == 15.0


def test_negative_quantity_and_weights_rejected(db_session: Session, order_model_fixtures):
    now = datetime.now(timezone.utc)
    order = Order(
        order_number="ORD-BAD-ITEM",
        customer_id=order_model_fixtures["customer_id"],
        warehouse_id=order_model_fixtures["warehouse_id"],
        expected_delivery_at=now + timedelta(hours=12),
        delivery_address="Address",
        delivery_latitude=12.9,
        delivery_longitude=77.6,
    )
    db_session.add(order)
    db_session.commit()

    with pytest.raises(ValueError):
        OrderItem(
            order_id=order.id,
            product_code="BAD",
            product_name="Bad",
            quantity=-1,
            unit_price=10.0,
            unit_weight_kg=1.0,
            subtotal=0.0,
            total_weight_kg=0.0,
        )


def test_order_status_history_model(db_session: Session, order_model_fixtures):
    now = datetime.now(timezone.utc)
    order = Order(
        order_number="ORD-HIST-TEST",
        customer_id=order_model_fixtures["customer_id"],
        warehouse_id=order_model_fixtures["warehouse_id"],
        expected_delivery_at=now + timedelta(hours=12),
        delivery_address="Address",
        delivery_latitude=12.9,
        delivery_longitude=77.6,
    )
    db_session.add(order)
    db_session.commit()

    hist = OrderStatusHistory(
        order_id=order.id,
        previous_status=OrderStatus.CREATED.value,
        new_status=OrderStatus.CONFIRMED.value,
        reason="Customer payment approved",
    )
    db_session.add(hist)
    db_session.commit()

    assert hist.id is not None
    assert hist.new_status == OrderStatus.CONFIRMED.value


def test_order_assignment_history_model(db_session: Session, order_model_fixtures):
    now = datetime.now(timezone.utc)
    order = Order(
        order_number="ORD-ASSIGN-TEST",
        customer_id=order_model_fixtures["customer_id"],
        warehouse_id=order_model_fixtures["warehouse_id"],
        expected_delivery_at=now + timedelta(hours=12),
        delivery_address="Address",
        delivery_latitude=12.9,
        delivery_longitude=77.6,
    )
    db_session.add(order)
    db_session.commit()

    veh_id = order_model_fixtures["vehicle_id"]
    assign = OrderAssignmentHistory(
        order_id=order.id,
        previous_vehicle_id=None,
        new_vehicle_id=veh_id,
        reason="Allocated to morning run",
    )
    db_session.add(assign)
    db_session.commit()

    assert assign.id is not None
    assert assign.new_vehicle_id == veh_id


def test_order_is_overdue_logic(db_session: Session, order_model_fixtures):
    now = datetime.now(timezone.utc)
    # 1. Past deadline -> is_overdue is True
    o_past = Order(
        order_number="ORD-PAST",
        customer_id=order_model_fixtures["customer_id"],
        warehouse_id=order_model_fixtures["warehouse_id"],
        status=OrderStatus.PROCESSING.value,
        expected_delivery_at=now - timedelta(hours=2),
        delivery_address="Address Past",
        delivery_latitude=12.9,
        delivery_longitude=77.6,
    )
    # 2. Future deadline -> is_overdue is False
    o_future = Order(
        order_number="ORD-FUTURE",
        customer_id=order_model_fixtures["customer_id"],
        warehouse_id=order_model_fixtures["warehouse_id"],
        status=OrderStatus.PROCESSING.value,
        expected_delivery_at=now + timedelta(hours=2),
        delivery_address="Address Future",
        delivery_latitude=12.9,
        delivery_longitude=77.6,
    )
    # 3. Delivered order past deadline -> is_overdue is False (delivered orders are never overdue)
    o_del = Order(
        order_number="ORD-DEL",
        customer_id=order_model_fixtures["customer_id"],
        warehouse_id=order_model_fixtures["warehouse_id"],
        status=OrderStatus.DELIVERED.value,
        expected_delivery_at=now - timedelta(hours=2),
        delivery_address="Address Delivered",
        delivery_latitude=12.9,
        delivery_longitude=77.6,
    )
    db_session.add_all([o_past, o_future, o_del])
    db_session.commit()

    assert o_past.is_overdue is True
    assert o_future.is_overdue is False
    assert o_del.is_overdue is False


def test_order_invalid_latitude_longitude(db_session: Session, order_model_fixtures):
    now = datetime.now(timezone.utc)
    with pytest.raises(ValueError):
        Order(
            order_number="ORD-BAD-LAT",
            customer_id=order_model_fixtures["customer_id"],
            warehouse_id=order_model_fixtures["warehouse_id"],
            expected_delivery_at=now + timedelta(hours=5),
            delivery_address="Address",
            delivery_latitude=-95.0,  # Invalid
            delivery_longitude=77.0,
        )


def test_order_negative_amount_and_weight_rejected(db_session: Session, order_model_fixtures):
    now = datetime.now(timezone.utc)
    with pytest.raises(ValueError):
        Order(
            order_number="ORD-NEG-WT",
            customer_id=order_model_fixtures["customer_id"],
            warehouse_id=order_model_fixtures["warehouse_id"],
            expected_delivery_at=now + timedelta(hours=5),
            delivery_address="Address",
            delivery_latitude=12.0,
            delivery_longitude=77.0,
            total_weight_kg=-5.0,
        )


def test_customer_empty_required_fields_rejected(db_session: Session):
    with pytest.raises(ValueError):
        Customer(
            customer_code="",
            name="Valid Name",
            phone="12345",
            address_line="A",
            city="B",
            state="C",
            postal_code="123",
            latitude=12.0,
            longitude=77.0,
        )


def test_order_item_zero_quantity_rejected(db_session: Session, order_model_fixtures):
    now = datetime.now(timezone.utc)
    order = Order(
        order_number="ORD-ZERO-QTY",
        customer_id=order_model_fixtures["customer_id"],
        warehouse_id=order_model_fixtures["warehouse_id"],
        expected_delivery_at=now + timedelta(hours=5),
        delivery_address="Address",
        delivery_latitude=12.0,
        delivery_longitude=77.0,
    )
    db_session.add(order)
    db_session.commit()

    with pytest.raises(ValueError):
        OrderItem(
            order_id=order.id,
            product_code="ZERO",
            product_name="Zero Product",
            quantity=0,
            unit_price=10.0,
            unit_weight_kg=1.0,
            subtotal=0.0,
            total_weight_kg=0.0,
        )


def test_permitted_transitions_state_machine():
    assert OrderStatus.CONFIRMED.value in PERMITTED_STATUS_TRANSITIONS[OrderStatus.CREATED.value]
    assert OrderStatus.CANCELLED.value in PERMITTED_STATUS_TRANSITIONS[OrderStatus.CREATED.value]
    assert OrderStatus.DELIVERED.value not in PERMITTED_STATUS_TRANSITIONS[OrderStatus.CREATED.value]
    assert len(PERMITTED_STATUS_TRANSITIONS[OrderStatus.DELIVERED.value]) == 0
    assert len(PERMITTED_STATUS_TRANSITIONS[OrderStatus.CANCELLED.value]) == 0

