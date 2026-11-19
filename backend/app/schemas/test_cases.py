"""Schemas for test case generation from requirement analysis."""

from enum import Enum
from typing import List, Literal, Optional

from pydantic import BaseModel, Field

from app.schemas.requirements import RequirementAnalysisResponse


class TestType(str, Enum):
    __test__ = False

    POSITIVE = "positive"
    NEGATIVE = "negative"
    BOUNDARY = "boundary"
    EDGE = "edge"
    INTEGRATION = "integration"


class TestPriority(str, Enum):
    __test__ = False

    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class AutomationSuitability(str, Enum):
    SUITABLE = "suitable"
    PARTIALLY_SUITABLE = "partially_suitable"
    MANUAL_ONLY = "manual_only"


class GenerationStatus(str, Enum):
    COMPLETE = "complete"
    PARTIAL = "partial"
    NEEDS_CLARIFICATION = "needs_clarification"
    NO_TEST_CASES = "no_test_cases"


class TestCaseStep(BaseModel):
    __test__ = False

    step_number: int = Field(..., ge=1)
    action: str = Field(..., min_length=1)
    expected_result: str = Field(..., min_length=1)


class TestCase(BaseModel):
    __test__ = False

    test_case_id: str
    title: str
    objective: str
    requirement_id: str
    acceptance_criterion_id: Optional[str] = None
    test_type: TestType
    priority: TestPriority
    preconditions: List[str] = Field(default_factory=list)
    test_data: List[str] = Field(default_factory=list)
    steps: List[TestCaseStep] = Field(default_factory=list)
    expected_result: str
    automation_suitability: AutomationSuitability
    assumptions: List[str] = Field(default_factory=list)
    needs_clarification: bool = False



class SkippedRequirement(BaseModel):
    """Requirement that could not support a meaningful test case."""

    requirement_id: str
    description: str
    reason: str


class TestCaseGenerationRequest(RequirementAnalysisResponse):
    """Request body: structured output from the Requirement Analysis Agent."""

    __test__ = False


class PersistenceStatus(str, Enum):
    """Outcome of persisting generated cases for QA review."""

    SAVED = "saved"
    NOT_REQUIRED = "not_required"
    FAILED = "failed"


class PersistenceError(BaseModel):
    """Structured persistence failure details (no internal stack traces)."""

    code: str
    message: str


class PersistenceResult(BaseModel):
    """Whether generated cases were stored for QA review."""

    status: PersistenceStatus = PersistenceStatus.NOT_REQUIRED
    saved_count: int = 0
    skipped_duplicates: int = 0
    warning: Optional[str] = None
    error: Optional[PersistenceError] = None


class TestCaseGenerationResponse(BaseModel):
    """Structured test cases with requirement and acceptance-criterion traceability."""

    __test__ = False

    story_id: str
    story_summary: str
    test_cases: List[TestCase]
    skipped_requirements: List[SkippedRequirement] = Field(default_factory=list)
    generation_status: GenerationStatus
    provider: str = Field(description="Provider that participated in generation.")
    provider_note: str = Field(
        description="States whether a real language model was called."
    )
    summary: str = Field(
        description="Short overview of what was generated and what was skipped."
    )
    persistence: PersistenceResult = Field(
        default_factory=PersistenceResult,
        description=(
            "Whether generated cases were persisted for QA review. "
            "status=failed means cases were generated but not saved."
        ),
    )


class TestCaseGenerationHealthResponse(BaseModel):
    __test__ = False

    status: Literal["ok"] = "ok"
    module: Literal["test_case_generation"] = "test_case_generation"
    llm_provider: str
    llm_available: bool
    mock_implementation: bool
    note: str
