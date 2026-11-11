import logging
from typing import List, Optional
from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    Query,
    WebSocket,
    WebSocketDisconnect,
    status,
)
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, require_roles
from app.core.security import decode_access_token
from app.database.session import get_db
from app.models.simulation import (
    Simulation,
    SimulationEvent,
    SimulationStatus,
    SimulationTelemetry,
    SimulationVehicleState,
)
from app.models.user import User, UserRole
from app.schemas.simulation import (
    PaginatedEventsResponse,
    PaginatedSimulationsResponse,
    PaginatedTelemetryResponse,
    SimulationCreate,
    SimulationEventRead,
    SimulationRead,
    SimulationSpeedUpdate,
    SimulationSummary,
    SimulationTelemetryRead,
    SimulationVehicleCreate,
    SimulationVehicleRead,
)
from app.services.simulation import (
    InvalidStateTransitionError,
    RouteCalculationError,
    SimulationNotFoundError,
    VehicleAlreadyAssignedError,
    VehicleUnavailableError,
    simulation_manager,
    ws_manager,
)

logger = logging.getLogger("simulations_api")

router = APIRouter(prefix="/simulations", tags=["Simulation Engine"])

# Roles with control execution rights
SIMULATION_CONTROL_ROLES = (
    UserRole.ADMIN,
    UserRole.OPERATIONS_MANAGER,
)

# Roles with read access
SIMULATION_READ_ROLES = (
    UserRole.ADMIN,
    UserRole.OPERATIONS_MANAGER,
    UserRole.ANALYST,
    UserRole.FLEET_MANAGER,
    UserRole.WAREHOUSE_MANAGER,
)


def _serialize_simulation(sim: Simulation) -> SimulationRead:
    return SimulationRead(
        id=sim.id,
        name=sim.name,
        seed=sim.seed,
        status=sim.status,
        simulation_speed_multiplier=sim.simulation_speed_multiplier,
        simulated_time=sim.simulated_time,
        started_at=sim.started_at,
        paused_at=sim.paused_at,
        resumed_at=sim.resumed_at,
        stopped_at=sim.stopped_at,
        created_by_user_id=sim.created_by_user_id,
        configuration=sim.configuration,
        total_vehicles=len(sim.vehicle_states) if sim.vehicle_states else 0,
        created_at=sim.created_at,
        updated_at=sim.updated_at,
    )


def _serialize_vehicle_state(vs: SimulationVehicleState) -> SimulationVehicleRead:
    return SimulationVehicleRead(
        id=vs.id,
        simulation_id=vs.simulation_id,
        vehicle_id=vs.vehicle_id,
        vehicle_code=vs.vehicle.vehicle_code if vs.vehicle else None,
        origin_node_id=vs.origin_node_id,
        destination_node_id=vs.destination_node_id,
        origin_node_name=vs.origin_node.name if vs.origin_node else None,
        destination_node_name=vs.destination_node.name if vs.destination_node else None,
        route_node_ids=vs.route_node_ids,
        current_route_segment=vs.current_route_segment,
        segment_progress=vs.segment_progress,
        progress_percentage=vs.progress_percentage,
        current_latitude=vs.current_latitude,
        current_longitude=vs.current_longitude,
        current_speed_kmph=vs.current_speed_kmph,
        heading_degrees=vs.heading_degrees,
        status=vs.status,
        simulated_departure_time=vs.simulated_departure_time,
        estimated_arrival_time=vs.estimated_arrival_time,
        actual_arrival_time=vs.actual_arrival_time,
        created_at=vs.created_at,
        updated_at=vs.updated_at,
    )


# ============================================================================
# SIMULATION LIFECYCLE MANAGEMENT
# ============================================================================

@router.post(
    "",
    response_model=SimulationRead,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new simulation run",
)
def create_simulation(
    payload: SimulationCreate,
    current_user: User = Depends(require_roles(*SIMULATION_CONTROL_ROLES)),
    db: Session = Depends(get_db),
) -> SimulationRead:
    sim = simulation_manager.create_simulation(
        db=db,
        name=payload.name,
        seed=payload.seed,
        speed_multiplier=payload.simulation_speed_multiplier,
        configuration=payload.configuration,
        created_by_user_id=current_user.id,
    )
    return _serialize_simulation(sim)


