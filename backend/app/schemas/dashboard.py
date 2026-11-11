from datetime import datetime
from typing import Any, Dict, Literal, Optional
from pydantic import BaseModel, Field


class NetworkKPIs(BaseModel):
    total_warehouses: int
    total_customers: int
    total_network_connections: int
    operational_warehouses: Optional[int] = Field(
        None, description="Count of warehouses currently in OPERATIONAL status"
    )
    total_storage_capacity: Optional[float] = Field(
        None, description="Aggregated total storage capacity across warehouses"
    )
    used_storage_capacity: Optional[float] = Field(
        None, description="Aggregated currently used storage capacity"
    )


class OperationalKPIs(BaseModel):
    total_vehicles: Optional[int] = Field(0, description="Total registered vehicles in fleet")
    active_vehicles: Optional[int] = Field(0, description="Total active vehicles in fleet")
    in_transit_vehicles: Optional[int] = Field(0, description="Vehicles currently in transit")
    total_orders: Optional[int] = Field(0, description="Total customer orders created")
    pending_orders: Optional[int] = Field(0, description="Orders pending fulfillment or dispatch")
    in_transit_orders: Optional[int] = Field(0, description="Orders currently out for delivery")
    delivered_orders: Optional[int] = Field(0, description="Successfully delivered orders")
    delayed_orders: Optional[int] = Field(0, description="Active orders past expected delivery deadline")


class SimulationKPIs(BaseModel):
    active_simulations: int
    completed_simulations: int


class PerformanceKPIs(BaseModel):
    on_time_delivery_rate: Optional[float] = Field(
        None, description="To be populated in Stage 6"
    )
    fleet_utilization: Optional[float] = Field(
        None, description="To be populated in Stage 5"
    )
    average_delivery_time_minutes: Optional[float] = Field(
        None, description="To be populated in Stage 6"
    )


class DisruptionKPIs(BaseModel):
    total_disruptions: int = Field(0, description="Total recorded disruptions")
    active_disruptions: int = Field(0, description="Disruptions currently in ACTIVE or MONITORING state")
    critical_disruptions: int = Field(0, description="Active disruptions with CRITICAL severity")
    affected_vehicles_count: int = Field(0, description="Count of vehicles impacted by active disruptions")
    affected_orders_count: int = Field(0, description="Count of orders impacted by active disruptions")


class DashboardSummaryResponse(BaseModel):
    network: NetworkKPIs
    operations: OperationalKPIs
    simulations: SimulationKPIs
    disruptions: Optional[DisruptionKPIs] = Field(default_factory=DisruptionKPIs)
    performance: PerformanceKPIs
    overview_summary: Optional[Dict[str, Any]] = None
    order_summary: Optional[Dict[str, Any]] = None
    fleet_summary: Optional[Dict[str, Any]] = None
    warehouse_summary: Optional[Dict[str, Any]] = None
    disruption_summary: Optional[Dict[str, Any]] = None
    agent_summary: Optional[Dict[str, Any]] = None
    recovery_summary: Optional[Dict[str, Any]] = None
    simulation_summary: Optional[Dict[str, Any]] = None
    generated_at: str
    data_source: Literal["SIMULATED"] = "SIMULATED"
    notes: str = (
        "Operational and performance metrics will be populated when vehicle and order "
        "models are implemented in Stages 5 and 6."
    )
