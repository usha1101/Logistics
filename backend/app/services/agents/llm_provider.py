import json
import logging
import re
import time
from abc import ABC, abstractmethod
from typing import Any, Dict, Optional, Type, TypeVar
import httpx
from pydantic import BaseModel, ValidationError

from app.core.config import settings
from app.services.agents.exceptions import (
    AIExecutionRateLimitError,
    AIExecutionTimeoutError,
    AIProviderUnavailableError,
    AIStructuredOutputValidationError,
)

logger = logging.getLogger("ai_llm_provider")

T = TypeVar("T", bound=BaseModel)


def clean_json_markdown(text: str) -> str:
    """Strips markdown ```json ... ``` wrappers if present."""
    text = text.strip()
    match = re.search(r"```(?:json)?\s*([\s\S]*?)\s*```", text)
    if match:
        return match.group(1).strip()
    return text


class BaseLLMProvider(ABC):
    """Abstract base class for LLM providers."""

    @abstractmethod
    async def generate_structured(
        self,
        system_prompt: str,
        user_prompt: str,
        output_schema: Type[T],
        temperature: float = 0.2,
    ) -> T:
        """Generates and parses a structured response conforming to output_schema."""
        pass

    @abstractmethod
    def is_configured(self) -> bool:
        """Checks if provider has valid credentials configured."""
        pass


class GeminiProvider(BaseLLMProvider):
    """Google Gemini LLM provider implementation using standard HTTP REST API."""

    def __init__(self, api_key: Optional[str] = None, model: Optional[str] = None):
        self.api_key = api_key if api_key is not None else settings.GEMINI_API_KEY
        self.model = model or settings.GEMINI_MODEL
        self.timeout = settings.AI_TIMEOUT_SECONDS

    def is_configured(self) -> bool:
        return bool(self.api_key and self.api_key.strip())

    async def generate_structured(
        self,
        system_prompt: str,
        user_prompt: str,
        output_schema: Type[T],
        temperature: float = 0.2,
    ) -> T:
        if not self.is_configured():
            raise AIProviderUnavailableError("Gemini API key is not configured.")

        url = f"https://generativelanguage.googleapis.com/v1beta/models/{self.model}:generateContent?key={self.api_key}"
        headers = {"Content-Type": "application/json"}
        payload = {
            "system_instruction": {"parts": [{"text": system_prompt}]},
            "contents": [{"parts": [{"text": user_prompt}]}],
            "generationConfig": {
                "temperature": temperature,
                "response_mime_type": "application/json",
            },
        }

        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.post(url, json=payload, headers=headers)

            if response.status_code == 429:
                raise AIExecutionRateLimitError("Gemini API rate limit exceeded.")
            if response.status_code >= 400:
                raise AIProviderUnavailableError(f"Gemini API returned error HTTP {response.status_code}: {response.text}")

            data = response.json()
            candidates = data.get("candidates", [])
            if not candidates:
                raise AIStructuredOutputValidationError("Gemini returned empty candidate response.")

            raw_text = candidates[0].get("content", {}).get("parts", [{}])[0].get("text", "")
            cleaned = clean_json_markdown(raw_text)
            parsed_json = json.loads(cleaned)
            return output_schema.model_validate(parsed_json)

        except (httpx.TimeoutException, TimeoutError) as e:
            raise AIExecutionTimeoutError(f"Gemini API request timed out after {self.timeout}s: {e}")
        except (json.JSONDecodeError, ValidationError) as e:
            raise AIStructuredOutputValidationError(f"Gemini structured output validation failed: {e}")
        except Exception as e:
            if isinstance(e, (AIExecutionRateLimitError, AIExecutionTimeoutError, AIStructuredOutputValidationError, AIProviderUnavailableError)):
                raise
            raise AIProviderUnavailableError(f"Gemini invocation failure: {e}")


