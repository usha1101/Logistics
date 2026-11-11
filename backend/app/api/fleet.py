from datetime import datetime, timezone
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.api.deps import require_roles
from app.database.session import get_db
from app.models.user import User, UserRole
from app.models.vehicle import (
    LocationSource,
    Vehicle,
    VehicleLocation,
    VehicleStatus,
    VehicleStatusHistory,
    VehicleType,
)
from app.models.warehouse import Warehouse
from app.schemas.fleet import (
    FleetSummaryResponse,
    PaginatedLocationsResponse,
    PaginatedVehiclesResponse,
    VehicleCreate,
    VehicleLocationRead,
    VehicleLocationUpdate,
    VehicleRead,
    VehicleStatusChangeResponse,
    VehicleStatusHistoryRead,
    VehicleStatusUpdate,
    VehicleUpdate,
)

router = APIRouter(prefix="/fleet", tags=["Fleet Management & Vehicle Tracking"])

ALL_FLEET_READ_ROLES = (
    UserRole.ADMIN,
    UserRole.OPERATIONS_MANAGER,
    UserRole.FLEET_MANAGER,
    UserRole.WAREHOUSE_MANAGER,
    UserRole.ANALYST,
)

FLEET_MANAGE_ROLES = (
    UserRole.ADMIN,
    UserRole.FLEET_MANAGER,
)

FLEET_OPERATE_ROLES = (
    UserRole.ADMIN,
    UserRole.FLEET_MANAGER,
    UserRole.OPERATIONS_MANAGER,
)


@router.get(
    "/summary",
    response_model=FleetSummaryResponse,
    summary="Get aggregated fleet KPIs, utilization, and vehicle status breakdown",
)
def get_fleet_summary(
    current_user: User = Depends(require_roles(*ALL_FLEET_READ_ROLES)),
    db: Session = Depends(get_db),
) -> FleetSummaryResponse:
    vehicles = list(db.execute(select(Vehicle)).scalars().all())

    total_vehicles = len(vehicles)
    active_vehicles = sum(1 for v in vehicles if v.is_active)
    available_vehicles = sum(1 for v in vehicles if v.status == VehicleStatus.AVAILABLE.value and v.is_active)
    idle_vehicles = sum(1 for v in vehicles if v.status == VehicleStatus.IDLE.value and v.is_active)
    in_transit_vehicles = sum(1 for v in vehicles if v.status == VehicleStatus.IN_TRANSIT.value and v.is_active)
    breakdown_vehicles = sum(1 for v in vehicles if v.status == VehicleStatus.BREAKDOWN.value)
    maintenance_vehicles = sum(1 for v in vehicles if v.status == VehicleStatus.MAINTENANCE.value)
    offline_vehicles = sum(1 for v in vehicles if v.status == VehicleStatus.OFFLINE.value or not v.is_active)

    total_capacity_kg = sum(v.capacity_kg for v in vehicles)
    current_load_kg = sum(v.current_load_kg for v in vehicles)
    available_capacity_kg = max(0.0, total_capacity_kg - current_load_kg)

    if total_capacity_kg > 0:
        utilization = round((current_load_kg / total_capacity_kg) * 100.0, 2)
    else:
        utilization = None

    return FleetSummaryResponse(
        total_vehicles=total_vehicles,
        active_vehicles=active_vehicles,
        available_vehicles=available_vehicles,
        idle_vehicles=idle_vehicles,
        in_transit_vehicles=in_transit_vehicles,
        breakdown_vehicles=breakdown_vehicles,
        maintenance_vehicles=maintenance_vehicles,
        offline_vehicles=offline_vehicles,
        total_capacity_kg=round(total_capacity_kg, 2),
        current_load_kg=round(current_load_kg, 2),
        available_capacity_kg=round(available_capacity_kg, 2),
        fleet_utilization_percentage=utilization,
        generated_at=datetime.now(timezone.utc),
        data_source="SIMULATED",
    )