@router.get(
    "",
    response_model=PaginatedSimulationsResponse,
    summary="List simulation runs with optional status filtering",
)
def list_simulations(
    status_filter: Optional[SimulationStatus] = Query(None, alias="status"),
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
    current_user: User = Depends(require_roles(*SIMULATION_READ_ROLES)),
    db: Session = Depends(get_db),
) -> PaginatedSimulationsResponse:
    query = select(Simulation)
    if status_filter:
        query = query.where(Simulation.status == status_filter.value)

    total = db.execute(select(func.count()).select_from(query.subquery())).scalar() or 0
    paginated_stmt = query.order_by(Simulation.created_at.desc()).offset(skip).limit(limit)
    sims = list(db.execute(paginated_stmt).scalars().all())

    return PaginatedSimulationsResponse(
        items=[_serialize_simulation(s) for s in sims],
        total=total,
        skip=skip,
        limit=limit,
    )


@router.get(
    "/{simulation_id}",
    response_model=SimulationRead,
    summary="Get single simulation run by ID",
)
def get_simulation(
    simulation_id: str,
    current_user: User = Depends(require_roles(*SIMULATION_READ_ROLES)),
    db: Session = Depends(get_db),
) -> SimulationRead:
    sim = db.execute(select(Simulation).where(Simulation.id == simulation_id)).scalar_one_or_none()
    if not sim:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Simulation '{simulation_id}' not found",
        )
    return _serialize_simulation(sim)


@router.post(
    "/{simulation_id}/start",
    response_model=SimulationRead,
    summary="Start or launch a simulation run",
)
def start_simulation(
    simulation_id: str,
    current_user: User = Depends(require_roles(*SIMULATION_CONTROL_ROLES)),
    db: Session = Depends(get_db),
) -> SimulationRead:
    try:
        sim = simulation_manager.start_simulation(simulation_id, db)
        return _serialize_simulation(sim)
    except SimulationNotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except InvalidStateTransitionError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.post(
    "/{simulation_id}/pause",
    response_model=SimulationRead,
    summary="Pause a running simulation",
)
def pause_simulation(
    simulation_id: str,
    current_user: User = Depends(require_roles(*SIMULATION_CONTROL_ROLES)),
    db: Session = Depends(get_db),
) -> SimulationRead:
    try:
        sim = simulation_manager.pause_simulation(simulation_id, db)
        return _serialize_simulation(sim)
    except SimulationNotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except InvalidStateTransitionError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.post(
    "/{simulation_id}/resume",
    response_model=SimulationRead,
    summary="Resume a paused simulation",
)
def resume_simulation(
    simulation_id: str,
    current_user: User = Depends(require_roles(*SIMULATION_CONTROL_ROLES)),
    db: Session = Depends(get_db),
) -> SimulationRead:
    try:
        sim = simulation_manager.resume_simulation(simulation_id, db)
        return _serialize_simulation(sim)
    except SimulationNotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except InvalidStateTransitionError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.post(
    "/{simulation_id}/stop",
    response_model=SimulationRead,
    summary="Stop a running or paused simulation",
)
def stop_simulation(
    simulation_id: str,
    current_user: User = Depends(require_roles(*SIMULATION_CONTROL_ROLES)),
    db: Session = Depends(get_db),
) -> SimulationRead:
    try:
        sim = simulation_manager.stop_simulation(simulation_id, db)
        return _serialize_simulation(sim)
    except SimulationNotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except InvalidStateTransitionError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.post(
    "/{simulation_id}/reset",
    response_model=SimulationRead,
    summary="Reset a stopped or completed simulation to initial state",
)
def reset_simulation(
    simulation_id: str,
    current_user: User = Depends(require_roles(*SIMULATION_CONTROL_ROLES)),
    db: Session = Depends(get_db),
) -> SimulationRead:
    try:
        sim = simulation_manager.reset_simulation(simulation_id, db)
        return _serialize_simulation(sim)
    except SimulationNotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except InvalidStateTransitionError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.patch(
    "/{simulation_id}/speed",
    response_model=SimulationRead,
    summary="Update simulation clock speed multiplier (0.1x to 100x)",
)
def update_simulation_speed(
    simulation_id: str,
    payload: SimulationSpeedUpdate,
    current_user: User = Depends(require_roles(*SIMULATION_CONTROL_ROLES)),
    db: Session = Depends(get_db),
) -> SimulationRead:
    try:
        sim = simulation_manager.update_speed(simulation_id, payload.speed_multiplier, db)
        return _serialize_simulation(sim)
    except SimulationNotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))