class GroqProvider(BaseLLMProvider):
    """Groq Cloud LLM provider implementation using OpenAI-compatible HTTP REST API."""

    def __init__(self, api_key: Optional[str] = None, model: Optional[str] = None):
        self.api_key = api_key if api_key is not None else settings.GROQ_API_KEY
        self.model = model or settings.GROQ_MODEL
        self.timeout = settings.AI_TIMEOUT_SECONDS

    def is_configured(self) -> bool:
        return bool(self.api_key and self.api_key.strip())

    async def generate_structured(
        self,
        system_prompt: str,
        user_prompt: str,
        output_schema: Type[T],
        temperature: float = 0.2,
    ) -> T:
        if not self.is_configured():
            raise AIProviderUnavailableError("Groq API key is not configured.")

        url = "https://api.groq.com/openai/v1/chat/completions"
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system_prompt + "\nYou MUST return valid raw JSON."},
                {"role": "user", "content": user_prompt},
            ],
            "response_format": {"type": "json_object"},
            "temperature": temperature,
        }

        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.post(url, json=payload, headers=headers)

            if response.status_code == 429:
                raise AIExecutionRateLimitError("Groq API rate limit exceeded.")
            if response.status_code >= 400:
                raise AIProviderUnavailableError(f"Groq API returned error HTTP {response.status_code}: {response.text}")

            data = response.json()
            choices = data.get("choices", [])
            if not choices:
                raise AIStructuredOutputValidationError("Groq returned empty choices response.")

            raw_text = choices[0].get("message", {}).get("content", "")
            cleaned = clean_json_markdown(raw_text)
            parsed_json = json.loads(cleaned)
            return output_schema.model_validate(parsed_json)

        except (httpx.TimeoutException, TimeoutError) as e:
            raise AIExecutionTimeoutError(f"Groq API request timed out after {self.timeout}s: {e}")
        except (json.JSONDecodeError, ValidationError) as e:
            raise AIStructuredOutputValidationError(f"Groq structured output validation failed: {e}")
        except Exception as e:
            if isinstance(e, (AIExecutionRateLimitError, AIExecutionTimeoutError, AIStructuredOutputValidationError, AIProviderUnavailableError)):
                raise
            raise AIProviderUnavailableError(f"Groq invocation failure: {e}")


class LLMService:
    """
    Manages provider selection, bounded retries, and automatic fallback between
    Gemini and Groq.
    """

    def __init__(
        self,
        primary_name: Optional[str] = None,
        fallback_name: Optional[str] = None,
    ):
        self.primary_name = (primary_name or settings.AI_PRIMARY_PROVIDER).lower()
        self.fallback_name = (fallback_name or settings.AI_FALLBACK_PROVIDER).lower()
        self.providers: Dict[str, BaseLLMProvider] = {
            "gemini": GeminiProvider(),
            "groq": GroqProvider(),
        }

    def get_provider(self, name: str) -> BaseLLMProvider:
        prov = self.providers.get(name)
        if not prov:
            raise AIProviderUnavailableError(f"Unknown AI provider '{name}'.")
        return prov

    async def generate_with_fallback(
        self,
        system_prompt: str,
        user_prompt: str,
        output_schema: Type[T],
        temperature: float = 0.2,
    ) -> tuple[T, str, str]:
        """
        Executes structured generation using primary provider, retrying up to AI_MAX_RETRIES.
        Falls back to fallback provider if primary fails or is unconfigured.
        Returns: (parsed_output, provider_name, model_name)
        """
        primary_prov = self.get_provider(self.primary_name)
        primary_model = settings.GEMINI_MODEL if self.primary_name == "gemini" else settings.GROQ_MODEL
        fallback_prov = self.get_provider(self.fallback_name)
        fallback_model = settings.GROQ_MODEL if self.fallback_name == "groq" else settings.GEMINI_MODEL

        # Attempt Primary
        if primary_prov.is_configured():
            for attempt in range(settings.AI_MAX_RETRIES + 1):
                try:
                    res = await primary_prov.generate_structured(
                        system_prompt, user_prompt, output_schema, temperature
                    )
                    return res, self.primary_name, primary_model
                except (AIExecutionRateLimitError, AIExecutionTimeoutError, AIStructuredOutputValidationError) as e:
                    logger.warning(f"Primary provider {self.primary_name} attempt {attempt + 1} failed: {e}")
                    if attempt == settings.AI_MAX_RETRIES:
                        break
                except AIProviderUnavailableError as e:
                    logger.warning(f"Primary provider {self.primary_name} unavailable: {e}")
                    break

        # Attempt Fallback
        if fallback_prov.is_configured() and self.fallback_name != self.primary_name:
            logger.info(f"Flipping to fallback AI provider: {self.fallback_name}")
            for attempt in range(settings.AI_MAX_RETRIES + 1):
                try:
                    res = await fallback_prov.generate_structured(
                        system_prompt, user_prompt, output_schema, temperature
                    )
                    return res, self.fallback_name, fallback_model
                except Exception as e:
                    logger.warning(f"Fallback provider {self.fallback_name} attempt {attempt + 1} failed: {e}")
                    if attempt == settings.AI_MAX_RETRIES:
                        break

        raise AIProviderUnavailableError(
            f"Both primary ({self.primary_name}) and fallback ({self.fallback_name}) AI providers failed or are unconfigured."
        )


llm_service = LLMService()