@router.get(
    "/vehicles/available",
    response_model=PaginatedVehiclesResponse,
    summary="List active vehicles with status AVAILABLE or IDLE and unallocated capacity",
)
def get_available_vehicles(
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    current_user: User = Depends(require_roles(*ALL_FLEET_READ_ROLES)),
    db: Session = Depends(get_db),
) -> PaginatedVehiclesResponse:
    query = (
        select(Vehicle)
        .where(
            Vehicle.is_active == True,
            Vehicle.status.in_([VehicleStatus.AVAILABLE.value, VehicleStatus.IDLE.value]),
            Vehicle.current_load_kg < Vehicle.capacity_kg,
        )
        .order_by(Vehicle.vehicle_code.asc())
    )

    total = db.execute(select(func.count()).select_from(query.subquery())).scalar() or 0
    vehicles = list(db.execute(query.offset(skip).limit(limit)).scalars().all())

    return PaginatedVehiclesResponse(
        items=[VehicleRead.model_validate(v) for v in vehicles],
        total=total,
        skip=skip,
        limit=limit,
    )


@router.get(
    "/vehicles",
    response_model=PaginatedVehiclesResponse,
    summary="List fleet vehicles with status, type, warehouse, and active filters",
)
def list_vehicles(
    status_filter: Optional[VehicleStatus] = Query(None, alias="status", description="Filter by vehicle status"),
    vehicle_type: Optional[VehicleType] = Query(None, description="Filter by vehicle classification"),
    home_warehouse_id: Optional[str] = Query(None, description="Filter by home base warehouse ID"),
    is_active: Optional[bool] = Query(None, description="Filter by active status"),
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    current_user: User = Depends(require_roles(*ALL_FLEET_READ_ROLES)),
    db: Session = Depends(get_db),
) -> PaginatedVehiclesResponse:
    query = select(Vehicle)

    if status_filter is not None:
        query = query.where(Vehicle.status == status_filter.value)
    if vehicle_type is not None:
        query = query.where(Vehicle.vehicle_type == vehicle_type.value)
    if home_warehouse_id is not None:
        query = query.where(Vehicle.home_warehouse_id == home_warehouse_id)
    if is_active is not None:
        query = query.where(Vehicle.is_active == is_active)

    total = db.execute(select(func.count()).select_from(query.subquery())).scalar() or 0
    vehicles = list(db.execute(query.order_by(Vehicle.vehicle_code.asc()).offset(skip).limit(limit)).scalars().all())

    return PaginatedVehiclesResponse(
        items=[VehicleRead.model_validate(v) for v in vehicles],
        total=total,
        skip=skip,
        limit=limit,
    )


@router.post(
    "/vehicles",
    response_model=VehicleRead,
    status_code=status.HTTP_201_CREATED,
    summary="Register a new fleet vehicle",
)
def register_vehicle(
    payload: VehicleCreate,
    current_user: User = Depends(require_roles(*FLEET_MANAGE_ROLES)),
    db: Session = Depends(get_db),
) -> VehicleRead:
    # Check duplicate vehicle code
    existing_code = db.execute(select(Vehicle).where(Vehicle.vehicle_code == payload.vehicle_code)).scalar_one_or_none()
    if existing_code:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Vehicle with code '{payload.vehicle_code}' already exists",
        )

    # Check duplicate registration number
    existing_reg = db.execute(
        select(Vehicle).where(Vehicle.registration_number == payload.registration_number)
    ).scalar_one_or_none()
    if existing_reg:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Vehicle with registration number '{payload.registration_number}' already exists",
        )

    # Validate home warehouse if provided
    if payload.home_warehouse_id:
        wh = db.execute(select(Warehouse).where(Warehouse.id == payload.home_warehouse_id)).scalar_one_or_none()
        if not wh:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Home warehouse '{payload.home_warehouse_id}' not found",
            )

    now = datetime.now(timezone.utc)
    vehicle = Vehicle(
        vehicle_code=payload.vehicle_code,
        registration_number=payload.registration_number,
        vehicle_type=payload.vehicle_type.value,
        manufacturer=payload.manufacturer,
        model=payload.model,
        capacity_kg=payload.capacity_kg,
        current_load_kg=0.0,
        status=VehicleStatus.AVAILABLE.value,
        home_warehouse_id=payload.home_warehouse_id,
        current_latitude=payload.initial_latitude,
        current_longitude=payload.initial_longitude,
        current_speed_kmph=payload.initial_speed_kmph,
        heading_degrees=payload.initial_heading_degrees,
        is_active=payload.is_active,
        last_location_update=now if (payload.initial_latitude is not None and payload.initial_longitude is not None) else None,
    )
    db.add(vehicle)
    db.flush()

    # Record initial location if provided
    if payload.initial_latitude is not None and payload.initial_longitude is not None:
        loc = VehicleLocation(
            vehicle_id=vehicle.id,
            latitude=payload.initial_latitude,
            longitude=payload.initial_longitude,
            speed_kmph=payload.initial_speed_kmph,
            heading_degrees=payload.initial_heading_degrees,
            source=LocationSource.MANUAL.value,
            recorded_at=now,
        )
        db.add(loc)

    db.commit()
    db.refresh(vehicle)
    return VehicleRead.model_validate(vehicle)


