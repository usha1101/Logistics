import os
from pathlib import Path
from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, inspect


def test_alembic_upgrade_and_downgrade(tmp_path: Path):
    temp_db_path = tmp_path / "temp_migration_test.db"
    db_url = f"sqlite:///{temp_db_path.as_posix()}"

    backend_dir = Path(__file__).resolve().parents[2]
    alembic_ini_path = backend_dir / "alembic.ini"

    alembic_cfg = Config(str(alembic_ini_path))
    alembic_cfg.set_main_option("script_location", str(backend_dir / "alembic"))
    alembic_cfg.set_main_option("sqlalchemy.url", db_url)

    engine = create_engine(db_url)

    # 1. Upgrade to head
    command.upgrade(alembic_cfg, "head")

    inspector = inspect(engine)
    tables = inspector.get_table_names()
    assert "simulations" in tables
    assert "users" in tables
    assert "network_nodes" in tables
    assert "network_edges" in tables
    assert "warehouses" in tables
    assert "inventory_items" in tables
    assert "inventory_movements" in tables
    assert "vehicles" in tables
    assert "vehicle_locations" in tables
    assert "vehicle_status_history" in tables
    assert "customers" in tables
    assert "orders" in tables
    assert "order_items" in tables
    assert "order_status_history" in tables
    assert "order_assignment_history" in tables
    assert "simulation_vehicle_states" in tables
    assert "simulation_events" in tables
    assert "simulation_telemetry" in tables
    assert "disruptions" in tables
    assert "disruption_impacts" in tables
    assert "disruption_events" in tables
    assert "reports" in tables
    assert "alembic_version" in tables

    disr_cols = {col["name"]: col for col in inspector.get_columns("disruptions")}
    assert "id" in disr_cols
    assert "disruption_code" in disr_cols
    assert "disruption_type" in disr_cols
    assert "severity" in disr_cols
    assert "status" in disr_cols

    sim_cols = {col["name"]: col for col in inspector.get_columns("simulations")}
    assert "id" in sim_cols
    assert "name" in sim_cols
    assert "status" in sim_cols
    assert "simulation_speed_multiplier" in sim_cols
    assert "simulated_time" in sim_cols

    sim_veh_cols = {col["name"]: col for col in inspector.get_columns("simulation_vehicle_states")}
    assert "id" in sim_veh_cols
    assert "simulation_id" in sim_veh_cols
    assert "vehicle_id" in sim_veh_cols
    assert "progress_percentage" in sim_veh_cols
    assert "current_latitude" in sim_veh_cols
    assert "current_longitude" in sim_veh_cols

    cust_cols = {col["name"]: col for col in inspector.get_columns("customers")}
    assert "id" in cust_cols
    assert "customer_code" in cust_cols
    assert "name" in cust_cols
    assert "phone" in cust_cols

    ord_cols = {col["name"]: col for col in inspector.get_columns("orders")}
    assert "id" in ord_cols
    assert "order_number" in ord_cols
    assert "customer_id" in ord_cols
    assert "warehouse_id" in ord_cols
    assert "status" in ord_cols
    assert "total_amount" in ord_cols
    assert "total_weight_kg" in ord_cols

    item_cols = {col["name"]: col for col in inspector.get_columns("order_items")}
    assert "id" in item_cols
    assert "order_id" in item_cols
    assert "product_code" in item_cols
    assert "subtotal" in item_cols

    veh_cols = {col["name"]: col for col in inspector.get_columns("vehicles")}
    assert "id" in veh_cols
    assert "vehicle_code" in veh_cols
    assert "registration_number" in veh_cols
    assert "capacity_kg" in veh_cols
    assert "current_load_kg" in veh_cols
    assert "status" in veh_cols

    wh_cols = {col["name"]: col for col in inspector.get_columns("warehouses")}
    assert "id" in wh_cols
    assert "network_node_id" in wh_cols
    assert "warehouse_code" in wh_cols
    assert "total_capacity" in wh_cols
    assert "used_capacity" in wh_cols

    inv_cols = {col["name"]: col for col in inspector.get_columns("inventory_items")}
    assert "id" in inv_cols
    assert "warehouse_id" in inv_cols
    assert "sku" in inv_cols
    assert "quantity" in inv_cols
    assert "reorder_level" in inv_cols

    # 2. Downgrade to base
    command.downgrade(alembic_cfg, "base")

    inspector = inspect(engine)
    tables_after = inspector.get_table_names()
    assert "simulations" not in tables_after
    assert "users" not in tables_after
    assert "network_nodes" not in tables_after
    assert "network_edges" not in tables_after
    assert "warehouses" not in tables_after
    assert "inventory_items" not in tables_after
    assert "inventory_movements" not in tables_after
    assert "vehicles" not in tables_after
    assert "vehicle_locations" not in tables_after
    assert "vehicle_status_history" not in tables_after
    assert "customers" not in tables_after
    assert "orders" not in tables_after
    assert "order_items" not in tables_after
    assert "order_status_history" not in tables_after
    assert "order_assignment_history" not in tables_after
    assert "simulation_vehicle_states" not in tables_after
    assert "simulation_events" not in tables_after
    assert "simulation_telemetry" not in tables_after
    assert "disruptions" not in tables_after
    assert "disruption_impacts" not in tables_after
    assert "disruption_events" not in tables_after
    assert "reports" not in tables_after

    engine.dispose()

