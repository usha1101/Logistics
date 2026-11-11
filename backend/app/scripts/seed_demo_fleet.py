"""Demo fleet seeding script for LOGIPULSE.

Seeds eight deterministic vehicles across the three existing Bengaluru distribution hubs.
Strictly idempotent: safe to execute multiple times.
"""

from datetime import datetime, timezone
from typing import Dict, List, Tuple
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database.session import SessionLocal
from app.models.user import User
from app.models.vehicle import (
    LocationSource,
    Vehicle,
    VehicleLocation,
    VehicleStatus,
    VehicleStatusHistory,
    VehicleType,
)
from app.models.warehouse import Warehouse

DEMO_VEHICLES = [
    {
        "vehicle_code": "TRK-001",
        "registration_number": "KA-01-EQ-1001",
        "vehicle_type": VehicleType.HEAVY_TRUCK.value,
        "manufacturer": "Tata Motors",
        "model": "Prima 2830.K",
        "capacity_kg": 1500.0,
        "current_load_kg": 650.0,
        "status": VehicleStatus.IN_TRANSIT.value,
        "warehouse_code": "WH-001",
        "latitude": 12.9680,
        "longitude": 77.7410,
        "speed_kmph": 45.0,
        "heading_degrees": 85.0,
    },
    {
        "vehicle_code": "TRK-002",
        "registration_number": "KA-01-EQ-1002",
        "vehicle_type": VehicleType.HEAVY_TRUCK.value,
        "manufacturer": "BharatBenz",
        "model": "2823R Heavy Hauler",
        "capacity_kg": 2000.0,
        "current_load_kg": 0.0,
        "status": VehicleStatus.AVAILABLE.value,
        "warehouse_code": "WH-001",
        "latitude": 12.9698,
        "longitude": 77.7499,
        "speed_kmph": 0.0,
        "heading_degrees": 0.0,
    },
    {
        "vehicle_code": "TRK-003",
        "registration_number": "KA-04-MB-2001",
        "vehicle_type": VehicleType.MEDIUM_TRUCK.value,
        "manufacturer": "Ashok Leyland",
        "model": "Boss 1215 HB",
        "capacity_kg": 1000.0,
        "current_load_kg": 0.0,
        "status": VehicleStatus.IDLE.value,
        "warehouse_code": "WH-003",
        "latitude": 13.0285,
        "longitude": 77.5190,
        "speed_kmph": 0.0,
        "heading_degrees": 180.0,
    },
    {
        "vehicle_code": "VAN-001",
        "registration_number": "KA-05-DV-3001",
        "vehicle_type": VehicleType.DELIVERY_VAN.value,
        "manufacturer": "Mahindra",
        "model": "Bolero Maxi Truck Plus",
        "capacity_kg": 500.0,
        "current_load_kg": 220.0,
        "status": VehicleStatus.IN_TRANSIT.value,
        "warehouse_code": "WH-002",
        "latitude": 12.8510,
        "longitude": 77.6620,
        "speed_kmph": 38.0,
        "heading_degrees": 270.0,
    },
    {
        "vehicle_code": "VAN-002",
        "registration_number": "KA-05-DV-3002",
        "vehicle_type": VehicleType.DELIVERY_VAN.value,
        "manufacturer": "Force Motors",
        "model": "Trax Delivery Van",
        "capacity_kg": 500.0,
        "current_load_kg": 0.0,
        "status": VehicleStatus.AVAILABLE.value,
        "warehouse_code": "WH-002",
        "latitude": 12.8440,
        "longitude": 77.6760,
        "speed_kmph": 0.0,
        "heading_degrees": 0.0,
    },
    {
        "vehicle_code": "VAN-003",
        "registration_number": "KA-04-DV-3003",
        "vehicle_type": VehicleType.DELIVERY_VAN.value,
        "manufacturer": "Isuzu",
        "model": "D-Max Commercial Cargo",
        "capacity_kg": 400.0,
        "current_load_kg": 0.0,
        "status": VehicleStatus.MAINTENANCE.value,
        "warehouse_code": "WH-003",
        "latitude": 13.0270,
        "longitude": 77.5180,
        "speed_kmph": 0.0,
        "heading_degrees": 0.0,
    },
    {
        "vehicle_code": "EV-001",
        "registration_number": "KA-05-EV-4001",
        "vehicle_type": VehicleType.ELECTRIC_VAN.value,
        "manufacturer": "Euler Motors",
        "model": "HiLoad EV Turbo",
        "capacity_kg": 300.0,
        "current_load_kg": 0.0,
        "status": VehicleStatus.AVAILABLE.value,
        "warehouse_code": "WH-002",
        "latitude": 12.8450,
        "longitude": 77.6780,
        "speed_kmph": 0.0,
        "heading_degrees": 90.0,
    },
    {
        "vehicle_code": "EV-002",
        "registration_number": "KA-01-EV-4002",
        "vehicle_type": VehicleType.ELECTRIC_VAN.value,
        "manufacturer": "Tata Motors",
        "model": "Ace EV Cargo",
        "capacity_kg": 300.0,
        "current_load_kg": 110.0,
        "status": VehicleStatus.BREAKDOWN.value,
        "warehouse_code": "WH-001",
        "latitude": 12.9550,
        "longitude": 77.7200,
        "speed_kmph": 0.0,
        "heading_degrees": 45.0,
    },
]