@router.get(
    "/vehicles/{vehicle_id}",
    response_model=VehicleRead,
    summary="Get complete vehicle details by ID",
)
def get_vehicle(
    vehicle_id: str,
    current_user: User = Depends(require_roles(*ALL_FLEET_READ_ROLES)),
    db: Session = Depends(get_db),
) -> VehicleRead:
    vehicle = db.execute(select(Vehicle).where(Vehicle.id == vehicle_id)).scalar_one_or_none()
    if not vehicle:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Vehicle '{vehicle_id}' not found",
        )
    return VehicleRead.model_validate(vehicle)


@router.patch(
    "/vehicles/{vehicle_id}",
    response_model=VehicleRead,
    summary="Update permitted vehicle specifications and metadata",
)
def update_vehicle(
    vehicle_id: str,
    payload: VehicleUpdate,
    current_user: User = Depends(require_roles(*FLEET_MANAGE_ROLES)),
    db: Session = Depends(get_db),
) -> VehicleRead:
    vehicle = db.execute(select(Vehicle).where(Vehicle.id == vehicle_id)).scalar_one_or_none()
    if not vehicle:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Vehicle '{vehicle_id}' not found",
        )

    if payload.capacity_kg is not None:
        if payload.capacity_kg < vehicle.current_load_kg:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Cannot reduce capacity to {payload.capacity_kg} kg below current load of {vehicle.current_load_kg} kg",
            )
        vehicle.capacity_kg = payload.capacity_kg

    if payload.vehicle_type is not None:
        vehicle.vehicle_type = payload.vehicle_type.value
    if payload.manufacturer is not None:
        vehicle.manufacturer = payload.manufacturer
    if payload.model is not None:
        vehicle.model = payload.model
    if payload.is_active is not None:
        vehicle.is_active = payload.is_active
    if payload.home_warehouse_id is not None:
        wh = db.execute(select(Warehouse).where(Warehouse.id == payload.home_warehouse_id)).scalar_one_or_none()
        if not wh:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Home warehouse '{payload.home_warehouse_id}' not found",
            )
        vehicle.home_warehouse_id = payload.home_warehouse_id

    db.commit()
    db.refresh(vehicle)
    return VehicleRead.model_validate(vehicle)


@router.patch(
    "/vehicles/{vehicle_id}/status",
    response_model=VehicleStatusChangeResponse,
    summary="Update vehicle operational status and record status change history",
)
def update_vehicle_status(
    vehicle_id: str,
    payload: VehicleStatusUpdate,
    current_user: User = Depends(require_roles(*FLEET_OPERATE_ROLES)),
    db: Session = Depends(get_db),
) -> VehicleStatusChangeResponse:
    vehicle = db.execute(select(Vehicle).where(Vehicle.id == vehicle_id)).scalar_one_or_none()
    if not vehicle:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Vehicle '{vehicle_id}' not found",
        )

    # Prevent inactive vehicles from becoming AVAILABLE
    if payload.status == VehicleStatus.AVAILABLE and not vehicle.is_active:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Inactive vehicles cannot be marked as AVAILABLE. Activate the vehicle first.",
        )

    # Note on order assignments: in Stage 5, vehicle order assignments are not yet implemented.
    # Future stages will validate that active in-flight assignments prevent transition to MAINTENANCE or AVAILABLE.

    # If status hasn't changed, do not create duplicate history
    if vehicle.status == payload.status.value:
        return VehicleStatusChangeResponse(
            vehicle=VehicleRead.model_validate(vehicle),
            status_history=None,
        )

    prev_status = vehicle.status
    vehicle.status = payload.status.value

    history = VehicleStatusHistory(
        vehicle_id=vehicle.id,
        previous_status=prev_status,
        new_status=payload.status.value,
        reason=payload.reason,
        changed_by_user_id=current_user.id,
    )
    db.add(history)
    db.commit()
    db.refresh(vehicle)
    db.refresh(history)

    return VehicleStatusChangeResponse(
        vehicle=VehicleRead.model_validate(vehicle),
        status_history=VehicleStatusHistoryRead.model_validate(history),
    )


