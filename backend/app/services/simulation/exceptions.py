class SimulationError(Exception):
    """Base exception for simulation engine operations."""
    pass


class SimulationNotFoundError(SimulationError):
    """Raised when a simulation run is not found."""
    pass


class InvalidStateTransitionError(SimulationError):
    """Raised when an illegal lifecycle transition is attempted."""
    pass


class VehicleAlreadyAssignedError(SimulationError):
    """Raised when a vehicle is already part of the simulation run."""
    pass


class VehicleUnavailableError(SimulationError):
    """Raised when a vehicle is inactive or under maintenance."""
    pass


class RouteCalculationError(SimulationError):
    """Raised when no navigable route exists between origin and destination."""
    pass

