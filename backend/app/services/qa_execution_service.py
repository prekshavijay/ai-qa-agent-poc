"""Business logic for QA execution runs.

This stage tracks runs and manual results only. It does not launch browsers,
call external systems, or generate automation scripts.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import List, Optional, Sequence, Tuple

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.core.exceptions import AppException
from app.core.logging import get_logger
from app.models.qa_execution import QaExecutionResult, QaExecutionRun
from app.models.test_case_management import TestCaseRecord, TestCaseVersion
from app.schemas.qa_execution import (
    CreateExecutionRunRequest,
    ExecutionResultResponse,
    ExecutionResultStatus,
    ExecutionRunDetailResponse,
    ExecutionRunListResponse,
    ExecutionRunResponse,
    RecordExecutionResultRequest,
    RunStatus,
    TriggerSource,
)
from app.schemas.test_case_management import ReviewStatus

logger = get_logger(__name__)

_FINAL_STATUSES = {
    ExecutionResultStatus.PASSED.value,
    ExecutionResultStatus.FAILED.value,
    ExecutionResultStatus.BLOCKED.value,
}


class QaExecutionService:
    """Create execution runs from approved test cases and record results."""

    def create_run(
        self, db: Session, request: CreateExecutionRunRequest
    ) -> ExecutionRunDetailResponse:
        story_id = request.story_id.strip()
        test_case_ids = list(request.test_case_ids)
        duplicates = _duplicate_ids(test_case_ids)
        if duplicates:
            raise AppException(
                "Duplicate test case IDs cannot be added to the same execution run",
                status_code=422,
                code="duplicate_test_case",
                details={"test_case_ids": duplicates},
            )

        missing: List[str] = []
        not_approved: List[dict[str, str]] = []
        selected: List[Tuple[TestCaseRecord, TestCaseVersion]] = []

        for test_case_id in test_case_ids:
            record = self._get_record(db, story_id, test_case_id)
            if record is None:
                missing.append(test_case_id)
                continue
            if record.review_status != ReviewStatus.APPROVED.value:
                not_approved.append(
                    {
                        "test_case_id": test_case_id,
                        "review_status": record.review_status,
                    }
                )
                continue
            selected.append((record, self._approved_snapshot(record)))

        if missing:
            raise AppException(
                "One or more test case IDs are invalid or are not part of this story",
                status_code=422,
                code="invalid_test_case_ids",
                details={"test_case_ids": missing},
            )
        if not_approved:
            raise AppException(
                "Only approved test cases can be included in an execution run",
                status_code=422,
                code="test_case_not_approved",
                details={"test_cases": not_approved},
            )

        now = datetime.now(timezone.utc)
        run = QaExecutionRun(
            run_id=self._allocate_run_id(db),
            story_id=story_id,
            status=RunStatus.QUEUED.value,
            trigger_source=request.trigger_source.value,
            started_at=now,
            completed_at=None,
            total_test_cases=len(selected),
            passed_count=0,
            failed_count=0,
            blocked_count=0,
            not_run_count=len(selected),
        )
        db.add(run)
        db.flush()

        for record, version in selected:
            db.add(
                QaExecutionResult(
                    execution_run_id=run.id,
                    test_case_id=record.test_case_id,
                    test_case_record_id=record.id,
                    approved_version_id=version.id,
                    status=ExecutionResultStatus.NOT_RUN.value,
                    actual_result=None,
                    error_details=None,
                    evidence={},
                    started_at=None,
                    completed_at=None,
                    duration_seconds=None,
                )
            )
        db.flush()
        db.refresh(run)
        self._refresh_summary(run)
        db.commit()
        logger.info(
            "Created execution run run_id=%s story_id=%s cases=%d",
            run.run_id,
            run.story_id,
            run.total_test_cases,
        )
        return self._to_detail(self._require_run(db, run.run_id))

    def list_runs(
        self, db: Session, *, story_id: Optional[str] = None
    ) -> ExecutionRunListResponse:
        stmt = select(QaExecutionRun).order_by(
            QaExecutionRun.created_at.desc(),
            QaExecutionRun.id.desc(),
        )
        if story_id is not None and story_id.strip():
            stmt = stmt.where(QaExecutionRun.story_id == story_id.strip())
        runs = list(db.scalars(stmt).all())
        return ExecutionRunListResponse(
            total=len(runs),
            runs=[self._to_summary(run) for run in runs],
        )

    def get_run(self, db: Session, run_id: str) -> ExecutionRunDetailResponse:
        return self._to_detail(self._require_run(db, run_id))

    def record_result(
        self,
        db: Session,
        run_id: str,
        payload: RecordExecutionResultRequest,
    ) -> ExecutionRunDetailResponse:
        run = self._require_run(db, run_id)
        result = next(
            (item for item in run.results if item.test_case_id == payload.test_case_id),
            None,
        )
        if result is None:
            raise AppException(
                "This test case is not part of the execution run",
                status_code=404,
                code="test_case_not_in_run",
                details={"run_id": run.run_id, "test_case_id": payload.test_case_id},
            )

        result.status = payload.status.value
        provided = payload.model_fields_set
        if "actual_result" in provided:
            result.actual_result = payload.actual_result
        if "error_details" in provided:
            result.error_details = payload.error_details
        if "evidence" in provided and payload.evidence is not None:
            result.evidence = payload.evidence
        self._apply_timing(result, payload)
        self._refresh_summary(run)
        db.commit()
        logger.info(
            "Recorded execution result run_id=%s test_case_id=%s status=%s run_status=%s",
            run.run_id,
            result.test_case_id,
            result.status,
            run.status,
        )
        return self._to_detail(self._require_run(db, run.run_id))

    def _allocate_run_id(self, db: Session) -> str:
        for _ in range(5):
            candidate = f"RUN-{uuid.uuid4().hex[:12].upper()}"
            existing = db.scalar(
                select(QaExecutionRun.id).where(QaExecutionRun.run_id == candidate)
            )
            if existing is None:
                return candidate
        raise AppException(
            "Could not allocate a unique run id",
            status_code=500,
            code="run_id_allocation_failed",
        )

    def _get_record(
        self, db: Session, story_id: str, test_case_id: str
    ) -> Optional[TestCaseRecord]:
        stmt = (
            select(TestCaseRecord)
            .where(
                TestCaseRecord.story_id == story_id,
                TestCaseRecord.test_case_id == test_case_id,
            )
            .options(selectinload(TestCaseRecord.versions))
        )
        return db.scalars(stmt).first()

    def _approved_snapshot(self, record: TestCaseRecord) -> TestCaseVersion:
        """Return the current approved snapshot, never a later draft."""
        for version in record.versions:
            if (
                version.version_number == record.current_version
                and version.is_approved_snapshot
            ):
                return version
        raise AppException(
            "Approved test case is missing its approved version snapshot",
            status_code=409,
            code="approved_version_missing",
            details={
                "test_case_id": record.test_case_id,
                "current_version": record.current_version,
            },
        )

    def _require_run(self, db: Session, run_id: str) -> QaExecutionRun:
        cleaned = run_id.strip()
        stmt = (
            select(QaExecutionRun)
            .where(QaExecutionRun.run_id == cleaned)
            .options(
                selectinload(QaExecutionRun.results).selectinload(
                    QaExecutionResult.approved_version
                )
            )
        )
        run = db.scalars(stmt).first()
        if run is None:
            raise AppException(
                "Execution run not found",
                status_code=404,
                code="not_found",
                details={"run_id": cleaned},
            )
        return run

    def _apply_timing(
        self, result: QaExecutionResult, payload: RecordExecutionResultRequest
    ) -> None:
        provided = payload.model_fields_set
        if "started_at" in provided and payload.started_at is not None:
            result.started_at = _as_utc(payload.started_at)
        if "completed_at" in provided and payload.completed_at is not None:
            result.completed_at = _as_utc(payload.completed_at)

        if payload.status != ExecutionResultStatus.NOT_RUN:
            now = datetime.now(timezone.utc)
            if result.started_at is None:
                result.started_at = now
            if result.completed_at is None:
                result.completed_at = now

        started = _as_utc(result.started_at) if result.started_at is not None else None
        completed = (
            _as_utc(result.completed_at) if result.completed_at is not None else None
        )
        if started is not None and completed is not None:
            delta = (completed - started).total_seconds()
            if delta < 0:
                raise AppException(
                    "completed_at must not be earlier than started_at",
                    status_code=422,
                    code="validation_error",
                    details={"test_case_id": result.test_case_id},
                )
            result.duration_seconds = delta
            return
        result.duration_seconds = None

    def _refresh_summary(self, run: QaExecutionRun) -> None:
        results = list(run.results)
        run.total_test_cases = len(results)
        run.passed_count = _count(results, ExecutionResultStatus.PASSED.value)
        run.failed_count = _count(results, ExecutionResultStatus.FAILED.value)
        run.blocked_count = _count(results, ExecutionResultStatus.BLOCKED.value)
        run.not_run_count = _count(results, ExecutionResultStatus.NOT_RUN.value)
        accounted = (
            run.passed_count + run.failed_count + run.blocked_count + run.not_run_count
        )
        if accounted != run.total_test_cases:
            raise AppException(
                "Execution result statuses are inconsistent",
                status_code=500,
                code="invalid_execution_state",
                details={"run_id": run.run_id},
            )

        # A failed test case is a final result. Run status `failed` is not used
        # here because this stage has no executor that can fail the run itself.
        if run.total_test_cases > 0 and run.not_run_count == 0:
            if any(item.status not in _FINAL_STATUSES for item in results):
                raise AppException(
                    "Execution result statuses are inconsistent",
                    status_code=500,
                    code="invalid_execution_state",
                    details={"run_id": run.run_id},
                )
            run.status = RunStatus.COMPLETED.value
            run.completed_at = datetime.now(timezone.utc)
            return

        run.completed_at = None
        if run.not_run_count == run.total_test_cases:
            run.status = RunStatus.QUEUED.value
            return
        run.status = RunStatus.RUNNING.value

    def _to_summary(self, run: QaExecutionRun) -> ExecutionRunResponse:
        return ExecutionRunResponse(
            run_id=run.run_id,
            story_id=run.story_id,
            status=RunStatus(run.status),
            trigger_source=TriggerSource(run.trigger_source),
            started_at=run.started_at,
            completed_at=run.completed_at,
            total_test_cases=run.total_test_cases,
            passed_count=run.passed_count,
            failed_count=run.failed_count,
            blocked_count=run.blocked_count,
            not_run_count=run.not_run_count,
            created_at=run.created_at,
            updated_at=run.updated_at,
        )

    def _to_result(
        self, run: QaExecutionRun, result: QaExecutionResult
    ) -> ExecutionResultResponse:
        version = result.approved_version
        if version is None:
            raise AppException(
                "Approved version linked to this result is missing",
                status_code=500,
                code="approved_version_missing",
                details={
                    "run_id": run.run_id,
                    "test_case_id": result.test_case_id,
                    "approved_version_id": result.approved_version_id,
                },
            )
        return ExecutionResultResponse(
            id=result.id,
            run_id=run.run_id,
            test_case_id=result.test_case_id,
            title=version.title,
            expected_result=version.expected_result,
            approved_version_id=result.approved_version_id,
            approved_version_number=version.version_number,
            status=ExecutionResultStatus(result.status),
            actual_result=result.actual_result,
            error_details=result.error_details,
            evidence=dict(result.evidence or {}),
            started_at=result.started_at,
            completed_at=result.completed_at,
            duration_seconds=result.duration_seconds,
            created_at=result.created_at,
            updated_at=result.updated_at,
        )

    def _to_detail(self, run: QaExecutionRun) -> ExecutionRunDetailResponse:
        summary = self._to_summary(run)
        results = [
            self._to_result(run, result)
            for result in sorted(run.results, key=lambda item: item.test_case_id)
        ]
        return ExecutionRunDetailResponse(
            **summary.model_dump(),
            results=results,
        )


def _duplicate_ids(test_case_ids: Sequence[str]) -> List[str]:
    seen: set[str] = set()
    duplicates: List[str] = []
    for test_case_id in test_case_ids:
        if test_case_id in seen and test_case_id not in duplicates:
            duplicates.append(test_case_id)
        seen.add(test_case_id)
    return duplicates


def _count(results: Sequence[QaExecutionResult], status: str) -> int:
    return sum(1 for item in results if item.status == status)


def _as_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)
