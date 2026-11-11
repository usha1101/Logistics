from datetime import datetime
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, ConfigDict, Field

from app.models.recovery import (
    OptimizationStrategy,
    RecoveryActionStatus,
    RecoveryPlanStatus,
)


class RecoveryPlanGenerateRequest(BaseModel):
    disruption_id: str
    simulation_id: Optional[str] = None
    optimization_strategy: OptimizationStrategy = OptimizationStrategy.MULTI_VEHICLE_RECOVERY
    weights: Optional[Dict[str, float]] = Field(
        default_factory=lambda: {
            "distance": 0.3,
            "travel_time": 0.4,
            "delay": 0.3,
        }
    )
    max_replacement_vehicles: Optional[int] = Field(5, ge=1, le=20)


class RecoveryPlanApproveRequest(BaseModel):
    notes: Optional[str] = Field(None, max_length=512)


class RecoveryPlanRejectRequest(BaseModel):
    reason: str = Field(..., min_length=3, max_length=1024)


class RecoveryAssignmentRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    recovery_plan_id: str
    order_id: str
    previous_vehicle_id: Optional[str] = None
    proposed_vehicle_id: str
    origin_node_id: str
    destination_node_id: str
    proposed_route_node_ids: List[str]
    proposed_route_edge_ids: List[str]
    estimated_distance_km: float
    estimated_travel_time_minutes: float
    estimated_delay_minutes: float
    order_priority: str
    assignment_reason: Optional[str] = None
    validation_status: str
    created_at: datetime


class RecoveryActionRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    recovery_plan_id: str
    action_type: str
    target_resource_type: str
    target_resource_id: str
    action_payload: Optional[Dict[str, Any]] = None
    status: str
    execution_result: Optional[Dict[str, Any]] = None
    error_message: Optional[str] = None
    executed_at: Optional[datetime] = None
    created_at: datetime


class RecoveryAuditLogRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    recovery_plan_id: str
    action: str
    previous_status: Optional[str] = None
    new_status: str
    performed_by_user_id: Optional[str] = None
    details: Optional[Dict[str, Any]] = None
    created_at: datetime


class RecoveryComparisonRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    recovery_plan_id: str
    metric_name: str
    baseline_value: float
    proposed_value: float
    improvement_value: float
    improvement_percentage: float
    unit: str
    created_at: datetime


class RecoveryPlanRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    recovery_code: str
    disruption_id: str
    simulation_id: Optional[str] = None
    agent_run_id: Optional[str] = None
    status: str
    optimization_strategy: str
    objective_value: Optional[float] = None
    estimated_total_distance_km: float
    estimated_total_travel_time_minutes: float
    estimated_total_delay_minutes: float
    estimated_recovery_cost: float
    affected_order_count: int
    reassigned_order_count: int
    assigned_vehicle_count: int
    optimization_metadata: Optional[Dict[str, Any]] = None
    created_by_user_id: Optional[str] = None
    approved_by_user_id: Optional[str] = None
    approved_at: Optional[datetime] = None
    executed_at: Optional[datetime] = None
    rejected_at: Optional[datetime] = None
    rejection_reason: Optional[str] = None
    created_at: datetime
    updated_at: datetime
    assignments: List[RecoveryAssignmentRead] = Field(default_factory=list)
    comparisons: List[RecoveryComparisonRead] = Field(default_factory=list)


class RecoveryPlanValidationReport(BaseModel):
    plan_id: str
    recovery_code: str
    is_valid: bool
    status: str
    checked_constraints: List[str]
    violations: List[str] = Field(default_factory=list)
    validated_at: datetime


class PaginatedRecoveryPlansResponse(BaseModel):
    items: List[RecoveryPlanRead]
    total: int
    page: int
    page_size: int
    total_pages: int


class RecoveryKPISummary(BaseModel):
    total_recovery_plans: int = 0
    pending_approval_count: int = 0
    approved_count: int = 0
    executed_count: int = 0
    rejected_count: int = 0
    total_orders_recovered: int = 0
    average_delay_reduction_pct: float = 0.0
    total_travel_time_saved_minutes: float = 0.0
