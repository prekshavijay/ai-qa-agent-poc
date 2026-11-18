"""Abstract LLM client contract — model- and provider-independent."""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


class LLMNotConfiguredError(RuntimeError):
    """Raised when an LLM provider has not been configured yet."""


@dataclass
class LLMMessage:
    role: str
    content: str


@dataclass
class LLMResponse:
    content: str
    model: str = ""
    provider: str = ""
    raw: Dict[str, Any] = field(default_factory=dict)


class LLMClient(ABC):
    """Interface that all LLM provider adapters must implement."""

    @abstractmethod
    async def complete(
        self,
        messages: List[LLMMessage],
        *,
        model: Optional[str] = None,
        temperature: float = 0.2,
        max_tokens: Optional[int] = None,
        **kwargs: Any,
    ) -> LLMResponse:
        """Generate a completion from a list of chat messages."""

    @abstractmethod
    async def is_available(self) -> bool:
        """Return True if the provider is reachable and credentials are valid."""
