"""create simulation engine tables

Revision ID: 0007_create_simulation_engine_tables
Revises: 0006_create_order_management_tables
Create Date: 2026-11-11 19:10:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "0007_create_simulation_engine_tables"
down_revision: Union[str, None] = "0006_create_order_management_tables"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Extend existing simulations table with lifecycle and configuration attributes
    with op.batch_alter_table("simulations", schema=None) as batch_op:
        batch_op.add_column(
            sa.Column("name", sa.String(length=128), nullable=False, server_default="Default Logistics Simulation")
        )
        batch_op.add_column(
            sa.Column("simulation_speed_multiplier", sa.Float(), nullable=False, server_default="1.0")
        )
        batch_op.add_column(
            sa.Column("simulated_time", sa.DateTime(timezone=True), nullable=True)
        )
        batch_op.add_column(
            sa.Column("started_at", sa.DateTime(timezone=True), nullable=True)
        )
        batch_op.add_column(
            sa.Column("paused_at", sa.DateTime(timezone=True), nullable=True)
        )
        batch_op.add_column(
            sa.Column("resumed_at", sa.DateTime(timezone=True), nullable=True)
        )
        batch_op.add_column(
            sa.Column("stopped_at", sa.DateTime(timezone=True), nullable=True)
        )
        batch_op.add_column(
            sa.Column("created_by_user_id", sa.String(length=36), nullable=True)
        )
        batch_op.add_column(
            sa.Column("configuration", sa.JSON(), nullable=True)
        )
        batch_op.create_index(batch_op.f("ix_simulations_name"), ["name"], unique=False)
        batch_op.create_foreign_key(
            "fk_simulations_created_by_user_id",
            "users",
            ["created_by_user_id"],
            ["id"],
            ondelete="SET NULL",
        )

    # 2. Create simulation_vehicle_states table
    op.create_table(
        "simulation_vehicle_states",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("simulation_id", sa.String(length=64), nullable=False),
        sa.Column("vehicle_id", sa.String(length=36), nullable=False),
        sa.Column("origin_node_id", sa.String(length=36), nullable=False),
        sa.Column("destination_node_id", sa.String(length=36), nullable=False),
        sa.Column("route_node_ids", sa.JSON(), nullable=False),
        sa.Column("current_route_segment", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("segment_progress", sa.Float(), nullable=False, server_default="0.0"),
        sa.Column("progress_percentage", sa.Float(), nullable=False, server_default="0.0"),
        sa.Column("current_latitude", sa.Float(), nullable=False),
        sa.Column("current_longitude", sa.Float(), nullable=False),
        sa.Column("current_speed_kmph", sa.Float(), nullable=False, server_default="0.0"),
        sa.Column("heading_degrees", sa.Float(), nullable=False, server_default="0.0"),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="QUEUED"),
        sa.Column("simulated_departure_time", sa.DateTime(timezone=True), nullable=True),
        sa.Column("estimated_arrival_time", sa.DateTime(timezone=True), nullable=True),
        sa.Column("actual_arrival_time", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("simulation_id", "vehicle_id", name="uq_sim_vehicle_state"),
        sa.ForeignKeyConstraint(["simulation_id"], ["simulations.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["vehicle_id"], ["vehicles.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["origin_node_id"], ["network_nodes.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["destination_node_id"], ["network_nodes.id"], ondelete="CASCADE"),
    )
    op.create_index(op.f("ix_simulation_vehicle_states_id"), "simulation_vehicle_states", ["id"], unique=False)
    op.create_index(op.f("ix_simulation_vehicle_states_simulation_id"), "simulation_vehicle_states", ["simulation_id"], unique=False)
    op.create_index(op.f("ix_simulation_vehicle_states_vehicle_id"), "simulation_vehicle_states", ["vehicle_id"], unique=False)
    op.create_index(op.f("ix_simulation_vehicle_states_status"), "simulation_vehicle_states", ["status"], unique=False)

    # 3. Create simulation_events table
    op.create_table(
        "simulation_events",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("simulation_id", sa.String(length=64), nullable=False),
        sa.Column("vehicle_id", sa.String(length=36), nullable=True),
        sa.Column("event_type", sa.String(length=64), nullable=False),
        sa.Column("event_data", sa.JSON(), nullable=True),
        sa.Column("simulated_timestamp", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["simulation_id"], ["simulations.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["vehicle_id"], ["vehicles.id"], ondelete="SET NULL"),
    )
    op.create_index(op.f("ix_simulation_events_id"), "simulation_events", ["id"], unique=False)
    op.create_index(op.f("ix_simulation_events_simulation_id"), "simulation_events", ["simulation_id"], unique=False)
    op.create_index(op.f("ix_simulation_events_vehicle_id"), "simulation_events", ["vehicle_id"], unique=False)
    op.create_index(op.f("ix_simulation_events_event_type"), "simulation_events", ["event_type"], unique=False)
    op.create_index("ix_sim_events_sim_created", "simulation_events", ["simulation_id", "created_at"], unique=False)

    # 4. Create simulation_telemetry table
    op.create_table(
        "simulation_telemetry",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("simulation_id", sa.String(length=64), nullable=False),
        sa.Column("vehicle_id", sa.String(length=36), nullable=False),
        sa.Column("latitude", sa.Float(), nullable=False),
        sa.Column("longitude", sa.Float(), nullable=False),
        sa.Column("speed_kmph", sa.Float(), nullable=False, server_default="0.0"),
        sa.Column("heading_degrees", sa.Float(), nullable=False, server_default="0.0"),
        sa.Column("recorded_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("source", sa.String(length=32), nullable=False, server_default="SIMULATION"),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["simulation_id"], ["simulations.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["vehicle_id"], ["vehicles.id"], ondelete="CASCADE"),
    )
    op.create_index(op.f("ix_simulation_telemetry_id"), "simulation_telemetry", ["id"], unique=False)
    op.create_index(op.f("ix_simulation_telemetry_simulation_id"), "simulation_telemetry", ["simulation_id"], unique=False)
    op.create_index(op.f("ix_simulation_telemetry_vehicle_id"), "simulation_telemetry", ["vehicle_id"], unique=False)
    op.create_index(op.f("ix_simulation_telemetry_recorded_at"), "simulation_telemetry", ["recorded_at"], unique=False)
    op.create_index("ix_sim_telemetry_sim_veh_rec", "simulation_telemetry", ["simulation_id", "vehicle_id", "recorded_at"], unique=False)


def downgrade() -> None:
    op.drop_table("simulation_telemetry")
    op.drop_table("simulation_events")
    op.drop_table("simulation_vehicle_states")
    with op.batch_alter_table("simulations", schema=None) as batch_op:
        batch_op.drop_constraint("fk_simulations_created_by_user_id", type_="foreignkey")
        batch_op.drop_index(batch_op.f("ix_simulations_name"))
        batch_op.drop_column("configuration")
        batch_op.drop_column("created_by_user_id")
        batch_op.drop_column("stopped_at")
        batch_op.drop_column("resumed_at")
        batch_op.drop_column("paused_at")
        batch_op.drop_column("started_at")
        batch_op.drop_column("simulated_time")
        batch_op.drop_column("simulation_speed_multiplier")
        batch_op.drop_column("name")

