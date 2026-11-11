import logging
import sys
from pathlib import Path
from typing import Dict, List, Tuple
from sqlalchemy import select
from sqlalchemy.orm import Session

# Ensure backend root is on sys.path
backend_dir = Path(__file__).resolve().parents[2]
if str(backend_dir) not in sys.path:
    sys.path.insert(0, str(backend_dir))

from app.database.session import SessionLocal
from app.models.network import NetworkEdge, NetworkNode, NodeType

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger("seed_demo_network")

# 3 Warehouse Hubs in Bengaluru
SAMPLE_WAREHOUSES = [
    {
        "name": "Whitefield Distribution Hub",
        "node_type": NodeType.WAREHOUSE.value,
        "latitude": 12.9698,
        "longitude": 77.7499,
        "region": "East Bengaluru",
        "address": "EPIP Zone, Whitefield, Bengaluru 560066",
    },
    {
        "name": "Electronic City Distribution Hub",
        "node_type": NodeType.WAREHOUSE.value,
        "latitude": 12.8399,
        "longitude": 77.6770,
        "region": "South Bengaluru",
        "address": "Phase 1, Electronic City, Bengaluru 560100",
    },
    {
        "name": "Peenya Distribution Hub",
        "node_type": NodeType.WAREHOUSE.value,
        "latitude": 13.0285,
        "longitude": 77.5197,
        "region": "North-West Bengaluru",
        "address": "Peenya Industrial Area Phase 2, Bengaluru 560058",
    },
]

# 15 Customer Locations across Bengaluru
SAMPLE_CUSTOMERS = [
    {
        "name": "Koramangala Commercial Hub",
        "node_type": NodeType.CUSTOMER.value,
        "latitude": 12.9352,
        "longitude": 77.6245,
        "region": "South Bengaluru",
        "address": "80 Feet Road, 4th Block, Koramangala, Bengaluru 560034",
    },
    {
        "name": "Indiranagar Retail Center",
        "node_type": NodeType.CUSTOMER.value,
        "latitude": 12.9784,
        "longitude": 77.6408,
        "region": "East Bengaluru",
        "address": "100 Feet Road, Indiranagar, Bengaluru 560038",
    },
    {
        "name": "Jayanagar Fulfillment Point",
        "node_type": NodeType.CUSTOMER.value,
        "latitude": 12.9308,
        "longitude": 77.5838,
        "region": "South Bengaluru",
        "address": "11th Main, 4th Block, Jayanagar, Bengaluru 560011",
    },
    {
        "name": "HSR Layout Delivery Hub",
        "node_type": NodeType.CUSTOMER.value,
        "latitude": 12.9121,
        "longitude": 77.6446,
        "region": "South-East Bengaluru",
        "address": "Sector 2, HSR Layout, Bengaluru 560102",
    },
    {
        "name": "Marathahalli Tech Outpost",
        "node_type": NodeType.CUSTOMER.value,
        "latitude": 12.9591,
        "longitude": 77.6974,
        "region": "East Bengaluru",
        "address": "Outer Ring Road, Marathahalli, Bengaluru 560037",
    },
    {
        "name": "Bellandur Eco-Park Hub",
        "node_type": NodeType.CUSTOMER.value,
        "latitude": 12.9260,
        "longitude": 77.6762,
        "region": "South-East Bengaluru",
        "address": "Bellandur Outer Ring Road, Bengaluru 560103",
    },
    {
        "name": "Malleshwaram Trade Node",
        "node_type": NodeType.CUSTOMER.value,
        "latitude": 13.0031,
        "longitude": 77.5643,
        "region": "North-West Bengaluru",
        "address": "Sampige Road, Malleshwaram, Bengaluru 560003",
    },
    {
        "name": "Rajajinagar Depot Point",
        "node_type": NodeType.CUSTOMER.value,
        "latitude": 12.9915,
        "longitude": 77.5525,
        "region": "West Bengaluru",
        "address": "10th Main, Rajajinagar 2nd Stage, Bengaluru 560010",
    },
    {
        "name": "Hebbal Junction Logistics",
        "node_type": NodeType.CUSTOMER.value,
        "latitude": 13.0358,
        "longitude": 77.5970,
        "region": "North Bengaluru",
        "address": "Bellary Road, Hebbal, Bengaluru 560024",
    },
    {
        "name": "Yelahanka North Depot",
        "node_type": NodeType.CUSTOMER.value,
        "latitude": 13.1007,
        "longitude": 77.5963,
        "region": "North Bengaluru",
        "address": "Old Town, Yelahanka, Bengaluru 560064",
    },
    {
        "name": "Banashankari Distribution Node",
        "node_type": NodeType.CUSTOMER.value,
        "latitude": 12.9155,
        "longitude": 77.5736,
        "region": "South Bengaluru",
        "address": "2nd Stage, Banashankari, Bengaluru 560070",
    },
    {
        "name": "Bannerghatta Tech Center",
        "node_type": NodeType.CUSTOMER.value,
        "latitude": 12.8876,
        "longitude": 77.5969,
        "region": "South Bengaluru",
        "address": "Bannerghatta Main Road, Hulimavu, Bengaluru 560076",
    },
    {
        "name": "BTM Layout Drop Center",
        "node_type": NodeType.CUSTOMER.value,
        "latitude": 12.9166,
        "longitude": 77.6101,
        "region": "South Bengaluru",
        "address": "Outer Ring Road, BTM 2nd Stage, Bengaluru 560076",
    },
    {
        "name": "Kalyan Nagar Logistics Point",
        "node_type": NodeType.CUSTOMER.value,
        "latitude": 13.0221,
        "longitude": 77.6403,
        "region": "East Bengaluru",
        "address": "Kammanahalli Main Road, Kalyan Nagar, Bengaluru 560043",
    },
    {
        "name": "Sarjapur Cluster Hub",
        "node_type": NodeType.CUSTOMER.value,
        "latitude": 12.9090,
        "longitude": 77.6850,
        "region": "South-East Bengaluru",
        "address": "Sarjapur Road Junction, Bengaluru 560035",
    },
]