# ============================================================================
# VEHICLE ASSIGNMENT & PROGRESS
# ============================================================================

@router.post(
    "/{simulation_id}/vehicles",
    response_model=SimulationVehicleRead,
    status_code=status.HTTP_201_CREATED,
    summary="Assign a vehicle to simulation with route calculated from origin to destination",
)
def add_vehicle_to_simulation(
    simulation_id: str,
    payload: SimulationVehicleCreate,
    current_user: User = Depends(require_roles(*SIMULATION_CONTROL_ROLES)),
    db: Session = Depends(get_db),
) -> SimulationVehicleRead:
    try:
        vs = simulation_manager.add_vehicle_to_simulation(
            simulation_id=simulation_id,
            vehicle_id=payload.vehicle_id,
            origin_node_id=payload.origin_node_id,
            destination_node_id=payload.destination_node_id,
            db=db,
        )
        return _serialize_vehicle_state(vs)
    except SimulationNotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except (VehicleUnavailableError, VehicleAlreadyAssignedError, RouteCalculationError) as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.get(
    "/{simulation_id}/vehicles",
    response_model=List[SimulationVehicleRead],
    summary="List all vehicle states for a simulation",
)
def list_simulation_vehicles(
    simulation_id: str,
    current_user: User = Depends(require_roles(*SIMULATION_READ_ROLES)),
    db: Session = Depends(get_db),
) -> List[SimulationVehicleRead]:
    sim = db.execute(select(Simulation).where(Simulation.id == simulation_id)).scalar_one_or_none()
    if not sim:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Simulation '{simulation_id}' not found")
    return [_serialize_vehicle_state(vs) for vs in sim.vehicle_states]


@router.get(
    "/{simulation_id}/vehicles/{vehicle_id}",
    response_model=SimulationVehicleRead,
    summary="Get state and progress of specific vehicle in simulation",
)
def get_simulation_vehicle(
    simulation_id: str,
    vehicle_id: str,
    current_user: User = Depends(require_roles(*SIMULATION_READ_ROLES)),
    db: Session = Depends(get_db),
) -> SimulationVehicleRead:
    vs = db.execute(
        select(SimulationVehicleState).where(
            SimulationVehicleState.simulation_id == simulation_id,
            SimulationVehicleState.vehicle_id == vehicle_id,
        )
    ).scalar_one_or_none()
    if not vs:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Vehicle '{vehicle_id}' not found in simulation '{simulation_id}'",
        )
    return _serialize_vehicle_state(vs)


# ============================================================================
# EVENTS & TELEMETRY
# ============================================================================

@router.get(
    "/{simulation_id}/events",
    response_model=PaginatedEventsResponse,
    summary="Get paginated event history for a simulation run",
)
def list_simulation_events(
    simulation_id: str,
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
    current_user: User = Depends(require_roles(*SIMULATION_READ_ROLES)),
    db: Session = Depends(get_db),
) -> PaginatedEventsResponse:
    sim = db.execute(select(Simulation).where(Simulation.id == simulation_id)).scalar_one_or_none()
    if not sim:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Simulation '{simulation_id}' not found")

    query = select(SimulationEvent).where(SimulationEvent.simulation_id == simulation_id)
    total = db.execute(select(func.count()).select_from(query.subquery())).scalar() or 0
    items = list(db.execute(query.order_by(SimulationEvent.created_at.desc()).offset(skip).limit(limit)).scalars().all())

    return PaginatedEventsResponse(
        items=[SimulationEventRead.model_validate(e) for e in items],
        total=total,
        skip=skip,
        limit=limit,
    )


