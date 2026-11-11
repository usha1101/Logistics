"""Demo disruption seeding script for LOGIPULSE.

Seeds realistic Bengaluru logistics disruption scenarios across vehicles, routes,
warehouses, and customer orders.
Strictly idempotent: safe to execute multiple times without duplicating records.
"""

from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database.session import SessionLocal
from app.models.disruption import (
    AffectedResourceType,
    Disruption,
    DisruptionEvent,
    DisruptionEventType,
    DisruptionImpact,
    DisruptionSeverity,
    DisruptionStatus,
    DisruptionType,
)
from app.models.vehicle import Vehicle
from app.models.network import NetworkEdge
from app.models.order import Order
from app.models.warehouse import Warehouse

DEMO_DISRUPTIONS: List[Dict[str, Any]] = [
    {
        "disruption_code": "DISR-DEMO-BREAKDOWN-001",
        "disruption_type": DisruptionType.VEHICLE_BREAKDOWN.value,
        "title": "Engine Transmission Failure on Outer Ring Road",
        "description": "Heavy Truck TRK-001 engine overheating and transmission fault on ORR near Marathahalli junction.",
        "severity": DisruptionSeverity.CRITICAL.value,
        "status": DisruptionStatus.ACTIVE.value,
        "target_type": "vehicle",
        "target_code": "TRK-001",
        "parameters": {
            "current_load_kg": 650.0,
            "has_urgent_orders": True,
            "delay_minutes": 120.0,
            "breakdown_cause": "Transmission overheating",
        },
        "delay_minutes": 120.0,
        "location": (12.9560, 77.7010),
    },
    {
        "disruption_code": "DISR-DEMO-TRAFFIC-001",
        "disruption_type": DisruptionType.TRAFFIC_CONGESTION.value,
        "title": "Heavy Congestion on Silk Board to Electronic City Flyover",
        "description": "Major traffic bottleneck due to waterlogging and vehicle stall on Hosur Road artery.",
        "severity": DisruptionSeverity.HIGH.value,
        "status": DisruptionStatus.ACTIVE.value,
        "target_type": "network_edge",
        "parameters": {
            "speed_reduction_pct": 55.0,
            "delay_minutes": 45.0,
            "congestion_cause": "Waterlogging and disabled bus",
        },
        "delay_minutes": 45.0,
        "location": (12.9175, 77.6234),
    },
    {
        "disruption_code": "DISR-DEMO-WAREHOUSE-001",
        "disruption_type": DisruptionType.WAREHOUSE_SHUTDOWN.value,
        "title": "Temporary Power Substation Maintenance at Whitefield Hub",
        "description": "Grid power disruption at Whitefield Fulfillment Hub requiring backup generator staging and automated sorter restart.",
        "severity": DisruptionSeverity.HIGH.value,
        "status": DisruptionStatus.MONITORING.value,
        "target_type": "warehouse",
        "target_code": "WH-001",
        "parameters": {
            "capacity_utilization_pct": 72.0,
            "active_orders": 15,
            "delay_minutes": 90.0,
            "generator_online": True,
        },
        "delay_minutes": 90.0,
        "location": (12.9698, 77.7499),
    },
    {
        "disruption_code": "DISR-DEMO-DEMAND-001",
        "disruption_type": DisruptionType.DEMAND_SURGE.value,
        "title": "Flash Sale Demand Surge in Koramangala & Indiranagar",
        "description": "High-volume priority retail order influx exceeding local delivery buffer by 2.2x.",
        "severity": DisruptionSeverity.HIGH.value,
        "status": DisruptionStatus.DETECTED.value,
        "target_type": "warehouse",
        "target_code": "WH-002",
        "parameters": {
            "surge_multiplier": 2.2,
            "extra_orders": 35,
            "delay_minutes": 60.0,
        },
        "delay_minutes": 60.0,
        "location": (12.8399, 77.6770),
    },
]


def seed_demo_disruptions(db: Session) -> List[Disruption]:
    """Idempotently seeds demo disruption scenarios with impact and event histories."""
    seeded: List[Disruption] = []
    now = datetime.now(timezone.utc)

    for item in DEMO_DISRUPTIONS:
        existing = db.scalars(
            select(Disruption).where(Disruption.disruption_code == item["disruption_code"])
        ).first()

        if existing:
            seeded.append(existing)
            continue

        vehicle_id = None
        warehouse_id = None
        network_edge_id = None

        if item["target_type"] == "vehicle":
            v = db.scalars(select(Vehicle).where(Vehicle.vehicle_code == item["target_code"])).first()
            if v:
                vehicle_id = v.id
        elif item["target_type"] == "warehouse":
            w = db.scalars(select(Warehouse).where(Warehouse.warehouse_code == item["target_code"])).first()
            if w:
                warehouse_id = w.id
        elif item["target_type"] == "network_edge":
            edge = db.scalars(select(NetworkEdge)).first()
            if edge:
                network_edge_id = edge.id

        disruption = Disruption(
            disruption_code=item["disruption_code"],
            disruption_type=item["disruption_type"],
            severity=item["severity"],
            status=item["status"],
            title=item["title"],
            description=item["description"],
            affected_vehicle_id=vehicle_id,
            affected_warehouse_id=warehouse_id,
            affected_network_edge_id=network_edge_id,
            location_latitude=item["location"][0],
            location_longitude=item["location"][1],
            parameters=item["parameters"],
            start_time=now - timedelta(minutes=45),
            expected_end_time=now + timedelta(minutes=75),
        )
        db.add(disruption)
        db.flush()

        # Add Event
        event = DisruptionEvent(
            disruption_id=disruption.id,
            event_type=DisruptionEventType.DISRUPTION_CREATED.value,
            previous_status=None,
            new_status=item["status"],
            event_data={"seeded": True, "title": item["title"]},
        )
        db.add(event)

        # Add Impact record if applicable
        if vehicle_id:
            impact = DisruptionImpact(
                disruption_id=disruption.id,
                affected_resource_type=AffectedResourceType.VEHICLE.value,
                affected_resource_id=vehicle_id,
                impact_category="DIRECT",
                severity=item["severity"],
                estimated_delay_minutes=item["delay_minutes"],
                impact_details={"vehicle_code": item.get("target_code", "TRK-001")},
            )
            db.add(impact)
        elif warehouse_id:
            impact = DisruptionImpact(
                disruption_id=disruption.id,
                affected_resource_type=AffectedResourceType.WAREHOUSE.value,
                affected_resource_id=warehouse_id,
                impact_category="DIRECT",
                severity=item["severity"],
                estimated_delay_minutes=item["delay_minutes"],
                impact_details={"warehouse_code": item.get("target_code", "WH-001")},
            )
            db.add(impact)

        db.commit()
        db.refresh(disruption)
        seeded.append(disruption)

    return seeded


if __name__ == "__main__":
    db = SessionLocal()
    try:
        results = seed_demo_disruptions(db)
        print(f"Successfully seeded {len(results)} demo disruptions.")
    finally:
        db.close()
