import enum
import re
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Set
from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship, validates

from app.database.base import Base


class OrderStatus(str, enum.Enum):
    CREATED = "CREATED"
    CONFIRMED = "CONFIRMED"
    PROCESSING = "PROCESSING"
    READY_FOR_DISPATCH = "READY_FOR_DISPATCH"
    DISPATCHED = "DISPATCHED"
    IN_TRANSIT = "IN_TRANSIT"
    DELIVERED = "DELIVERED"
    CANCELLED = "CANCELLED"
    ON_HOLD = "ON_HOLD"
    FAILED_DELIVERY = "FAILED_DELIVERY"


class OrderPriority(str, enum.Enum):
    LOW = "LOW"
    NORMAL = "NORMAL"
    HIGH = "HIGH"
    URGENT = "URGENT"


PERMITTED_STATUS_TRANSITIONS: Dict[str, Set[str]] = {
    OrderStatus.CREATED.value: {OrderStatus.CONFIRMED.value, OrderStatus.CANCELLED.value},
    OrderStatus.CONFIRMED.value: {OrderStatus.PROCESSING.value, OrderStatus.ON_HOLD.value, OrderStatus.CANCELLED.value},
    OrderStatus.PROCESSING.value: {OrderStatus.READY_FOR_DISPATCH.value, OrderStatus.ON_HOLD.value, OrderStatus.CANCELLED.value},
    OrderStatus.READY_FOR_DISPATCH.value: {OrderStatus.DISPATCHED.value, OrderStatus.ON_HOLD.value, OrderStatus.CANCELLED.value},
    OrderStatus.DISPATCHED.value: {OrderStatus.IN_TRANSIT.value, OrderStatus.FAILED_DELIVERY.value},
    OrderStatus.IN_TRANSIT.value: {OrderStatus.DELIVERED.value, OrderStatus.FAILED_DELIVERY.value},
    OrderStatus.ON_HOLD.value: {OrderStatus.CONFIRMED.value, OrderStatus.PROCESSING.value, OrderStatus.CANCELLED.value},
    OrderStatus.FAILED_DELIVERY.value: {OrderStatus.PROCESSING.value, OrderStatus.ON_HOLD.value, OrderStatus.CANCELLED.value},
    OrderStatus.DELIVERED.value: set(),
    OrderStatus.CANCELLED.value: set(),
}


