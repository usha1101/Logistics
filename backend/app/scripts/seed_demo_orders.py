"""Demo Order Management seeding script for LOGIPULSE.

Seeds realistic Bengaluru commercial customers, 16 multi-status orders,
order items, status histories, and vehicle assignments.
Strictly idempotent: safe to execute multiple times.
"""

from datetime import datetime, timedelta, timezone
from typing import Dict, List, Tuple
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database.session import SessionLocal
from app.models.order import (
    Customer,
    Order,
    OrderAssignmentHistory,
    OrderItem,
    OrderPriority,
    OrderStatus,
    OrderStatusHistory,
)
from app.models.user import User
from app.models.vehicle import Vehicle, VehicleStatus
from app.models.warehouse import Warehouse

DEMO_CUSTOMERS = [
    {
        "customer_code": "CUST-BLR-001",
        "name": "Zenith Retail Superstores",
        "email": "procurement@zenithretail.in",
        "phone": "+91-80-2558-1001",
        "address_line": "104 Brigade Road, Ashok Nagar",
        "city": "Bengaluru",
        "state": "Karnataka",
        "postal_code": "560025",
        "latitude": 12.9719,
        "longitude": 77.6070,
    },
    {
        "customer_code": "CUST-BLR-002",
        "name": "Koramangala Tech Innovations Hub",
        "email": "hardware-ops@koramangalatech.io",
        "phone": "+91-80-4112-2002",
        "address_line": "80 Feet Road, 4th Block, Koramangala",
        "city": "Bengaluru",
        "state": "Karnataka",
        "postal_code": "560034",
        "latitude": 12.9352,
        "longitude": 77.6245,
    },
    {
        "customer_code": "CUST-BLR-003",
        "name": "Indiranagar Urban Quick-Commerce Depot",
        "email": "inventory@indiranagardepot.in",
        "phone": "+91-80-6771-3003",
        "address_line": "100 Feet Road, HAL 2nd Stage, Indiranagar",
        "city": "Bengaluru",
        "state": "Karnataka",
        "postal_code": "560038",
        "latitude": 12.9784,
        "longitude": 77.6408,
    },
    {
        "customer_code": "CUST-BLR-004",
        "name": "Jayanagar Green Energy Logistics",
        "email": "dispatch@jayanagargreen.com",
        "phone": "+91-80-2663-4004",
        "address_line": "11th Main Road, 4th Block, Jayanagar",
        "city": "Bengaluru",
        "state": "Karnataka",
        "postal_code": "560011",
        "latitude": 12.9299,
        "longitude": 77.5833,
    },
    {
        "customer_code": "CUST-BLR-005",
        "name": "Hebbal Industrial Fasteners & Spares",
        "email": "supplies@hebbalfasteners.org",
        "phone": "+91-80-3021-5005",
        "address_line": "Bellary Road, Ganganagar, Hebbal",
        "city": "Bengaluru",
        "state": "Karnataka",
        "postal_code": "560032",
        "latitude": 13.0358,
        "longitude": 77.5970,
    },
]

