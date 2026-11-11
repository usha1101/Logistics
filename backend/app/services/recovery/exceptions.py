class RecoveryEngineError(Exception):
    """Base exception for all recovery and optimization operations."""
    status_code: int = 400
    error_code: str = "RECOVERY_ENGINE_ERROR"

    def __init__(self, message: str):
        super().__init__(message)
        self.message = message


class RecoveryPlanNotFoundError(RecoveryEngineError):
    """Raised when a requested recovery plan does not exist."""
    status_code: int = 404
    error_code: str = "RECOVERY_PLAN_NOT_FOUND"


class InfeasibleOptimizationError(RecoveryEngineError):
    """Raised when constraints prevent finding any feasible recovery plan."""
    status_code: int = 422
    error_code: str = "OPTIMIZATION_INFEASIBLE"


class PlanValidationFailedError(RecoveryEngineError):
    """Raised when a candidate recovery plan fails deterministic safety verification."""
    status_code: int = 400
    error_code: str = "PLAN_VALIDATION_FAILED"


class StalePlanStateError(RecoveryEngineError):
    """Raised when database operational state has changed since the plan was generated."""
    status_code: int = 409
    error_code: str = "STALE_PLAN_STATE"


class InvalidPlanStatusTransitionError(RecoveryEngineError):
    """Raised when attempting an invalid status transition on a recovery plan."""
    status_code: int = 400
    error_code: str = "INVALID_PLAN_TRANSITION"


class RecoveryExecutionError(RecoveryEngineError):
    """Raised when transactional application of recovery actions fails."""
    status_code: int = 500
    error_code: str = "RECOVERY_EXECUTION_FAILED"

