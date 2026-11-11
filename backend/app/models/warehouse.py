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
    Integer,
    JSON,
    String,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship, validates

from app.database.base import Base


class WarehouseStatus(str, enum.Enum):
    OPERATIONAL = "OPERATIONAL"
    DEGRADED = "DEGRADED"
    CLOSED = "CLOSED"
    MAINTENANCE = "MAINTENANCE"


class WarehouseType(str, enum.Enum):
    DISTRIBUTION_CENTER = "DISTRIBUTION_CENTER"
    FULFILLMENT_CENTER = "FULFILLMENT_CENTER"
    STORAGE_FACILITY = "STORAGE_FACILITY"


class MovementType(str, enum.Enum):
    STOCK_RECEIVED = "STOCK_RECEIVED"
    STOCK_DISPATCHED = "STOCK_DISPATCHED"
    STOCK_ADJUSTMENT = "STOCK_ADJUSTMENT"


class StockStatus(str, enum.Enum):
    OUT_OF_STOCK = "OUT_OF_STOCK"
    LOW_STOCK = "LOW_STOCK"
    IN_STOCK = "IN_STOCK"


class Warehouse(Base):
    __tablename__ = "warehouses"
    __table_args__ = (
        CheckConstraint("total_capacity > 0", name="check_positive_total_capacity"),
        CheckConstraint("used_capacity >= 0", name="check_non_negative_used_capacity"),
        CheckConstraint("used_capacity <= total_capacity", name="check_used_within_total_capacity"),
    )

    id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=lambda: str(uuid.uuid4()),
        index=True,
    )
    network_node_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("network_nodes.id", ondelete="RESTRICT"),
        unique=True,
        nullable=False,
        index=True,
    )
    warehouse_code: Mapped[str] = mapped_column(
        String(32),
        unique=True,
        nullable=False,
        index=True,
    )
    warehouse_type: Mapped[str] = mapped_column(
        String(32),
        default=WarehouseType.DISTRIBUTION_CENTER.value,
        nullable=False,
    )
    total_capacity: Mapped[float] = mapped_column(
        Float,
        nullable=False,
    )
    used_capacity: Mapped[float] = mapped_column(
        Float,
        default=0.0,
        nullable=False,
    )
    status: Mapped[str] = mapped_column(
        String(32),
        default=WarehouseStatus.OPERATIONAL.value,
        nullable=False,
    )
    manager_name: Mapped[Optional[str]] = mapped_column(
        String(128),
        nullable=True,
    )
    contact_number: Mapped[Optional[str]] = mapped_column(
        String(32),
        nullable=True,
    )
    operating_hours: Mapped[Optional[Dict[str, Any]]] = mapped_column(
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
        server_default=func.now(),
        onupdate=func.now(),
    )

    # Relationships
    network_node = relationship("NetworkNode", backref="warehouse_profile", lazy="joined")
    inventory_items = relationship(
        "InventoryItem",
        back_populates="warehouse",
        cascade="all, delete-orphan",
        lazy="select",
    )

    @validates("total_capacity")
    def validate_total_capacity(self, key, value):
        if float(value) <= 0:
            raise ValueError("total_capacity must be greater than 0")
        return float(value)

    @validates("used_capacity")
    def validate_used_capacity(self, key, value):
        val = float(value)
        if val < 0:
            raise ValueError("used_capacity cannot be negative")
        if hasattr(self, "total_capacity") and self.total_capacity is not None and val > self.total_capacity:
            raise ValueError("used_capacity cannot exceed total_capacity")
        return val


class InventoryItem(Base):
    __tablename__ = "inventory_items"
    __table_args__ = (
        UniqueConstraint("warehouse_id", "sku", name="uq_warehouse_sku"),
        CheckConstraint("quantity >= 0", name="check_non_negative_quantity"),
        CheckConstraint("reorder_level >= 0", name="check_non_negative_reorder_level"),
        CheckConstraint("unit_volume IS NULL OR unit_volume > 0", name="check_positive_unit_volume"),
    )

    id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=lambda: str(uuid.uuid4()),
        index=True,
    )
    warehouse_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("warehouses.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    sku: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
        index=True,
    )
    product_name: Mapped[str] = mapped_column(
        String(128),
        nullable=False,
    )
    category: Mapped[Optional[str]] = mapped_column(
        String(64),
        nullable=True,
        index=True,
    )
    quantity: Mapped[int] = mapped_column(
        Integer,
        default=0,
        nullable=False,
    )
    reorder_level: Mapped[int] = mapped_column(
        Integer,
        default=10,
        nullable=False,
    )
    unit: Mapped[str] = mapped_column(
        String(32),
        default="units",
        nullable=False,
    )
    unit_volume: Mapped[Optional[float]] = mapped_column(
        Float,
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
        server_default=func.now(),
        onupdate=func.now(),
    )

    # Relationships
    warehouse = relationship("Warehouse", back_populates="inventory_items")
    movements = relationship(
        "InventoryMovement",
        back_populates="inventory_item",
        cascade="all, delete-orphan",
        lazy="select",
    )

    @property
    def status(self) -> str:
        """Dynamically calculated inventory health status."""
        if self.quantity == 0:
            return StockStatus.OUT_OF_STOCK.value
        elif self.quantity <= self.reorder_level:
            return StockStatus.LOW_STOCK.value
        return StockStatus.IN_STOCK.value

    @validates("quantity")
    def validate_quantity(self, key, value):
        if int(value) < 0:
            raise ValueError("quantity cannot be negative")
        return int(value)

    @validates("reorder_level")
    def validate_reorder_level(self, key, value):
        if int(value) < 0:
            raise ValueError("reorder_level cannot be negative")
        return int(value)

    @validates("unit_volume")
    def validate_unit_volume(self, key, value):
        if value is not None and float(value) <= 0:
            raise ValueError("unit_volume must be greater than 0")
        return float(value) if value is not None else None


class InventoryMovement(Base):
    __tablename__ = "inventory_movements"
    __table_args__ = (
        CheckConstraint("quantity > 0", name="check_positive_movement_quantity"),
    )

    id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=lambda: str(uuid.uuid4()),
        index=True,
    )
    inventory_item_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("inventory_items.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    movement_type: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
    )
    quantity: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
    )
    previous_quantity: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
    )
    new_quantity: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
    )
    reference: Mapped[Optional[str]] = mapped_column(
        String(128),
        nullable=True,
    )
    notes: Mapped[Optional[str]] = mapped_column(
        String(255),
        nullable=True,
    )
    created_by_user_id: Mapped[Optional[str]] = mapped_column(
        String(36),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        server_default=func.now(),
    )

    # Relationships
    inventory_item = relationship("InventoryItem", back_populates="movements")
    created_by_user = relationship("User", lazy="joined")