def seed_demo_fleet(db: Session) -> Tuple[int, int]:
    """Seed demo fleet vehicles. Returns (created_count, skipped_count)."""
    # 1. Lookup warehouses by warehouse_code
    warehouses = {wh.warehouse_code: wh for wh in db.execute(select(Warehouse)).scalars().all()}
    if not warehouses:
        print("[!] No warehouses found. Please run seed_demo_warehouse first.")
        return 0, 0

    # Lookup admin user for initial status attribution if available
    admin_user = db.execute(select(User).where(User.username == "admin")).scalar_one_or_none()
    admin_id = admin_user.id if admin_user else None

    created_count = 0
    skipped_count = 0
    now = datetime.now(timezone.utc)

    for item in DEMO_VEHICLES:
        code = item["vehicle_code"]
        existing = db.execute(select(Vehicle).where(Vehicle.vehicle_code == code)).scalar_one_or_none()
        if existing:
            skipped_count += 1
            continue

        wh = warehouses.get(item["warehouse_code"])
        wh_id = wh.id if wh else None

        vehicle = Vehicle(
            vehicle_code=code,
            registration_number=item["registration_number"],
            vehicle_type=item["vehicle_type"],
            manufacturer=item["manufacturer"],
            model=item["model"],
            capacity_kg=item["capacity_kg"],
            current_load_kg=item["current_load_kg"],
            status=item["status"],
            home_warehouse_id=wh_id,
            current_latitude=item["latitude"],
            current_longitude=item["longitude"],
            current_speed_kmph=item["speed_kmph"],
            heading_degrees=item["heading_degrees"],
            is_active=True,
            last_location_update=now,
        )
        db.add(vehicle)
        db.flush()

        # Create initial location telemetry record
        location = VehicleLocation(
            vehicle_id=vehicle.id,
            latitude=item["latitude"],
            longitude=item["longitude"],
            speed_kmph=item["speed_kmph"],
            heading_degrees=item["heading_degrees"],
            source=LocationSource.SIMULATION.value,
            recorded_at=now,
        )
        db.add(location)

        # Create initial status history record
        status_hist = VehicleStatusHistory(
            vehicle_id=vehicle.id,
            previous_status=None,
            new_status=item["status"],
            reason="Initial fleet onboarding and commissioning",
            changed_by_user_id=admin_id,
            changed_at=now,
        )
        db.add(status_hist)

        created_count += 1

    db.commit()
    return created_count, skipped_count


def main() -> None:
    db = SessionLocal()
    try:
        created, skipped = seed_demo_fleet(db)
        print(f"[*] Demo Fleet Seeding Summary: Created {created} vehicles, Skipped {skipped} existing vehicles.")
    finally:
        db.close()


if __name__ == "__main__":
    main()

