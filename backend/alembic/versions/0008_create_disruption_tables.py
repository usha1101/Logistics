"""create disruption management tables

Revision ID: 0008_create_disruption_tables
Revises: 0007_create_simulation_engine_tables
Create Date: 2026-11-11 19:40:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "0008_create_disruption_tables"
down_revision: Union[str, None] = "0007_create_simulation_engine_tables"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Create disruptions table
    op.create_table(
        "disruptions",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("disruption_code", sa.String(length=64), nullable=False),
        sa.Column("disruption_type", sa.String(length=64), nullable=False),
        sa.Column("severity", sa.String(length=32), nullable=False, server_default="MEDIUM"),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="DETECTED"),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("description", sa.String(length=1024), nullable=True),
        sa.Column("simulation_id", sa.String(length=64), nullable=True),
        sa.Column("affected_vehicle_id", sa.String(length=36), nullable=True),
        sa.Column("affected_warehouse_id", sa.String(length=36), nullable=True),
        sa.Column("affected_network_edge_id", sa.String(length=36), nullable=True),
        sa.Column("affected_order_id", sa.String(length=36), nullable=True),
        sa.Column("location_latitude", sa.Float(), nullable=True),
        sa.Column("location_longitude", sa.Float(), nullable=True),
        sa.Column("parameters", sa.JSON(), nullable=True),
        sa.Column("start_time", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expected_end_time", sa.DateTime(timezone=True), nullable=True),
        sa.Column("actual_end_time", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_by_user_id", sa.String(length=36), nullable=True),
        sa.Column("resolved_by_user_id", sa.String(length=36), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("disruption_code", name="uq_disruption_code"),
        sa.ForeignKeyConstraint(["simulation_id"], ["simulations.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["affected_vehicle_id"], ["vehicles.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["affected_warehouse_id"], ["warehouses.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["affected_network_edge_id"], ["network_edges.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["affected_order_id"], ["orders.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["created_by_user_id"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["resolved_by_user_id"], ["users.id"], ondelete="SET NULL"),
    )
    op.create_index(op.f("ix_disruptions_id"), "disruptions", ["id"], unique=False)
    op.create_index(op.f("ix_disruptions_disruption_code"), "disruptions", ["disruption_code"], unique=False)
    op.create_index(op.f("ix_disruptions_disruption_type"), "disruptions", ["disruption_type"], unique=False)
    op.create_index(op.f("ix_disruptions_severity"), "disruptions", ["severity"], unique=False)
    op.create_index(op.f("ix_disruptions_status"), "disruptions", ["status"], unique=False)
    op.create_index(op.f("ix_disruptions_simulation_id"), "disruptions", ["simulation_id"], unique=False)
    op.create_index(op.f("ix_disruptions_affected_vehicle_id"), "disruptions", ["affected_vehicle_id"], unique=False)
    op.create_index(op.f("ix_disruptions_affected_warehouse_id"), "disruptions", ["affected_warehouse_id"], unique=False)
    op.create_index(op.f("ix_disruptions_affected_network_edge_id"), "disruptions", ["affected_network_edge_id"], unique=False)
    op.create_index("ix_disruptions_type_status", "disruptions", ["disruption_type", "status"], unique=False)

    # 2. Create disruption_impacts table
    op.create_table(
        "disruption_impacts",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("disruption_id", sa.String(length=36), nullable=False),
        sa.Column("affected_resource_type", sa.String(length=32), nullable=False),
        sa.Column("affected_resource_id", sa.String(length=64), nullable=False),
        sa.Column("impact_category", sa.String(length=64), nullable=False, server_default="DIRECT"),
        sa.Column("severity", sa.String(length=32), nullable=False),
        sa.Column("estimated_delay_minutes", sa.Float(), nullable=True),
        sa.Column("impact_details", sa.JSON(), nullable=True),
        sa.Column("detected_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("disruption_id", "affected_resource_type", "affected_resource_id", name="uq_disruption_impact_resource"),
        sa.ForeignKeyConstraint(["disruption_id"], ["disruptions.id"], ondelete="CASCADE"),
    )
    op.create_index(op.f("ix_disruption_impacts_id"), "disruption_impacts", ["id"], unique=False)
    op.create_index(op.f("ix_disruption_impacts_disruption_id"), "disruption_impacts", ["disruption_id"], unique=False)
    op.create_index("ix_disruption_impacts_resource", "disruption_impacts", ["affected_resource_type", "affected_resource_id"], unique=False)

    # 3. Create disruption_events table
    op.create_table(
        "disruption_events",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("disruption_id", sa.String(length=36), nullable=False),
        sa.Column("event_type", sa.String(length=64), nullable=False),
        sa.Column("previous_status", sa.String(length=32), nullable=True),
        sa.Column("new_status", sa.String(length=32), nullable=True),
        sa.Column("event_data", sa.JSON(), nullable=True),
        sa.Column("performed_by_user_id", sa.String(length=36), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["disruption_id"], ["disruptions.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["performed_by_user_id"], ["users.id"], ondelete="SET NULL"),
    )
    op.create_index(op.f("ix_disruption_events_id"), "disruption_events", ["id"], unique=False)
    op.create_index(op.f("ix_disruption_events_disruption_id"), "disruption_events", ["disruption_id"], unique=False)
    op.create_index("ix_disruption_events_disr_created", "disruption_events", ["disruption_id", "created_at"], unique=False)


def downgrade() -> None:
    op.drop_table("disruption_events")
    op.drop_table("disruption_impacts")
    op.drop_table("disruptions")

