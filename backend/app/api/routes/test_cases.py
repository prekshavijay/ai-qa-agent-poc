"""Test case generation endpoints."""

from fastapi import APIRouter

from app.agents.test_case_generation_agent import TestCaseGenerationAgent
from app.schemas.requirements import RequirementAnalysisResponse
from app.schemas.test_cases import (
    TestCaseGenerationHealthResponse,
    TestCaseGenerationResponse,
)

router = APIRouter(tags=["test-cases"])


def _agent() -> TestCaseGenerationAgent:
    return TestCaseGenerationAgent()


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
        "traceable test cases. The mock provider does not call an external model."
    ),
)
async def generate_test_cases(
    analysis: RequirementAnalysisResponse,
) -> TestCaseGenerationResponse:
    return await _agent().generate(analysis)
