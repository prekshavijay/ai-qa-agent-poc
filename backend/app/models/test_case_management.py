"""ORM models for QA review, approval, and test case versioning."""

from __future__ import annotations

from datetime import datetime
from typing import Any, List, Optional

from sqlalchemy import (
    JSON,
    Boolean,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.session import Base
from app.models.base import TimestampMixin


class TestCaseRecord(Base, TimestampMixin):
    """Current state of a managed test case for a story."""

    __test__ = False
    __tablename__ = "test_case_records"
    __table_args__ = (
        UniqueConstraint(
            "story_id",
            "test_case_id",
            name="uq_test_case_records_story_test_case",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    test_case_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    story_id: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    requirement_id: Mapped[str] = mapped_column(String(64), nullable=False)
    acceptance_criterion_id: Mapped[Optional[str]] = mapped_column(
        String(64), nullable=True
    )
    current_version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    review_status: Mapped[str] = mapped_column(
        String(32), nullable=False, default="pending_review", index=True
    )
    # Snapshot of linked analysis IDs for edit-time traceability checks
    linked_requirement_ids: Mapped[List[str]] = mapped_column(
        JSON, nullable=False, default=list
    )
    linked_acceptance_criterion_ids: Mapped[List[str]] = mapped_column(
        JSON, nullable=False, default=list
    )
    # Idempotency key for a generation save request
    generation_fingerprint: Mapped[Optional[str]] = mapped_column(
        String(64), nullable=True, index=True
    )

    versions: Mapped[List["TestCaseVersion"]] = relationship(
        "TestCaseVersion",
        back_populates="test_case",
        cascade="all, delete-orphan",
        order_by="TestCaseVersion.version_number",
    )
    reviews: Mapped[List["TestCaseReview"]] = relationship(
        "TestCaseReview",
        back_populates="test_case",
        cascade="all, delete-orphan",
        order_by="TestCaseReview.created_at",
    )


class TestCaseVersion(Base):
    """Immutable history of test case content across versions."""

    __tablename__ = "test_case_versions"
    __table_args__ = (
        UniqueConstraint(
            "test_case_record_id",
            "version_number",
            name="uq_test_case_versions_record_version",
        ),
    )
    __test__ = False

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    test_case_record_id: Mapped[int] = mapped_column(
        ForeignKey("test_case_records.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    version_number: Mapped[int] = mapped_column(Integer, nullable=False)
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    objective: Mapped[str] = mapped_column(Text, nullable=False)
    test_type: Mapped[str] = mapped_column(String(32), nullable=False)
    priority: Mapped[str] = mapped_column(String(32), nullable=False)
    preconditions: Mapped[List[str]] = mapped_column(JSON, nullable=False, default=list)
    test_data: Mapped[List[str]] = mapped_column(JSON, nullable=False, default=list)
    steps: Mapped[List[dict[str, Any]]] = mapped_column(
        JSON, nullable=False, default=list
    )
    expected_result: Mapped[str] = mapped_column(Text, nullable=False)
    automation_suitability: Mapped[str] = mapped_column(String(32), nullable=False)
    assumptions: Mapped[List[str]] = mapped_column(JSON, nullable=False, default=list)
    needs_clarification: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False
    )
    is_approved_snapshot: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False
    )
    is_original: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    test_case: Mapped["TestCaseRecord"] = relationship(
        "TestCaseRecord", back_populates="versions"
    )
    reviews: Mapped[List["TestCaseReview"]] = relationship(
        "TestCaseReview", back_populates="version"
    )


class TestCaseReview(Base):
    """Audit trail of review actions on a test case version."""

    __tablename__ = "test_case_reviews"
    __test__ = False

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    test_case_record_id: Mapped[int] = mapped_column(
        ForeignKey("test_case_records.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    version_id: Mapped[int] = mapped_column(
        ForeignKey("test_case_versions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    review_action: Mapped[str] = mapped_column(String(32), nullable=False)
    reviewer_id: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    comments: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    test_case: Mapped["TestCaseRecord"] = relationship(
        "TestCaseRecord", back_populates="reviews"
    )
    version: Mapped["TestCaseVersion"] = relationship(
        "TestCaseVersion", back_populates="reviews"
    )
