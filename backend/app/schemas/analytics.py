from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class MetricAvailabilityStatus(str, Enum):
    ACTUAL = "ACTUAL"
    ESTIMATED = "ESTIMATED"
    SIMULATED = "SIMULATED"
    UNAVAILABLE = "UNAVAILABLE"


class TrendGrouping(str, Enum):
    DAY = "DAY"
    WEEK = "WEEK"
    MONTH = "MONTH"


class ComparisonDirection(str, Enum):
    LOWER_IS_BETTER = "LOWER_IS_BETTER"
    HIGHER_IS_BETTER = "HIGHER_IS_BETTER"
    NEUTRAL = "NEUTRAL"


class AnalyticsFilterMeta(BaseModel):
    start_date: Optional[datetime] = None
    end_date: Optional[datetime] = None
    simulation_id: Optional[str] = None
    include_simulations: bool = False
    data_scope: str = Field(
        default="OPERATIONAL",
        description="OPERATIONAL, SIMULATION_SPECIFIC, or OPERATIONAL_AND_SIMULATED",
    )
    generated_at: datetime


class OverviewAnalyticsResponse(BaseModel):
    total_orders: int
    delivered_orders: int
    in_transit_orders: int
    overdue_orders: int
    estimated_delayed_orders: int
    cancelled_orders: int
    delivery_success_rate: float
    on_time_delivery_rate: float
    total_vehicles: int
    active_vehicles: int
    fleet_utilization_rate: float
    total_warehouses: int
    warehouse_utilization_rate: float
    active_disruptions: int
    resolved_disruptions: int
    total_agent_runs: int
    total_recovery_plans: int
    executed_recovery_plans: int
    recovery_success_rate: float
    active_simulations: int
    metric_classifications: Dict[str, str] = Field(default_factory=dict)
    unavailable_metrics: List[str] = Field(default_factory=list)
    filter_meta: AnalyticsFilterMeta


class OrderAnalyticsResponse(BaseModel):
    total_orders: int
    orders_by_status: Dict[str, int]
    orders_by_priority: Dict[str, int]
    delivered_orders: int
    cancelled_orders: int
    in_transit_orders: int
    overdue_orders: int
    estimated_delayed_orders: int
    eligible_orders: int
    on_time_delivered_orders: int
    late_delivered_orders: int
    delivery_success_rate: float
    on_time_delivery_rate: float
    average_delivery_duration_minutes: Optional[float] = None
    average_estimated_delay_minutes: Optional[float] = None
    total_order_weight_kg: float
    total_order_value: float
    metric_classifications: Dict[str, str] = Field(default_factory=dict)
    unavailable_metrics: List[str] = Field(default_factory=list)
    filter_meta: AnalyticsFilterMeta


class VehiclePerformanceSummary(BaseModel):
    vehicle_id: str
    vehicle_code: str
    registration_number: str
    vehicle_type: str
    status: str
    capacity_kg: float
    current_load_kg: float
    load_utilization_percentage: float
    assigned_orders_count: int
    distance_travelled_km: Optional[float] = None
    distance_data_source: str = "UNAVAILABLE"


class FleetAnalyticsResponse(BaseModel):
    total_vehicles: int
    available_vehicles: int
    in_transit_vehicles: int
    idle_vehicles: int
    breakdown_vehicles: int
    maintenance_vehicles: int
    offline_vehicles: int
    vehicles_by_status: Dict[str, int]
    vehicles_by_type: Dict[str, int]
    total_fleet_capacity_kg: float
    total_current_load_kg: float
    average_load_utilization_percentage: float
    fleet_capacity_utilization_percentage: float
    active_vehicle_utilization_rate: float
    total_distance_travelled_km: Optional[float] = None
    average_distance_per_vehicle_km: Optional[float] = None
    vehicles: List[VehiclePerformanceSummary] = Field(default_factory=list)
    metric_classifications: Dict[str, str] = Field(default_factory=dict)
    unavailable_metrics: List[str] = Field(default_factory=list)
    filter_meta: AnalyticsFilterMeta


class WarehousePerformanceSummary(BaseModel):
    warehouse_id: str
    warehouse_code: str
    name: str
    status: str
    total_capacity: float
    used_capacity: float
    utilization_percentage: float
    total_skus: int
    in_stock_count: int
    low_stock_count: int
    out_of_stock_count: int


class WarehouseAnalyticsResponse(BaseModel):
    total_warehouses: int
    operational_warehouses: int
    degraded_warehouses: int
    closed_warehouses: int
    maintenance_warehouses: int
    total_capacity: float
    total_used_capacity: float
    overall_utilization_percentage: float
    average_warehouse_utilization_percentage: float
    total_inventory_items: int
    in_stock_items: int
    low_stock_items: int
    out_of_stock_items: int
    total_inventory_movements: int
    inbound_movements_count: int
    outbound_movements_count: int
    adjustment_movements_count: int
    inbound_quantity_total: int
    outbound_quantity_total: int
    adjustment_quantity_total: int
    warehouses: List[WarehousePerformanceSummary] = Field(default_factory=list)
    metric_classifications: Dict[str, str] = Field(default_factory=dict)
    unavailable_metrics: List[str] = Field(default_factory=list)
    filter_meta: AnalyticsFilterMeta