# Connection definitions: (source_node_name, target_node_name, distance_km, estimated_minutes, road_type)
SAMPLE_CONNECTIONS: List[Tuple[str, str, float, int, str]] = [
    # Whitefield Hub Outgoing
    ("Whitefield Distribution Hub", "Marathahalli Tech Outpost", 8.5, 22, "ARTERIAL"),
    ("Whitefield Distribution Hub", "Indiranagar Retail Center", 14.2, 35, "PRIMARY"),
    ("Whitefield Distribution Hub", "Bellandur Eco-Park Hub", 12.8, 30, "PRIMARY"),
    ("Whitefield Distribution Hub", "Kalyan Nagar Logistics Point", 16.5, 40, "PRIMARY"),
    ("Whitefield Distribution Hub", "Sarjapur Cluster Hub", 15.0, 38, "SECONDARY"),
    # Electronic City Hub Outgoing
    ("Electronic City Distribution Hub", "HSR Layout Delivery Hub", 11.5, 28, "PRIMARY"),
    ("Electronic City Distribution Hub", "Koramangala Commercial Hub", 14.0, 34, "PRIMARY"),
    ("Electronic City Distribution Hub", "Bannerghatta Tech Center", 9.2, 24, "SECONDARY"),
    ("Electronic City Distribution Hub", "BTM Layout Drop Center", 12.3, 30, "PRIMARY"),
    ("Electronic City Distribution Hub", "Jayanagar Fulfillment Point", 15.5, 36, "PRIMARY"),
    ("Electronic City Distribution Hub", "Bellandur Eco-Park Hub", 13.6, 32, "PRIMARY"),
    # Peenya Hub Outgoing
    ("Peenya Distribution Hub", "Malleshwaram Trade Node", 7.8, 20, "PRIMARY"),
    ("Peenya Distribution Hub", "Rajajinagar Depot Point", 6.5, 18, "PRIMARY"),
    ("Peenya Distribution Hub", "Hebbal Junction Logistics", 11.2, 26, "HIGHWAY"),
    ("Peenya Distribution Hub", "Yelahanka North Depot", 15.4, 35, "HIGHWAY"),
    ("Peenya Distribution Hub", "Banashankari Distribution Node", 17.5, 42, "ARTERIAL"),
    # Warehouse Trunk Interconnects (Bidirectional)
    ("Peenya Distribution Hub", "Electronic City Distribution Hub", 32.0, 65, "NICE_HIGHWAY"),
    ("Electronic City Distribution Hub", "Peenya Distribution Hub", 32.0, 65, "NICE_HIGHWAY"),
    ("Electronic City Distribution Hub", "Whitefield Distribution Hub", 26.5, 55, "PRIMARY_ORR"),
    ("Whitefield Distribution Hub", "Electronic City Distribution Hub", 26.5, 55, "PRIMARY_ORR"),
    ("Peenya Distribution Hub", "Whitefield Distribution Hub", 28.0, 60, "ORR_HIGHWAY"),
    ("Whitefield Distribution Hub", "Peenya Distribution Hub", 28.0, 60, "ORR_HIGHWAY"),
    # Cross-cluster connections
    ("Marathahalli Tech Outpost", "Bellandur Eco-Park Hub", 4.5, 12, "ARTERIAL"),
    ("Koramangala Commercial Hub", "HSR Layout Delivery Hub", 3.8, 10, "SECONDARY"),
    ("Hebbal Junction Logistics", "Kalyan Nagar Logistics Point", 6.2, 16, "PRIMARY"),
]


