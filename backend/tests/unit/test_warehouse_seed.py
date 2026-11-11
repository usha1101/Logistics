from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.network import NetworkNode, NodeType
from app.models.warehouse import InventoryItem, Warehouse
from app.scripts.seed_demo_network import seed_demo_network
from app.scripts.seed_demo_warehouse import seed_demo_warehouse


def test_seed_demo_warehouse_creates_and_is_idempotent(db_session: Session):
    # Prerequisite: Seed network so the 3 warehouse NetworkNodes exist
    seed_demo_network(db_session)

    # First run of warehouse seeding
    stats_first = seed_demo_warehouse(db_session)
    assert stats_first["warehouses_created"] == 3
    assert stats_first["inventory_created"] == 15
    assert stats_first["skipped"] == 0

    warehouses = db_session.execute(select(Warehouse)).scalars().all()
    assert len(warehouses) == 3
    wh_codes = {w.warehouse_code for w in warehouses}
    assert wh_codes == {"WH-001", "WH-002", "WH-003"}

    items = db_session.execute(select(InventoryItem)).scalars().all()
    assert len(items) == 15

    # Second run of warehouse seeding: must be strictly idempotent
    stats_second = seed_demo_warehouse(db_session)
    assert stats_second["warehouses_created"] == 0
    assert stats_second["inventory_created"] == 0
    assert stats_second["skipped"] == 18

    # Verify no new NetworkNodes were created
    total_nodes = db_session.execute(
        select(NetworkNode).where(NetworkNode.node_type == NodeType.WAREHOUSE.value)
    ).scalars().all()
    assert len(total_nodes) == 3

