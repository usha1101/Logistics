import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.order import Customer, Order, OrderItem, OrderStatusHistory
from app.scripts.seed_demo_fleet import seed_demo_fleet
from app.scripts.seed_demo_network import seed_demo_network
from app.scripts.seed_demo_orders import seed_demo_orders
from app.scripts.seed_demo_warehouse import seed_demo_warehouse


def test_seed_demo_orders_creates_and_is_idempotent(db_session: Session):
    # Setup dependencies
    seed_demo_network(db_session)
    seed_demo_warehouse(db_session)
    seed_demo_fleet(db_session)

    # 1. First run creates customers and orders
    c_created, o_created, o_skipped = seed_demo_orders(db_session)
    assert c_created == 5
    assert o_created == 16
    assert o_skipped == 0

    customers = list(db_session.execute(select(Customer)).scalars().all())
    assert len(customers) == 5

    orders = list(db_session.execute(select(Order)).scalars().all())
    assert len(orders) == 16

    items = list(db_session.execute(select(OrderItem)).scalars().all())
    assert len(items) >= 16

    hist = list(db_session.execute(select(OrderStatusHistory)).scalars().all())
    assert len(hist) >= 16

    # 2. Second run is strictly idempotent
    c_created2, o_created2, o_skipped2 = seed_demo_orders(db_session)
    assert c_created2 == 0
    assert o_created2 == 0
    assert o_skipped2 == 16

    orders_after = list(db_session.execute(select(Order)).scalars().all())
    assert len(orders_after) == 16

