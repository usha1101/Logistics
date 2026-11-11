import pytest
from sqlalchemy.exc import IntegrityError, OperationalError
from sqlalchemy.orm import Session

from app.models.network import NetworkNode, NodeType
from app.models.vehicle import (
    LocationSource,
    Vehicle,
    VehicleLocation,
    VehicleStatus,
    VehicleStatusHistory,
    VehicleType,
)
from app.models.warehouse import Warehouse, WarehouseStatus, WarehouseType


@pytest.fixture
def sample_warehouse(db_session: Session) -> Warehouse:
    node = NetworkNode(
        name="Hub South",
        node_type=NodeType.WAREHOUSE.value,
        latitude=12.92,
        longitude=77.61,
        region="South",
        address="Bannerghatta Road",
        is_active=True,
    )
    db_session.add(node)
    db_session.commit()

    wh = Warehouse(
        network_node_id=node.id,
        warehouse_code="WH-TEST-SOUTH",
        warehouse_type=WarehouseType.DISTRIBUTION_CENTER.value,
        total_capacity=5000.0,
        used_capacity=1000.0,
        status=WarehouseStatus.OPERATIONAL.value,
    )
    db_session.add(wh)
    db_session.commit()
    return wh


def test_vehicle_creation_and_properties(db_session: Session, sample_warehouse: Warehouse):
    vehicle = Vehicle(
        vehicle_code="TEST-V-01",
        registration_number="KA-01-AB-1234",
        vehicle_type=VehicleType.HEAVY_TRUCK.value,
        manufacturer="Tata Motors",
        model="Prima",
        capacity_kg=2500.0,
        current_load_kg=500.0,
        status=VehicleStatus.AVAILABLE.value,
        home_warehouse_id=sample_warehouse.id,
        current_latitude=12.92,
        current_longitude=77.61,
        current_speed_kmph=40.0,
        heading_degrees=90.0,
    )
    db_session.add(vehicle)
    db_session.commit()

    assert vehicle.id is not None
    assert vehicle.remaining_capacity_kg == 2000.0
    assert vehicle.coordinates == [77.61, 12.92]
    assert vehicle.home_warehouse.warehouse_code == "WH-TEST-SOUTH"


def test_duplicate_vehicle_code_rejected(db_session: Session):
    v1 = Vehicle(
        vehicle_code="DUP-01",
        registration_number="KA-01-DUP-1",
        vehicle_type=VehicleType.DELIVERY_VAN.value,
        capacity_kg=500.0,
    )
    db_session.add(v1)
    db_session.commit()

    v2 = Vehicle(
        vehicle_code="DUP-01",
        registration_number="KA-01-DUP-2",
        vehicle_type=VehicleType.DELIVERY_VAN.value,
        capacity_kg=600.0,
    )
    db_session.add(v2)
    with pytest.raises((IntegrityError, OperationalError)):
        db_session.commit()
    db_session.rollback()


def test_duplicate_registration_number_rejected(db_session: Session):
    v1 = Vehicle(
        vehicle_code="CODE-A",
        registration_number="KA-01-REG-DUP",
        vehicle_type=VehicleType.ELECTRIC_VAN.value,
        capacity_kg=300.0,
    )
    db_session.add(v1)
    db_session.commit()

    v2 = Vehicle(
        vehicle_code="CODE-B",
        registration_number="KA-01-REG-DUP",
        vehicle_type=VehicleType.ELECTRIC_VAN.value,
        capacity_kg=350.0,
    )
    db_session.add(v2)
    with pytest.raises((IntegrityError, OperationalError)):
        db_session.commit()
    db_session.rollback()


def test_positive_capacity_validation(db_session: Session):
    with pytest.raises(ValueError):
        Vehicle(
            vehicle_code="BAD-CAP",
            registration_number="KA-01-BAD-CAP",
            vehicle_type=VehicleType.MEDIUM_TRUCK.value,
            capacity_kg=-100.0,
        )


def test_current_load_exceeding_capacity_rejected(db_session: Session):
    with pytest.raises(ValueError):
        Vehicle(
            vehicle_code="OVERLOAD",
            registration_number="KA-01-OVERLOAD",
            vehicle_type=VehicleType.DELIVERY_VAN.value,
            capacity_kg=500.0,
            current_load_kg=600.0,
        )


def test_invalid_coordinates_rejected(db_session: Session):
    # Latitude > 90
    with pytest.raises(ValueError):
        Vehicle(
            vehicle_code="BAD-LAT",
            registration_number="KA-01-BAD-LAT",
            vehicle_type=VehicleType.DELIVERY_VAN.value,
            capacity_kg=500.0,
            current_latitude=95.0,
            current_longitude=77.0,
        )

    # Longitude < -180
    with pytest.raises(ValueError):
        Vehicle(
            vehicle_code="BAD-LON",
            registration_number="KA-01-BAD-LON",
            vehicle_type=VehicleType.DELIVERY_VAN.value,
            capacity_kg=500.0,
            current_latitude=12.0,
            current_longitude=-185.0,
        )


def test_negative_speed_and_invalid_heading_rejected(db_session: Session):
    with pytest.raises(ValueError):
        Vehicle(
            vehicle_code="BAD-SPD",
            registration_number="KA-01-BAD-SPD",
            vehicle_type=VehicleType.DELIVERY_VAN.value,
            capacity_kg=500.0,
            current_speed_kmph=-5.0,
        )

    with pytest.raises(ValueError):
        Vehicle(
            vehicle_code="BAD-HDG",
            registration_number="KA-01-BAD-HDG",
            vehicle_type=VehicleType.DELIVERY_VAN.value,
            capacity_kg=500.0,
            heading_degrees=365.0,
        )


def test_vehicle_location_history_model(db_session: Session):
    v = Vehicle(
        vehicle_code="LOC-TEST-01",
        registration_number="KA-01-LOC-01",
        vehicle_type=VehicleType.DELIVERY_VAN.value,
        capacity_kg=500.0,
    )
    db_session.add(v)
    db_session.commit()

    loc1 = VehicleLocation(
        vehicle_id=v.id,
        latitude=12.9716,
        longitude=77.5946,
        speed_kmph=30.0,
        heading_degrees=45.0,
        source=LocationSource.SIMULATION.value,
    )
    db_session.add(loc1)
    db_session.commit()

    assert loc1.id is not None
    assert loc1.coordinates == [77.5946, 12.9716]
    assert loc1.vehicle.vehicle_code == "LOC-TEST-01"


def test_vehicle_status_history_model(db_session: Session):
    v = Vehicle(
        vehicle_code="STAT-TEST-01",
        registration_number="KA-01-STAT-01",
        vehicle_type=VehicleType.HEAVY_TRUCK.value,
        capacity_kg=2000.0,
    )
    db_session.add(v)
    db_session.commit()

    hist = VehicleStatusHistory(
        vehicle_id=v.id,
        previous_status=VehicleStatus.AVAILABLE.value,
        new_status=VehicleStatus.IN_TRANSIT.value,
        reason="Dispatched on Route 4",
    )
    db_session.add(hist)
    db_session.commit()

    assert hist.id is not None
    assert hist.new_status == VehicleStatus.IN_TRANSIT.value
    assert hist.vehicle.vehicle_code == "STAT-TEST-01"

