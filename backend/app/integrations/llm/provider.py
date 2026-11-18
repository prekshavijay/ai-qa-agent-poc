"""LLM client factory.

Resolves a concrete client from configuration without hardcoding a vendor.
`LLM_PROVIDER=mock` (or an empty value) uses the deterministic mock client.
Named providers other than mock stay unconfigured until an adapter is registered.
"""

from typing import Any, List, Optional

from app.core.config import settings
from app.core.logging import get_logger
from app.integrations.llm.base import (
    LLMClient,
    LLMMessage,
    LLMNotConfiguredError,
    LLMResponse,
)
from app.integrations.llm.mock import MOCK_PROVIDER_NAME, MockLLMClient

logger = get_logger(__name__)


class UnconfiguredLLMClient(LLMClient):
    """Placeholder client used before a real provider is wired."""

    provider_name = "unconfigured"

    async def complete(
        self,
        messages: List[LLMMessage],
        *,
        model: Optional[str] = None,
        temperature: float = 0.2,
        max_tokens: Optional[int] = None,
        **kwargs: Any,
    ) -> LLMResponse:
        raise LLMNotConfiguredError(
            "No LLM provider configured. Set LLM_PROVIDER (and related env vars) "
            "and register a concrete adapter in a later step."
        )

    async def is_available(self) -> bool:
        return False


def get_llm_client() -> LLMClient:
    """
    Return an LLM client based on environment configuration.

    The mock provider is deterministic and does not call an external model.
    Future adapters (OpenAI-compatible, Anthropic, Azure, local, etc.) should
    be registered here keyed by settings.llm_provider — without baking a
    specific vendor into agent or service code.
    """
    provider = (settings.llm_provider or "").strip().lower()

    if provider in ("", MOCK_PROVIDER_NAME):
        logger.debug("Using deterministic MockLLMClient")
        return MockLLMClient()

    logger.warning(
        "LLM provider '%s' is set but no adapter is registered yet; "
        "falling back to UnconfiguredLLMClient",
        provider,
    )
    return UnconfiguredLLMClient()
