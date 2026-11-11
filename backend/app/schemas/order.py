import re
from datetime import datetime
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.models.order import OrderPriority, OrderStatus


# Customer Schemas
class CustomerBase(BaseModel):
    customer_code: str = Field(..., min_length=2, max_length=64, description="Unique customer reference code")
    name: str = Field(..., min_length=2, max_length=128, description="Customer or company name")
    email: Optional[str] = Field(None, max_length=128, description="Contact email address")
    phone: str = Field(..., min_length=5, max_length=32, description="Contact phone number")
    address_line: str = Field(..., min_length=3, max_length=255, description="Street address line")
    city: str = Field(..., min_length=2, max_length=64, description="City")
    state: str = Field(..., min_length=2, max_length=64, description="State / Province")
    postal_code: str = Field(..., min_length=3, max_length=16, description="Postal code")
    latitude: float = Field(..., ge=-90.0, le=90.0, description="Latitude between -90 and 90")
    longitude: float = Field(..., ge=-180.0, le=180.0, description="Longitude between -180 and 180")
    is_active: bool = Field(True, description="Whether customer account is active")

    @field_validator("email")
    @classmethod
    def validate_email_address(cls, v: Optional[str]) -> Optional[str]:
        if v:
            pattern = r"^[^@\s]+@[^@\s]+\.[^@\s]+$"
            if not re.match(pattern, v):
                raise ValueError("Invalid email address format")
            return v.strip().lower()
        return v


class CustomerCreate(CustomerBase):
    pass


class CustomerUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=2, max_length=128)
    email: Optional[str] = Field(None, max_length=128)
    phone: Optional[str] = Field(None, min_length=5, max_length=32)
    address_line: Optional[str] = Field(None, min_length=3, max_length=255)
    city: Optional[str] = Field(None, min_length=2, max_length=64)
    state: Optional[str] = Field(None, min_length=2, max_length=64)
    postal_code: Optional[str] = Field(None, min_length=3, max_length=16)
    latitude: Optional[float] = Field(None, ge=-90.0, le=90.0)
    longitude: Optional[float] = Field(None, ge=-180.0, le=180.0)
    is_active: Optional[bool] = None

    @field_validator("email")
    @classmethod
    def validate_email_address(cls, v: Optional[str]) -> Optional[str]:
        if v:
            pattern = r"^[^@\s]+@[^@\s]+\.[^@\s]+$"
            if not re.match(pattern, v):
                raise ValueError("Invalid email address format")
            return v.strip().lower()
        return v


class CustomerRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    customer_code: str
    name: str
    email: Optional[str] = None
    phone: str
    address_line: str
    city: str
    state: str
    postal_code: str
    latitude: float
    longitude: float
    coordinates: List[float]
    is_active: bool
    created_at: datetime
    updated_at: datetime


class PaginatedCustomersResponse(BaseModel):
    items: List[CustomerRead]
    total: int
    skip: int
    limit: int


# Order Item Schemas
class OrderItemCreate(BaseModel):
    product_code: str = Field(..., min_length=2, max_length=64, description="SKU or product code")
    product_name: str = Field(..., min_length=2, max_length=128, description="Product title")
    quantity: int = Field(..., gt=0, description="Item quantity (must be > 0)")
    unit_price: float = Field(..., ge=0.0, description="Unit price (cannot be negative)")
    unit_weight_kg: float = Field(..., ge=0.0, description="Weight in kg per unit (cannot be negative)")


class OrderItemRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    order_id: str
    product_code: str
    product_name: str
    quantity: int
    unit_price: float
    unit_weight_kg: float
    subtotal: float
    total_weight_kg: float
    created_at: datetime
    updated_at: datetime


# Order Schemas
class OrderCreate(BaseModel):
    order_number: str = Field(..., min_length=2, max_length=64, description="Unique human-readable order identifier")
    customer_id: str = Field(..., description="UUID of existing customer")
    warehouse_id: str = Field(..., description="UUID of origin warehouse")
    priority: Optional[OrderPriority] = Field(OrderPriority.NORMAL, description="Order priority level")
    expected_delivery_at: datetime = Field(..., description="Target delivery deadline (UTC)")
    delivery_address: str = Field(..., min_length=3, max_length=255, description="Destination delivery address")
    delivery_latitude: float = Field(..., ge=-90.0, le=90.0, description="Destination latitude (-90 to 90)")
    delivery_longitude: float = Field(..., ge=-180.0, le=180.0, description="Destination longitude (-180 to 180)")
    notes: Optional[str] = Field(None, max_length=255, description="Special delivery instructions or notes")
    items: Optional[List[OrderItemCreate]] = Field(None, description="Optional initial list of items")


class OrderUpdate(BaseModel):
    priority: Optional[OrderPriority] = None
    expected_delivery_at: Optional[datetime] = None
    delivery_address: Optional[str] = Field(None, min_length=3, max_length=255)
    delivery_latitude: Optional[float] = Field(None, ge=-90.0, le=90.0)
    delivery_longitude: Optional[float] = Field(None, ge=-180.0, le=180.0)
    notes: Optional[str] = Field(None, max_length=255)


class OrderStatusUpdate(BaseModel):
    status: OrderStatus = Field(..., description="Target order lifecycle status")
    reason: Optional[str] = Field(None, max_length=255, description="Reason for status transition")


class OrderAssignmentUpdate(BaseModel):
    vehicle_id: Optional[str] = Field(None, description="UUID of vehicle to assign, or null to unassign")
    reason: Optional[str] = Field(None, max_length=255, description="Reason for vehicle assignment / reassignment")


class OrderStatusHistoryRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    order_id: str
    previous_status: Optional[str] = None
    new_status: str
    reason: Optional[str] = None
    changed_by_user_id: Optional[str] = None
    changed_at: datetime


class OrderAssignmentHistoryRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    order_id: str
    previous_vehicle_id: Optional[str] = None
    new_vehicle_id: Optional[str] = None
    assigned_by_user_id: Optional[str] = None
    reason: Optional[str] = None
    assigned_at: datetime


class OrderRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    order_number: str
    customer_id: str
    warehouse_id: str
    status: str
    priority: str
    order_date: datetime
    expected_delivery_at: datetime
    dispatched_at: Optional[datetime] = None
    delivered_at: Optional[datetime] = None
    delivery_address: str
    delivery_latitude: float
    delivery_longitude: float
    coordinates: List[float]
    total_weight_kg: float
    total_amount: float
    notes: Optional[str] = None
    assigned_vehicle_id: Optional[str] = None
    created_by_user_id: Optional[str] = None
    is_overdue: bool
    created_at: datetime
    updated_at: datetime
    customer: Optional[CustomerRead] = None
    items: Optional[List[OrderItemRead]] = None


class PaginatedOrdersResponse(BaseModel):
    items: List[OrderRead]
    total: int
    skip: int
    limit: int


class OrderSummaryResponse(BaseModel):
    total_orders: int
    created_orders: int
    confirmed_orders: int
    processing_orders: int
    ready_for_dispatch_orders: int
    dispatched_orders: int
    in_transit_orders: int
    delivered_orders: int
    cancelled_orders: int
    on_hold_orders: int
    failed_delivery_orders: int
    overdue_orders: int
    unassigned_orders: int
    urgent_orders: int
    total_order_value: float
    total_order_weight_kg: float
    generated_at: datetime
    data_source: str = "SIMULATED"