DEMO_ORDERS = [
    # 1. Whitefield (WH-001) Orders
    {
        "order_number": "ORD-2026-001",
        "customer_code": "CUST-BLR-001",
        "warehouse_code": "WH-001",
        "status": OrderStatus.IN_TRANSIT.value,
        "priority": OrderPriority.URGENT.value,
        "days_ago": 2,
        "due_hours_ahead": -4,  # Overdue
        "delivery_address": "Brigade Road Retail Center, Ashok Nagar",
        "latitude": 12.9719,
        "longitude": 77.6070,
        "vehicle_code": "TRK-001",
        "items": [
            {"product_code": "SKU-SOL-100", "product_name": "Solar Inverter 5kVA", "quantity": 2, "unit_price": 45000.0, "unit_weight_kg": 18.0},
            {"product_code": "SKU-BAT-201", "product_name": "Lithium Iron Battery 48V", "quantity": 4, "unit_price": 28000.0, "unit_weight_kg": 25.0},
        ],
    },
    {
        "order_number": "ORD-2026-002",
        "customer_code": "CUST-BLR-002",
        "warehouse_code": "WH-001",
        "status": OrderStatus.READY_FOR_DISPATCH.value,
        "priority": OrderPriority.HIGH.value,
        "days_ago": 1,
        "due_hours_ahead": 6,
        "delivery_address": "80 Feet Road, 4th Block, Koramangala",
        "latitude": 12.9352,
        "longitude": 77.6245,
        "vehicle_code": None,
        "items": [
            {"product_code": "SKU-SEN-301", "product_name": "IoT Multi-Sensor Pack", "quantity": 10, "unit_price": 3200.0, "unit_weight_kg": 1.5},
        ],
    },
    {
        "order_number": "ORD-2026-003",
        "customer_code": "CUST-BLR-003",
        "warehouse_code": "WH-001",
        "status": OrderStatus.DELIVERED.value,
        "priority": OrderPriority.NORMAL.value,
        "days_ago": 3,
        "due_hours_ahead": -24,
        "dispatched_offset_hours": -30,
        "delivered_offset_hours": -26,  # On-time
        "delivery_address": "100 Feet Road, Indiranagar",
        "latitude": 12.9784,
        "longitude": 77.6408,
        "vehicle_code": None,
        "items": [
            {"product_code": "SKU-BOX-501", "product_name": "Heavy Duty Shipping Box L", "quantity": 50, "unit_price": 120.0, "unit_weight_kg": 0.8},
        ],
    },
    {
        "order_number": "ORD-2026-004",
        "customer_code": "CUST-BLR-004",
        "warehouse_code": "WH-001",
        "status": OrderStatus.FAILED_DELIVERY.value,
        "priority": OrderPriority.NORMAL.value,
        "days_ago": 1,
        "due_hours_ahead": -2,
        "delivery_address": "11th Main Road, Jayanagar",
        "latitude": 12.9299,
        "longitude": 77.5833,
        "vehicle_code": None,
        "items": [
            {"product_code": "SKU-TAP-502", "product_name": "Reinforced Filament Tape", "quantity": 20, "unit_price": 450.0, "unit_weight_kg": 0.5},
        ],
    },
    {
        "order_number": "ORD-2026-005",
        "customer_code": "CUST-BLR-005",
        "warehouse_code": "WH-001",
        "status": OrderStatus.CREATED.value,
        "priority": OrderPriority.LOW.value,
        "days_ago": 0,
        "due_hours_ahead": 48,
        "delivery_address": "Bellary Road, Hebbal",
        "latitude": 13.0358,
        "longitude": 77.5970,
        "vehicle_code": None,
        "items": [
            {"product_code": "SKU-SOL-100", "product_name": "Solar Inverter 5kVA", "quantity": 1, "unit_price": 45000.0, "unit_weight_kg": 18.0},
        ],
    },
    # 2. Electronic City (WH-002) Orders
    {
        "order_number": "ORD-2026-006",
        "customer_code": "CUST-BLR-002",
        "warehouse_code": "WH-002",
        "status": OrderStatus.IN_TRANSIT.value,
        "priority": OrderPriority.HIGH.value,
        "days_ago": 1,
        "due_hours_ahead": 4,
        "delivery_address": "Koramangala Innovations Lab 2",
        "latitude": 12.9360,
        "longitude": 77.6250,
        "vehicle_code": "VAN-001",
        "items": [
            {"product_code": "SKU-EV-601", "product_name": "Fast Charger Type-2 EV", "quantity": 3, "unit_price": 38000.0, "unit_weight_kg": 14.0},
            {"product_code": "SKU-SEN-301", "product_name": "IoT Multi-Sensor Pack", "quantity": 5, "unit_price": 3200.0, "unit_weight_kg": 1.5},
        ],
    },
    {
        "order_number": "ORD-2026-007",
        "customer_code": "CUST-BLR-001",
        "warehouse_code": "WH-002",
        "status": OrderStatus.CONFIRMED.value,
        "priority": OrderPriority.NORMAL.value,
        "days_ago": 0,
        "due_hours_ahead": 24,
        "delivery_address": "Brigade Road Commercial Plaza",
        "latitude": 12.9725,
        "longitude": 77.6080,
        "vehicle_code": None,
        "items": [
            {"product_code": "SKU-EV-602", "product_name": "Portable Level-1 EV Cable", "quantity": 8, "unit_price": 9500.0, "unit_weight_kg": 4.5},
        ],
    },
    {
        "order_number": "ORD-2026-008",
        "customer_code": "CUST-BLR-004",
        "warehouse_code": "WH-002",
        "status": OrderStatus.PROCESSING.value,
        "priority": OrderPriority.HIGH.value,
        "days_ago": 1,
        "due_hours_ahead": 12,
        "delivery_address": "Jayanagar Metro Distribution Point",
        "latitude": 12.9310,
        "longitude": 77.5840,
        "vehicle_code": None,
        "items": [
            {"product_code": "SKU-EV-601", "product_name": "Fast Charger Type-2 EV", "quantity": 2, "unit_price": 38000.0, "unit_weight_kg": 14.0},
        ],
    },
    {
        "order_number": "ORD-2026-009",
        "customer_code": "CUST-BLR-003",
        "warehouse_code": "WH-002",
        "status": OrderStatus.ON_HOLD.value,
        "priority": OrderPriority.NORMAL.value,
        "days_ago": 2,
        "due_hours_ahead": 18,
        "delivery_address": "Indiranagar Hub 3",
        "latitude": 12.9790,
        "longitude": 77.6415,
        "vehicle_code": None,
        "items": [
            {"product_code": "SKU-BOX-501", "product_name": "Heavy Duty Shipping Box L", "quantity": 100, "unit_price": 120.0, "unit_weight_kg": 0.8},
        ],
    },
    {
        "order_number": "ORD-2026-010",
        "customer_code": "CUST-BLR-005",
        "warehouse_code": "WH-002",
        "status": OrderStatus.CANCELLED.value,
        "priority": OrderPriority.LOW.value,
        "days_ago": 3,
        "due_hours_ahead": -10,
        "delivery_address": "Hebbal Hardware Annex",
        "latitude": 13.0365,
        "longitude": 77.5980,
        "vehicle_code": None,
        "items": [
            {"product_code": "SKU-EV-602", "product_name": "Portable Level-1 EV Cable", "quantity": 2, "unit_price": 9500.0, "unit_weight_kg": 4.5},
        ],
    },
    # 3. Peenya (WH-003) Orders
    {
        "order_number": "ORD-2026-011",
        "customer_code": "CUST-BLR-005",
        "warehouse_code": "WH-003",
        "status": OrderStatus.DISPATCHED.value,
        "priority": OrderPriority.URGENT.value,
        "days_ago": 0,
        "due_hours_ahead": 3,
        "delivery_address": "Hebbal Heavy Hardware Yard",
        "latitude": 13.0358,
        "longitude": 77.5970,
        "vehicle_code": None,
        "items": [
            {"product_code": "SKU-STR-701", "product_name": "Heavy Galvanized Steel Strapping", "quantity": 15, "unit_price": 1850.0, "unit_weight_kg": 12.0},
        ],
    },
    {
        "order_number": "ORD-2026-012",
        "customer_code": "CUST-BLR-004",
        "warehouse_code": "WH-003",
        "status": OrderStatus.DELIVERED.value,
        "priority": OrderPriority.NORMAL.value,
        "days_ago": 4,
        "due_hours_ahead": -40,
        "dispatched_offset_hours": -48,
        "delivered_offset_hours": -42,
        "delivery_address": "Jayanagar Hardware Terminal",
        "latitude": 12.9299,
        "longitude": 77.5833,
        "vehicle_code": None,
        "items": [
            {"product_code": "SKU-STR-702", "product_name": "Industrial Caster Wheel Set", "quantity": 8, "unit_price": 2400.0, "unit_weight_kg": 6.5},
        ],
    },
    {
        "order_number": "ORD-2026-013",
        "customer_code": "CUST-BLR-001",
        "warehouse_code": "WH-003",
        "status": OrderStatus.READY_FOR_DISPATCH.value,
        "priority": OrderPriority.NORMAL.value,
        "days_ago": 1,
        "due_hours_ahead": 8,
        "delivery_address": "Brigade Road Warehouse Gate 2",
        "latitude": 12.9719,
        "longitude": 77.6070,
        "vehicle_code": None,
        "items": [
            {"product_code": "SKU-STR-701", "product_name": "Heavy Galvanized Steel Strapping", "quantity": 5, "unit_price": 1850.0, "unit_weight_kg": 12.0},
        ],
    },
    {
        "order_number": "ORD-2026-014",
        "customer_code": "CUST-BLR-002",
        "warehouse_code": "WH-003",
        "status": OrderStatus.CONFIRMED.value,
        "priority": OrderPriority.LOW.value,
        "days_ago": 0,
        "due_hours_ahead": 36,
        "delivery_address": "Koramangala Workshop 1",
        "latitude": 12.9352,
        "longitude": 77.6245,
        "vehicle_code": None,
        "items": [
            {"product_code": "SKU-STR-702", "product_name": "Industrial Caster Wheel Set", "quantity": 4, "unit_price": 2400.0, "unit_weight_kg": 6.5},
        ],
    },
    {
        "order_number": "ORD-2026-015",
        "customer_code": "CUST-BLR-003",
        "warehouse_code": "WH-003",
        "status": OrderStatus.PROCESSING.value,
        "priority": OrderPriority.URGENT.value,
        "days_ago": 1,
        "due_hours_ahead": -6,  # Overdue
        "delivery_address": "Indiranagar Express Hub",
        "latitude": 12.9784,
        "longitude": 77.6408,
        "vehicle_code": None,
        "items": [
            {"product_code": "SKU-STR-701", "product_name": "Heavy Galvanized Steel Strapping", "quantity": 10, "unit_price": 1850.0, "unit_weight_kg": 12.0},
        ],
    },
    {
        "order_number": "ORD-2026-016",
        "customer_code": "CUST-BLR-004",
        "warehouse_code": "WH-001",
        "status": OrderStatus.CREATED.value,
        "priority": OrderPriority.NORMAL.value,
        "days_ago": 0,
        "due_hours_ahead": 28,
        "delivery_address": "Jayanagar Quick Pick Point",
        "latitude": 12.9305,
        "longitude": 77.5845,
        "vehicle_code": None,
        "items": [
            {"product_code": "SKU-SOL-100", "product_name": "Solar Inverter 5kVA", "quantity": 1, "unit_price": 45000.0, "unit_weight_kg": 18.0},
            {"product_code": "SKU-BOX-501", "product_name": "Heavy Duty Shipping Box L", "quantity": 10, "unit_price": 120.0, "unit_weight_kg": 0.8},
        ],
    },
]


