import enum
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    JSON,
    String,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base


class SimulationStatus(str, enum.Enum):
    CREATED = "CREATED"
    RUNNING = "RUNNING"
    PAUSED = "PAUSED"
    COMPLETED = "COMPLETED"
    STOPPED = "STOPPED"
    FAILED = "FAILED"


class SimulationVehicleStatus(str, enum.Enum):
    QUEUED = "QUEUED"
    EN_ROUTE = "EN_ROUTE"
    PAUSED = "PAUSED"
    BREAKDOWN = "BREAKDOWN"
    ARRIVED = "ARRIVED"


class SimulationEventType(str, enum.Enum):
    SIMULATION_STARTED = "SIMULATION_STARTED"
    SIMULATION_PAUSED = "SIMULATION_PAUSED"
    SIMULATION_RESUMED = "SIMULATION_RESUMED"
    SIMULATION_STOPPED = "SIMULATION_STOPPED"
    SIMULATION_RESET = "SIMULATION_RESET"
    SIMULATION_SPEED_CHANGED = "SIMULATION_SPEED_CHANGED"
    VEHICLE_ASSIGNED = "VEHICLE_ASSIGNED"
    VEHICLE_DEPARTED = "VEHICLE_DEPARTED"
    VEHICLE_POSITION_UPDATED = "VEHICLE_POSITION_UPDATED"
    VEHICLE_ARRIVED = "VEHICLE_ARRIVED"
    SIMULATION_COMPLETED = "SIMULATION_COMPLETED"
    SIMULATION_FAILED = "SIMULATION_FAILED"


class Simulation(Base):
    __tablename__ = "simulations"

    id: Mapped[str] = mapped_column(
        String(64),
        primary_key=True,
        default=lambda: str(uuid.uuid4()),
        index=True,
    )
    name: Mapped[str] = mapped_column(
        String(128),
        nullable=False,
        default="Default Logistics Simulation",
        index=True,
    )
    seed: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=42,
    )
    status: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        default=SimulationStatus.CREATED.value,
        index=True,
    )
    simulation_speed_multiplier: Mapped[float] = mapped_column(
        Float,
        nullable=False,
        default=1.0,
    )
    simulated_time: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    started_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    paused_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    resumed_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    stopped_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    created_by_user_id: Mapped[Optional[str]] = mapped_column(
        String(36),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    configuration: Mapped[Optional[Dict[str, Any]]] = mapped_column(
        JSON,
        nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        server_default=func.now(),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        server_default=func.now(),
        onupdate=func.now(),
    )

    # Relationships
    vehicle_states = relationship(
        "SimulationVehicleState",
        back_populates="simulation",
        cascade="all, delete-orphan",
        lazy="select",
    )
    events = relationship(
        "SimulationEvent",
        back_populates="simulation",
        cascade="all, delete-orphan",
        lazy="select",
        order_by="desc(SimulationEvent.created_at)",
    )
    telemetry_points = relationship(
        "SimulationTelemetry",
        back_populates="simulation",
        cascade="all, delete-orphan",
        lazy="select",
        order_by="desc(SimulationTelemetry.recorded_at)",
    )


class SimulationVehicleState(Base):
    __tablename__ = "simulation_vehicle_states"
    __table_args__ = (
        UniqueConstraint(
            "simulation_id",
            "vehicle_id",
            name="uq_sim_vehicle_state",
        ),
        CheckConstraint(
            "segment_progress >= 0.0 AND segment_progress <= 1.0",
            name="check_segment_progress_range",
        ),
        CheckConstraint(
            "progress_percentage >= 0.0 AND progress_percentage <= 100.0",
            name="check_progress_percentage_range",
        ),
    )

    id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=lambda: str(uuid.uuid4()),
        index=True,
    )
    simulation_id: Mapped[str] = mapped_column(
        String(64),
        ForeignKey("simulations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    vehicle_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("vehicles.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    origin_node_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("network_nodes.id", ondelete="CASCADE"),
        nullable=False,
    )
    destination_node_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("network_nodes.id", ondelete="CASCADE"),
        nullable=False,
    )
    route_node_ids: Mapped[List[str]] = mapped_column(
        JSON,
        nullable=False,
    )
    current_route_segment: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
    )
    segment_progress: Mapped[float] = mapped_column(
        Float,
        nullable=False,
        default=0.0,
    )
    progress_percentage: Mapped[float] = mapped_column(
        Float,
        nullable=False,
        default=0.0,
    )
    current_latitude: Mapped[float] = mapped_column(
        Float,
        nullable=False,
    )
    current_longitude: Mapped[float] = mapped_column(
        Float,
        nullable=False,
    )
    current_speed_kmph: Mapped[float] = mapped_column(
        Float,
        nullable=False,
        default=0.0,
    )
    heading_degrees: Mapped[float] = mapped_column(
        Float,
        nullable=False,
        default=0.0,
    )
    status: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        default=SimulationVehicleStatus.QUEUED.value,
        index=True,
    )
    simulated_departure_time: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    estimated_arrival_time: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    actual_arrival_time: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        server_default=func.now(),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        server_default=func.now(),
        onupdate=func.now(),
    )

    # Relationships
    simulation = relationship("Simulation", back_populates="vehicle_states")
    vehicle = relationship("Vehicle", lazy="joined")
    origin_node = relationship("NetworkNode", foreign_keys=[origin_node_id], lazy="joined")
    destination_node = relationship("NetworkNode", foreign_keys=[destination_node_id], lazy="joined")


