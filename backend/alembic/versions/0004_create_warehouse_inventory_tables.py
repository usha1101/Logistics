"""create warehouse, inventory_items, and inventory_movements tables

Revision ID: 0004_create_warehouse_inventory_tables
Revises: 0003_create_network_tables
Create Date: 2026-11-11 14:30:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "0004_create_warehouse_inventory_tables"
down_revision: Union[str, None] = "0003_create_network_tables"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Create warehouses table
    op.create_table(
        "warehouses",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("network_node_id", sa.String(length=36), nullable=False),
        sa.Column("warehouse_code", sa.String(length=32), nullable=False),
        sa.Column("warehouse_type", sa.String(length=32), nullable=False, server_default="DISTRIBUTION_CENTER"),
        sa.Column("total_capacity", sa.Float(), nullable=False),
        sa.Column("used_capacity", sa.Float(), nullable=False, server_default="0.0"),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="OPERATIONAL"),
        sa.Column("manager_name", sa.String(length=128), nullable=True),
        sa.Column("contact_number", sa.String(length=32), nullable=True),
        sa.Column("operating_hours", sa.JSON(), nullable=True),
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
        sa.CheckConstraint("total_capacity > 0", name="check_positive_total_capacity"),
        sa.CheckConstraint("used_capacity >= 0", name="check_non_negative_used_capacity"),
        sa.CheckConstraint("used_capacity <= total_capacity", name="check_used_within_total_capacity"),
        sa.ForeignKeyConstraint(["network_node_id"], ["network_nodes.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("network_node_id", name="uq_warehouses_network_node_id"),
        sa.UniqueConstraint("warehouse_code", name="uq_warehouses_warehouse_code"),
    )
    op.create_index(op.f("ix_warehouses_id"), "warehouses", ["id"], unique=False)
    op.create_index(op.f("ix_warehouses_network_node_id"), "warehouses", ["network_node_id"], unique=True)
    op.create_index(op.f("ix_warehouses_warehouse_code"), "warehouses", ["warehouse_code"], unique=True)

    # 2. Create inventory_items table
    op.create_table(
        "inventory_items",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("warehouse_id", sa.String(length=36), nullable=False),
        sa.Column("sku", sa.String(length=64), nullable=False),
        sa.Column("product_name", sa.String(length=128), nullable=False),
        sa.Column("category", sa.String(length=64), nullable=True),
        sa.Column("quantity", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("reorder_level", sa.Integer(), nullable=False, server_default="10"),
        sa.Column("unit", sa.String(length=32), nullable=False, server_default="units"),
        sa.Column("unit_volume", sa.Float(), nullable=True),
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
        sa.CheckConstraint("quantity >= 0", name="check_non_negative_quantity"),
        sa.CheckConstraint("reorder_level >= 0", name="check_non_negative_reorder_level"),
        sa.CheckConstraint("unit_volume IS NULL OR unit_volume > 0", name="check_positive_unit_volume"),
        sa.ForeignKeyConstraint(["warehouse_id"], ["warehouses.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("warehouse_id", "sku", name="uq_warehouse_sku"),
    )
    op.create_index(op.f("ix_inventory_items_id"), "inventory_items", ["id"], unique=False)
    op.create_index(op.f("ix_inventory_items_warehouse_id"), "inventory_items", ["warehouse_id"], unique=False)
    op.create_index(op.f("ix_inventory_items_sku"), "inventory_items", ["sku"], unique=False)
    op.create_index(op.f("ix_inventory_items_category"), "inventory_items", ["category"], unique=False)

    # 3. Create inventory_movements table
    op.create_table(
        "inventory_movements",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("inventory_item_id", sa.String(length=36), nullable=False),
        sa.Column("movement_type", sa.String(length=32), nullable=False),
        sa.Column("quantity", sa.Integer(), nullable=False),
        sa.Column("previous_quantity", sa.Integer(), nullable=False),
        sa.Column("new_quantity", sa.Integer(), nullable=False),
        sa.Column("reference", sa.String(length=128), nullable=True),
        sa.Column("notes", sa.String(length=255), nullable=True),
        sa.Column("created_by_user_id", sa.String(length=36), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.CheckConstraint("quantity > 0", name="check_positive_movement_quantity"),
        sa.ForeignKeyConstraint(["inventory_item_id"], ["inventory_items.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["created_by_user_id"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_inventory_movements_id"), "inventory_movements", ["id"], unique=False)
    op.create_index(op.f("ix_inventory_movements_inventory_item_id"), "inventory_movements", ["inventory_item_id"], unique=False)
    op.create_index(op.f("ix_inventory_movements_created_by_user_id"), "inventory_movements", ["created_by_user_id"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_inventory_movements_created_by_user_id"), table_name="inventory_movements")
    op.drop_index(op.f("ix_inventory_movements_inventory_item_id"), table_name="inventory_movements")
    op.drop_index(op.f("ix_inventory_movements_id"), table_name="inventory_movements")
    op.drop_table("inventory_movements")

    op.drop_index(op.f("ix_inventory_items_category"), table_name="inventory_items")
    op.drop_index(op.f("ix_inventory_items_sku"), table_name="inventory_items")
    op.drop_index(op.f("ix_inventory_items_warehouse_id"), table_name="inventory_items")
    op.drop_index(op.f("ix_inventory_items_id"), table_name="inventory_items")
    op.drop_table("inventory_items")

    op.drop_index(op.f("ix_warehouses_warehouse_code"), table_name="warehouses")
    op.drop_index(op.f("ix_warehouses_network_node_id"), table_name="warehouses")
    op.drop_index(op.f("ix_warehouses_id"), table_name="warehouses")
    op.drop_table("warehouses")

