import logging
import sys
from pathlib import Path
from typing import Any, Dict, List
from sqlalchemy import select
from sqlalchemy.orm import Session

# Ensure backend root is on sys.path
backend_dir = Path(__file__).resolve().parents[2]
if str(backend_dir) not in sys.path:
    sys.path.insert(0, str(backend_dir))

from app.database.session import SessionLocal
from app.models.network import NetworkNode, NodeType
from app.models.warehouse import (
    InventoryItem,
    Warehouse,
    WarehouseStatus,
    WarehouseType,
)

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger("seed_demo_warehouse")

SAMPLE_WAREHOUSES_CONFIG = [
    {
        "node_name": "Whitefield Distribution Hub",
        "warehouse_code": "WH-001",
        "warehouse_type": WarehouseType.DISTRIBUTION_CENTER.value,
        "total_capacity": 10000.0,
        "manager_name": "Rajesh Sharma",
        "contact_number": "+91 98450 11001",
        "operating_hours": {
            "monday_friday": "06:00 - 22:00",
            "saturday": "08:00 - 18:00",
            "sunday": "Closed",
        },
        "inventory": [
            {
                "sku": "ELEC-WH01-01",
                "product_name": "Lithium-Ion Battery Pack 48V",
                "category": "Electronics",
                "quantity": 120,
                "reorder_level": 25,
                "unit": "packs",
                "unit_volume": 0.15,
            },
            {
                "sku": "ELEC-WH01-02",
                "product_name": "IoT Telemetry Gateway",
                "category": "Electronics",
                "quantity": 18,
                "reorder_level": 20,
                "unit": "units",
                "unit_volume": 0.05,
            },
            {
                "sku": "CONS-WH01-03",
                "product_name": "Premium Organic Green Tea",
                "category": "Consumer goods",
                "quantity": 350,
                "reorder_level": 50,
                "unit": "boxes",
                "unit_volume": 0.02,
            },
            {
                "sku": "PACK-WH01-04",
                "product_name": "Heavy-Duty Corrugated Cartons (XL)",
                "category": "Packaging supplies",
                "quantity": 0,
                "reorder_level": 100,
                "unit": "bundles",
                "unit_volume": 0.50,
            },
            {
                "sku": "INDU-WH01-05",
                "product_name": "Industrial Barcode Scanners",
                "category": "Industrial supplies",
                "quantity": 45,
                "reorder_level": 15,
                "unit": "units",
                "unit_volume": 0.08,
            },
        ],
    },
    {
        "node_name": "Electronic City Distribution Hub",
        "warehouse_code": "WH-002",
        "warehouse_type": WarehouseType.FULFILLMENT_CENTER.value,
        "total_capacity": 8000.0,
        "manager_name": "Priya Nair",
        "contact_number": "+91 98450 22002",
        "operating_hours": {
            "monday_sunday": "24/7 Operations",
        },
        "inventory": [
            {
                "sku": "ELEC-WH02-01",
                "product_name": "Microcontroller Circuit Boards",
                "category": "Electronics",
                "quantity": 500,
                "reorder_level": 100,
                "unit": "units",
                "unit_volume": 0.01,
            },
            {
                "sku": "ELEC-WH02-02",
                "product_name": "High-Precision GPS Trackers",
                "category": "Electronics",
                "quantity": 8,
                "reorder_level": 15,
                "unit": "units",
                "unit_volume": 0.02,
            },
            {
                "sku": "CONS-WH02-03",
                "product_name": "Ergonomic Packing Tape Dispenser",
                "category": "Consumer goods",
                "quantity": 80,
                "reorder_level": 20,
                "unit": "units",
                "unit_volume": 0.04,
            },
            {
                "sku": "PACK-WH02-04",
                "product_name": "Biodegradable Bubble Wrap Rolls",
                "category": "Packaging supplies",
                "quantity": 0,
                "reorder_level": 40,
                "unit": "rolls",
                "unit_volume": 0.25,
            },
            {
                "sku": "INDU-WH02-05",
                "product_name": "Safety Helmets (Industrial Grade)",
                "category": "Industrial supplies",
                "quantity": 110,
                "reorder_level": 30,
                "unit": "units",
                "unit_volume": 0.09,
            },
        ],
    },
    {
        "node_name": "Peenya Distribution Hub",
        "warehouse_code": "WH-003",
        "warehouse_type": WarehouseType.STORAGE_FACILITY.value,
        "total_capacity": 12000.0,
        "manager_name": "Anil Kumar",
        "contact_number": "+91 98450 33003",
        "operating_hours": {
            "monday_saturday": "07:00 - 20:00",
            "sunday": "08:00 - 14:00",
        },
        "inventory": [
            {
                "sku": "INDU-WH03-01",
                "product_name": "Hydraulic Pallet Jack Spares",
                "category": "Industrial supplies",
                "quantity": 60,
                "reorder_level": 15,
                "unit": "kits",
                "unit_volume": 0.35,
            },
            {
                "sku": "INDU-WH03-02",
                "product_name": "Steel Strapping Coils (19mm)",
                "category": "Industrial supplies",
                "quantity": 5,
                "reorder_level": 12,
                "unit": "coils",
                "unit_volume": 0.20,
            },
            {
                "sku": "PACK-WH03-03",
                "product_name": "Standard Wooden Pallets (Euro)",
                "category": "Packaging supplies",
                "quantity": 200,
                "reorder_level": 50,
                "unit": "pallets",
                "unit_volume": 1.20,
            },
            {
                "sku": "CONS-WH03-04",
                "product_name": "Workstation Disinfectant Solution",
                "category": "Consumer goods",
                "quantity": 0,
                "reorder_level": 25,
                "unit": "cans",
                "unit_volume": 0.06,
            },
            {
                "sku": "ELEC-WH03-05",
                "product_name": "RFID Passive Smart Tags",
                "category": "Electronics",
                "quantity": 2500,
                "reorder_level": 300,
                "unit": "tags",
                "unit_volume": 0.001,
            },
        ],
    },
]


