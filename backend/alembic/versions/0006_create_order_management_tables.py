"""create customers, orders, order_items, order_status_history, and order_assignment_history tables

Revision ID: 0006_create_order_management_tables
Revises: 0005_create_fleet_vehicles_tables
Create Date: 2026-11-11 15:30:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "0006_create_order_management_tables"
down_revision: Union[str, None] = "0005_create_fleet_vehicles_tables"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Create customers table
    op.create_table(
        "customers",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("customer_code", sa.String(length=64), nullable=False),
        sa.Column("name", sa.String(length=128), nullable=False),
        sa.Column("email", sa.String(length=128), nullable=True),
        sa.Column("phone", sa.String(length=32), nullable=False),
        sa.Column("address_line", sa.String(length=255), nullable=False),
        sa.Column("city", sa.String(length=64), nullable=False),
        sa.Column("state", sa.String(length=64), nullable=False),
        sa.Column("postal_code", sa.String(length=16), nullable=False),
        sa.Column("latitude", sa.Float(), nullable=False),
        sa.Column("longitude", sa.Float(), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.CheckConstraint("latitude >= -90.0 AND latitude <= 90.0", name="check_valid_customer_lat"),
        sa.CheckConstraint("longitude >= -180.0 AND longitude <= 180.0", name="check_valid_customer_lon"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("customer_code", name="uq_customers_customer_code"),
    )
    op.create_index(op.f("ix_customers_id"), "customers", ["id"], unique=False)
    op.create_index(op.f("ix_customers_customer_code"), "customers", ["customer_code"], unique=True)
    op.create_index(op.f("ix_customers_name"), "customers", ["name"], unique=False)
    op.create_index(op.f("ix_customers_city"), "customers", ["city"], unique=False)
    op.create_index(op.f("ix_customers_is_active"), "customers", ["is_active"], unique=False)

    # 2. Create orders table
    op.create_table(
        "orders",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("order_number", sa.String(length=64), nullable=False),
        sa.Column("customer_id", sa.String(length=36), nullable=False),
        sa.Column("warehouse_id", sa.String(length=36), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="CREATED"),
        sa.Column("priority", sa.String(length=32), nullable=False, server_default="NORMAL"),
        sa.Column(
            "order_date",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column("expected_delivery_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("dispatched_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("delivered_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("delivery_address", sa.String(length=255), nullable=False),
        sa.Column("delivery_latitude", sa.Float(), nullable=False),
        sa.Column("delivery_longitude", sa.Float(), nullable=False),
        sa.Column("total_weight_kg", sa.Float(), nullable=False, server_default="0.0"),
        sa.Column("total_amount", sa.Float(), nullable=False, server_default="0.0"),
        sa.Column("notes", sa.String(length=255), nullable=True),
        sa.Column("assigned_vehicle_id", sa.String(length=36), nullable=True),
        sa.Column("created_by_user_id", sa.String(length=36), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.CheckConstraint("total_weight_kg >= 0", name="check_non_negative_order_weight"),
        sa.CheckConstraint("total_amount >= 0", name="check_non_negative_order_amount"),
        sa.CheckConstraint(
            "delivery_latitude >= -90.0 AND delivery_latitude <= 90.0",
            name="check_valid_delivery_lat",
        ),
        sa.CheckConstraint(
            "delivery_longitude >= -180.0 AND delivery_longitude <= 180.0",
            name="check_valid_delivery_lon",
        ),
        sa.ForeignKeyConstraint(["customer_id"], ["customers.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["warehouse_id"], ["warehouses.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["assigned_vehicle_id"], ["vehicles.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["created_by_user_id"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("order_number", name="uq_orders_order_number"),
    )
    op.create_index(op.f("ix_orders_id"), "orders", ["id"], unique=False)
    op.create_index(op.f("ix_orders_order_number"), "orders", ["order_number"], unique=True)
    op.create_index(op.f("ix_orders_customer_id"), "orders", ["customer_id"], unique=False)
    op.create_index(op.f("ix_orders_warehouse_id"), "orders", ["warehouse_id"], unique=False)
    op.create_index(op.f("ix_orders_status"), "orders", ["status"], unique=False)
    op.create_index(op.f("ix_orders_priority"), "orders", ["priority"], unique=False)
    op.create_index(op.f("ix_orders_expected_delivery_at"), "orders", ["expected_delivery_at"], unique=False)
    op.create_index(op.f("ix_orders_assigned_vehicle_id"), "orders", ["assigned_vehicle_id"], unique=False)
    op.create_index(op.f("ix_orders_created_by_user_id"), "orders", ["created_by_user_id"], unique=False)

    # 3. Create order_items table
    op.create_table(
        "order_items",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("order_id", sa.String(length=36), nullable=False),
        sa.Column("product_code", sa.String(length=64), nullable=False),
        sa.Column("product_name", sa.String(length=128), nullable=False),
        sa.Column("quantity", sa.Integer(), nullable=False),
        sa.Column("unit_price", sa.Float(), nullable=False),
        sa.Column("unit_weight_kg", sa.Float(), nullable=False),
        sa.Column("subtotal", sa.Float(), nullable=False),
        sa.Column("total_weight_kg", sa.Float(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.CheckConstraint("quantity > 0", name="check_positive_item_quantity"),
        sa.CheckConstraint("unit_price >= 0", name="check_non_negative_unit_price"),
        sa.CheckConstraint("unit_weight_kg >= 0", name="check_non_negative_unit_weight"),
        sa.CheckConstraint("subtotal >= 0", name="check_non_negative_subtotal"),
        sa.CheckConstraint("total_weight_kg >= 0", name="check_non_negative_item_weight"),
        sa.ForeignKeyConstraint(["order_id"], ["orders.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_order_items_id"), "order_items", ["id"], unique=False)
    op.create_index(op.f("ix_order_items_order_id"), "order_items", ["order_id"], unique=False)
    op.create_index(op.f("ix_order_items_product_code"), "order_items", ["product_code"], unique=False)

    # 4. Create order_status_history table
    op.create_table(
        "order_status_history",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("order_id", sa.String(length=36), nullable=False),
        sa.Column("previous_status", sa.String(length=32), nullable=True),
        sa.Column("new_status", sa.String(length=32), nullable=False),
        sa.Column("reason", sa.String(length=255), nullable=True),
        sa.Column("changed_by_user_id", sa.String(length=36), nullable=True),
        sa.Column(
            "changed_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["order_id"], ["orders.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["changed_by_user_id"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_order_status_history_id"), "order_status_history", ["id"], unique=False)
    op.create_index(op.f("ix_order_status_history_order_id"), "order_status_history", ["order_id"], unique=False)
    op.create_index(op.f("ix_order_status_history_changed_at"), "order_status_history", ["changed_at"], unique=False)
    op.create_index(
        op.f("ix_order_status_history_changed_by_user_id"),
        "order_status_history",
        ["changed_by_user_id"],
        unique=False,
    )
    op.create_index(
        "ix_order_status_history_order_changed",
        "order_status_history",
        ["order_id", "changed_at"],
        unique=False,
    )

    # 5. Create order_assignment_history table
    op.create_table(
        "order_assignment_history",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("order_id", sa.String(length=36), nullable=False),
        sa.Column("previous_vehicle_id", sa.String(length=36), nullable=True),
        sa.Column("new_vehicle_id", sa.String(length=36), nullable=True),
        sa.Column("assigned_by_user_id", sa.String(length=36), nullable=True),
        sa.Column("reason", sa.String(length=255), nullable=True),
        sa.Column(
            "assigned_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["order_id"], ["orders.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["previous_vehicle_id"], ["vehicles.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["new_vehicle_id"], ["vehicles.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["assigned_by_user_id"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_order_assignment_history_id"), "order_assignment_history", ["id"], unique=False)
    op.create_index(op.f("ix_order_assignment_history_order_id"), "order_assignment_history", ["order_id"], unique=False)
    op.create_index(op.f("ix_order_assignment_history_assigned_at"), "order_assignment_history", ["assigned_at"], unique=False)
    op.create_index(
        op.f("ix_order_assignment_history_previous_vehicle_id"),
        "order_assignment_history",
        ["previous_vehicle_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_order_assignment_history_new_vehicle_id"),
        "order_assignment_history",
        ["new_vehicle_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_order_assignment_history_assigned_by_user_id"),
        "order_assignment_history",
        ["assigned_by_user_id"],
        unique=False,
    )
    op.create_index(
        "ix_order_assignment_history_order_assigned",
        "order_assignment_history",
        ["order_id", "assigned_at"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_order_assignment_history_order_assigned", table_name="order_assignment_history")
    op.drop_index(op.f("ix_order_assignment_history_assigned_by_user_id"), table_name="order_assignment_history")
    op.drop_index(op.f("ix_order_assignment_history_new_vehicle_id"), table_name="order_assignment_history")
    op.drop_index(op.f("ix_order_assignment_history_previous_vehicle_id"), table_name="order_assignment_history")
    op.drop_index(op.f("ix_order_assignment_history_assigned_at"), table_name="order_assignment_history")
    op.drop_index(op.f("ix_order_assignment_history_order_id"), table_name="order_assignment_history")
    op.drop_index(op.f("ix_order_assignment_history_id"), table_name="order_assignment_history")
    op.drop_table("order_assignment_history")

    op.drop_index("ix_order_status_history_order_changed", table_name="order_status_history")
    op.drop_index(op.f("ix_order_status_history_changed_by_user_id"), table_name="order_status_history")
    op.drop_index(op.f("ix_order_status_history_changed_at"), table_name="order_status_history")
    op.drop_index(op.f("ix_order_status_history_order_id"), table_name="order_status_history")
    op.drop_index(op.f("ix_order_status_history_id"), table_name="order_status_history")
    op.drop_table("order_status_history")

    op.drop_index(op.f("ix_order_items_product_code"), table_name="order_items")
    op.drop_index(op.f("ix_order_items_order_id"), table_name="order_items")
    op.drop_index(op.f("ix_order_items_id"), table_name="order_items")
    op.drop_table("order_items")

    op.drop_index(op.f("ix_orders_created_by_user_id"), table_name="orders")
    op.drop_index(op.f("ix_orders_assigned_vehicle_id"), table_name="orders")
    op.drop_index(op.f("ix_orders_expected_delivery_at"), table_name="orders")
    op.drop_index(op.f("ix_orders_priority"), table_name="orders")
    op.drop_index(op.f("ix_orders_status"), table_name="orders")
    op.drop_index(op.f("ix_orders_warehouse_id"), table_name="orders")
    op.drop_index(op.f("ix_orders_customer_id"), table_name="orders")
    op.drop_index(op.f("ix_orders_order_number"), table_name="orders")
    op.drop_index(op.f("ix_orders_id"), table_name="orders")
    op.drop_table("orders")

    op.drop_index(op.f("ix_customers_is_active"), table_name="customers")
    op.drop_index(op.f("ix_customers_city"), table_name="customers")
    op.drop_index(op.f("ix_customers_name"), table_name="customers")
    op.drop_index(op.f("ix_customers_customer_code"), table_name="customers")
    op.drop_index(op.f("ix_customers_id"), table_name="customers")
    op.drop_table("customers")

