"""ORM models for QA execution runs and individual test results.

Runs pin the approved test case version that was current at creation time.
Later edits create a new draft version and do not change that link.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, List, Optional

from sqlalchemy import JSON, DateTime, Float, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.session import Base
from app.models.base import TimestampMixin
from app.models.test_case_management import TestCaseVersion


class QaExecutionRun(Base, TimestampMixin):
    """One automated QA execution attempt for a story.

    Status `failed` is reserved for a later executor failure. Recording a
    failed test case does not fail the run; the run completes once every
    case has a final result.
    """

    __tablename__ = "qa_execution_runs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    run_id: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, index=True)
    story_id: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    status: Mapped[str] = mapped_column(
        String(32), nullable=False, default="queued", index=True
    )
    trigger_source: Mapped[str] = mapped_column(String(32), nullable=False, default="manual")
    started_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    completed_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    total_test_cases: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    passed_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    failed_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    blocked_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    not_run_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    results: Mapped[List["QaExecutionResult"]] = relationship(
        "QaExecutionResult",
        back_populates="run",
        cascade="all, delete-orphan",
        order_by="QaExecutionResult.test_case_id",
    )


class QaExecutionResult(Base, TimestampMixin):
    """Result for one approved test case inside a single execution run."""

    __tablename__ = "qa_execution_results"
    __table_args__ = (
        UniqueConstraint(
            "execution_run_id",
            "test_case_id",
            name="uq_qa_execution_results_run_case",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    execution_run_id: Mapped[int] = mapped_column(
        ForeignKey("qa_execution_runs.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    test_case_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    test_case_record_id: Mapped[int] = mapped_column(
        ForeignKey("test_case_records.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    approved_version_id: Mapped[int] = mapped_column(
        ForeignKey("test_case_versions.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="not_run")
    actual_result: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    error_details: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    evidence: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    started_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    completed_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    duration_seconds: Mapped[Optional[float]] = mapped_column(Float, nullable=True)

    run: Mapped["QaExecutionRun"] = relationship("QaExecutionRun", back_populates="results")
    approved_version: Mapped[TestCaseVersion] = relationship(
        "TestCaseVersion",
        foreign_keys=[approved_version_id],
    )
