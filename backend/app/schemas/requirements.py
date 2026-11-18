"""Schemas for user-story requirement analysis."""

from enum import Enum
from typing import List, Literal, Optional

from pydantic import BaseModel, Field, field_validator


class Priority(str, Enum):
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class TestabilityStatus(str, Enum):
    TESTABLE = "testable"
    PARTIALLY_TESTABLE = "partially_testable"
    NOT_TESTABLE = "not_testable"


class AnalysisStatus(str, Enum):
    COMPLETE = "complete"
    NEEDS_CLARIFICATION = "needs_clarification"
    INSUFFICIENT_INPUT = "insufficient_input"


class StoryInput(BaseModel):
    """User story submitted for requirement analysis."""

    title: str = Field(..., min_length=1, max_length=300)
    description: str = Field(default="", max_length=20000)
    acceptance_criteria: List[str] = Field(default_factory=list, max_length=50)
    story_id: Optional[str] = Field(default=None, max_length=100)
    project_id: Optional[str] = Field(default=None, max_length=100)

    @field_validator("title")
    @classmethod
    def title_must_not_be_blank(cls, value: str) -> str:
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("title must not be empty")
        return cleaned

    @field_validator("description")
    @classmethod
    def strip_description(cls, value: str) -> str:
        return value.strip()

    @field_validator("story_id", "project_id")
    @classmethod
    def blank_identifier_to_none(cls, value: Optional[str]) -> Optional[str]:
        if value is None:
            return None
        cleaned = value.strip()
        return cleaned or None

    @field_validator("acceptance_criteria")
    @classmethod
    def strip_acceptance_criteria(cls, value: List[str]) -> List[str]:
        return [item.strip() for item in value if item and item.strip()]


class FunctionalRequirement(BaseModel):
    requirement_id: str
    description: str
    priority: Priority
    source_acceptance_criterion: Optional[str] = None
    testability_status: TestabilityStatus


class NonFunctionalRequirement(FunctionalRequirement):
    category: str


class AcceptanceCriterion(BaseModel):
    criterion_id: str
    description: str
    testability_status: TestabilityStatus


class Ambiguity(BaseModel):
    ambiguity_id: str
    statement: str
    reason: str
    source: Literal["title", "description", "acceptance_criteria"]


class RequirementAnalysisResponse(BaseModel):
    """Structured requirement analysis. Requirements are traceable to the story."""

    story_id: str
    story_summary: str
    functional_requirements: List[FunctionalRequirement]
    non_functional_requirements: List[NonFunctionalRequirement]
    acceptance_criteria: List[AcceptanceCriterion]
    ambiguities: List[Ambiguity]
    clarification_questions: List[str]
    analysis_status: AnalysisStatus
    provider: str = Field(description="Provider that participated in the analysis.")
    provider_note: str = Field(
        description="States whether a real language model was called."
    )


class RequirementAnalysisHealthResponse(BaseModel):
    status: Literal["ok"] = "ok"
    module: Literal["requirement_analysis"] = "requirement_analysis"
    llm_provider: str
    llm_available: bool
    mock_implementation: bool
    note: str
