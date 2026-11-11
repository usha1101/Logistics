import enum
from datetime import datetime
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, ConfigDict, Field

from app.models.disruption import (
    AffectedResourceType,
    DisruptionEventType,
    DisruptionSeverity,
    DisruptionStatus,
    DisruptionType,
)


# ============================================================================
# Nested / Support Schemas
# ============================================================================

class AffectedVehicleSummary(BaseModel):
    vehicle_id: str
    vehicle_code: str
    registration_number: Optional[str] = None
    status: str
    current_load_kg: float = 0.0
    impact_category: str = "DIRECT"
    severity: str
    estimated_delay_minutes: Optional[float] = None


class AffectedOrderSummary(BaseModel):
    order_id: str
    order_number: str
    status: str
    priority: str
    sla_hours: Optional[float] = None
    expected_delivery_at: Optional[datetime] = None
    estimated_delay_minutes: Optional[float] = None
    is_at_risk: bool = False
    is_overdue: bool = False
    customer_name: Optional[str] = None


class AtRiskOrderSummary(BaseModel):
    order_id: str
    order_number: str
    status: str
    priority: str
    expected_delivery_at: Optional[datetime] = None
    estimated_delay_minutes: float
    risk_level: str  # HIGH, CRITICAL, MEDIUM


# ============================================================================
# Disruption Impact Schemas
# ============================================================================

class DisruptionImpactCreate(BaseModel):
    affected_resource_type: AffectedResourceType
    affected_resource_id: str
    impact_category: str = "DIRECT"
    severity: DisruptionSeverity
    estimated_delay_minutes: Optional[float] = None
    impact_details: Optional[Dict[str, Any]] = None


class DisruptionImpactRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    disruption_id: str
    affected_resource_type: str
    affected_resource_id: str
    impact_category: str
    severity: str
    estimated_delay_minutes: Optional[float] = None
    impact_details: Optional[Dict[str, Any]] = None
    detected_at: datetime


# ============================================================================
# Disruption Event Schemas
# ============================================================================

class DisruptionEventRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    disruption_id: str
    event_type: str
    previous_status: Optional[str] = None
    new_status: Optional[str] = None
    event_data: Optional[Dict[str, Any]] = None
    performed_by_user_id: Optional[str] = None
    created_at: datetime


# ============================================================================
# Disruption CRUD Schemas
# ============================================================================

class DisruptionCreate(BaseModel):
    disruption_type: DisruptionType
    title: str = Field(..., min_length=3, max_length=255)
    description: Optional[str] = Field(None, max_length=1024)
    severity: Optional[DisruptionSeverity] = None  # If None, calculated deterministically
    simulation_id: Optional[str] = None
    affected_vehicle_id: Optional[str] = None
    affected_warehouse_id: Optional[str] = None
    affected_network_edge_id: Optional[str] = None
    affected_order_id: Optional[str] = None
    location_latitude: Optional[float] = Field(None, ge=-90.0, le=90.0)
    location_longitude: Optional[float] = Field(None, ge=-180.0, le=180.0)
    parameters: Optional[Dict[str, Any]] = Field(default_factory=dict)
    start_time: Optional[datetime] = None
    expected_end_time: Optional[datetime] = None


class DisruptionUpdate(BaseModel):
    title: Optional[str] = Field(None, min_length=3, max_length=255)
    description: Optional[str] = Field(None, max_length=1024)
    severity: Optional[DisruptionSeverity] = None
    expected_end_time: Optional[datetime] = None
    parameters: Optional[Dict[str, Any]] = None


class DisruptionResolveRequest(BaseModel):
    notes: Optional[str] = Field(None, max_length=1024)
    actual_end_time: Optional[datetime] = None


class DisruptionCancelRequest(BaseModel):
    reason: Optional[str] = Field(None, max_length=1024)


class DisruptionSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    disruption_code: str
    disruption_type: str
    severity: str
    status: str
    title: str
    simulation_id: Optional[str] = None
    affected_vehicle_id: Optional[str] = None
    affected_warehouse_id: Optional[str] = None
    affected_network_edge_id: Optional[str] = None
    affected_order_id: Optional[str] = None
    start_time: datetime
    expected_end_time: Optional[datetime] = None
    actual_end_time: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime


class DisruptionRead(DisruptionSummary):
    description: Optional[str] = None
    location_latitude: Optional[float] = None
    location_longitude: Optional[float] = None
    parameters: Optional[Dict[str, Any]] = None
    created_by_user_id: Optional[str] = None
    resolved_by_user_id: Optional[str] = None
    impacts: List[DisruptionImpactRead] = Field(default_factory=list)
    events: List[DisruptionEventRead] = Field(default_factory=list)


# ============================================================================
# Impact Analysis Detailed Result
# ============================================================================

class DisruptionAnalysisReport(BaseModel):
    disruption_id: str
    disruption_code: str
    disruption_type: str
    severity: str
    status: str
    affected_vehicles_count: int = 0
    affected_orders_count: int = 0
    urgent_orders_count: int = 0
    overdue_orders_count: int = 0
    at_risk_orders_count: int = 0
    affected_warehouses_count: int = 0
    affected_network_edges_count: int = 0
    total_estimated_delay_minutes: float = 0.0
    affected_vehicles: List[AffectedVehicleSummary] = Field(default_factory=list)
    affected_orders: List[AffectedOrderSummary] = Field(default_factory=list)
    at_risk_orders: List[AtRiskOrderSummary] = Field(default_factory=list)
    analyzed_at: datetime


# ============================================================================
# Paginated Responses
# ============================================================================

class PaginatedDisruptionsResponse(BaseModel):
    items: List[DisruptionSummary]
    total: int
    page: int
    page_size: int
    total_pages: int


class PaginatedImpactsResponse(BaseModel):
    items: List[DisruptionImpactRead]
    total: int
    page: int
    page_size: int
    total_pages: int


class PaginatedDisruptionEventsResponse(BaseModel):
    items: List[DisruptionEventRead]
    total: int
    page: int
    page_size: int
    total_pages: int

