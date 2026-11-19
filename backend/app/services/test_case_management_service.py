"""Business logic for QA review, approval, and test case versioning."""

from __future__ import annotations

import hashlib
import json
from typing import List, Optional, Set, Tuple

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.core.exceptions import AppException
from app.core.logging import get_logger
from app.models.test_case_management import (
    TestCaseRecord,
    TestCaseReview,
    TestCaseVersion,
)
from app.schemas.requirements import RequirementAnalysisResponse
from app.schemas.test_case_management import (
    ClarifyTestCaseRequest,
    ManagedTestCaseResponse,
    ManagedTestCaseReviewResponse,
    ManagedTestCaseVersionResponse,
    RejectTestCaseRequest,
    ReviewAction,
    ReviewerActionRequest,
    ReviewStatus,
    SaveGeneratedTestCasesRequest,
    SaveGeneratedTestCasesResponse,
    StoryTestCaseSummary,
    TestCaseEditRequest,
)
from app.schemas.test_cases import (
    AutomationSuitability,
    TestCase,
    TestCaseGenerationResponse,
    TestCaseStep,
    TestPriority,
    TestType,
)

logger = get_logger(__name__)


class TestCaseManagementService:
    """Persist, version, and review AI-generated test cases."""

    __test__ = False

    def save_generated_test_cases(
        self,
        db: Session,
        request: SaveGeneratedTestCasesRequest,
    ) -> SaveGeneratedTestCasesResponse:
        generation = request.generation
        story_id = generation.story_id.strip()
        if not story_id:
            raise AppException(
                "story_id must not be empty",
                status_code=422,
                code="validation_error",
            )

        valid_requirement_ids, valid_criterion_ids = self._resolve_linked_ids(request)
        fingerprint = self._generation_fingerprint(generation)

        saved_ids: List[Tuple[str, str]] = []
        newly_saved = 0
        skipped = 0

        for case in generation.test_cases:
            if case.requirement_id not in valid_requirement_ids:
                raise AppException(
                    "Cannot save test case with unknown requirement mapping",
                    status_code=422,
                    code="invalid_requirement_mapping",
                    details={
                        "test_case_id": case.test_case_id,
                        "requirement_id": case.requirement_id,
                    },
                )
            if (
                case.acceptance_criterion_id
                and case.acceptance_criterion_id not in valid_criterion_ids
            ):
                raise AppException(
                    "Cannot save test case with unknown acceptance criterion mapping",
                    status_code=422,
                    code="invalid_acceptance_criterion_mapping",
                    details={
                        "test_case_id": case.test_case_id,
                        "acceptance_criterion_id": case.acceptance_criterion_id,
                    },
                )

            existing = self._get_record(db, story_id, case.test_case_id)
            if existing is not None:
                skipped += 1
                saved_ids.append((story_id, case.test_case_id))
                if existing.generation_fingerprint != fingerprint:
                    logger.info(
                        "Skipped duplicate save story_id=%s test_case_id=%s",
                        story_id,
                        case.test_case_id,
                    )
                continue

            record = TestCaseRecord(
                test_case_id=case.test_case_id,
                story_id=story_id,
                requirement_id=case.requirement_id,
                acceptance_criterion_id=case.acceptance_criterion_id,
                current_version=1,
                review_status=ReviewStatus.PENDING_REVIEW.value,
                linked_requirement_ids=sorted(valid_requirement_ids),
                linked_acceptance_criterion_ids=sorted(valid_criterion_ids),
                generation_fingerprint=fingerprint,
            )
            db.add(record)
            db.flush()

            version = self._build_version_from_case(
                record_id=record.id,
                version_number=1,
                case=case,
                is_original=True,
                is_approved_snapshot=False,
            )
            db.add(version)
            db.flush()

            db.add(
                TestCaseReview(
                    test_case_record_id=record.id,
                    version_id=version.id,
                    review_action=ReviewAction.SAVE.value,
                    reviewer_id=None,
                    comments="Saved from test case generation",
                )
            )
            db.flush()
            newly_saved += 1
            saved_ids.append((story_id, case.test_case_id))

        db.commit()

        reloaded: List[ManagedTestCaseResponse] = []
        for sid, tcid in saved_ids:
            record = self._get_record(db, sid, tcid)
            if record is not None:
                reloaded.append(self._to_managed_response(record))

        logger.info(
            "Saved generated test cases story_id=%s saved=%d skipped_duplicates=%d",
            story_id,
            newly_saved,
            skipped,
        )
        return SaveGeneratedTestCasesResponse(
            story_id=story_id,
            saved_count=newly_saved,
            skipped_duplicates=skipped,
            test_cases=reloaded,
        )

    def save_from_generation(
        self,
        db: Session,
        generation: TestCaseGenerationResponse,
        analysis: RequirementAnalysisResponse,
    ) -> SaveGeneratedTestCasesResponse:
        return self.save_generated_test_cases(
            db,
            SaveGeneratedTestCasesRequest(
                generation=generation,
                analysis=analysis,
            ),
        )

    def get_by_story(self, db: Session, story_id: str) -> StoryTestCaseSummary:
        story_id = story_id.strip()
        records = self._list_by_story(db, story_id)
        responses = [self._to_managed_response(record) for record in records]
        return StoryTestCaseSummary(
            story_id=story_id,
            total=len(responses),
            pending_review=sum(
                1
                for item in responses
                if item.review_status == ReviewStatus.PENDING_REVIEW
            ),
            approved=sum(
                1 for item in responses if item.review_status == ReviewStatus.APPROVED
            ),
            rejected=sum(
                1 for item in responses if item.review_status == ReviewStatus.REJECTED
            ),
            needs_clarification=sum(
                1
                for item in responses
                if item.review_status == ReviewStatus.NEEDS_CLARIFICATION
            ),
            test_cases=responses,
        )

    def get_test_case(
        self, db: Session, test_case_id: str, *, story_id: Optional[str] = None
    ) -> ManagedTestCaseResponse:
        record = self._require_record(db, test_case_id, story_id=story_id)
        return self._to_managed_response(record)

    def update_test_case(
        self,
        db: Session,
        test_case_id: str,
        payload: TestCaseEditRequest,
        *,
        story_id: Optional[str] = None,
    ) -> ManagedTestCaseResponse:
        record = self._require_record(db, test_case_id, story_id=story_id)
        self._validate_mapping_on_edit(record, payload)

        requirement_id = (payload.requirement_id or record.requirement_id).strip()
        acceptance_criterion_id = payload.acceptance_criterion_id
        if acceptance_criterion_id is not None:
            acceptance_criterion_id = acceptance_criterion_id.strip() or None

        record.requirement_id = requirement_id
        record.acceptance_criterion_id = acceptance_criterion_id

        current = self._current_version(record)
        status = ReviewStatus(record.review_status)

        if status == ReviewStatus.APPROVED:
            # Editing an approved case creates a new pending version.
            new_number = record.current_version + 1
            version = self._build_version_from_edit(
                record_id=record.id,
                version_number=new_number,
                payload=payload,
                is_original=False,
                is_approved_snapshot=False,
            )
            db.add(version)
            db.flush()
            record.current_version = new_number
            record.review_status = ReviewStatus.PENDING_REVIEW.value
            db.add(
                TestCaseReview(
                    test_case_record_id=record.id,
                    version_id=version.id,
                    review_action=ReviewAction.EDIT.value,
                    reviewer_id=payload.reviewer_id,
                    comments=payload.comments
                    or "Edited approved test case; new version pending review",
                )
            )
        elif status in {
            ReviewStatus.PENDING_REVIEW,
            ReviewStatus.NEEDS_CLARIFICATION,
            ReviewStatus.REJECTED,
        }:
            # Preserve version 1 as the generated original when still on v1.
            if current.is_original and current.version_number == 1:
                new_number = 2
                version = self._build_version_from_edit(
                    record_id=record.id,
                    version_number=new_number,
                    payload=payload,
                    is_original=False,
                    is_approved_snapshot=False,
                )
                db.add(version)
                db.flush()
                record.current_version = new_number
                version_id = version.id
            else:
                self._apply_edit_to_version(current, payload)
                version_id = current.id
            # Clarification / rejection edits return to pending review.
            record.review_status = ReviewStatus.PENDING_REVIEW.value
            db.add(
                TestCaseReview(
                    test_case_record_id=record.id,
                    version_id=version_id,
                    review_action=ReviewAction.EDIT.value,
                    reviewer_id=payload.reviewer_id,
                    comments=payload.comments or "Updated draft test case",
                )
            )
        else:
            raise AppException(
                "Unsupported review status for edit",
                status_code=409,
                code="invalid_review_state",
                details={"review_status": record.review_status},
            )

        db.commit()
        db.refresh(record)
        logger.info(
            "Updated test case story_id=%s test_case_id=%s version=%s status=%s",
            record.story_id,
            record.test_case_id,
            record.current_version,
            record.review_status,
        )
        return self._to_managed_response(
            self._require_record(db, record.test_case_id, story_id=record.story_id)
        )

    def approve(
        self,
        db: Session,
        test_case_id: str,
        payload: ReviewerActionRequest,
        *,
        story_id: Optional[str] = None,
    ) -> ManagedTestCaseResponse:
        record = self._require_record(db, test_case_id, story_id=story_id)
        status = ReviewStatus(record.review_status)

        if status == ReviewStatus.NEEDS_CLARIFICATION:
            raise AppException(
                "Cannot approve a test case that needs clarification until it is resolved",
                status_code=409,
                code="clarification_required",
                details={"test_case_id": record.test_case_id},
            )
        if status == ReviewStatus.REJECTED:
            raise AppException(
                "Cannot approve a rejected test case; edit it first to return it to pending review",
                status_code=409,
                code="invalid_review_state",
                details={"review_status": status.value},
            )
        if status == ReviewStatus.APPROVED:
            raise AppException(
                "Test case is already approved",
                status_code=409,
                code="already_approved",
                details={"test_case_id": record.test_case_id},
            )
        if status != ReviewStatus.PENDING_REVIEW:
            raise AppException(
                "Only pending_review test cases can be approved",
                status_code=409,
                code="invalid_review_state",
                details={"review_status": status.value},
            )

        version = self._current_version(record)
        version.is_approved_snapshot = True
        record.review_status = ReviewStatus.APPROVED.value
        db.add(
            TestCaseReview(
                test_case_record_id=record.id,
                version_id=version.id,
                review_action=ReviewAction.APPROVE.value,
                reviewer_id=payload.reviewer_id,
                comments=payload.comments,
            )
        )
        db.commit()
        logger.info(
            "Approved test case story_id=%s test_case_id=%s version=%s",
            record.story_id,
            record.test_case_id,
            record.current_version,
        )
        return self._to_managed_response(
            self._require_record(db, record.test_case_id, story_id=record.story_id)
        )

    def reject(
        self,
        db: Session,
        test_case_id: str,
        payload: RejectTestCaseRequest,
        *,
        story_id: Optional[str] = None,
    ) -> ManagedTestCaseResponse:
        record = self._require_record(db, test_case_id, story_id=story_id)
        status = ReviewStatus(record.review_status)
        if status == ReviewStatus.APPROVED:
            raise AppException(
                "Cannot reject an approved test case; edit it to create a new pending version first",
                status_code=409,
                code="invalid_review_state",
            )

        version = self._current_version(record)
        record.review_status = ReviewStatus.REJECTED.value
        db.add(
            TestCaseReview(
                test_case_record_id=record.id,
                version_id=version.id,
                review_action=ReviewAction.REJECT.value,
                reviewer_id=payload.reviewer_id,
                comments=payload.comments,
            )
        )
        db.commit()
        logger.info(
            "Rejected test case story_id=%s test_case_id=%s",
            record.story_id,
            record.test_case_id,
        )
        return self._to_managed_response(
            self._require_record(db, record.test_case_id, story_id=record.story_id)
        )

    def request_clarification(
        self,
        db: Session,
        test_case_id: str,
        payload: ClarifyTestCaseRequest,
        *,
        story_id: Optional[str] = None,
    ) -> ManagedTestCaseResponse:
        record = self._require_record(db, test_case_id, story_id=story_id)
        status = ReviewStatus(record.review_status)
        if status == ReviewStatus.APPROVED:
            raise AppException(
                "Cannot request clarification on an approved test case; edit it first",
                status_code=409,
                code="invalid_review_state",
            )

        version = self._current_version(record)
        record.review_status = ReviewStatus.NEEDS_CLARIFICATION.value
        db.add(
            TestCaseReview(
                test_case_record_id=record.id,
                version_id=version.id,
                review_action=ReviewAction.REQUEST_CLARIFICATION.value,
                reviewer_id=payload.reviewer_id,
                comments=payload.comments,
            )
        )
        db.commit()
        logger.info(
            "Clarification requested story_id=%s test_case_id=%s",
            record.story_id,
            record.test_case_id,
        )
        return self._to_managed_response(
            self._require_record(db, record.test_case_id, story_id=record.story_id)
        )

    def get_versions(
        self, db: Session, test_case_id: str, *, story_id: Optional[str] = None
    ) -> List[ManagedTestCaseVersionResponse]:
        record = self._require_record(db, test_case_id, story_id=story_id)
        return [self._to_version_response(version) for version in record.versions]

    def get_reviews(
        self, db: Session, test_case_id: str, *, story_id: Optional[str] = None
    ) -> List[ManagedTestCaseReviewResponse]:
        record = self._require_record(db, test_case_id, story_id=story_id)
        version_map = {version.id: version.version_number for version in record.versions}
        return [
            ManagedTestCaseReviewResponse(
                review_action=ReviewAction(review.review_action),
                version_number=version_map.get(review.version_id, record.current_version),
                reviewer_id=review.reviewer_id,
                comments=review.comments,
                created_at=review.created_at,
            )
            for review in record.reviews
        ]

    def get_approved_by_story(
        self, db: Session, story_id: str
    ) -> List[ManagedTestCaseResponse]:
        summary = self.get_by_story(db, story_id)
        return [
            item
            for item in summary.test_cases
            if item.review_status == ReviewStatus.APPROVED
        ]

    def _resolve_linked_ids(
        self, request: SaveGeneratedTestCasesRequest
    ) -> Tuple[Set[str], Set[str]]:
        requirement_ids: Set[str] = set(request.valid_requirement_ids)
        criterion_ids: Set[str] = set(request.valid_acceptance_criterion_ids)

        if request.analysis is not None:
            analysis = request.analysis
            requirement_ids |= {
                item.requirement_id for item in analysis.functional_requirements
            }
            requirement_ids |= {
                item.requirement_id for item in analysis.non_functional_requirements
            }
            criterion_ids |= {
                item.criterion_id for item in analysis.acceptance_criteria
            }

        if not requirement_ids:
            # Fall back to IDs present on the generated cases themselves.
            requirement_ids = {
                case.requirement_id for case in request.generation.test_cases
            }
            criterion_ids = {
                case.acceptance_criterion_id
                for case in request.generation.test_cases
                if case.acceptance_criterion_id
            }

        return requirement_ids, criterion_ids

    def _generation_fingerprint(self, generation: TestCaseGenerationResponse) -> str:
        payload = {
            "story_id": generation.story_id,
            "test_cases": [
                case.model_dump(mode="json") for case in generation.test_cases
            ],
        }
        raw = json.dumps(payload, sort_keys=True, ensure_ascii=False)
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()

    def _list_by_story(self, db: Session, story_id: str) -> List[TestCaseRecord]:
        stmt = (
            select(TestCaseRecord)
            .where(TestCaseRecord.story_id == story_id)
            .options(
                selectinload(TestCaseRecord.versions),
                selectinload(TestCaseRecord.reviews),
            )
            .order_by(TestCaseRecord.test_case_id)
        )
        return list(db.scalars(stmt).all())

    def _get_record(
        self, db: Session, story_id: str, test_case_id: str
    ) -> Optional[TestCaseRecord]:
        stmt = (
            select(TestCaseRecord)
            .where(
                TestCaseRecord.story_id == story_id,
                TestCaseRecord.test_case_id == test_case_id,
            )
            .options(
                selectinload(TestCaseRecord.versions),
                selectinload(TestCaseRecord.reviews),
            )
        )
        return db.scalars(stmt).first()

    def _require_record(
        self,
        db: Session,
        test_case_id: str,
        *,
        story_id: Optional[str] = None,
    ) -> TestCaseRecord:
        stmt = (
            select(TestCaseRecord)
            .where(TestCaseRecord.test_case_id == test_case_id)
            .options(
                selectinload(TestCaseRecord.versions),
                selectinload(TestCaseRecord.reviews),
            )
        )
        if story_id:
            stmt = stmt.where(TestCaseRecord.story_id == story_id)

        records = list(db.scalars(stmt).all())
        if not records:
            raise AppException(
                "Test case not found",
                status_code=404,
                code="not_found",
                details={"test_case_id": test_case_id},
            )
        if len(records) > 1 and not story_id:
            raise AppException(
                "Multiple test cases share this test_case_id; provide story_id",
                status_code=409,
                code="ambiguous_test_case",
                details={
                    "test_case_id": test_case_id,
                    "story_ids": [item.story_id for item in records],
                },
            )
        return records[0]

    def _current_version(self, record: TestCaseRecord) -> TestCaseVersion:
        for version in record.versions:
            if version.version_number == record.current_version:
                return version
        raise AppException(
            "Current version is missing",
            status_code=500,
            code="version_missing",
            details={
                "test_case_id": record.test_case_id,
                "current_version": record.current_version,
            },
        )

    def _validate_mapping_on_edit(
        self, record: TestCaseRecord, payload: TestCaseEditRequest
    ) -> None:
        requirement_id = (payload.requirement_id or record.requirement_id).strip()
        linked_requirements = set(record.linked_requirement_ids or [])
        linked_criteria = set(record.linked_acceptance_criterion_ids or [])

        if requirement_id not in linked_requirements:
            raise AppException(
                "Edited test case references a requirement that is not in the linked analysis",
                status_code=422,
                code="invalid_requirement_mapping",
                details={
                    "requirement_id": requirement_id,
                    "allowed_requirement_ids": sorted(linked_requirements),
                },
            )

        criterion_id = payload.acceptance_criterion_id
        if criterion_id is not None:
            criterion_id = criterion_id.strip() or None
        if criterion_id and criterion_id not in linked_criteria:
            raise AppException(
                "Edited test case references an acceptance criterion that is not in the linked analysis",
                status_code=422,
                code="invalid_acceptance_criterion_mapping",
                details={
                    "acceptance_criterion_id": criterion_id,
                    "allowed_acceptance_criterion_ids": sorted(linked_criteria),
                },
            )

    def _build_version_from_case(
        self,
        *,
        record_id: int,
        version_number: int,
        case: TestCase,
        is_original: bool,
        is_approved_snapshot: bool,
    ) -> TestCaseVersion:
        return TestCaseVersion(
            test_case_record_id=record_id,
            version_number=version_number,
            title=case.title,
            objective=case.objective,
            test_type=case.test_type.value,
            priority=case.priority.value,
            preconditions=list(case.preconditions),
            test_data=list(case.test_data),
            steps=[step.model_dump(mode="json") for step in case.steps],
            expected_result=case.expected_result,
            automation_suitability=case.automation_suitability.value,
            assumptions=list(case.assumptions),
            needs_clarification=case.needs_clarification,
            is_original=is_original,
            is_approved_snapshot=is_approved_snapshot,
        )

    def _build_version_from_edit(
        self,
        *,
        record_id: int,
        version_number: int,
        payload: TestCaseEditRequest,
        is_original: bool,
        is_approved_snapshot: bool,
    ) -> TestCaseVersion:
        return TestCaseVersion(
            test_case_record_id=record_id,
            version_number=version_number,
            title=payload.title,
            objective=payload.objective,
            test_type=payload.test_type.value,
            priority=payload.priority.value,
            preconditions=list(payload.preconditions),
            test_data=list(payload.test_data),
            steps=[step.model_dump(mode="json") for step in payload.steps],
            expected_result=payload.expected_result,
            automation_suitability=payload.automation_suitability.value,
            assumptions=list(payload.assumptions),
            needs_clarification=payload.needs_clarification,
            is_original=is_original,
            is_approved_snapshot=is_approved_snapshot,
        )

    def _apply_edit_to_version(
        self, version: TestCaseVersion, payload: TestCaseEditRequest
    ) -> None:
        if version.is_approved_snapshot:
            raise AppException(
                "Cannot overwrite an approved version",
                status_code=409,
                code="immutable_version",
                details={"version_number": version.version_number},
            )
        if version.is_original:
            raise AppException(
                "Cannot overwrite the original generated version",
                status_code=409,
                code="immutable_version",
                details={"version_number": version.version_number},
            )
        version.title = payload.title
        version.objective = payload.objective
        version.test_type = payload.test_type.value
        version.priority = payload.priority.value
        version.preconditions = list(payload.preconditions)
        version.test_data = list(payload.test_data)
        version.steps = [step.model_dump(mode="json") for step in payload.steps]
        version.expected_result = payload.expected_result
        version.automation_suitability = payload.automation_suitability.value
        version.assumptions = list(payload.assumptions)
        version.needs_clarification = payload.needs_clarification

    def _to_version_response(
        self, version: TestCaseVersion
    ) -> ManagedTestCaseVersionResponse:
        steps = [
            TestCaseStep.model_validate(step)
            if not isinstance(step, TestCaseStep)
            else step
            for step in (version.steps or [])
        ]
        return ManagedTestCaseVersionResponse(
            version_number=version.version_number,
            title=version.title,
            objective=version.objective,
            test_type=TestType(version.test_type),
            priority=TestPriority(version.priority),
            preconditions=list(version.preconditions or []),
            test_data=list(version.test_data or []),
            steps=steps,
            expected_result=version.expected_result,
            automation_suitability=AutomationSuitability(version.automation_suitability),
            assumptions=list(version.assumptions or []),
            needs_clarification=bool(version.needs_clarification),
            is_original=bool(version.is_original),
            is_approved_snapshot=bool(version.is_approved_snapshot),
            created_at=version.created_at,
        )

    def _to_managed_response(self, record: TestCaseRecord) -> ManagedTestCaseResponse:
        current = self._current_version(record)
        original = next(
            (version for version in record.versions if version.is_original),
            None,
        )
        current_payload = self._to_version_response(current)
        return ManagedTestCaseResponse(
            test_case_id=record.test_case_id,
            story_id=record.story_id,
            requirement_id=record.requirement_id,
            acceptance_criterion_id=record.acceptance_criterion_id,
            current_version=record.current_version,
            review_status=ReviewStatus(record.review_status),
            title=current_payload.title,
            objective=current_payload.objective,
            test_type=current_payload.test_type,
            priority=current_payload.priority,
            preconditions=current_payload.preconditions,
            test_data=current_payload.test_data,
            steps=current_payload.steps,
            expected_result=current_payload.expected_result,
            automation_suitability=current_payload.automation_suitability,
            assumptions=current_payload.assumptions,
            needs_clarification=current_payload.needs_clarification,
            created_at=record.created_at,
            updated_at=record.updated_at,
            original_version=(
                self._to_version_response(original) if original is not None else None
            ),
        )
