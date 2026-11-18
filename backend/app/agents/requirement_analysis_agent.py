"""Coordinates validation, requirement analysis, and the LLM provider."""

from typing import Optional

from app.core.exceptions import AppException
from app.core.logging import get_logger
from app.integrations.llm.base import LLMClient, LLMNotConfiguredError
from app.integrations.llm.provider import get_llm_client
from app.schemas.requirements import (
    RequirementAnalysisHealthResponse,
    RequirementAnalysisResponse,
    StoryInput,
)
from app.services.requirement_analysis_service import RequirementAnalysisService

logger = get_logger(__name__)

_PROVIDER_FAILURE_NOTE = (
    "Deterministic analysis was used because the language-model provider failed. "
    "No external model result was applied, and no requirements were invented."
)


class RequirementAnalysisAgent:
    """Validate a story, ask the configured provider to review it, and return grounded output."""

    def __init__(
        self,
        llm_client: Optional[LLMClient] = None,
        service: Optional[RequirementAnalysisService] = None,
    ) -> None:
        self._llm_client = llm_client
        self._service = service or RequirementAnalysisService()

    async def analyze(self, story: StoryInput) -> RequirementAnalysisResponse:
        validated = self._validate_input(story)
        logger.info(
            "Requirement analysis started title=%s project_id=%s",
            validated.title,
            validated.project_id or "(none)",
        )
        draft = self._service.build_draft(validated)
        messages = self._service.build_messages(validated, draft)
        client = self._resolve_client()

        try:
            llm_response = await client.complete(messages, temperature=0.0)
        except LLMNotConfiguredError as exc:
            logger.warning("LLM provider is not configured: %s", exc)
            return self._service.apply_provider(
                draft,
                provider="unavailable",
                provider_note=_PROVIDER_FAILURE_NOTE,
            )
        except ValueError as exc:
            logger.exception("Requirement analysis provider rejected the request")
            raise AppException(
                "Requirement analysis failed",
                status_code=500,
                code="requirement_analysis_error",
            ) from exc
        except (OSError, TimeoutError) as exc:
            logger.exception("LLM provider request failed: %s", exc)
            return self._service.apply_provider(
                draft,
                provider="unavailable",
                provider_note=_PROVIDER_FAILURE_NOTE,
            )

        analysis = self._service.validate_structured_output(
            llm_response.content,
            validated,
            draft,
            provider=llm_response.provider,
        )
        logger.info(
            "Requirement analysis finished story_id=%s provider=%s status=%s "
            "functional=%d non_functional=%d ambiguities=%d",
            analysis.story_id,
            analysis.provider,
            analysis.analysis_status.value,
            len(analysis.functional_requirements),
            len(analysis.non_functional_requirements),
            len(analysis.ambiguities),
        )
        return analysis

    async def health(self) -> RequirementAnalysisHealthResponse:
        client = self._resolve_client()
        provider_name = getattr(client, "provider_name", None) or "unconfigured"
        try:
            available = await client.is_available()
        except Exception:
            logger.exception("Requirement analysis health check failed")
            available = False

        mock = provider_name == "mock"
        if mock:
            note = (
                "Deterministic mock provider is active. "
                "No external language model is called."
            )
        elif available:
            note = f"Provider '{provider_name}' is available."
        else:
            note = (
                f"Provider '{provider_name}' is not available. "
                "Requirement analysis will use deterministic rules and will not invent requirements."
            )
        return RequirementAnalysisHealthResponse(
            status="ok",
            module="requirement_analysis",
            llm_provider=str(provider_name),
            llm_available=available,
            mock_implementation=mock,
            note=note,
        )

    def _resolve_client(self) -> LLMClient:
        return self._llm_client or get_llm_client()

    def _validate_input(self, story: StoryInput) -> StoryInput:
        title = story.title.strip()
        if not title:
            raise AppException(
                "Story title must not be empty",
                status_code=422,
                code="validation_error",
            )
        return story.model_copy(
            update={
                "title": title,
                "description": story.description.strip(),
                "acceptance_criteria": [
                    item.strip() for item in story.acceptance_criteria if item and item.strip()
                ],
                "story_id": story.story_id.strip() if story.story_id else None,
                "project_id": story.project_id.strip() if story.project_id else None,
            }
        )
