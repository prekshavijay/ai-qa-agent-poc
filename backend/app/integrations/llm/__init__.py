"""Provider-agnostic LLM integration layer.

`get_llm_client()` returns the deterministic mock when LLM_PROVIDER is empty
or `mock`. Register a real adapter later without changing agent code.
"""

from app.integrations.llm.base import (
    LLMClient,
    LLMMessage,
    LLMNotConfiguredError,
    LLMResponse,
)
from app.integrations.llm.mock import MockLLMClient
from app.integrations.llm.provider import get_llm_client

__all__ = [
    "LLMClient",
    "LLMMessage",
    "LLMNotConfiguredError",
    "LLMResponse",
    "MockLLMClient",
    "get_llm_client",
]
