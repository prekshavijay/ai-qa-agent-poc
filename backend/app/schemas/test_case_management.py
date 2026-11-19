"""Schemas for QA review, approval, and test case management."""

from datetime import datetime
from enum import Enum
from typing import List, Literal, Optional

from pydantic import BaseModel, Field, field_validator

from app.schemas.requirements import RequirementAnalysisResponse
from app.schemas.test_cases import (
    AutomationSuitability,
    TestCase,
    TestCaseGenerationResponse,
    TestCaseStep,
    TestPriority,
    TestType,
)


class ReviewStatus(str, Enum):
    PENDING_REVIEW = "pending_review"
    APPROVED = "approved"
    REJECTED = "rejected"
    NEEDS_CLARIFICATION = "needs_clarification"


class ReviewAction(str, Enum):
    APPROVE = "approve"
    REJECT = "reject"
    REQUEST_CLARIFICATION = "request_clarification"
    EDIT = "edit"
    SAVE = "save"


class TestCaseVersionContent(BaseModel):
    """Editable / stored content for a single version."""

    __test__ = False

    title: str = Field(..., min_length=1, max_length=500)
    objective: str = Field(..., min_length=1)
    test_type: TestType
    priority: TestPriority
    preconditions: List[str] = Field(default_factory=list)
    test_data: List[str] = Field(default_factory=list)
    steps: List[TestCaseStep] = Field(default_factory=list)
    expected_result: str = Field(..., min_length=1)
    automation_suitability: AutomationSuitability
    assumptions: List[str] = Field(default_factory=list)
    needs_clarification: bool = False

    @field_validator("title", "objective", "expected_result")
    @classmethod
    def strip_required_text(cls, value: str) -> str:
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("must not be empty")
        return cleaned


class TestCaseEditRequest(TestCaseVersionContent):
    """Body for updating a managed test case."""

    __test__ = False

    requirement_id: Optional[str] = None
    acceptance_criterion_id: Optional[str] = None
    reviewer_id: Optional[str] = Field(default=None, max_length=100)
    comments: Optional[str] = None


class ReviewerActionRequest(BaseModel):
    """Shared body for approve / reject / clarify actions."""

    reviewer_id: Optional[str] = Field(default=None, max_length=100)
    comments: Optional[str] = None

    @field_validator("reviewer_id")
    @classmethod
    def blank_reviewer_to_none(cls, value: Optional[str]) -> Optional[str]:
        if value is None:
            return None
        cleaned = value.strip()
        return cleaned or None


class RejectTestCaseRequest(ReviewerActionRequest):
    comments: str = Field(..., min_length=1)

    @field_validator("comments")
    @classmethod
    def comments_required(cls, value: str) -> str:
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("A rejection reason is required")
        return cleaned


class ClarifyTestCaseRequest(ReviewerActionRequest):
    comments: str = Field(..., min_length=1)

    @field_validator("comments")
    @classmethod
    def comments_required(cls, value: str) -> str:
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("Clarification comments are required")
        return cleaned


class SaveGeneratedTestCasesRequest(BaseModel):
    """Persist generated test cases for QA review."""

    __test__ = False

    generation: TestCaseGenerationResponse
    analysis: Optional[RequirementAnalysisResponse] = None
    valid_requirement_ids: List[str] = Field(default_factory=list)
    valid_acceptance_criterion_ids: List[str] = Field(default_factory=list)


class ManagedTestCaseVersionResponse(BaseModel):
    __test__ = False

    version_number: int
    title: str
    objective: str
    test_type: TestType
    priority: TestPriority
    preconditions: List[str]
    test_data: List[str]
    steps: List[TestCaseStep]
    expected_result: str
    automation_suitability: AutomationSuitability
    assumptions: List[str]
    needs_clarification: bool
    is_original: bool
    is_approved_snapshot: bool
    created_at: datetime


class ManagedTestCaseReviewResponse(BaseModel):
    __test__ = False

    review_action: ReviewAction
    version_number: int
    reviewer_id: Optional[str] = None
    comments: Optional[str] = None
    created_at: datetime


class ManagedTestCaseResponse(BaseModel):
    """Public representation of a managed test case (no internal DB ids)."""

    __test__ = False

    test_case_id: str
    story_id: str
    requirement_id: str
    acceptance_criterion_id: Optional[str] = None
    current_version: int
    review_status: ReviewStatus
    title: str
    objective: str
    test_type: TestType
    priority: TestPriority
    preconditions: List[str]
    test_data: List[str]
    steps: List[TestCaseStep]
    expected_result: str
    automation_suitability: AutomationSuitability
    assumptions: List[str]
    needs_clarification: bool
    created_at: datetime
    updated_at: datetime
    original_version: Optional[ManagedTestCaseVersionResponse] = None


class StoryTestCaseSummary(BaseModel):
    __test__ = False

    story_id: str
    total: int
    pending_review: int
    approved: int
    rejected: int
    needs_clarification: int
    test_cases: List[ManagedTestCaseResponse]


class SaveGeneratedTestCasesResponse(BaseModel):
    __test__ = False

    story_id: str
    saved_count: int
    skipped_duplicates: int
    test_cases: List[ManagedTestCaseResponse]


class TestCaseManagementHealthResponse(BaseModel):
    __test__ = False

    status: Literal["ok"] = "ok"
    module: Literal["test_case_management"] = "test_case_management"
    note: str
