"""add soft deletes and compound indexes

Revision ID: 0013_add_soft_deletes_and_indexes
Revises: 0012_create_token_tables
Create Date: 2026-11-20 15:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '0013_add_soft_deletes_and_indexes'
down_revision = '0012_create_token_tables'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 1. Vehicles: soft deletes & compound indexes
    with op.batch_alter_table('vehicles', schema=None) as batch_op:
        batch_op.add_column(sa.Column('is_deleted', sa.Boolean(), nullable=False, server_default=sa.text('0')))
        batch_op.add_column(sa.Column('deleted_at', sa.DateTime(timezone=True), nullable=True))
        batch_op.create_index(batch_op.f('ix_vehicles_is_deleted'), ['is_deleted'], unique=False)
        batch_op.create_index('ix_vehicles_status_deleted', ['status', 'is_deleted'], unique=False)
        batch_op.create_index('ix_vehicles_type_status', ['vehicle_type', 'status'], unique=False)

    # 2. Warehouses: soft deletes & compound indexes
    with op.batch_alter_table('warehouses', schema=None) as batch_op:
        batch_op.add_column(sa.Column('is_deleted', sa.Boolean(), nullable=False, server_default=sa.text('0')))
        batch_op.add_column(sa.Column('deleted_at', sa.DateTime(timezone=True), nullable=True))
        batch_op.create_index(batch_op.f('ix_warehouses_is_deleted'), ['is_deleted'], unique=False)
        batch_op.create_index('ix_warehouses_type_deleted', ['warehouse_type', 'is_deleted'], unique=False)

    # 3. Customers: soft deletes & compound indexes
    with op.batch_alter_table('customers', schema=None) as batch_op:
        batch_op.add_column(sa.Column('is_deleted', sa.Boolean(), nullable=False, server_default=sa.text('0')))
        batch_op.add_column(sa.Column('deleted_at', sa.DateTime(timezone=True), nullable=True))
        batch_op.create_index(batch_op.f('ix_customers_is_deleted'), ['is_deleted'], unique=False)
        batch_op.create_index('ix_customers_city_deleted', ['city', 'is_deleted'], unique=False)

    # 4. Orders: soft deletes & compound indexes
    with op.batch_alter_table('orders', schema=None) as batch_op:
        batch_op.add_column(sa.Column('is_deleted', sa.Boolean(), nullable=False, server_default=sa.text('0')))
        batch_op.add_column(sa.Column('deleted_at', sa.DateTime(timezone=True), nullable=True))
        batch_op.create_index(batch_op.f('ix_orders_is_deleted'), ['is_deleted'], unique=False)
        batch_op.create_index('ix_orders_customer_created', ['customer_id', 'created_at'], unique=False)
        batch_op.create_index('ix_orders_status_created', ['status', 'created_at'], unique=False)
        batch_op.create_index('ix_orders_assigned_vehicle_status', ['assigned_vehicle_id', 'status'], unique=False)
        batch_op.create_index('ix_orders_deleted_status', ['is_deleted', 'status'], unique=False)

    # 5. Inventory Items: compound index
    with op.batch_alter_table('inventory_items', schema=None) as batch_op:
        batch_op.create_index('ix_inventory_items_wh_quantity', ['warehouse_id', 'quantity'], unique=False)

    # 6. Simulation Telemetry: compound index
    with op.batch_alter_table('simulation_telemetry', schema=None) as batch_op:
        batch_op.create_index('ix_sim_telemetry_sim_recorded', ['simulation_id', 'recorded_at'], unique=False)


def downgrade() -> None:
    with op.batch_alter_table('simulation_telemetry', schema=None) as batch_op:
        batch_op.drop_index('ix_sim_telemetry_sim_recorded')

    with op.batch_alter_table('inventory_items', schema=None) as batch_op:
        batch_op.drop_index('ix_inventory_items_wh_quantity')

    with op.batch_alter_table('orders', schema=None) as batch_op:
        batch_op.drop_index('ix_orders_deleted_status')
        batch_op.drop_index('ix_orders_assigned_vehicle_status')
        batch_op.drop_index('ix_orders_status_created')
        batch_op.drop_index('ix_orders_customer_created')
        batch_op.drop_index(batch_op.f('ix_orders_is_deleted'))
        batch_op.drop_column('deleted_at')
        batch_op.drop_column('is_deleted')

    with op.batch_alter_table('customers', schema=None) as batch_op:
        batch_op.drop_index('ix_customers_city_deleted')
        batch_op.drop_index(batch_op.f('ix_customers_is_deleted'))
        batch_op.drop_column('deleted_at')
        batch_op.drop_column('is_deleted')

    with op.batch_alter_table('warehouses', schema=None) as batch_op:
        batch_op.drop_index('ix_warehouses_type_deleted')
        batch_op.drop_index(batch_op.f('ix_warehouses_is_deleted'))
        batch_op.drop_column('deleted_at')
        batch_op.drop_column('is_deleted')

    with op.batch_alter_table('vehicles', schema=None) as batch_op:
        batch_op.drop_index('ix_vehicles_type_status')
        batch_op.drop_index('ix_vehicles_status_deleted')
        batch_op.drop_index(batch_op.f('ix_vehicles_is_deleted'))
        batch_op.drop_column('deleted_at')
        batch_op.drop_column('is_deleted')