class DisruptionAnalyticsResponse(BaseModel):
    total_disruptions: int
    active_disruptions: int
    resolved_disruptions: int
    cancelled_disruptions: int
    disruptions_by_status: Dict[str, int]
    disruptions_by_severity: Dict[str, int]
    disruptions_by_type: Dict[str, int]
    affected_vehicles_count: int
    affected_orders_count: int
    affected_warehouses_count: int
    affected_edges_count: int
    average_resolution_time_minutes: Optional[float] = None
    estimated_total_delay_minutes: float
    metric_classifications: Dict[str, str] = Field(default_factory=dict)
    unavailable_metrics: List[str] = Field(default_factory=list)
    filter_meta: AnalyticsFilterMeta


class AgentAnalyticsResponse(BaseModel):
    total_agent_runs: int
    completed_runs: int
    partially_completed_runs: int
    failed_runs: int
    ai_unavailable_runs: int
    runs_by_status: Dict[str, int]
    total_agent_executions: int
    executions_by_status: Dict[str, int]
    executions_by_agent_name: Dict[str, int]
    provider_usage_distribution: Dict[str, int]
    total_recommendations: int
    validated_recommendations: int
    rejected_recommendations: int
    requires_validation_recommendations: int
    informational_recommendations: int
    recommendations_by_validation_status: Dict[str, int]
    recommendations_by_type: Dict[str, int]
    average_agent_execution_duration_ms: Optional[float] = None
    average_run_duration_ms: Optional[float] = None
    average_confidence_score: Optional[float] = None
    agent_success_rate: float
    token_usage_total: Optional[int] = None
    estimated_llm_cost_usd: Optional[float] = None
    metric_classifications: Dict[str, str] = Field(default_factory=dict)
    unavailable_metrics: List[str] = Field(default_factory=list)
    filter_meta: AnalyticsFilterMeta


class RecoveryAnalyticsResponse(BaseModel):
    total_recovery_plans: int
    optimized_plans: int
    pending_approval_plans: int
    approved_plans: int
    rejected_plans: int
    executed_plans: int
    partially_executed_plans: int
    failed_plans: int
    infeasible_plans: int
    plans_by_status: Dict[str, int]
    plans_by_strategy: Dict[str, int]
    total_affected_orders_in_plans: int
    total_reassigned_orders_proposed: int
    total_recovered_orders: int
    total_recovery_actions: int
    executed_actions: int
    failed_actions: int
    pending_actions: int
    recovery_success_rate: float
    average_recovery_execution_time_minutes: Optional[float] = None
    estimated_delay_reduction_minutes: float
    estimated_distance_change_km: float
    estimated_cost_change: float
    metric_classifications: Dict[str, str] = Field(default_factory=dict)
    unavailable_metrics: List[str] = Field(default_factory=list)
    filter_meta: AnalyticsFilterMeta


class SimulationAnalyticsResponse(BaseModel):
    total_simulations: int
    running_simulations: int
    paused_simulations: int
    completed_simulations: int
    failed_simulations: int
    cancelled_simulations: int
    simulations_by_status: Dict[str, int]
    total_simulated_vehicles: int
    total_simulated_distance_km: Optional[float] = None
    average_simulation_duration_seconds: Optional[float] = None
    simulated_disruptions_count: int
    simulated_recovery_plans_count: int
    simulated_recovery_success_rate: float
    metric_classifications: Dict[str, str] = Field(default_factory=dict)
    unavailable_metrics: List[str] = Field(default_factory=list)
    filter_meta: AnalyticsFilterMeta


class TrendPoint(BaseModel):
    period: str
    value: float
    count: int = 0
    secondary_value: Optional[float] = None
    breakdown: Optional[Dict[str, Any]] = None


class TrendSeriesResponse(BaseModel):
    domain: str
    metric_name: str
    grouping: TrendGrouping
    unit: str
    data_points: List[TrendPoint] = Field(default_factory=list)
    total_points: int = 0
    is_historical: bool = True
    notes: Optional[str] = None
    filter_meta: AnalyticsFilterMeta


class ComparisonMetricItem(BaseModel):
    metric_name: str
    label: str
    before_value: Optional[float] = None
    after_value: Optional[float] = None
    absolute_difference: Optional[float] = None
    percentage_change: Optional[float] = None
    improvement_direction: ComparisonDirection
    is_improved: Optional[bool] = None
    unit: str = ""
    data_classification: str = "ACTUAL"


class PerformanceComparisonResponse(BaseModel):
    comparison_scope: str
    disruption_id: Optional[str] = None
    recovery_plan_id: Optional[str] = None
    simulation_id: Optional[str] = None
    total_comparisons_evaluated: int
    metrics: List[ComparisonMetricItem] = Field(default_factory=list)
    notes: List[str] = Field(default_factory=list)
    filter_meta: AnalyticsFilterMeta


class AnalyticsHealthResponse(BaseModel):
    status: str
    analytics_engine: str
    pdf_reporting_engine: str
    reportlab_available: bool
    reports_storage_ready: bool
    database_connected: bool
    total_generated_reports: int
    timestamp: datetime

