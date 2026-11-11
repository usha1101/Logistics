import logging
import time
from abc import ABC, abstractmethod
from typing import Any, Dict, Optional, Type
from pydantic import BaseModel

from app.models.agent import AgentExecutionStatus
from app.services.agents.exceptions import (
    AIExecutionRateLimitError,
    AIExecutionTimeoutError,
    AIProviderUnavailableError,
    AIStructuredOutputValidationError,
)
from app.services.agents.llm_provider import LLMService, llm_service
from app.services.agents.schemas import BaseAgentOutput

logger = logging.getLogger("base_agent")


class BaseAgent(ABC):
    """
    Abstract base specialist agent with unified prompt rendering, structured LLM execution,
    deterministic fallback, execution timing, and error handling.
    """

    def __init__(self, agent_name: str, system_prompt: str, output_schema: Type[BaseAgentOutput]):
        self.agent_name = agent_name
        self.system_prompt = system_prompt
        self.output_schema = output_schema
        self.llm: LLMService = llm_service

    @abstractmethod
    def build_user_prompt(self, operational_context: Dict[str, Any]) -> str:
        """Transforms structured database/service facts into the specialist LLM prompt."""
        pass

    @abstractmethod
    def build_deterministic_fallback(self, operational_context: Dict[str, Any], reason: str) -> BaseAgentOutput:
        """Provides verified rule-based findings if LLM provider is completely offline."""
        pass

    async def execute(self, operational_context: Dict[str, Any]) -> BaseAgentOutput:
        """Executes the agent analysis and guarantees a valid schema-conforming output."""
        start_time = time.perf_counter()
        user_prompt = self.build_user_prompt(operational_context)

        try:
            output, provider, model = await self.llm.generate_with_fallback(
                system_prompt=self.system_prompt,
                user_prompt=user_prompt,
                output_schema=self.output_schema,
            )
            duration_ms = (time.perf_counter() - start_time) * 1000.0
            output.provider = provider
            output.model = model
            output.execution_duration_ms = round(duration_ms, 2)
            output.execution_status = AgentExecutionStatus.COMPLETED
            return output

        except Exception as e:
            logger.warning(f"Agent '{self.agent_name}' LLM call failed ({type(e).__name__}: {e}). Triggering deterministic fallback.")
            duration_ms = (time.perf_counter() - start_time) * 1000.0
            fallback_output = self.build_deterministic_fallback(operational_context, reason=str(e))
            fallback_output.provider = "deterministic_fallback"
            fallback_output.model = "rule_engine"
            fallback_output.execution_duration_ms = round(duration_ms, 2)
            fallback_output.warnings.append(f"AI provider unavailable or failed: {str(e)}")
            return fallback_output

