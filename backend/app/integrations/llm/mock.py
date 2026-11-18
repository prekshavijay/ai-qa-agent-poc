"""Deterministic mock LLM provider.

This client does not call an external language model. It returns the
structured draft embedded in the user message and labels the result as mock.
Supports requirement analysis (`draft_analysis`) and test case generation
(`draft_test_cases`) payloads.
"""

import json
from typing import Any, List, Optional

from app.core.logging import get_logger
from app.integrations.llm.base import LLMClient, LLMMessage, LLMResponse

logger = get_logger(__name__)

MOCK_PROVIDER_NAME = "mock"
MOCK_MODEL_NAME = "mock-deterministic-v1"
MOCK_NOTE = "Deterministic mock provider. No external language model was called."


class MockLLMClient(LLMClient):
    """Predictable stand-in for a real LLMClient implementation."""

    provider_name = MOCK_PROVIDER_NAME

    async def complete(
        self,
        messages: List[LLMMessage],
        *,
        model: Optional[str] = None,
        temperature: float = 0.2,
        max_tokens: Optional[int] = None,
        **kwargs: Any,
    ) -> LLMResponse:
        del model, temperature, max_tokens, kwargs
        user_content = ""
        for message in reversed(messages):
            if message.role == "user":
                user_content = message.content
                break

        try:
            payload = json.loads(user_content)
        except (json.JSONDecodeError, TypeError) as exc:
            raise ValueError(
                "MockLLMClient expected a JSON user message. "
                "No external language model was called."
            ) from exc

        if not isinstance(payload, dict):
            raise ValueError(
                "MockLLMClient expected a JSON object user message. "
                "No external language model was called."
            )

        if "draft_test_cases" in payload:
            draft = payload["draft_test_cases"]
            body = {
                "provider": MOCK_PROVIDER_NAME,
                "mock": True,
                "note": MOCK_NOTE,
                "generation": draft,
            }
            logger.info(
                "MockLLMClient returned deterministic test cases (model=%s). "
                "No external language model was called.",
                MOCK_MODEL_NAME,
            )
        elif "draft_analysis" in payload:
            draft = payload["draft_analysis"]
            body = {
                "provider": MOCK_PROVIDER_NAME,
                "mock": True,
                "note": MOCK_NOTE,
                "analysis": draft,
            }
            logger.info(
                "MockLLMClient returned a deterministic analysis (model=%s). "
                "No external language model was called.",
                MOCK_MODEL_NAME,
            )
        else:
            raise ValueError(
                "MockLLMClient expected draft_analysis or draft_test_cases in the "
                "user message. No external language model was called."
            )

        return LLMResponse(
            content=json.dumps(body),
            model=MOCK_MODEL_NAME,
            provider=MOCK_PROVIDER_NAME,
            raw={"mock": True, "external_call": False},
        )

    async def is_available(self) -> bool:
        return True