@router.get(
    "/{simulation_id}/telemetry",
    response_model=PaginatedTelemetryResponse,
    summary="Get recorded simulated telemetry breadcrumbs",
)
def list_simulation_telemetry(
    simulation_id: str,
    vehicle_id: Optional[str] = Query(None, description="Filter telemetry by vehicle"),
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    current_user: User = Depends(require_roles(*SIMULATION_READ_ROLES)),
    db: Session = Depends(get_db),
) -> PaginatedTelemetryResponse:
    sim = db.execute(select(Simulation).where(Simulation.id == simulation_id)).scalar_one_or_none()
    if not sim:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Simulation '{simulation_id}' not found")

    query = select(SimulationTelemetry).where(SimulationTelemetry.simulation_id == simulation_id)
    if vehicle_id:
        query = query.where(SimulationTelemetry.vehicle_id == vehicle_id)

    total = db.execute(select(func.count()).select_from(query.subquery())).scalar() or 0
    items = list(db.execute(query.order_by(SimulationTelemetry.recorded_at.desc()).offset(skip).limit(limit)).scalars().all())

    return PaginatedTelemetryResponse(
        items=[SimulationTelemetryRead.model_validate(t) for t in items],
        total=total,
        skip=skip,
        limit=limit,
    )


@router.get(
    "/{simulation_id}/summary",
    response_model=SimulationSummary,
    summary="Get comprehensive simulation KPIs and summary metrics",
)
def get_simulation_summary(
    simulation_id: str,
    current_user: User = Depends(require_roles(*SIMULATION_READ_ROLES)),
    db: Session = Depends(get_db),
) -> SimulationSummary:
    sim = db.execute(select(Simulation).where(Simulation.id == simulation_id)).scalar_one_or_none()
    if not sim:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Simulation '{simulation_id}' not found")

    v_states = sim.vehicle_states
    total_v = len(v_states)
    queued_v = sum(1 for v in v_states if v.status == "QUEUED")
    en_route_v = sum(1 for v in v_states if v.status == "EN_ROUTE")
    arrived_v = sum(1 for v in v_states if v.status == "ARRIVED")
    avg_progress = (sum(v.progress_percentage for v in v_states) / total_v) if total_v > 0 else 0.0

    total_telem = db.execute(
        select(func.count()).where(SimulationTelemetry.simulation_id == simulation_id)
    ).scalar() or 0

    total_ev = db.execute(
        select(func.count()).where(SimulationEvent.simulation_id == simulation_id)
    ).scalar() or 0

    elapsed_seconds = None
    if sim.started_at and sim.simulated_time:
        elapsed_seconds = round((sim.simulated_time - sim.started_at).total_seconds(), 1)

    return SimulationSummary(
        id=sim.id,
        name=sim.name,
        status=sim.status,
        speed_multiplier=sim.simulation_speed_multiplier,
        simulated_time=sim.simulated_time,
        total_vehicles=total_v,
        queued_vehicles=queued_v,
        en_route_vehicles=en_route_v,
        arrived_vehicles=arrived_v,
        average_progress_percentage=round(avg_progress, 1),
        total_telemetry_points=total_telem,
        total_events=total_ev,
        started_at=sim.started_at,
        elapsed_simulated_seconds=elapsed_seconds,
        data_source="SIMULATED",
    )


# ============================================================================
# WEBSOCKET STREAMING
# ============================================================================

@router.websocket("/{simulation_id}/ws")
async def simulation_websocket_endpoint(
    websocket: WebSocket,
    simulation_id: str,
):
    """Real-time event streaming WebSocket for simulation telemetry and lifecycle events."""
    await ws_manager.connect(simulation_id, websocket)
    try:
        while True:
            # Keep connection open and receive optional client heartbeats / control pings
            data = await websocket.receive_text()
            if data == "ping":
                await websocket.send_text("pong")
    except WebSocketDisconnect:
        ws_manager.disconnect(simulation_id, websocket)
    except Exception as e:
        logger.warning(f"WebSocket connection error on '{simulation_id}': {e}")
        ws_manager.disconnect(simulation_id, websocket)

