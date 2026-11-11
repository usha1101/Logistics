import pytest
from unittest.mock import AsyncMock, patch
from pydantic import BaseModel, Field

from app.core.config import settings
from app.services.agents.exceptions import (
    AIExecutionRateLimitError,
    AIExecutionTimeoutError,
    AIProviderUnavailableError,
    AIStructuredOutputValidationError,
)
from app.services.agents.llm_provider import GeminiProvider, GroqProvider, LLMService, clean_json_markdown


class SampleOutput(BaseModel):
    decision: str
    confidence: float


def test_clean_json_markdown():
    wrapped = "```json\n{\"decision\": \"APPROVE\", \"confidence\": 0.95}\n```"
    cleaned = clean_json_markdown(wrapped)
    assert cleaned == '{"decision": "APPROVE", "confidence": 0.95}'

    raw = '{"decision": "REJECT", "confidence": 0.8}'
    assert clean_json_markdown(raw) == raw


def test_provider_configuration_detection():
    # Without keys
    gemini = GeminiProvider(api_key="")
    groq = GroqProvider(api_key="")
    assert not gemini.is_configured()
    assert not groq.is_configured()

    # With keys
    gemini_active = GeminiProvider(api_key="test-gemini-key")
    groq_active = GroqProvider(api_key="test-groq-key")
    assert gemini_active.is_configured()
    assert groq_active.is_configured()


@pytest.mark.anyio
async def test_gemini_provider_unconfigured_raises():
    gemini = GeminiProvider(api_key="")
    with pytest.raises(AIProviderUnavailableError):
        await gemini.generate_structured("sys", "user", SampleOutput)


@pytest.mark.anyio
async def test_groq_provider_unconfigured_raises():
    groq = GroqProvider(api_key="")
    with pytest.raises(AIProviderUnavailableError):
        await groq.generate_structured("sys", "user", SampleOutput)


@pytest.mark.anyio
async def test_llm_service_primary_success():
    service = LLMService(primary_name="gemini", fallback_name="groq")
    mock_gemini = AsyncMock(spec=GeminiProvider)
    mock_gemini.is_configured.return_value = True
    mock_gemini.generate_structured.return_value = SampleOutput(decision="SUCCESS", confidence=0.99)

    service.providers["gemini"] = mock_gemini

    result, prov, model = await service.generate_with_fallback("sys", "user", SampleOutput)
    assert result.decision == "SUCCESS"
    assert prov == "gemini"


@pytest.mark.anyio
async def test_llm_service_fallback_to_groq_when_gemini_fails():
    service = LLMService(primary_name="gemini", fallback_name="groq")

    mock_gemini = AsyncMock(spec=GeminiProvider)
    mock_gemini.is_configured.return_value = True
    mock_gemini.generate_structured.side_effect = AIExecutionTimeoutError("Gemini timed out")

    mock_groq = AsyncMock(spec=GroqProvider)
    mock_groq.is_configured.return_value = True
    mock_groq.generate_structured.return_value = SampleOutput(decision="GROQ_FALLBACK", confidence=0.88)

    service.providers["gemini"] = mock_gemini
    service.providers["groq"] = mock_groq

    result, prov, model = await service.generate_with_fallback("sys", "user", SampleOutput)
    assert result.decision == "GROQ_FALLBACK"
    assert prov == "groq"


@pytest.mark.anyio
async def test_llm_service_both_providers_fail_raises():
    service = LLMService(primary_name="gemini", fallback_name="groq")

    mock_gemini = AsyncMock(spec=GeminiProvider)
    mock_gemini.is_configured.return_value = True
    mock_gemini.generate_structured.side_effect = AIProviderUnavailableError("Gemini down")

    mock_groq = AsyncMock(spec=GroqProvider)
    mock_groq.is_configured.return_value = True
    mock_groq.generate_structured.side_effect = AIProviderUnavailableError("Groq down")

    service.providers["gemini"] = mock_gemini
    service.providers["groq"] = mock_groq

    with pytest.raises(AIProviderUnavailableError):
        await service.generate_with_fallback("sys", "user", SampleOutput)

