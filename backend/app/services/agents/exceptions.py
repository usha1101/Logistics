class AgentIntelligenceError(Exception):
    """Base exception for all AI agent intelligence operations."""
    status_code: int = 400
    error_code: str = "AGENT_INTELLIGENCE_ERROR"

    def __init__(self, message: str):
        super().__init__(message)
        self.message = message


class AgentRunNotFoundError(AgentIntelligenceError):
    """Raised when a requested agent run is not found."""
    status_code: int = 404
    error_code: str = "AGENT_RUN_NOT_FOUND"


class AIProviderUnavailableError(AgentIntelligenceError):
    """Raised when primary and fallback LLM providers are offline, unconfigured, or failing."""
    status_code: int = 503
    error_code: str = "AI_UNAVAILABLE"


class AIStructuredOutputValidationError(AgentIntelligenceError):
    """Raised when an LLM returns unparseable or schema-invalid JSON after retries."""
    status_code: int = 502
    error_code: str = "AI_STRUCTURED_OUTPUT_VALIDATION_ERROR"


class AIExecutionTimeoutError(AgentIntelligenceError):
    """Raised when an LLM request exceeds configured timeout."""
    status_code: int = 504
    error_code: str = "AI_TIMEOUT"


class AIExecutionRateLimitError(AgentIntelligenceError):
    """Raised when LLM provider returns 429 rate limit error."""
    status_code: int = 429
    error_code: str = "AI_RATE_LIMIT"


class InvalidOrchestrationStateError(AgentIntelligenceError):
    """Raised when attempting an invalid operation on an agent run."""
    status_code: int = 400
    error_code: str = "INVALID_ORCHESTRATION_STATE"

