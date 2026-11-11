class DisruptionError(Exception):
    """Base error for disruption operations."""
    status_code: int = 400
    error_code: str = "DISRUPTION_ERROR"

    def __init__(self, message: str):
        super().__init__(message)
        self.message = message


class DisruptionNotFoundError(DisruptionError):
    """Raised when a requested disruption record is not found."""
    status_code: int = 404
    error_code: str = "DISRUPTION_NOT_FOUND"


class InvalidDisruptionTransitionError(DisruptionError):
    """Raised when an illegal status lifecycle transition is attempted."""
    status_code: int = 400
    error_code: str = "INVALID_DISRUPTION_TRANSITION"


class TargetResourceValidationError(DisruptionError):
    """Raised when the target resource specified for a disruption does not exist or is invalid."""
    status_code: int = 422
    error_code: str = "INVALID_TARGET_RESOURCE"


class SimulationVehicleNotFoundError(DisruptionError):
    """Raised when a simulated vehicle cannot be found in the active simulation session."""
    status_code: int = 404
    error_code: str = "SIMULATION_VEHICLE_NOT_FOUND"
