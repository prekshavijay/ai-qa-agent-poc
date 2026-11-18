"""Coordinates validation, test case generation, and the LLM provider."""

from typing import Optional

from app.core.exceptions import AppException
from app.core.logging import get_logger
from app.integrations.llm.base import LLMClient, LLMNotConfiguredError
from app.integrations.llm.provider import get_llm_client
from app.schemas.requirements import RequirementAnalysisResponse
from app.schemas.test_cases import (
    TestCaseGenerationHealthResponse,
    TestCaseGenerationRequest,
    TestCaseGenerationResponse,
)
from app.services.test_case_generation_service import TestCaseGenerationService

logger = get_logger(__name__)

_PROVIDER_FAILURE_NOTE = (
    "Deterministic generation was used because the language-model provider failed. "
    "No external model result was applied, and no test behaviour was invented."
)


class TestCaseGenerationAgent:
    """Validate analysis input, generate draft cases, and return grounded output."""

    __test__ = False

    def __init__(
        self,
        llm_client: Optional[LLMClient] = None,
        service: Optional[TestCaseGenerationService] = None,
    ) -> None:
        self._llm_client = llm_client
        self._service = service or TestCaseGenerationService()

    async def generate(
        self, analysis: RequirementAnalysisResponse
    ) -> TestCaseGenerationResponse:
        validated = self._validate_input(analysis)
        logger.info(
            "Test case generation started story_id=%s functional=%d non_functional=%d",
            validated.story_id,
            len(validated.functional_requirements),
            len(validated.non_functional_requirements),
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
            logger.exception("Test case generation provider rejected the request")
            raise AppException(
                "Test case generation failed",
                status_code=500,
                code="test_case_generation_error",
            ) from exc
        except (OSError, TimeoutError) as exc:
            logger.exception("LLM provider request failed: %s", exc)
            return self._service.apply_provider(
                draft,
                provider="unavailable",
                provider_note=_PROVIDER_FAILURE_NOTE,
            )

        generation = self._service.validate_structured_output(
            llm_response.content,
            validated,
            draft,
            provider=llm_response.provider,
        )
        self._assert_traceability(validated, generation)
        logger.info(
            "Test case generation finished story_id=%s provider=%s status=%s "
            "cases=%d skipped=%d",
            generation.story_id,
            generation.provider,
            generation.generation_status.value,
            len(generation.test_cases),
            len(generation.skipped_requirements),
        )
        return generation

    async def health(self) -> TestCaseGenerationHealthResponse:
        client = self._resolve_client()
        provider_name = getattr(client, "provider_name", None) or "unconfigured"
        try:
            available = await client.is_available()
        except Exception:
            logger.exception("Test case generation health check failed")
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
                "Test case generation will use deterministic rules and will not invent behaviour."
            )
        return TestCaseGenerationHealthResponse(
            status="ok",
            module="test_case_generation",
            llm_provider=str(provider_name),
            llm_available=available,
            mock_implementation=mock,
            note=note,
        )

    def _resolve_client(self) -> LLMClient:
        return self._llm_client or get_llm_client()

    def _validate_input(
        self, analysis: RequirementAnalysisResponse
    ) -> RequirementAnalysisResponse:
        try:
            validated = TestCaseGenerationRequest.model_validate(
                analysis.model_dump(mode="json")
            )
        except Exception as exc:
            raise AppException(
                "Invalid requirement analysis payload",
                status_code=422,
                code="validation_error",
                details={"reason": str(exc)},
            ) from exc

        story_id = validated.story_id.strip()
        if not story_id:
            raise AppException(
                "story_id must not be empty",
                status_code=422,
                code="validation_error",
            )

        for requirement in (
            list(validated.functional_requirements)
            + list(validated.non_functional_requirements)
        ):
            if not requirement.requirement_id.strip():
                raise AppException(
                    "Each requirement must include a requirement_id",
                    status_code=422,
                    code="validation_error",
                )

        return validated.model_copy(update={"story_id": story_id})

    def _assert_traceability(
        self,
        analysis: RequirementAnalysisResponse,
        generation: TestCaseGenerationResponse,
    ) -> None:
        valid_requirement_ids = {
            item.requirement_id for item in analysis.functional_requirements
        } | {item.requirement_id for item in analysis.non_functional_requirements}
        valid_criterion_ids = {
            item.criterion_id for item in analysis.acceptance_criteria
        }

        for case in generation.test_cases:
            if case.requirement_id not in valid_requirement_ids:
                raise AppException(
                    "Generated test case is missing requirement traceability",
                    status_code=500,
                    code="traceability_error",
                    details={
                        "test_case_id": case.test_case_id,
                        "requirement_id": case.requirement_id,
                    },
                )
            if (
                case.acceptance_criterion_id
                and case.acceptance_criterion_id not in valid_criterion_ids
            ):
                raise AppException(
                    "Generated test case references an unknown acceptance criterion",
                    status_code=500,
                    code="traceability_error",
                    details={
                        "test_case_id": case.test_case_id,
                        "acceptance_criterion_id": case.acceptance_criterion_id,
                    },
                )
