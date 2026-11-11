import enum
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from sqlalchemy import (
    CheckConstraint,
    DateTime,
    Float,
    ForeignKey,
    Index,
    JSON,
    String,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base


class DisruptionType(str, enum.Enum):
    VEHICLE_BREAKDOWN = "VEHICLE_BREAKDOWN"
    TRAFFIC_CONGESTION = "TRAFFIC_CONGESTION"
    WAREHOUSE_SHUTDOWN = "WAREHOUSE_SHUTDOWN"
    DEMAND_SURGE = "DEMAND_SURGE"
    DELIVERY_DELAY = "DELIVERY_DELAY"


class DisruptionSeverity(str, enum.Enum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


class DisruptionStatus(str, enum.Enum):
    DETECTED = "DETECTED"
    ACTIVE = "ACTIVE"
    MONITORING = "MONITORING"
    RESOLVED = "RESOLVED"
    CANCELLED = "CANCELLED"


class DisruptionEventType(str, enum.Enum):
    DISRUPTION_CREATED = "DISRUPTION_CREATED"
    DISRUPTION_ACTIVATED = "DISRUPTION_ACTIVATED"
    DISRUPTION_IMPACT_ANALYZED = "DISRUPTION_IMPACT_ANALYZED"
    DISRUPTION_UPDATED = "DISRUPTION_UPDATED"
    DISRUPTION_MONITORING = "DISRUPTION_MONITORING"
    DISRUPTION_RESOLVED = "DISRUPTION_RESOLVED"
    DISRUPTION_CANCELLED = "DISRUPTION_CANCELLED"


class AffectedResourceType(str, enum.Enum):
    VEHICLE = "VEHICLE"
    ORDER = "ORDER"
    WAREHOUSE = "WAREHOUSE"
    NETWORK_EDGE = "NETWORK_EDGE"


class Disruption(Base):
    __tablename__ = "disruptions"
    __table_args__ = (
        UniqueConstraint("disruption_code", name="uq_disruption_code"),
        Index("ix_disruptions_type_status", "disruption_type", "status"),
    )

    id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=lambda: str(uuid.uuid4()),
        index=True,
    )
    disruption_code: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
        index=True,
    )
    disruption_type: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
        index=True,
    )
    severity: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        default=DisruptionSeverity.MEDIUM.value,
        index=True,
    )
    status: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        default=DisruptionStatus.DETECTED.value,
        index=True,
    )
    title: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )
    description: Mapped[Optional[str]] = mapped_column(
        String(1024),
        nullable=True,
    )
    simulation_id: Mapped[Optional[str]] = mapped_column(
        String(64),
        ForeignKey("simulations.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    affected_vehicle_id: Mapped[Optional[str]] = mapped_column(
        String(36),
        ForeignKey("vehicles.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    affected_warehouse_id: Mapped[Optional[str]] = mapped_column(
        String(36),
        ForeignKey("warehouses.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    affected_network_edge_id: Mapped[Optional[str]] = mapped_column(
        String(36),
        ForeignKey("network_edges.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    affected_order_id: Mapped[Optional[str]] = mapped_column(
        String(36),
        ForeignKey("orders.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    location_latitude: Mapped[Optional[float]] = mapped_column(
        Float,
        nullable=True,
    )
    location_longitude: Mapped[Optional[float]] = mapped_column(
        Float,
        nullable=True,
    )
    parameters: Mapped[Optional[Dict[str, Any]]] = mapped_column(
        JSON,
        nullable=True,
    )
    start_time: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )
    expected_end_time: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    actual_end_time: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    created_by_user_id: Mapped[Optional[str]] = mapped_column(
        String(36),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    resolved_by_user_id: Mapped[Optional[str]] = mapped_column(
        String(36),
        ForeignKey("users.id", ondelete="SET NULL"),
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
    simulation = relationship("Simulation", lazy="joined")
    affected_vehicle = relationship("Vehicle", foreign_keys=[affected_vehicle_id], lazy="joined")
    affected_warehouse = relationship("Warehouse", foreign_keys=[affected_warehouse_id], lazy="joined")
    affected_network_edge = relationship("NetworkEdge", foreign_keys=[affected_network_edge_id], lazy="joined")
    affected_order = relationship("Order", foreign_keys=[affected_order_id], lazy="joined")
    created_by_user = relationship("User", foreign_keys=[created_by_user_id], lazy="joined")
    resolved_by_user = relationship("User", foreign_keys=[resolved_by_user_id], lazy="joined")

    impacts = relationship(
        "DisruptionImpact",
        back_populates="disruption",
        cascade="all, delete-orphan",
        lazy="select",
    )
    events = relationship(
        "DisruptionEvent",
        back_populates="disruption",
        cascade="all, delete-orphan",
        lazy="select",
        order_by="desc(DisruptionEvent.created_at)",
    )


class DisruptionImpact(Base):
    __tablename__ = "disruption_impacts"
    __table_args__ = (
        UniqueConstraint(
            "disruption_id",
            "affected_resource_type",
            "affected_resource_id",
            name="uq_disruption_impact_resource",
        ),
        Index("ix_disruption_impacts_resource", "affected_resource_type", "affected_resource_id"),
    )

    id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=lambda: str(uuid.uuid4()),
        index=True,
    )
    disruption_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("disruptions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    affected_resource_type: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
    )
    affected_resource_id: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
    )
    impact_category: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
        default="DIRECT",
    )
    severity: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
    )
    estimated_delay_minutes: Mapped[Optional[float]] = mapped_column(
        Float,
        nullable=True,
    )
    impact_details: Mapped[Optional[Dict[str, Any]]] = mapped_column(
        JSON,
        nullable=True,
    )
    detected_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        server_default=func.now(),
    )

    # Relationships
    disruption = relationship("Disruption", back_populates="impacts")


class DisruptionEvent(Base):
    __tablename__ = "disruption_events"
    __table_args__ = (
        Index("ix_disruption_events_disr_created", "disruption_id", "created_at"),
    )

    id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=lambda: str(uuid.uuid4()),
        index=True,
    )
    disruption_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("disruptions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    event_type: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
        index=True,
    )
    previous_status: Mapped[Optional[str]] = mapped_column(
        String(32),
        nullable=True,
    )
    new_status: Mapped[Optional[str]] = mapped_column(
        String(32),
        nullable=True,
    )
    event_data: Mapped[Optional[Dict[str, Any]]] = mapped_column(
        JSON,
        nullable=True,
    )
    performed_by_user_id: Mapped[Optional[str]] = mapped_column(
        String(36),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        server_default=func.now(),
    )

    # Relationships
    disruption = relationship("Disruption", back_populates="events")
    performed_by_user = relationship("User", foreign_keys=[performed_by_user_id], lazy="joined")
