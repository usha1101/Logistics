import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.vehicle import Vehicle, VehicleLocation, VehicleStatusHistory
from app.scripts.seed_demo_fleet import seed_demo_fleet
from app.scripts.seed_demo_network import seed_demo_network
from app.scripts.seed_demo_warehouse import seed_demo_warehouse


def test_seed_demo_fleet_creates_and_is_idempotent(db_session: Session):
    # Setup network and warehouses first
    seed_demo_network(db_session)
    seed_demo_warehouse(db_session)

    # 1. First run creates 8 vehicles
    created, skipped = seed_demo_fleet(db_session)
    assert created == 8
    assert skipped == 0

    vehicles = list(db_session.execute(select(Vehicle)).scalars().all())
    assert len(vehicles) == 8

    locations = list(db_session.execute(select(VehicleLocation)).scalars().all())
    assert len(locations) == 8

    history = list(db_session.execute(select(VehicleStatusHistory)).scalars().all())
    assert len(history) == 8

    # 2. Second run is idempotent
    created2, skipped2 = seed_demo_fleet(db_session)
    assert created2 == 0
    assert skipped2 == 8

    vehicles_after = list(db_session.execute(select(Vehicle)).scalars().all())
    assert len(vehicles_after) == 8

