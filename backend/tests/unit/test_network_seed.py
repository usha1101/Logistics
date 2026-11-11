from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.network import NetworkEdge, NetworkNode, NodeType
from app.models.user import User, UserRole
from app.scripts.seed_demo_network import seed_demo_network


def test_seed_demo_network_creates_expected_records(db_session: Session):
    stats = seed_demo_network(db_session)

    assert stats["warehouses_created"] == 3
    assert stats["customers_created"] == 15
    assert stats["connections_created"] == 25
    assert stats["skipped"] == 0

    warehouses = db_session.execute(
        select(NetworkNode).where(NetworkNode.node_type == NodeType.WAREHOUSE.value)
    ).scalars().all()
    assert len(warehouses) == 3

    customers = db_session.execute(
        select(NetworkNode).where(NetworkNode.node_type == NodeType.CUSTOMER.value)
    ).scalars().all()
    assert len(customers) == 15

    connections = db_session.execute(select(NetworkEdge)).scalars().all()
    assert len(connections) == 25


def test_seed_demo_network_is_idempotent(db_session: Session):
    # Initial seeding
    stats_first = seed_demo_network(db_session)
    assert stats_first["warehouses_created"] == 3

    # Rerunning seeding must create 0 new records and skip existing
    stats_second = seed_demo_network(db_session)
    assert stats_second["warehouses_created"] == 0
    assert stats_second["customers_created"] == 0
    assert stats_second["connections_created"] == 0
    assert stats_second["skipped"] == 43


def test_seeding_preserves_unrelated_records(db_session: Session):
    # Create an unrelated custom user and custom node
    custom_user = User(
        username="unrelated_user",
        email="unrelated@logipulse.io",
        full_name="Unrelated User",
        role=UserRole.ANALYST.value,
        hashed_password="some_hash_value",
        is_active=True,
    )
    custom_node = NetworkNode(
        name="Independent Hub",
        node_type=NodeType.WAREHOUSE.value,
        latitude=12.5,
        longitude=77.5,
        is_active=True,
    )
    db_session.add_all([custom_user, custom_node])
    db_session.commit()

    # Run seed
    seed_demo_network(db_session)

    # Verify custom records were not modified or deleted
    user_check = db_session.execute(
        select(User).where(User.username == "unrelated_user")
    ).scalar_one_or_none()
    assert user_check is not None

    node_check = db_session.execute(
        select(NetworkNode).where(NetworkNode.name == "Independent Hub")
    ).scalar_one_or_none()
    assert node_check is not None