def seed_demo_orders(db: Session) -> Tuple[int, int, int]:
    """Seed demo customers and orders. Returns (customers_created, orders_created, orders_skipped)."""
    now = datetime.now(timezone.utc)

    # 1. Seed Customers
    customers_created = 0
    customers_map: Dict[str, Customer] = {}
    for c_data in DEMO_CUSTOMERS:
        cust = db.execute(select(Customer).where(Customer.customer_code == c_data["customer_code"])).scalar_one_or_none()
        if not cust:
            cust = Customer(
                customer_code=c_data["customer_code"],
                name=c_data["name"],
                email=c_data["email"],
                phone=c_data["phone"],
                address_line=c_data["address_line"],
                city=c_data["city"],
                state=c_data["state"],
                postal_code=c_data["postal_code"],
                latitude=c_data["latitude"],
                longitude=c_data["longitude"],
                is_active=True,
            )
            db.add(cust)
            db.flush()
            customers_created += 1
        customers_map[c_data["customer_code"]] = cust

    # 2. Lookup warehouses
    warehouses = {wh.warehouse_code: wh for wh in db.execute(select(Warehouse)).scalars().all()}
    if not warehouses:
        print("[!] No warehouses found. Please run seed_demo_warehouse first.")
        return 0, 0, 0

    # 3. Lookup vehicles
    vehicles = {v.vehicle_code: v for v in db.execute(select(Vehicle)).scalars().all()}

    # 4. Lookup admin user
    admin_user = db.execute(select(User).where(User.username == "admin")).scalar_one_or_none()
    admin_id = admin_user.id if admin_user else None

    orders_created = 0
    orders_skipped = 0

    for o_data in DEMO_ORDERS:
        order_num = o_data["order_number"]
        existing = db.execute(select(Order).where(Order.order_number == order_num)).scalar_one_or_none()
        if existing:
            orders_skipped += 1
            continue

        cust = customers_map.get(o_data["customer_code"])
        wh = warehouses.get(o_data["warehouse_code"])
        if not cust or not wh:
            continue

        order_dt = now - timedelta(days=o_data["days_ago"])
        expected_dt = now + timedelta(hours=o_data["due_hours_ahead"])
        dispatched_dt = now + timedelta(hours=o_data["dispatched_offset_hours"]) if "dispatched_offset_hours" in o_data else None
        delivered_dt = now + timedelta(hours=o_data["delivered_offset_hours"]) if "delivered_offset_hours" in o_data else None

        veh = vehicles.get(o_data["vehicle_code"]) if o_data.get("vehicle_code") else None
        veh_id = veh.id if veh else None

        order = Order(
            order_number=order_num,
            customer_id=cust.id,
            warehouse_id=wh.id,
            status=o_data["status"],
            priority=o_data["priority"],
            order_date=order_dt,
            expected_delivery_at=expected_dt,
            dispatched_at=dispatched_dt,
            delivered_at=delivered_dt,
            delivery_address=o_data["delivery_address"],
            delivery_latitude=o_data["latitude"],
            delivery_longitude=o_data["longitude"],
            total_weight_kg=0.0,
            total_amount=0.0,
            assigned_vehicle_id=veh_id,
            created_by_user_id=admin_id,
            created_at=order_dt,
            updated_at=now,
        )
        db.add(order)
        db.flush()

        # Add items and calculate totals
        tot_wt = 0.0
        tot_amt = 0.0
        for itm_data in o_data["items"]:
            sub = round(itm_data["quantity"] * itm_data["unit_price"], 2)
            wt = round(itm_data["quantity"] * itm_data["unit_weight_kg"], 2)
            item = OrderItem(
                order_id=order.id,
                product_code=itm_data["product_code"],
                product_name=itm_data["product_name"],
                quantity=itm_data["quantity"],
                unit_price=itm_data["unit_price"],
                unit_weight_kg=itm_data["unit_weight_kg"],
                subtotal=sub,
                total_weight_kg=wt,
                created_at=order_dt,
            )
            db.add(item)
            tot_amt += sub
            tot_wt += wt

        order.total_amount = round(tot_amt, 2)
        order.total_weight_kg = round(tot_wt, 2)

        # Initial status history
        hist = OrderStatusHistory(
            order_id=order.id,
            previous_status=None,
            new_status=o_data["status"],
            reason="Initial demo order seeding",
            changed_by_user_id=admin_id,
            changed_at=order_dt,
        )
        db.add(hist)

        # Assignment history if vehicle assigned
        if veh_id:
            assign_hist = OrderAssignmentHistory(
                order_id=order.id,
                previous_vehicle_id=None,
                new_vehicle_id=veh_id,
                assigned_by_user_id=admin_id,
                reason="Initial vehicle dispatch assignment",
                assigned_at=order_dt,
            )
            db.add(assign_hist)

        orders_created += 1

    db.commit()
    return customers_created, orders_created, orders_skipped


def main() -> None:
    db = SessionLocal()
    try:
        c_count, o_created, o_skipped = seed_demo_orders(db)
        print(
            f"[*] Demo Orders Seeding Summary: Created {c_count} customers, "
            f"Created {o_created} orders, Skipped {o_skipped} existing orders."
        )
    finally:
        db.close()


if __name__ == "__main__":
    main()

