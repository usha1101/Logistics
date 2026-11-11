import enum
import uuid
from datetime import datetime
from typing import Optional
from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship, validates

from app.database.base import Base


class NodeType(str, enum.Enum):
    WAREHOUSE = "WAREHOUSE"
    CUSTOMER = "CUSTOMER"


class NetworkNode(Base):
    __tablename__ = "network_nodes"
    __table_args__ = (
        CheckConstraint(
            "latitude >= -90.0 AND latitude <= 90.0",
            name="check_latitude_range",
        ),
        CheckConstraint(
            "longitude >= -180.0 AND longitude <= 180.0",
            name="check_longitude_range",
        ),
    )

    id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=lambda: str(uuid.uuid4()),
        index=True,
    )
    name: Mapped[str] = mapped_column(
        String(128),
        nullable=False,
        index=True,
    )
    node_type: Mapped[str] = mapped_column(
        String(32),
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
    address: Mapped[Optional[str]] = mapped_column(
        String(255),
        nullable=True,
    )
    region: Mapped[Optional[str]] = mapped_column(
        String(64),
        nullable=True,
        index=True,
    )
    is_active: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        nullable=False,
        index=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )

    @validates("latitude")
    def validate_latitude(self, key, value):
        if not (-90.0 <= float(value) <= 90.0):
            raise ValueError("Latitude must be between -90.0 and 90.0")
        return float(value)

    @validates("longitude")
    def validate_longitude(self, key, value):
        if not (-180.0 <= float(value) <= 180.0):
            raise ValueError("Longitude must be between -180.0 and 180.0")
        return float(value)


class NetworkEdge(Base):
    __tablename__ = "network_edges"
    __table_args__ = (
        CheckConstraint(
            "source_node_id != target_node_id",
            name="check_no_self_edge",
        ),
        CheckConstraint(
            "distance_km > 0",
            name="check_positive_distance",
        ),
        CheckConstraint(
            "estimated_travel_minutes > 0",
            name="check_positive_travel_time",
        ),
        UniqueConstraint(
            "source_node_id",
            "target_node_id",
            name="uq_network_edge_source_target",
        ),
    )

    id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=lambda: str(uuid.uuid4()),
        index=True,
    )
    source_node_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("network_nodes.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    target_node_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("network_nodes.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    distance_km: Mapped[float] = mapped_column(
        Float,
        nullable=False,
    )
    estimated_travel_minutes: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
    )
    road_type: Mapped[Optional[str]] = mapped_column(
        String(64),
        nullable=True,
    )
    is_active: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        nullable=False,
        index=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )

    source_node: Mapped[NetworkNode] = relationship(
        "NetworkNode",
        foreign_keys=[source_node_id],
        backref="outgoing_edges",
    )
    target_node: Mapped[NetworkNode] = relationship(
        "NetworkNode",
        foreign_keys=[target_node_id],
        backref="incoming_edges",
    )

    @validates("distance_km")
    def validate_distance(self, key, value):
        if float(value) <= 0:
            raise ValueError("distance_km must be greater than 0")
        return float(value)

    @validates("estimated_travel_minutes")
    def validate_travel_time(self, key, value):
        if int(value) <= 0:
            raise ValueError("estimated_travel_minutes must be greater than 0")
        return int(value)

    @validates("target_node_id")
    def validate_target_node(self, key, value):
        if hasattr(self, "source_node_id") and self.source_node_id and value == self.source_node_id:
            raise ValueError("source_node_id and target_node_id cannot be identical")
        return value

