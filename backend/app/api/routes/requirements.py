"""Requirement analysis endpoints."""

from fastapi import APIRouter

from app.agents.requirement_analysis_agent import RequirementAnalysisAgent
from app.schemas.requirements import (
    RequirementAnalysisHealthResponse,
    RequirementAnalysisResponse,
    StoryInput,
)

router = APIRouter(tags=["requirements"])


def _agent() -> RequirementAnalysisAgent:
    return RequirementAnalysisAgent()


@router.get(
    "/health",
    response_model=RequirementAnalysisHealthResponse,
    summary="Requirement analysis health",
    description=(
        "Reports whether requirement analysis is available and whether the "
        "deterministic mock provider is active."
    ),
)
async def requirement_analysis_health() -> RequirementAnalysisHealthResponse:
    return await _agent().health()


@router.post(
    "/analyze",
    response_model=RequirementAnalysisResponse,
    summary="Analyze a user story",
    description=(
        "Converts a user story into structured requirements, ambiguities, "
        "and clarification questions. The mock provider does not call an external model."
    ),
)
async def analyze_requirements(story: StoryInput) -> RequirementAnalysisResponse:
    return await _agent().analyze(story)
