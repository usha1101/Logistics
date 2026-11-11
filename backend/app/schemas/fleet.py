from datetime import datetime
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, ConfigDict, Field

from app.models.vehicle import LocationSource, VehicleStatus, VehicleType


class VehicleBase(BaseModel):
    vehicle_code: str = Field(..., min_length=2, max_length=64, description="Unique vehicle code, e.g. TRK-001")
    registration_number: str = Field(..., min_length=2, max_length=64, description="License plate / registration")
    vehicle_type: VehicleType = Field(..., description="Vehicle category/size")
    manufacturer: Optional[str] = Field(None, max_length=64)
    model: Optional[str] = Field(None, max_length=64)
    capacity_kg: float = Field(..., gt=0, description="Maximum cargo payload capacity in kg")
    home_warehouse_id: Optional[str] = Field(None, description="UUID of home base warehouse")
    is_active: bool = Field(True, description="Whether the vehicle is currently active in the fleet")


class VehicleCreate(VehicleBase):
    initial_latitude: Optional[float] = Field(None, ge=-90.0, le=90.0)
    initial_longitude: Optional[float] = Field(None, ge=-180.0, le=180.0)
    initial_speed_kmph: Optional[float] = Field(None, ge=0.0)
    initial_heading_degrees: Optional[float] = Field(None, ge=0.0, le=360.0)


class VehicleUpdate(BaseModel):
    vehicle_type: Optional[VehicleType] = None
    manufacturer: Optional[str] = None
    model: Optional[str] = None
    capacity_kg: Optional[float] = Field(None, gt=0)
    home_warehouse_id: Optional[str] = None
    is_active: Optional[bool] = None


class VehicleStatusUpdate(BaseModel):
    status: VehicleStatus = Field(..., description="Target vehicle status")
    reason: Optional[str] = Field(None, max_length=255, description="Reason for status change")


class VehicleLocationUpdate(BaseModel):
    latitude: float = Field(..., ge=-90.0, le=90.0, description="Latitude between -90 and 90")
    longitude: float = Field(..., ge=-180.0, le=180.0, description="Longitude between -180 and 180")
    speed_kmph: Optional[float] = Field(None, ge=0.0, description="Current ground speed in km/h")
    heading_degrees: Optional[float] = Field(None, ge=0.0, le=360.0, description="Compass heading 0-360 degrees")
    source: Optional[LocationSource] = Field(LocationSource.MANUAL, description="Location update telemetry source")


class WarehouseMiniRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    warehouse_code: str
    warehouse_type: str
    status: str


class VehicleRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    vehicle_code: str
    registration_number: str
    vehicle_type: str
    manufacturer: Optional[str] = None
    model: Optional[str] = None
    capacity_kg: float
    current_load_kg: float
    remaining_capacity_kg: float
    status: str
    home_warehouse_id: Optional[str] = None
    current_latitude: Optional[float] = None
    current_longitude: Optional[float] = None
    current_speed_kmph: Optional[float] = None
    heading_degrees: Optional[float] = None
    coordinates: Optional[List[float]] = None
    is_active: bool
    last_location_update: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime
    home_warehouse: Optional[WarehouseMiniRead] = None


class VehicleLocationRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    vehicle_id: str
    latitude: float
    longitude: float
    speed_kmph: Optional[float] = None
    heading_degrees: Optional[float] = None
    coordinates: List[float]
    recorded_at: datetime
    source: str


class VehicleStatusHistoryRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    vehicle_id: str
    previous_status: Optional[str] = None
    new_status: str
    reason: Optional[str] = None
    changed_by_user_id: Optional[str] = None
    changed_at: datetime


class VehicleStatusChangeResponse(BaseModel):
    vehicle: VehicleRead
    status_history: Optional[VehicleStatusHistoryRead] = None


class PaginatedVehiclesResponse(BaseModel):
    items: List[VehicleRead]
    total: int
    skip: int
    limit: int


class PaginatedLocationsResponse(BaseModel):
    items: List[VehicleLocationRead]
    total: int
    skip: int
    limit: int


class FleetSummaryResponse(BaseModel):
    total_vehicles: int
    active_vehicles: int
    available_vehicles: int
    idle_vehicles: int
    in_transit_vehicles: int
    breakdown_vehicles: int
    maintenance_vehicles: int
    offline_vehicles: int
    total_capacity_kg: float
    current_load_kg: float
    available_capacity_kg: float
    fleet_utilization_percentage: Optional[float]
    generated_at: datetime
    data_source: str = "SIMULATED"

