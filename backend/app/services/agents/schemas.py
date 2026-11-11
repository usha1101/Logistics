import enum
from datetime import datetime
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, ConfigDict, Field

from app.models.agent import (
    AgentExecutionStatus,
    AgentRunStatus,
    RecommendationExecutionStatus,
    RecommendationPriority,
    RecommendationValidationStatus,
)


class EvidenceReference(BaseModel):
    resource_type: str = Field(..., description="VEHICLE, ORDER, WAREHOUSE, NETWORK_EDGE, or CALCULATION")
    resource_id: str = Field(..., description="Exact UUID or code of the referenced resource")
    description: str = Field(..., description="Operational fact verified against database/service")
    metric_value: Optional[Any] = None


class BaseAgentRecommendation(BaseModel):
    recommendation_type: str = Field(..., description="E.g., DISPATCH_STANDBY_VEHICLE, REROUTE_EDGE, REALLOCATE_WAREHOUSE, REPRIORITIZE_ORDER")
    priority: RecommendationPriority = RecommendationPriority.MEDIUM
    title: str = Field(..., min_length=3, max_length=255)
    description: str = Field(..., min_length=10)
    target_resource_type: Optional[str] = None
    target_resource_id: Optional[str] = None
    evidence: Optional[Dict[str, Any]] = Field(default_factory=dict)
    validation_status: RecommendationValidationStatus = RecommendationValidationStatus.VALIDATED


class BaseAgentOutput(BaseModel):
    agent_name: str
    execution_status: AgentExecutionStatus = AgentExecutionStatus.COMPLETED
    summary: str
    findings: List[str] = Field(default_factory=list)
    recommendations: List[BaseAgentRecommendation] = Field(default_factory=list)
    evidence_references: List[EvidenceReference] = Field(default_factory=list)
    confidence_score: float = Field(0.8, ge=0.0, le=1.0)
    missing_information: List[str] = Field(default_factory=list)
    warnings: List[str] = Field(default_factory=list)
    provider: str = "unknown"
    model: str = "unknown"
    execution_duration_ms: Optional[float] = None


# Specialist Outputs
class DisruptionAnalysisAgentOutput(BaseAgentOutput):
    agent_name: str = "DISRUPTION_ANALYSIS"
    severity_assessment: str
    blast_radius_summary: str
    criticality_drivers: List[str] = Field(default_factory=list)


class FleetIntelligenceAgentOutput(BaseAgentOutput):
    agent_name: str = "FLEET_INTELLIGENCE"
    available_candidate_vehicle_ids: List[str] = Field(default_factory=list)
    capacity_feasibility: Dict[str, Any] = Field(default_factory=dict)
    unusable_vehicle_reasons: Dict[str, str] = Field(default_factory=dict)


class RoutingIntelligenceAgentOutput(BaseAgentOutput):
    agent_name: str = "ROUTING_INTELLIGENCE"
    primary_route_impediment: Optional[str] = None
    alternative_path_found: bool = False
    alternative_path_node_ids: List[str] = Field(default_factory=list)
    distance_km: Optional[float] = None
    estimated_travel_minutes: Optional[float] = None


class WarehouseIntelligenceAgentOutput(BaseAgentOutput):
    agent_name: str = "WAREHOUSE_INTELLIGENCE"
    affected_warehouse_id: Optional[str] = None
    capacity_strain_assessment: str
    stock_shortage_detected: bool = False
    alternative_warehouse_candidates: List[str] = Field(default_factory=list)


class OrderPriorityAgentOutput(BaseAgentOutput):
    agent_name: str = "ORDER_PRIORITY"
    total_impacted_orders: int = 0
    urgent_orders_count: int = 0
    ranked_order_ids: List[str] = Field(default_factory=list)
    sla_breach_risks: List[Dict[str, Any]] = Field(default_factory=list)


class ConflictItem(BaseModel):
    conflict_type: str
    description: str
    involved_agents: List[str]
    evidence_details: Dict[str, Any]
    resolution_guidance: str


class CoordinatorSynthesisOutput(BaseModel):
    executive_summary: str
    overall_confidence_score: float = Field(..., ge=0.0, le=1.0)
    operational_risks: List[str] = Field(default_factory=list)
    detected_conflicts: List[ConflictItem] = Field(default_factory=list)
    consolidated_recommendations: List[BaseAgentRecommendation] = Field(default_factory=list)
    missing_data_warnings: List[str] = Field(default_factory=list)


# API Read/Response Schemas
class AgentRecommendationRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    agent_run_id: str
    source_agent: str
    recommendation_type: str
    priority: str
    title: str
    description: str
    target_resource_type: Optional[str] = None
    target_resource_id: Optional[str] = None
    evidence: Optional[Dict[str, Any]] = None
    validation_status: str
    execution_status: str
    created_at: datetime


class AgentExecutionRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    agent_run_id: str
    agent_name: str
    status: str
    provider: str
    model: str
    input_summary: Optional[str] = None
    output: Optional[Dict[str, Any]] = None
    confidence_score: Optional[float] = None
    evidence_references: Optional[List[Dict[str, Any]]] = None
    warnings: Optional[List[str]] = None
    execution_duration_ms: Optional[float] = None
    started_at: datetime
    completed_at: Optional[datetime] = None


class AgentRunRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    disruption_id: str
    simulation_id: Optional[str] = None
    status: str
    primary_provider: str
    started_at: datetime
    completed_at: Optional[datetime] = None
    execution_duration_ms: Optional[float] = None
    error_summary: Optional[str] = None
    created_by_user_id: Optional[str] = None
    created_at: datetime
    executions: List[AgentExecutionRead] = Field(default_factory=list)
    recommendations: List[AgentRecommendationRead] = Field(default_factory=list)


class PaginatedAgentRunsResponse(BaseModel):
    items: List[AgentRunRead]
    total: int
    page: int
    page_size: int
    total_pages: int


class ProviderStatusResponse(BaseModel):
    gemini_configured: bool
    groq_configured: bool
    primary_provider: str
    fallback_provider: str
    primary_model: str
    fallback_model: str
    timeout_seconds: float
    max_retries: int
