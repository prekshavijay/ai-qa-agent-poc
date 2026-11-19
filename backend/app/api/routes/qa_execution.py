"""QA execution run endpoints.

Creating a run records approved cases as not_run. It does not execute them.
"""

from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.database.session import get_db
from app.schemas.qa_execution import (
    CreateExecutionRunRequest,
    ExecutionRunDetailResponse,
    ExecutionRunListResponse,
    QaExecutionHealthResponse,
    RecordExecutionResultRequest,
)
from app.services.qa_execution_service import QaExecutionService

router = APIRouter(tags=["qa-execution"])


def _service() -> QaExecutionService:
    return QaExecutionService()


@router.get(
    "/health",
    response_model=QaExecutionHealthResponse,
    summary="QA execution health",
)
async def qa_execution_health() -> QaExecutionHealthResponse:
    return QaExecutionHealthResponse(
        status="ok",
        module="qa_execution",
        note=(
            "Execution runs can be created from QA-approved test cases and "
            "results can be recorded manually. Automated browser and API "
            "execution is not implemented yet."
        ),
    )


@router.post(
    "/runs",
    response_model=ExecutionRunDetailResponse,
    summary="Create an execution run",
    description=(
        "Creates a run for the selected approved test cases. Each case is "
        "stored as not_run and linked to the approved version. No tests are executed."
    ),
)
async def create_execution_run(
    request: CreateExecutionRunRequest,
    db: Session = Depends(get_db),
) -> ExecutionRunDetailResponse:
    return _service().create_run(db, request)


@router.get(
    "/runs",
    response_model=ExecutionRunListResponse,
    summary="List execution runs",
)
async def list_execution_runs(
    story_id: Optional[str] = Query(default=None),
    db: Session = Depends(get_db),
) -> ExecutionRunListResponse:
    return _service().list_runs(db, story_id=story_id)


@router.get(
    "/runs/{run_id}",
    response_model=ExecutionRunDetailResponse,
    summary="Get an execution run and its results",
)
async def get_execution_run(
    run_id: str,
    db: Session = Depends(get_db),
) -> ExecutionRunDetailResponse:
    return _service().get_run(db, run_id)


@router.post(
    "/runs/{run_id}/results",
    response_model=ExecutionRunDetailResponse,
    summary="Record or update one execution result",
    description=(
        "Updates the existing result row for a test case in this run and "
        "recalculates run counts. Does not execute the test case."
    ),
)
async def record_execution_result(
    run_id: str,
    payload: RecordExecutionResultRequest,
    db: Session = Depends(get_db),
) -> ExecutionRunDetailResponse:
    return _service().record_result(db, run_id, payload)
