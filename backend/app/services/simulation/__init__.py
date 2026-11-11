"""Simulation package for LOGIPULSE digital twin engine."""

from app.services.simulation.clock import SimulationClock
from app.services.simulation.events import create_simulation_event
from app.services.simulation.exceptions import (
    InvalidStateTransitionError,
    RouteCalculationError,
    SimulationError,
    SimulationNotFoundError,
    VehicleAlreadyAssignedError,
    VehicleUnavailableError,
)
from app.services.simulation.manager import (
    SimulationManager,
    WebSocketConnectionManager,
    simulation_manager,
    ws_manager,
)
from app.services.simulation.movement import (
    MovementStepResult,
    advance_vehicle_along_route,
    calculate_bearing,
    calculate_haversine_distance,
    interpolate_position,
)

__all__ = [
    "SimulationClock",
    "create_simulation_event",
    "SimulationError",
    "SimulationNotFoundError",
    "InvalidStateTransitionError",
    "VehicleAlreadyAssignedError",
    "VehicleUnavailableError",
    "RouteCalculationError",
    "SimulationManager",
    "WebSocketConnectionManager",
    "simulation_manager",
    "ws_manager",
    "MovementStepResult",
    "calculate_haversine_distance",
    "calculate_bearing",
    "interpolate_position",
    "advance_vehicle_along_route",
]

