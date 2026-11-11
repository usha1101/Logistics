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
    String,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship, validates

from app.database.base import Base


class VehicleType(str, enum.Enum):
    HEAVY_TRUCK = "HEAVY_TRUCK"
    MEDIUM_TRUCK = "MEDIUM_TRUCK"
    DELIVERY_VAN = "DELIVERY_VAN"
    ELECTRIC_VAN = "ELECTRIC_VAN"


class VehicleStatus(str, enum.Enum):
    AVAILABLE = "AVAILABLE"
    IDLE = "IDLE"
    IN_TRANSIT = "IN_TRANSIT"
    BREAKDOWN = "BREAKDOWN"
    MAINTENANCE = "MAINTENANCE"
    OFFLINE = "OFFLINE"


class LocationSource(str, enum.Enum):
    SIMULATION = "SIMULATION"
    MANUAL = "MANUAL"
    GPS = "GPS"


class Vehicle(Base):
    __tablename__ = "vehicles"
    __table_args__ = (
        CheckConstraint("capacity_kg > 0", name="check_positive_vehicle_capacity"),
        CheckConstraint("current_load_kg >= 0", name="check_non_negative_current_load"),
        CheckConstraint("current_load_kg <= capacity_kg", name="check_current_load_within_capacity"),
        CheckConstraint(
            "current_latitude IS NULL OR (current_latitude >= -90.0 AND current_latitude <= 90.0)",
            name="check_valid_current_latitude",
        ),
        CheckConstraint(
            "current_longitude IS NULL OR (current_longitude >= -180.0 AND current_longitude <= 180.0)",
            name="check_valid_current_longitude",
        ),
        CheckConstraint(
            "current_speed_kmph IS NULL OR current_speed_kmph >= 0.0",
            name="check_non_negative_speed",
        ),
        CheckConstraint(
            "heading_degrees IS NULL OR (heading_degrees >= 0.0 AND heading_degrees <= 360.0)",
            name="check_valid_heading",
        ),
    )

    id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=lambda: str(uuid.uuid4()),
        index=True,
    )
    vehicle_code: Mapped[str] = mapped_column(
        String(64),
        unique=True,
        nullable=False,
        index=True,
    )
    registration_number: Mapped[str] = mapped_column(
        String(64),
        unique=True,
        nullable=False,
        index=True,
    )
    vehicle_type: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        index=True,
    )
    manufacturer: Mapped[Optional[str]] = mapped_column(
        String(64),
        nullable=True,
    )
    model: Mapped[Optional[str]] = mapped_column(
        String(64),
        nullable=True,
    )
    capacity_kg: Mapped[float] = mapped_column(
        Float,
        nullable=False,
    )
    current_load_kg: Mapped[float] = mapped_column(
        Float,
        nullable=False,
        default=0.0,
    )
    status: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        default=VehicleStatus.AVAILABLE.value,
        index=True,
    )
    home_warehouse_id: Mapped[Optional[str]] = mapped_column(
        String(36),
        ForeignKey("warehouses.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    current_latitude: Mapped[Optional[float]] = mapped_column(
        Float,
        nullable=True,
    )
    current_longitude: Mapped[Optional[float]] = mapped_column(
        Float,
        nullable=True,
    )
    current_speed_kmph: Mapped[Optional[float]] = mapped_column(
        Float,
        nullable=True,
    )
    heading_degrees: Mapped[Optional[float]] = mapped_column(
        Float,
        nullable=True,
    )
    is_active: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        nullable=False,
        index=True,
    )
    last_location_update: Mapped[Optional[datetime]] = mapped_column(
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
    home_warehouse = relationship("Warehouse", lazy="joined")
    locations = relationship(
        "VehicleLocation",
        back_populates="vehicle",
        cascade="all, delete-orphan",
        lazy="select",
        order_by="desc(VehicleLocation.recorded_at)",
    )
    status_history = relationship(
        "VehicleStatusHistory",
        back_populates="vehicle",
        cascade="all, delete-orphan",
        lazy="select",
        order_by="desc(VehicleStatusHistory.changed_at)",
    )

    @property
    def remaining_capacity_kg(self) -> float:
        """Remaining capacity available on this vehicle."""
        return max(0.0, round(self.capacity_kg - self.current_load_kg, 2))

    @property
    def coordinates(self) -> Optional[List[float]]:
        """GeoJSON format [longitude, latitude] if coordinates exist."""
        if self.current_latitude is not None and self.current_longitude is not None:
            return [self.current_longitude, self.current_latitude]
        return None

    @validates("capacity_kg")
    def validate_capacity(self, key: str, value: float) -> float:
        if value is None or value <= 0:
            raise ValueError("capacity_kg must be greater than zero")
        return value

    @validates("current_load_kg")
    def validate_current_load(self, key: str, value: float) -> float:
        if value is None or value < 0:
            raise ValueError("current_load_kg cannot be negative")
        if self.capacity_kg is not None and value > self.capacity_kg:
            raise ValueError(f"current_load_kg ({value}) cannot exceed capacity_kg ({self.capacity_kg})")
        return value

    @validates("current_latitude")
    def validate_lat(self, key: str, value: Optional[float]) -> Optional[float]:
        if value is not None and not (-90.0 <= value <= 90.0):
            raise ValueError(f"current_latitude must be between -90 and 90, got {value}")
        return value

    @validates("current_longitude")
    def validate_lon(self, key: str, value: Optional[float]) -> Optional[float]:
        if value is not None and not (-180.0 <= value <= 180.0):
            raise ValueError(f"current_longitude must be between -180 and 180, got {value}")
        return value

    @validates("current_speed_kmph")
    def validate_speed(self, key: str, value: Optional[float]) -> Optional[float]:
        if value is not None and value < 0:
            raise ValueError(f"current_speed_kmph cannot be negative, got {value}")
        return value

    @validates("heading_degrees")
    def validate_heading(self, key: str, value: Optional[float]) -> Optional[float]:
        if value is not None and not (0.0 <= value <= 360.0):
            raise ValueError(f"heading_degrees must be between 0 and 360, got {value}")
        return value


class VehicleLocation(Base):
    __tablename__ = "vehicle_locations"
    __table_args__ = (
        CheckConstraint("latitude >= -90.0 AND latitude <= 90.0", name="check_valid_location_lat"),
        CheckConstraint("longitude >= -180.0 AND longitude <= 180.0", name="check_valid_location_lon"),
        CheckConstraint("speed_kmph IS NULL OR speed_kmph >= 0.0", name="check_valid_location_speed"),
        CheckConstraint(
            "heading_degrees IS NULL OR (heading_degrees >= 0.0 AND heading_degrees <= 360.0)",
            name="check_valid_location_heading",
        ),
        Index("ix_vehicle_locations_vehicle_recorded", "vehicle_id", "recorded_at"),
    )

    id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=lambda: str(uuid.uuid4()),
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
    speed_kmph: Mapped[Optional[float]] = mapped_column(
        Float,
        nullable=True,
    )
    heading_degrees: Mapped[Optional[float]] = mapped_column(
        Float,
        nullable=True,
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
        default=LocationSource.SIMULATION.value,
    )

    # Relationship
    vehicle = relationship("Vehicle", back_populates="locations")

    @property
    def coordinates(self) -> List[float]:
        """GeoJSON format [longitude, latitude]."""
        return [self.longitude, self.latitude]

    @validates("latitude")
    def validate_lat(self, key: str, value: float) -> float:
        if not (-90.0 <= value <= 90.0):
            raise ValueError(f"latitude must be between -90 and 90, got {value}")
        return value

    @validates("longitude")
    def validate_lon(self, key: str, value: float) -> float:
        if not (-180.0 <= value <= 180.0):
            raise ValueError(f"longitude must be between -180 and 180, got {value}")
        return value

    @validates("speed_kmph")
    def validate_speed(self, key: str, value: Optional[float]) -> Optional[float]:
        if value is not None and value < 0:
            raise ValueError(f"speed_kmph cannot be negative, got {value}")
        return value

    @validates("heading_degrees")
    def validate_heading(self, key: str, value: Optional[float]) -> Optional[float]:
        if value is not None and not (0.0 <= value <= 360.0):
            raise ValueError(f"heading_degrees must be between 0 and 360, got {value}")
        return value


class VehicleStatusHistory(Base):
    __tablename__ = "vehicle_status_history"
    __table_args__ = (
        Index("ix_vehicle_status_history_vehicle_changed", "vehicle_id", "changed_at"),
    )

    id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=lambda: str(uuid.uuid4()),
        index=True,
    )
    vehicle_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("vehicles.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    previous_status: Mapped[Optional[str]] = mapped_column(
        String(32),
        nullable=True,
    )
    new_status: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
    )
    reason: Mapped[Optional[str]] = mapped_column(
        String(255),
        nullable=True,
    )
    changed_by_user_id: Mapped[Optional[str]] = mapped_column(
        String(36),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    changed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        server_default=func.now(),
        index=True,
    )

    # Relationships
    vehicle = relationship("Vehicle", back_populates="status_history")
    changed_by_user = relationship("User", lazy="joined")