class SimulationEvent(Base):
    __tablename__ = "simulation_events"
    __table_args__ = (
        Index("ix_sim_events_sim_created", "simulation_id", "created_at"),
    )

    id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=lambda: str(uuid.uuid4()),
        index=True,
    )
    simulation_id: Mapped[str] = mapped_column(
        String(64),
        ForeignKey("simulations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    vehicle_id: Mapped[Optional[str]] = mapped_column(
        String(36),
        ForeignKey("vehicles.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    event_type: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
        index=True,
    )
    event_data: Mapped[Optional[Dict[str, Any]]] = mapped_column(
        JSON,
        nullable=True,
    )
    simulated_timestamp: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        server_default=func.now(),
    )

    # Relationships
    simulation = relationship("Simulation", back_populates="events")
    vehicle = relationship("Vehicle", lazy="joined")


class SimulationTelemetry(Base):
    __tablename__ = "simulation_telemetry"
    __table_args__ = (
        CheckConstraint("latitude >= -90.0 AND latitude <= 90.0", name="check_sim_telemetry_lat"),
        CheckConstraint("longitude >= -180.0 AND longitude <= 180.0", name="check_sim_telemetry_lon"),
        CheckConstraint("speed_kmph >= 0.0", name="check_sim_telemetry_speed"),
        Index("ix_sim_telemetry_sim_veh_rec", "simulation_id", "vehicle_id", "recorded_at"),
    )

    id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=lambda: str(uuid.uuid4()),
        index=True,
    )
    simulation_id: Mapped[str] = mapped_column(
        String(64),
        ForeignKey("simulations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    vehicle_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("vehicles.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    latitude: Mapped[float] = mapped_column(
        Float,
        nullable=False,
    )
    longitude: Mapped[float] = mapped_column(
        Float,
        nullable=False,
    )
    speed_kmph: Mapped[float] = mapped_column(
        Float,
        nullable=False,
        default=0.0,
    )
    heading_degrees: Mapped[float] = mapped_column(
        Float,
        nullable=False,
        default=0.0,
    )
    recorded_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        server_default=func.now(),
        index=True,
    )
    source: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        default="SIMULATION",
    )

    # Relationships
    simulation = relationship("Simulation", back_populates="telemetry_points")
    vehicle = relationship("Vehicle", lazy="joined")
