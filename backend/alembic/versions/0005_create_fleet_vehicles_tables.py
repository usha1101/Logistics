"""create vehicles, vehicle_locations, and vehicle_status_history tables

Revision ID: 0005_create_fleet_vehicles_tables
Revises: 0004_create_warehouse_inventory_tables
Create Date: 2026-11-11 15:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "0005_create_fleet_vehicles_tables"
down_revision: Union[str, None] = "0004_create_warehouse_inventory_tables"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Create vehicles table
    op.create_table(
        "vehicles",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("vehicle_code", sa.String(length=64), nullable=False),
        sa.Column("registration_number", sa.String(length=64), nullable=False),
        sa.Column("vehicle_type", sa.String(length=32), nullable=False),
        sa.Column("manufacturer", sa.String(length=64), nullable=True),
        sa.Column("model", sa.String(length=64), nullable=True),
        sa.Column("capacity_kg", sa.Float(), nullable=False),
        sa.Column("current_load_kg", sa.Float(), nullable=False, server_default="0.0"),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="AVAILABLE"),
        sa.Column("home_warehouse_id", sa.String(length=36), nullable=True),
        sa.Column("current_latitude", sa.Float(), nullable=True),
        sa.Column("current_longitude", sa.Float(), nullable=True),
        sa.Column("current_speed_kmph", sa.Float(), nullable=True),
        sa.Column("heading_degrees", sa.Float(), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("last_location_update", sa.DateTime(timezone=True), nullable=True),
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
        sa.CheckConstraint("capacity_kg > 0", name="check_positive_vehicle_capacity"),
        sa.CheckConstraint("current_load_kg >= 0", name="check_non_negative_current_load"),
        sa.CheckConstraint("current_load_kg <= capacity_kg", name="check_current_load_within_capacity"),
        sa.CheckConstraint(
            "current_latitude IS NULL OR (current_latitude >= -90.0 AND current_latitude <= 90.0)",
            name="check_valid_current_latitude",
        ),
        sa.CheckConstraint(
            "current_longitude IS NULL OR (current_longitude >= -180.0 AND current_longitude <= 180.0)",
            name="check_valid_current_longitude",
        ),
        sa.CheckConstraint(
            "current_speed_kmph IS NULL OR current_speed_kmph >= 0.0",
            name="check_non_negative_speed",
        ),
        sa.CheckConstraint(
            "heading_degrees IS NULL OR (heading_degrees >= 0.0 AND heading_degrees <= 360.0)",
            name="check_valid_heading",
        ),
        sa.ForeignKeyConstraint(["home_warehouse_id"], ["warehouses.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("vehicle_code", name="uq_vehicles_vehicle_code"),
        sa.UniqueConstraint("registration_number", name="uq_vehicles_registration_number"),
    )
    op.create_index(op.f("ix_vehicles_id"), "vehicles", ["id"], unique=False)
    op.create_index(op.f("ix_vehicles_vehicle_code"), "vehicles", ["vehicle_code"], unique=True)
    op.create_index(op.f("ix_vehicles_registration_number"), "vehicles", ["registration_number"], unique=True)
    op.create_index(op.f("ix_vehicles_vehicle_type"), "vehicles", ["vehicle_type"], unique=False)
    op.create_index(op.f("ix_vehicles_status"), "vehicles", ["status"], unique=False)
    op.create_index(op.f("ix_vehicles_home_warehouse_id"), "vehicles", ["home_warehouse_id"], unique=False)
    op.create_index(op.f("ix_vehicles_is_active"), "vehicles", ["is_active"], unique=False)

    # 2. Create vehicle_locations table
    op.create_table(
        "vehicle_locations",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("vehicle_id", sa.String(length=36), nullable=False),
        sa.Column("latitude", sa.Float(), nullable=False),
        sa.Column("longitude", sa.Float(), nullable=False),
        sa.Column("speed_kmph", sa.Float(), nullable=True),
        sa.Column("heading_degrees", sa.Float(), nullable=True),
        sa.Column(
            "recorded_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column("source", sa.String(length=32), nullable=False, server_default="SIMULATION"),
        sa.CheckConstraint("latitude >= -90.0 AND latitude <= 90.0", name="check_valid_location_lat"),
        sa.CheckConstraint("longitude >= -180.0 AND longitude <= 180.0", name="check_valid_location_lon"),
        sa.CheckConstraint("speed_kmph IS NULL OR speed_kmph >= 0.0", name="check_valid_location_speed"),
        sa.CheckConstraint(
            "heading_degrees IS NULL OR (heading_degrees >= 0.0 AND heading_degrees <= 360.0)",
            name="check_valid_location_heading",
        ),
        sa.ForeignKeyConstraint(["vehicle_id"], ["vehicles.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_vehicle_locations_id"), "vehicle_locations", ["id"], unique=False)
    op.create_index(op.f("ix_vehicle_locations_vehicle_id"), "vehicle_locations", ["vehicle_id"], unique=False)
    op.create_index(op.f("ix_vehicle_locations_recorded_at"), "vehicle_locations", ["recorded_at"], unique=False)
    op.create_index(
        "ix_vehicle_locations_vehicle_recorded",
        "vehicle_locations",
        ["vehicle_id", "recorded_at"],
        unique=False,
    )

    # 3. Create vehicle_status_history table
    op.create_table(
        "vehicle_status_history",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("vehicle_id", sa.String(length=36), nullable=False),
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
        sa.ForeignKeyConstraint(["vehicle_id"], ["vehicles.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["changed_by_user_id"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_vehicle_status_history_id"), "vehicle_status_history", ["id"], unique=False)
    op.create_index(op.f("ix_vehicle_status_history_vehicle_id"), "vehicle_status_history", ["vehicle_id"], unique=False)
    op.create_index(op.f("ix_vehicle_status_history_changed_at"), "vehicle_status_history", ["changed_at"], unique=False)
    op.create_index(
        op.f("ix_vehicle_status_history_changed_by_user_id"),
        "vehicle_status_history",
        ["changed_by_user_id"],
        unique=False,
    )
    op.create_index(
        "ix_vehicle_status_history_vehicle_changed",
        "vehicle_status_history",
        ["vehicle_id", "changed_at"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_vehicle_status_history_vehicle_changed", table_name="vehicle_status_history")
    op.drop_index(op.f("ix_vehicle_status_history_changed_by_user_id"), table_name="vehicle_status_history")
    op.drop_index(op.f("ix_vehicle_status_history_changed_at"), table_name="vehicle_status_history")
    op.drop_index(op.f("ix_vehicle_status_history_vehicle_id"), table_name="vehicle_status_history")
    op.drop_index(op.f("ix_vehicle_status_history_id"), table_name="vehicle_status_history")
    op.drop_table("vehicle_status_history")

    op.drop_index("ix_vehicle_locations_vehicle_recorded", table_name="vehicle_locations")
    op.drop_index(op.f("ix_vehicle_locations_recorded_at"), table_name="vehicle_locations")
    op.drop_index(op.f("ix_vehicle_locations_vehicle_id"), table_name="vehicle_locations")
    op.drop_index(op.f("ix_vehicle_locations_id"), table_name="vehicle_locations")
    op.drop_table("vehicle_locations")

    op.drop_index(op.f("ix_vehicles_is_active"), table_name="vehicles")
    op.drop_index(op.f("ix_vehicles_home_warehouse_id"), table_name="vehicles")
    op.drop_index(op.f("ix_vehicles_status"), table_name="vehicles")
    op.drop_index(op.f("ix_vehicles_vehicle_type"), table_name="vehicles")
    op.drop_index(op.f("ix_vehicles_registration_number"), table_name="vehicles")
    op.drop_index(op.f("ix_vehicles_vehicle_code"), table_name="vehicles")
    op.drop_index(op.f("ix_vehicles_id"), table_name="vehicles")
    op.drop_table("vehicles")

