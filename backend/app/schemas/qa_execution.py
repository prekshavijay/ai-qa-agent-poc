"""Schemas for QA execution runs and manual result recording."""

from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, Field, field_validator


class RunStatus(str, Enum):
    QUEUED = "queued"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


class ExecutionResultStatus(str, Enum):
    PASSED = "passed"
    FAILED = "failed"
    BLOCKED = "blocked"
    NOT_RUN = "not_run"


class TriggerSource(str, Enum):
    MANUAL = "manual"


class CreateExecutionRunRequest(BaseModel):
    """Create a run from explicitly selected approved test cases."""

    story_id: str = Field(..., min_length=1, max_length=100)
    test_case_ids: List[str] = Field(..., min_length=1)
    trigger_source: TriggerSource = TriggerSource.MANUAL

    @field_validator("story_id")
    @classmethod
    def strip_story_id(cls, value: str) -> str:
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("story_id must not be empty")
        return cleaned

    @field_validator("test_case_ids")
    @classmethod
    def strip_test_case_ids(cls, value: List[str]) -> List[str]:
        cleaned: List[str] = []
        for item in value:
            test_case_id = item.strip()
            if not test_case_id:
                raise ValueError("test_case_id must not be empty")
            cleaned.append(test_case_id)
        return cleaned


class RecordExecutionResultRequest(BaseModel):
    """Record or update the result for one test case already in a run."""

    test_case_id: str = Field(..., min_length=1, max_length=64)
    status: ExecutionResultStatus
    actual_result: Optional[str] = None
    error_details: Optional[str] = None
    evidence: Optional[Dict[str, Any]] = None
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None

    @field_validator("test_case_id")
    @classmethod
    def strip_test_case_id(cls, value: str) -> str:
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("test_case_id must not be empty")
        return cleaned

    @field_validator("actual_result", "error_details")
    @classmethod
    def blank_text_to_none(cls, value: Optional[str]) -> Optional[str]:
        if value is None:
            return None
        cleaned = value.strip()
        return cleaned or None

    @field_validator("evidence")
    @classmethod
    def evidence_must_be_object(
        cls, value: Optional[Dict[str, Any]]
    ) -> Optional[Dict[str, Any]]:
        if value is None:
            return None
        if not isinstance(value, dict):
            raise ValueError("evidence must be a JSON object")
        return value


class ExecutionResultResponse(BaseModel):
    id: int
    run_id: str
    test_case_id: str
    title: str
    expected_result: str
    approved_version_id: int
    approved_version_number: int
    status: ExecutionResultStatus
    actual_result: Optional[str] = None
    error_details: Optional[str] = None
    evidence: Dict[str, Any]
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    duration_seconds: Optional[float] = None
    created_at: datetime
    updated_at: datetime


class ExecutionRunResponse(BaseModel):
    run_id: str
    story_id: str
    status: RunStatus
    trigger_source: TriggerSource
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    total_test_cases: int
    passed_count: int
    failed_count: int
    blocked_count: int
    not_run_count: int
    created_at: datetime
    updated_at: datetime


class ExecutionRunDetailResponse(ExecutionRunResponse):
    results: List[ExecutionResultResponse]


class ExecutionRunListResponse(BaseModel):
    total: int
    runs: List[ExecutionRunResponse]


class QaExecutionHealthResponse(BaseModel):
    status: Literal["ok"] = "ok"
    module: Literal["qa_execution"] = "qa_execution"
    note: str
