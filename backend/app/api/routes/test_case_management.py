"""QA review and test case management endpoints."""

from typing import List, Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.database.session import get_db
from app.schemas.test_case_management import (
    ClarifyTestCaseRequest,
    ManagedTestCaseResponse,
    ManagedTestCaseReviewResponse,
    ManagedTestCaseVersionResponse,
    RejectTestCaseRequest,
    ReviewerActionRequest,
    SaveGeneratedTestCasesRequest,
    SaveGeneratedTestCasesResponse,
    StoryTestCaseSummary,
    TestCaseEditRequest,
    TestCaseManagementHealthResponse,
)
from app.services.test_case_management_service import TestCaseManagementService

router = APIRouter(tags=["test-case-management"])


def _service() -> TestCaseManagementService:
    return TestCaseManagementService()


@router.get(
    "/health",
    response_model=TestCaseManagementHealthResponse,
    summary="Test case management health",
)
async def test_case_management_health() -> TestCaseManagementHealthResponse:
    return TestCaseManagementHealthResponse(
        status="ok",
        module="test_case_management",
        note="QA review, approval, and version history endpoints are available.",
    )


@router.post(
    "/save",
    response_model=SaveGeneratedTestCasesResponse,
    summary="Save generated test cases for review",
    description=(
        "Persists AI-generated test cases with pending_review status. "
        "Duplicate generation requests for the same story and test_case_id are skipped."
    ),
)
async def save_generated_test_cases(
    request: SaveGeneratedTestCasesRequest,
    db: Session = Depends(get_db),
) -> SaveGeneratedTestCasesResponse:
    return _service().save_generated_test_cases(db, request)


@router.get(
    "/stories/{story_id}/approved",
    response_model=List[ManagedTestCaseResponse],
    summary="List approved test cases for a story",
)
async def list_approved_test_cases(
    story_id: str,
    db: Session = Depends(get_db),
) -> List[ManagedTestCaseResponse]:
    return _service().get_approved_by_story(db, story_id)


@router.get(
    "/stories/{story_id}",
    response_model=StoryTestCaseSummary,
    summary="List managed test cases for a story",
)
async def list_story_test_cases(
    story_id: str,
    db: Session = Depends(get_db),
) -> StoryTestCaseSummary:
    return _service().get_by_story(db, story_id)


@router.get(
    "/{test_case_id}/versions",
    response_model=List[ManagedTestCaseVersionResponse],
    summary="Version history for a test case",
)
async def get_test_case_versions(
    test_case_id: str,
    story_id: Optional[str] = Query(default=None),
    db: Session = Depends(get_db),
) -> List[ManagedTestCaseVersionResponse]:
    return _service().get_versions(db, test_case_id, story_id=story_id)


@router.get(
    "/{test_case_id}/reviews",
    response_model=List[ManagedTestCaseReviewResponse],
    summary="Review history for a test case",
)
async def get_test_case_reviews(
    test_case_id: str,
    story_id: Optional[str] = Query(default=None),
    db: Session = Depends(get_db),
) -> List[ManagedTestCaseReviewResponse]:
    return _service().get_reviews(db, test_case_id, story_id=story_id)


@router.post(
    "/{test_case_id}/approve",
    response_model=ManagedTestCaseResponse,
    summary="Approve a test case",
)
async def approve_test_case(
    test_case_id: str,
    payload: ReviewerActionRequest,
    story_id: Optional[str] = Query(default=None),
    db: Session = Depends(get_db),
) -> ManagedTestCaseResponse:
    return _service().approve(db, test_case_id, payload, story_id=story_id)


@router.post(
    "/{test_case_id}/reject",
    response_model=ManagedTestCaseResponse,
    summary="Reject a test case",
)
async def reject_test_case(
    test_case_id: str,
    payload: RejectTestCaseRequest,
    story_id: Optional[str] = Query(default=None),
    db: Session = Depends(get_db),
) -> ManagedTestCaseResponse:
    return _service().reject(db, test_case_id, payload, story_id=story_id)


@router.post(
    "/{test_case_id}/clarify",
    response_model=ManagedTestCaseResponse,
    summary="Request clarification on a test case",
)
async def clarify_test_case(
    test_case_id: str,
    payload: ClarifyTestCaseRequest,
    story_id: Optional[str] = Query(default=None),
    db: Session = Depends(get_db),
) -> ManagedTestCaseResponse:
    return _service().request_clarification(
        db, test_case_id, payload, story_id=story_id
    )


@router.get(
    "/{test_case_id}",
    response_model=ManagedTestCaseResponse,
    summary="Get a managed test case",
)
async def get_test_case(
    test_case_id: str,
    story_id: Optional[str] = Query(default=None),
    db: Session = Depends(get_db),
) -> ManagedTestCaseResponse:
    return _service().get_test_case(db, test_case_id, story_id=story_id)


@router.put(
    "/{test_case_id}",
    response_model=ManagedTestCaseResponse,
    summary="Edit a managed test case",
)
async def update_test_case(
    test_case_id: str,
    payload: TestCaseEditRequest,
    story_id: Optional[str] = Query(default=None),
    db: Session = Depends(get_db),
) -> ManagedTestCaseResponse:
    return _service().update_test_case(
        db, test_case_id, payload, story_id=story_id
    )
