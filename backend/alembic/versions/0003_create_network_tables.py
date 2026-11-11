"""create network nodes and edges tables

Revision ID: 0003_create_network_tables
Revises: 0002_create_users_table
Create Date: 2026-11-11 14:10:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "0003_create_network_tables"
down_revision: Union[str, None] = "0002_create_users_table"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Create network_nodes table
    op.create_table(
        "network_nodes",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("name", sa.String(length=128), nullable=False),
        sa.Column("node_type", sa.String(length=32), nullable=False),
        sa.Column("latitude", sa.Float(), nullable=False),
        sa.Column("longitude", sa.Float(), nullable=False),
        sa.Column("address", sa.String(length=255), nullable=True),
        sa.Column("region", sa.String(length=64), nullable=True),
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
        sa.CheckConstraint("latitude >= -90.0 AND latitude <= 90.0", name="check_latitude_range"),
        sa.CheckConstraint("longitude >= -180.0 AND longitude <= 180.0", name="check_longitude_range"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_network_nodes_id"), "network_nodes", ["id"], unique=False)
    op.create_index(op.f("ix_network_nodes_name"), "network_nodes", ["name"], unique=False)
    op.create_index(op.f("ix_network_nodes_node_type"), "network_nodes", ["node_type"], unique=False)
    op.create_index(op.f("ix_network_nodes_region"), "network_nodes", ["region"], unique=False)
    op.create_index(op.f("ix_network_nodes_is_active"), "network_nodes", ["is_active"], unique=False)

    # 2. Create network_edges table
    op.create_table(
        "network_edges",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("source_node_id", sa.String(length=36), nullable=False),
        sa.Column("target_node_id", sa.String(length=36), nullable=False),
        sa.Column("distance_km", sa.Float(), nullable=False),
        sa.Column("estimated_travel_minutes", sa.Integer(), nullable=False),
        sa.Column("road_type", sa.String(length=64), nullable=True),
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
        sa.CheckConstraint("source_node_id != target_node_id", name="check_no_self_edge"),
        sa.CheckConstraint("distance_km > 0", name="check_positive_distance"),
        sa.CheckConstraint("estimated_travel_minutes > 0", name="check_positive_travel_time"),
        sa.ForeignKeyConstraint(["source_node_id"], ["network_nodes.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["target_node_id"], ["network_nodes.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("source_node_id", "target_node_id", name="uq_network_edge_source_target"),
    )
    op.create_index(op.f("ix_network_edges_id"), "network_edges", ["id"], unique=False)
    op.create_index(op.f("ix_network_edges_source_node_id"), "network_edges", ["source_node_id"], unique=False)
    op.create_index(op.f("ix_network_edges_target_node_id"), "network_edges", ["target_node_id"], unique=False)
    op.create_index(op.f("ix_network_edges_is_active"), "network_edges", ["is_active"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_network_edges_is_active"), table_name="network_edges")
    op.drop_index(op.f("ix_network_edges_target_node_id"), table_name="network_edges")
    op.drop_index(op.f("ix_network_edges_source_node_id"), table_name="network_edges")
    op.drop_index(op.f("ix_network_edges_id"), table_name="network_edges")
    op.drop_table("network_edges")

    op.drop_index(op.f("ix_network_nodes_is_active"), table_name="network_nodes")
    op.drop_index(op.f("ix_network_nodes_region"), table_name="network_nodes")
    op.drop_index(op.f("ix_network_nodes_node_type"), table_name="network_nodes")
    op.drop_index(op.f("ix_network_nodes_name"), table_name="network_nodes")
    op.drop_index(op.f("ix_network_nodes_id"), table_name="network_nodes")
    op.drop_table("network_nodes")