def seed_demo_network(db: Session = None) -> Dict[str, int]:
    """
    Seeds the demo logistics network deterministically and idempotently.
    Returns counts: warehouses_created, customers_created, connections_created, skipped.
    """
    close_session = False
    if db is None:
        db = SessionLocal()
        close_session = True

    stats = {
        "warehouses_created": 0,
        "customers_created": 0,
        "connections_created": 0,
        "skipped": 0,
    }

    try:
        node_map: Dict[str, NetworkNode] = {}

        # 1. Seed Warehouses
        for wh_data in SAMPLE_WAREHOUSES:
            stmt = select(NetworkNode).where(NetworkNode.name == wh_data["name"])
            existing = db.execute(stmt).scalar_one_or_none()
            if existing:
                node_map[existing.name] = existing
                stats["skipped"] += 1
            else:
                node = NetworkNode(
                    name=wh_data["name"],
                    node_type=wh_data["node_type"],
                    latitude=wh_data["latitude"],
                    longitude=wh_data["longitude"],
                    region=wh_data["region"],
                    address=wh_data["address"],
                    is_active=True,
                )
                db.add(node)
                db.flush()
                node_map[node.name] = node
                stats["warehouses_created"] += 1

        # 2. Seed Customers
        for cust_data in SAMPLE_CUSTOMERS:
            stmt = select(NetworkNode).where(NetworkNode.name == cust_data["name"])
            existing = db.execute(stmt).scalar_one_or_none()
            if existing:
                node_map[existing.name] = existing
                stats["skipped"] += 1
            else:
                node = NetworkNode(
                    name=cust_data["name"],
                    node_type=cust_data["node_type"],
                    latitude=cust_data["latitude"],
                    longitude=cust_data["longitude"],
                    region=cust_data["region"],
                    address=cust_data["address"],
                    is_active=True,
                )
                db.add(node)
                db.flush()
                node_map[node.name] = node
                stats["customers_created"] += 1

        # 3. Seed Connections (Edges)
        for src_name, tgt_name, dist, time_min, road in SAMPLE_CONNECTIONS:
            src_node = node_map.get(src_name)
            tgt_node = node_map.get(tgt_name)

            if not src_node or not tgt_node:
                continue

            stmt = select(NetworkEdge).where(
                NetworkEdge.source_node_id == src_node.id,
                NetworkEdge.target_node_id == tgt_node.id,
            )
            existing_edge = db.execute(stmt).scalar_one_or_none()

            if existing_edge:
                stats["skipped"] += 1
            else:
                edge = NetworkEdge(
                    source_node_id=src_node.id,
                    target_node_id=tgt_node.id,
                    distance_km=dist,
                    estimated_travel_minutes=time_min,
                    road_type=road,
                    is_active=True,
                )
                db.add(edge)
                stats["connections_created"] += 1

        db.commit()

        print(f"Number of warehouses created: {stats['warehouses_created']}")
        print(f"Number of customers created: {stats['customers_created']}")
        print(f"Number of connections created: {stats['connections_created']}")
        print(f"Number of existing records skipped: {stats['skipped']}")

        return stats
    except Exception:
        db.rollback()
        raise
    finally:
        if close_session:
            db.close()


if __name__ == "__main__":
    seed_demo_network()