class Customer(Base):
    __tablename__ = "customers"
    __table_args__ = (
        CheckConstraint("latitude >= -90.0 AND latitude <= 90.0", name="check_valid_customer_lat"),
        CheckConstraint("longitude >= -180.0 AND longitude <= 180.0", name="check_valid_customer_lon"),
    )

    id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=lambda: str(uuid.uuid4()),
        index=True,
    )
    customer_code: Mapped[str] = mapped_column(
        String(64),
        unique=True,
        nullable=False,
        index=True,
    )
    name: Mapped[str] = mapped_column(
        String(128),
        nullable=False,
        index=True,
    )
    email: Mapped[Optional[str]] = mapped_column(
        String(128),
        nullable=True,
    )
    phone: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
    )
    address_line: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )
    city: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
        index=True,
    )
    state: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
    )
    postal_code: Mapped[str] = mapped_column(
        String(16),
        nullable=False,
    )
    latitude: Mapped[float] = mapped_column(
        Float,
        nullable=False,
    )
    longitude: Mapped[float] = mapped_column(
        Float,
        nullable=False,
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
    orders = relationship("Order", back_populates="customer", cascade="all, delete-orphan", lazy="select")

    @property
    def coordinates(self) -> List[float]:
        return [self.longitude, self.latitude]

    @validates("customer_code")
    def validate_code(self, key: str, value: str) -> str:
        if not value or not value.strip():
            raise ValueError("customer_code cannot be empty")
        return value.strip()

    @validates("name")
    def validate_name(self, key: str, value: str) -> str:
        if not value or not value.strip():
            raise ValueError("customer name cannot be empty")
        return value.strip()

    @validates("phone")
    def validate_phone(self, key: str, value: str) -> str:
        if not value or not value.strip():
            raise ValueError("customer phone cannot be empty")
        return value.strip()

    @validates("email")
    def validate_email(self, key: str, value: Optional[str]) -> Optional[str]:
        if value:
            pattern = r"^[^@\s]+@[^@\s]+\.[^@\s]+$"
            if not re.match(pattern, value):
                raise ValueError(f"Invalid email format: {value}")
            return value.strip().lower()
        return value

    @validates("latitude")
    def validate_lat(self, key: str, value: float) -> float:
        if value is None or not (-90.0 <= value <= 90.0):
            raise ValueError(f"latitude must be between -90 and 90, got {value}")
        return value

    @validates("longitude")
    def validate_lon(self, key: str, value: float) -> float:
        if value is None or not (-180.0 <= value <= 180.0):
            raise ValueError(f"longitude must be between -180 and 180, got {value}")
        return value


class Order(Base):
    __tablename__ = "orders"
    __table_args__ = (
        CheckConstraint("total_weight_kg >= 0", name="check_non_negative_order_weight"),
        CheckConstraint("total_amount >= 0", name="check_non_negative_order_amount"),
        CheckConstraint("delivery_latitude >= -90.0 AND delivery_latitude <= 90.0", name="check_valid_delivery_lat"),
        CheckConstraint("delivery_longitude >= -180.0 AND delivery_longitude <= 180.0", name="check_valid_delivery_lon"),
    )

    id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=lambda: str(uuid.uuid4()),
        index=True,
    )
    order_number: Mapped[str] = mapped_column(
        String(64),
        unique=True,
        nullable=False,
        index=True,
    )
    customer_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("customers.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    warehouse_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("warehouses.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    status: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        default=OrderStatus.CREATED.value,
        index=True,
    )
    priority: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        default=OrderPriority.NORMAL.value,
        index=True,
    )
    order_date: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        server_default=func.now(),
    )
    expected_delivery_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        index=True,
    )
    dispatched_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    delivered_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    delivery_address: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )
    delivery_latitude: Mapped[float] = mapped_column(
        Float,
        nullable=False,
    )
    delivery_longitude: Mapped[float] = mapped_column(
        Float,
        nullable=False,
    )
    total_weight_kg: Mapped[float] = mapped_column(
        Float,
        nullable=False,
        default=0.0,
    )
    total_amount: Mapped[float] = mapped_column(
        Float,
        nullable=False,
        default=0.0,
    )
    notes: Mapped[Optional[str]] = mapped_column(
        String(255),
        nullable=True,
    )
    assigned_vehicle_id: Mapped[Optional[str]] = mapped_column(
        String(36),
        ForeignKey("vehicles.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
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
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        server_default=func.now(),
        onupdate=func.now(),
    )

    # Relationships
    customer = relationship("Customer", back_populates="orders", lazy="joined")
    warehouse = relationship("Warehouse", lazy="joined")
    assigned_vehicle = relationship("Vehicle", lazy="joined")
    created_by_user = relationship("User", lazy="joined")
    items = relationship(
        "OrderItem",
        back_populates="order",
        cascade="all, delete-orphan",
        lazy="select",
    )
    status_history = relationship(
        "OrderStatusHistory",
        back_populates="order",
        cascade="all, delete-orphan",
        lazy="select",
        order_by="desc(OrderStatusHistory.changed_at)",
    )
    assignment_history = relationship(
        "OrderAssignmentHistory",
        back_populates="order",
        cascade="all, delete-orphan",
        lazy="select",
        order_by="desc(OrderAssignmentHistory.assigned_at)",
    )

    @property
    def coordinates(self) -> List[float]:
        return [self.delivery_longitude, self.delivery_latitude]

    @property
    def is_overdue(self) -> bool:
        if self.status in (OrderStatus.DELIVERED.value, OrderStatus.CANCELLED.value):
            return False
        exp = self.expected_delivery_at
        if exp is None:
            return False
        if exp.tzinfo is None:
            exp = exp.replace(tzinfo=timezone.utc)
        return datetime.now(timezone.utc) > exp

    @validates("order_number")
    def validate_order_number(self, key: str, value: str) -> str:
        if not value or not value.strip():
            raise ValueError("order_number cannot be empty")
        return value.strip()

    @validates("total_weight_kg")
    def validate_weight(self, key: str, value: float) -> float:
        if value is not None and value < 0:
            raise ValueError("total_weight_kg cannot be negative")
        return value

    @validates("total_amount")
    def validate_amount(self, key: str, value: float) -> float:
        if value is not None and value < 0:
            raise ValueError("total_amount cannot be negative")
        return value

    @validates("delivery_latitude")
    def validate_lat(self, key: str, value: float) -> float:
        if value is None or not (-90.0 <= value <= 90.0):
            raise ValueError(f"delivery_latitude must be between -90 and 90, got {value}")
        return value

    @validates("delivery_longitude")
    def validate_lon(self, key: str, value: float) -> float:
        if value is None or not (-180.0 <= value <= 180.0):
            raise ValueError(f"delivery_longitude must be between -180 and 180, got {value}")
        return value


class OrderItem(Base):
    __tablename__ = "order_items"
    __table_args__ = (
        CheckConstraint("quantity > 0", name="check_positive_item_quantity"),
        CheckConstraint("unit_price >= 0", name="check_non_negative_unit_price"),
        CheckConstraint("unit_weight_kg >= 0", name="check_non_negative_unit_weight"),
        CheckConstraint("subtotal >= 0", name="check_non_negative_subtotal"),
        CheckConstraint("total_weight_kg >= 0", name="check_non_negative_item_weight"),
    )

    id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=lambda: str(uuid.uuid4()),
        index=True,
    )
    order_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("orders.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    product_code: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
        index=True,
    )
    product_name: Mapped[str] = mapped_column(
        String(128),
        nullable=False,
    )
    quantity: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
    )
    unit_price: Mapped[float] = mapped_column(
        Float,
        nullable=False,
    )
    unit_weight_kg: Mapped[float] = mapped_column(
        Float,
        nullable=False,
    )
    subtotal: Mapped[float] = mapped_column(
        Float,
        nullable=False,
    )
    total_weight_kg: Mapped[float] = mapped_column(
        Float,
        nullable=False,
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

    # Relationship
    order = relationship("Order", back_populates="items")

    @validates("quantity")
    def validate_quantity(self, key: str, value: int) -> int:
        if value is None or value <= 0:
            raise ValueError("quantity must be greater than zero")
        return value

    @validates("unit_price")
    def validate_price(self, key: str, value: float) -> float:
        if value is None or value < 0:
            raise ValueError("unit_price cannot be negative")
        return value

    @validates("unit_weight_kg")
    def validate_unit_weight(self, key: str, value: float) -> float:
        if value is None or value < 0:
            raise ValueError("unit_weight_kg cannot be negative")
        return value


class OrderStatusHistory(Base):
    __tablename__ = "order_status_history"
    __table_args__ = (
        Index("ix_order_status_history_order_changed", "order_id", "changed_at"),
    )

    id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=lambda: str(uuid.uuid4()),
        index=True,
    )
    order_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("orders.id", ondelete="CASCADE"),
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
    order = relationship("Order", back_populates="status_history")
    changed_by_user = relationship("User", lazy="joined")


class OrderAssignmentHistory(Base):
    __tablename__ = "order_assignment_history"
    __table_args__ = (
        Index("ix_order_assignment_history_order_assigned", "order_id", "assigned_at"),
    )

    id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=lambda: str(uuid.uuid4()),
        index=True,
    )
    order_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("orders.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    previous_vehicle_id: Mapped[Optional[str]] = mapped_column(
        String(36),
        ForeignKey("vehicles.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    new_vehicle_id: Mapped[Optional[str]] = mapped_column(
        String(36),
        ForeignKey("vehicles.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    assigned_by_user_id: Mapped[Optional[str]] = mapped_column(
        String(36),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    reason: Mapped[Optional[str]] = mapped_column(
        String(255),
        nullable=True,
    )
    assigned_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        server_default=func.now(),
        index=True,
    )

    # Relationships
    order = relationship("Order", back_populates="assignment_history")
    previous_vehicle = relationship("Vehicle", foreign_keys=[previous_vehicle_id], lazy="joined")
    new_vehicle = relationship("Vehicle", foreign_keys=[new_vehicle_id], lazy="joined")
    assigned_by_user = relationship("User", lazy="joined")

