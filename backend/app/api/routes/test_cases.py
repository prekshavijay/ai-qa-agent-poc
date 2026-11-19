"""Test case generation endpoints."""

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.agents.test_case_generation_agent import TestCaseGenerationAgent
from app.core.exceptions import AppException
from app.core.logging import get_logger
from app.database.session import get_db
from app.schemas.requirements import RequirementAnalysisResponse
from app.schemas.test_cases import (
    PersistenceError,
    PersistenceResult,
    PersistenceStatus,
    TestCaseGenerationHealthResponse,
    TestCaseGenerationResponse,
)
from app.services.test_case_management_service import TestCaseManagementService

router = APIRouter(tags=["test-cases"])
logger = get_logger(__name__)


def _agent() -> TestCaseGenerationAgent:
    return TestCaseGenerationAgent()


def _management_service() -> TestCaseManagementService:
    return TestCaseManagementService()


def _with_persistence(
    generation: TestCaseGenerationResponse,
    persistence: PersistenceResult,
) -> TestCaseGenerationResponse:
    return generation.model_copy(update={"persistence": persistence})


@router.get(
    "/health",
    response_model=TestCaseGenerationHealthResponse,
    summary="Test case generation health",
    description=(
        "Reports whether test case generation is available and whether the "
        "deterministic mock provider is active."
    ),
)
async def test_case_generation_health() -> TestCaseGenerationHealthResponse:
    return await _agent().health()


@router.post(
    "/generate",
    response_model=TestCaseGenerationResponse,
    summary="Generate test cases from requirement analysis",
    description=(
        "Accepts a RequirementAnalysisResponse and returns structured, "
        "traceable test cases. Generated cases are also saved for QA review "
        "with pending_review status when persistence succeeds. The response "
        "persistence field reports whether cases were saved. The mock provider "
        "does not call an external model."
    ),
)
async def generate_test_cases(
    analysis: RequirementAnalysisResponse,
    db: Session = Depends(get_db),
) -> TestCaseGenerationResponse:
    generation = await _agent().generate(analysis)
    if not generation.test_cases:
        return _with_persistence(
            generation,
            PersistenceResult(
                status=PersistenceStatus.NOT_REQUIRED,
                warning="No test cases were generated, so nothing was saved for review.",
            ),
        )

    try:
        save_result = _management_service().save_from_generation(
            db, generation, analysis
        )
        logger.info(
            "Persisted generated cases for review story_id=%s saved=%d skipped=%d",
            generation.story_id,
            save_result.saved_count,
            save_result.skipped_duplicates,
        )
        warning = None
        if save_result.saved_count == 0 and save_result.skipped_duplicates > 0:
            warning = (
                "No new records were created; matching cases for this story "
                "were already saved and duplicates were skipped."
            )
        return _with_persistence(
            generation,
            PersistenceResult(
                status=PersistenceStatus.SAVED,
                saved_count=save_result.saved_count,
                skipped_duplicates=save_result.skipped_duplicates,
                warning=warning,
            ),
        )
    except AppException as exc:
        logger.exception(
            "Failed to persist generated test cases for story_id=%s code=%s",
            generation.story_id,
            exc.code,
        )
        db.rollback()
        return _with_persistence(
            generation,
            PersistenceResult(
                status=PersistenceStatus.FAILED,
                warning=(
                    "Test cases were generated but not saved for QA review. "
                    "Use the save endpoint to retry persistence."
                ),
                error=PersistenceError(code=exc.code, message=exc.message),
            ),
        )
    except Exception as exc:
        logger.exception(
            "Failed to persist generated test cases for story_id=%s",
            generation.story_id,
        )
        db.rollback()
        return _with_persistence(
            generation,
            PersistenceResult(
                status=PersistenceStatus.FAILED,
                warning=(
                    "Test cases were generated but not saved for QA review. "
                    "Use the save endpoint to retry persistence."
                ),
                error=PersistenceError(
                    code="persistence_error",
                    message=str(exc) or "Unexpected persistence failure",
                ),
            ),
        )