def seed_demo_warehouse(db: Session = None) -> Dict[str, int]:
    """
    Seeds warehouses and inventory records linked to existing WAREHOUSE NetworkNodes.
    Idempotent: Never creates duplicate warehouse records or duplicate items.
    """
    close_session = False
    if db is None:
        db = SessionLocal()
        close_session = True

    stats = {
        "warehouses_created": 0,
        "inventory_created": 0,
        "skipped": 0,
    }

    try:
        for wh_cfg in SAMPLE_WAREHOUSES_CONFIG:
            # 1. Lookup existing WAREHOUSE NetworkNode
            node_stmt = select(NetworkNode).where(
                NetworkNode.name == wh_cfg["node_name"],
                NetworkNode.node_type == NodeType.WAREHOUSE.value,
            )
            node = db.execute(node_stmt).scalar_one_or_none()
            if not node:
                logger.warning(
                    f"Required NetworkNode '{wh_cfg['node_name']}' not found. Please run seed_demo_network first."
                )
                continue

            # 2. Check if warehouse already exists
            wh_stmt = select(Warehouse).where(
                (Warehouse.warehouse_code == wh_cfg["warehouse_code"])
                | (Warehouse.network_node_id == node.id)
            )
            warehouse = db.execute(wh_stmt).scalar_one_or_none()

            if warehouse:
                stats["skipped"] += 1
            else:
                warehouse = Warehouse(
                    network_node_id=node.id,
                    warehouse_code=wh_cfg["warehouse_code"],
                    warehouse_type=wh_cfg["warehouse_type"],
                    total_capacity=wh_cfg["total_capacity"],
                    used_capacity=0.0,
                    status=WarehouseStatus.OPERATIONAL.value,
                    manager_name=wh_cfg["manager_name"],
                    contact_number=wh_cfg["contact_number"],
                    operating_hours=wh_cfg["operating_hours"],
                )
                db.add(warehouse)
                db.flush()
                stats["warehouses_created"] += 1

            # 3. Seed inventory items for this warehouse
            used_volume = 0.0
            for item_cfg in wh_cfg["inventory"]:
                item_stmt = select(InventoryItem).where(
                    InventoryItem.warehouse_id == warehouse.id,
                    InventoryItem.sku == item_cfg["sku"],
                )
                existing_item = db.execute(item_stmt).scalar_one_or_none()

                if existing_item:
                    stats["skipped"] += 1
                    used_volume += (existing_item.unit_volume or 0.0) * existing_item.quantity
                else:
                    item = InventoryItem(
                        warehouse_id=warehouse.id,
                        sku=item_cfg["sku"],
                        product_name=item_cfg["product_name"],
                        category=item_cfg["category"],
                        quantity=item_cfg["quantity"],
                        reorder_level=item_cfg["reorder_level"],
                        unit=item_cfg["unit"],
                        unit_volume=item_cfg["unit_volume"],
                    )
                    db.add(item)
                    stats["inventory_created"] += 1
                    used_volume += (item_cfg["unit_volume"] or 0.0) * item_cfg["quantity"]

            warehouse.used_capacity = round(min(warehouse.total_capacity, used_volume), 2)

        db.commit()

        print(f"Number of warehouses created: {stats['warehouses_created']}")
        print(f"Number of inventory items created: {stats['inventory_created']}")
        print(f"Number of existing records skipped: {stats['skipped']}")

        return stats
    except Exception:
        db.rollback()
        raise
    finally:
        if close_session:
            db.close()


if __name__ == "__main__":
    seed_demo_warehouse()