@router.patch(
    "/vehicles/{vehicle_id}/location",
    response_model=VehicleLocationRead,
    summary="Update vehicle telemetry coordinates, speed, and heading with immutable history",
)
def update_vehicle_location(
    vehicle_id: str,
    payload: VehicleLocationUpdate,
    current_user: User = Depends(require_roles(*FLEET_OPERATE_ROLES)),
    db: Session = Depends(get_db),
) -> VehicleLocationRead:
    vehicle = db.execute(select(Vehicle).where(Vehicle.id == vehicle_id)).scalar_one_or_none()
    if not vehicle:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Vehicle '{vehicle_id}' not found",
        )

    now = datetime.now(timezone.utc)
    source_val = payload.source.value if payload.source else LocationSource.MANUAL.value

    loc = VehicleLocation(
        vehicle_id=vehicle.id,
        latitude=payload.latitude,
        longitude=payload.longitude,
        speed_kmph=payload.speed_kmph,
        heading_degrees=payload.heading_degrees,
        source=source_val,
        recorded_at=now,
    )
    db.add(loc)

    # Update vehicle current location
    vehicle.current_latitude = payload.latitude
    vehicle.current_longitude = payload.longitude
    vehicle.current_speed_kmph = payload.speed_kmph
    vehicle.heading_degrees = payload.heading_degrees
    vehicle.last_location_update = now

    db.commit()
    db.refresh(loc)
    return VehicleLocationRead.model_validate(loc)


@router.get(
    "/vehicles/{vehicle_id}/location",
    response_model=VehicleLocationRead,
    summary="Get current location coordinates of a vehicle",
)
def get_vehicle_current_location(
    vehicle_id: str,
    current_user: User = Depends(require_roles(*ALL_FLEET_READ_ROLES)),
    db: Session = Depends(get_db),
) -> VehicleLocationRead:
    vehicle = db.execute(select(Vehicle).where(Vehicle.id == vehicle_id)).scalar_one_or_none()
    if not vehicle:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Vehicle '{vehicle_id}' not found",
        )

    if vehicle.current_latitude is None or vehicle.current_longitude is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No location telemetry recorded for vehicle '{vehicle_id}'",
        )

    # Find latest location record or synthesize from vehicle
    latest_loc = (
        db.execute(
            select(VehicleLocation)
            .where(VehicleLocation.vehicle_id == vehicle_id)
            .order_by(VehicleLocation.recorded_at.desc())
        )
        .scalars()
        .first()
    )

    if latest_loc:
        return VehicleLocationRead.model_validate(latest_loc)

    return VehicleLocationRead(
        id=f"loc-synth-{vehicle.id}",
        vehicle_id=vehicle.id,
        latitude=vehicle.current_latitude,
        longitude=vehicle.current_longitude,
        speed_kmph=vehicle.current_speed_kmph,
        heading_degrees=vehicle.heading_degrees,
        coordinates=[vehicle.current_longitude, vehicle.current_latitude],
        recorded_at=vehicle.last_location_update or datetime.now(timezone.utc),
        source=LocationSource.SIMULATION.value,
    )


@router.get(
    "/vehicles/{vehicle_id}/history",
    response_model=PaginatedLocationsResponse,
    summary="Get chronological location history for a vehicle (newest first)",
)
def get_vehicle_location_history(
    vehicle_id: str,
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
    current_user: User = Depends(require_roles(*ALL_FLEET_READ_ROLES)),
    db: Session = Depends(get_db),
) -> PaginatedLocationsResponse:
    vehicle = db.execute(select(Vehicle).where(Vehicle.id == vehicle_id)).scalar_one_or_none()
    if not vehicle:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Vehicle '{vehicle_id}' not found",
        )

    query = (
        select(VehicleLocation)
        .where(VehicleLocation.vehicle_id == vehicle_id)
        .order_by(VehicleLocation.recorded_at.desc())
    )

    total = db.execute(select(func.count()).select_from(query.subquery())).scalar() or 0
    locations = list(db.execute(query.offset(skip).limit(limit)).scalars().all())

    return PaginatedLocationsResponse(
        items=[VehicleLocationRead.model_validate(loc) for loc in locations],
        total=total,
        skip=skip,
        limit=limit,
    )

