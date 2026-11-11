from datetime import datetime
from typing import Any, Dict, List, Literal, Optional
from pydantic import BaseModel, ConfigDict, Field, computed_field

from app.models.simulation import (
    SimulationEventType,
    SimulationStatus,
    SimulationVehicleStatus,
)


class SimulationCreate(BaseModel):
    name: str = Field(default="Bengaluru Logistics Simulation", max_length=128)
    seed: int = Field(default=42, ge=0)
    simulation_speed_multiplier: float = Field(default=1.0, ge=0.1, le=100.0)
    configuration: Optional[Dict[str, Any]] = None


class SimulationSpeedUpdate(BaseModel):
    speed_multiplier: float = Field(..., ge=0.1, le=100.0, description="Speed multiplier (0.1x to 100x)")


class SimulationVehicleCreate(BaseModel):
    vehicle_id: str = Field(..., description="UUID of existing active vehicle")
    origin_node_id: str = Field(..., description="UUID of origin network node")
    destination_node_id: str = Field(..., description="UUID of destination network node")


class SimulationVehicleRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    simulation_id: str
    vehicle_id: str
    vehicle_code: Optional[str] = None
    origin_node_id: str
    destination_node_id: str
    origin_node_name: Optional[str] = None
    destination_node_name: Optional[str] = None
    route_node_ids: List[str]
    current_route_segment: int
    segment_progress: float
    progress_percentage: float
    current_latitude: float
    current_longitude: float
    current_speed_kmph: float
    heading_degrees: float
    status: str
    simulated_departure_time: Optional[datetime] = None
    estimated_arrival_time: Optional[datetime] = None
    actual_arrival_time: Optional[datetime] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    @computed_field
    def coordinates(self) -> List[float]:
        return [self.current_longitude, self.current_latitude]


class SimulationEventRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    simulation_id: str
    vehicle_id: Optional[str] = None
    event_type: str
    event_data: Optional[Dict[str, Any]] = None
    simulated_timestamp: Optional[datetime] = None
    created_at: Optional[datetime] = None


class SimulationTelemetryRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    simulation_id: str
    vehicle_id: str
    latitude: float
    longitude: float
    speed_kmph: float
    heading_degrees: float
    recorded_at: datetime
    source: str = "SIMULATION"

    @computed_field
    def coordinates(self) -> List[float]:
        return [self.longitude, self.latitude]


class SimulationRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    name: str
    seed: int
    status: str
    simulation_speed_multiplier: float
    simulated_time: Optional[datetime] = None
    started_at: Optional[datetime] = None
    paused_at: Optional[datetime] = None
    resumed_at: Optional[datetime] = None
    stopped_at: Optional[datetime] = None
    created_by_user_id: Optional[str] = None
    configuration: Optional[Dict[str, Any]] = None
    total_vehicles: int = 0
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


class SimulationSummary(BaseModel):
    id: str
    name: str
    status: str
    speed_multiplier: float
    simulated_time: Optional[datetime] = None
    total_vehicles: int
    queued_vehicles: int
    en_route_vehicles: int
    arrived_vehicles: int
    average_progress_percentage: float
    total_telemetry_points: int
    total_events: int
    started_at: Optional[datetime] = None
    elapsed_simulated_seconds: Optional[float] = None
    data_source: Literal["SIMULATED"] = "SIMULATED"


class PaginatedSimulationsResponse(BaseModel):
    items: List[SimulationRead]
    total: int
    skip: int
    limit: int


class PaginatedEventsResponse(BaseModel):
    items: List[SimulationEventRead]
    total: int
    skip: int
    limit: int


class PaginatedTelemetryResponse(BaseModel):
    items: List[SimulationTelemetryRead]
    total: int
    skip: int
    limit: int

