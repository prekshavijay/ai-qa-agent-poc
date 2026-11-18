"""Test case generation business rules.

Consumes RequirementAnalysisResponse only. Does not re-analyse the original
story or invent business rules, limits, error messages, or expected behaviour
that the requirements do not state.
"""

import json
import re
from typing import Dict, List, Optional, Sequence, Set, Tuple, Union

from pydantic import ValidationError

from app.core.logging import get_logger
from app.integrations.llm.base import LLMMessage
from app.schemas.requirements import (
    AcceptanceCriterion,
    FunctionalRequirement,
    NonFunctionalRequirement,
    Priority,
    RequirementAnalysisResponse,
    TestabilityStatus,
)
from app.schemas.test_cases import (
    AutomationSuitability,
    GenerationStatus,
    SkippedRequirement,
    TestCase,
    TestCaseGenerationResponse,
    TestCaseStep,
    TestPriority,
    TestType,
)
from app.services.requirement_rules import (
    find_vague_terms,
    has_measurement,
    normalize_text,
)

logger = get_logger(__name__)

SYSTEM_PROMPT = (
    "You generate software test cases for a QA team from structured requirements. "
    "Return JSON only. Every test case must map to an existing requirement_id. "
    "Do not invent business rules, limits, error messages, permissions, or behaviour. "
    "If a detail is missing, mark assumptions or needs_clarification instead of guessing."
)

RequirementItem = Union[FunctionalRequirement, NonFunctionalRequirement]

_CONSTRAINT_PATTERN = re.compile(
    r"\b("
    r"must|must not|shall|should not|cannot|can not|at least|at most|"
    r"expires?|expired|reject|rejects|validate|validates|required|require|"
    r"contain|contains|minimum|maximum|only|unless|without|invalid|unauthorized"
    r")\b",
    re.IGNORECASE,
)

_INTEGRATION_PATTERN = re.compile(
    r"\b("
    r"email|e-mail|sms|api|webhook|third[- ]party|integrat(?:e|es|ion)|"
    r"notify|notifies|notification|sends?|receives?|redirect|callback|"
    r"external|downstream|upstream|service"
    r")\b",
    re.IGNORECASE,
)

_EDGE_PATTERN = re.compile(
    r"\b("
    r"empty|blank|null|zero|none|already|duplicate|concurrent|"
    r"expired|missing|absent|first|last|maximum|minimum|boundary"
    r")\b",
    re.IGNORECASE,
)

_NUMBER_PATTERN = re.compile(r"\b\d+(?:\.\d+)?\b")


class TestCaseGenerationService:
    """Build, validate, and ground test cases from a requirement analysis."""

    def build_draft(
        self, analysis: RequirementAnalysisResponse
    ) -> TestCaseGenerationResponse:
        test_cases, skipped = self._generate_from_analysis(analysis)
        return self._assemble(
            analysis,
            test_cases,
            skipped,
            provider="deterministic",
            provider_note="Draft produced from requirement analysis before provider review.",
        )

    def build_messages(
        self,
        analysis: RequirementAnalysisResponse,
        draft: TestCaseGenerationResponse,
    ) -> List[LLMMessage]:
        payload = {
            "task": "generate_test_cases",
            "instructions": (
                "Return the draft_test_cases JSON without inventing requirements, "
                "business rules, limits, error messages, or expected behaviour. "
                "Keep every test_case.requirement_id equal to an existing requirement."
            ),
            "analysis": analysis.model_dump(mode="json"),
            "draft_test_cases": draft.model_dump(mode="json"),
        }
        return [
            LLMMessage(role="system", content=SYSTEM_PROMPT),
            LLMMessage(
                role="user",
                content=json.dumps(payload, ensure_ascii=False, sort_keys=True),
            ),
        ]

    def validate_structured_output(
        self,
        content: str,
        analysis: RequirementAnalysisResponse,
        draft: TestCaseGenerationResponse,
        *,
        provider: str,
    ) -> TestCaseGenerationResponse:
        """Parse provider JSON, enforce traceability, and drop unsupported inventions."""
        provider_name = provider or "unspecified"
        note = "Structured output was checked against the requirement analysis."
        generation_payload, provider_name, note = self._unwrap_provider_payload(
            content,
            provider_name,
            note,
        )
        if generation_payload is None:
            return self.apply_provider(draft, provider_name, note)

        try:
            parsed = TestCaseGenerationResponse.model_validate(generation_payload)
        except ValidationError as exc:
            logger.warning("Provider test-case output failed schema validation: %s", exc)
            return self.apply_provider(
                draft,
                provider_name,
                "Deterministic generation was kept because the provider output did not match the schema.",
            )

        valid_requirement_ids = self._requirement_ids(analysis)
        valid_criterion_ids = {item.criterion_id for item in analysis.acceptance_criteria}
        requirement_lookup = self._requirement_lookup(analysis)

        merged: List[TestCase] = []
        seen: Set[str] = set()
        for case in list(draft.test_cases) + list(parsed.test_cases):
            if case.requirement_id not in valid_requirement_ids:
                logger.warning(
                    "Removed test case with unknown requirement_id=%s",
                    case.requirement_id,
                )
                continue
            if (
                case.acceptance_criterion_id
                and case.acceptance_criterion_id not in valid_criterion_ids
            ):
                logger.warning(
                    "Cleared unknown acceptance_criterion_id=%s on %s",
                    case.acceptance_criterion_id,
                    case.test_case_id,
                )
                case = case.model_copy(update={"acceptance_criterion_id": None})

            requirement = requirement_lookup.get(case.requirement_id)
            if requirement is None:
                continue
            grounded = self._ground_case(case, requirement, analysis)
            if grounded is None:
                continue
            key = self._dedupe_key(grounded)
            if key in seen:
                continue
            seen.add(key)
            merged.append(grounded)

        skipped = self._rebuild_skipped(analysis, merged, draft.skipped_requirements)
        return self._assemble(
            analysis,
            merged,
            skipped,
            provider=provider_name,
            provider_note=note,
        )

    def apply_provider(
        self,
        generation: TestCaseGenerationResponse,
        provider: str,
        provider_note: str,
    ) -> TestCaseGenerationResponse:
        return generation.model_copy(
            update={"provider": provider, "provider_note": provider_note}
        )

    def _unwrap_provider_payload(
        self,
        content: str,
        provider_name: str,
        note: str,
    ) -> Tuple[Optional[dict], str, str]:
        try:
            payload = json.loads(content)
        except json.JSONDecodeError:
            logger.warning("Provider returned non-JSON output. Using deterministic generation.")
            return (
                None,
                provider_name,
                "Deterministic generation was kept because the provider output was not valid JSON.",
            )

        if not isinstance(payload, dict):
            logger.warning("Provider returned a non-object payload. Using deterministic generation.")
            return (
                None,
                provider_name,
                "Deterministic generation was kept because the provider output was not a JSON object.",
            )

        if payload.get("mock") is True:
            provider_name = "mock"
            envelope_note = payload.get("note")
            if isinstance(envelope_note, str) and envelope_note.strip():
                note = envelope_note.strip()
            else:
                note = (
                    "Deterministic mock provider. No external language model was called."
                )
            generation = payload.get("generation") or payload.get("test_cases_payload")
            return generation, provider_name, note

        return payload, provider_name, note

    def _generate_from_analysis(
        self, analysis: RequirementAnalysisResponse
    ) -> Tuple[List[TestCase], List[SkippedRequirement]]:
        cases: List[TestCase] = []
        skipped: List[SkippedRequirement] = []
        seen: Set[str] = set()
        counter = 0

        for requirement in self._all_requirements(analysis):
            if requirement.testability_status == TestabilityStatus.NOT_TESTABLE:
                skipped.append(
                    SkippedRequirement(
                        requirement_id=requirement.requirement_id,
                        description=requirement.description,
                        reason=(
                            "Requirement is marked not_testable. "
                            "No expected result was fabricated."
                        ),
                    )
                )
                continue

            generated = self._cases_for_requirement(requirement, analysis)
            if not generated:
                skipped.append(
                    SkippedRequirement(
                        requirement_id=requirement.requirement_id,
                        description=requirement.description,
                        reason=(
                            "No independently executable test case could be derived "
                            "from the stated requirement without inventing behaviour."
                        ),
                    )
                )
                continue

            for case in generated:
                key = self._dedupe_key(case)
                if key in seen:
                    continue
                seen.add(key)
                counter += 1
                cases.append(
                    case.model_copy(
                        update={"test_case_id": f"TC-{counter:03d}"}
                    )
                )

        return cases, skipped

    def _cases_for_requirement(
        self,
        requirement: RequirementItem,
        analysis: RequirementAnalysisResponse,
    ) -> List[TestCase]:
        criterion_id = self._criterion_id_for(requirement, analysis)
        ambiguous = self._is_ambiguous(requirement, analysis)
        needs_clarification = (
            requirement.testability_status != TestabilityStatus.TESTABLE or ambiguous
        )
        assumptions = self._assumptions_for(requirement, needs_clarification)

        cases: List[TestCase] = [
            self._build_case(
                requirement=requirement,
                criterion_id=criterion_id,
                test_type=TestType.POSITIVE,
                title=f"Positive: {self._short_title(requirement.description)}",
                objective=(
                    f"Verify the stated behaviour for {requirement.requirement_id}."
                ),
                needs_clarification=needs_clarification,
                assumptions=assumptions,
                expected_result=self._positive_expected(requirement, needs_clarification),
                steps=self._positive_steps(requirement, needs_clarification),
                test_data=self._safe_test_data(requirement, TestType.POSITIVE),
                preconditions=self._preconditions(requirement, needs_clarification),
            )
        ]

        if self._supports_negative(requirement) and not (
            requirement.testability_status == TestabilityStatus.NOT_TESTABLE
        ):
            cases.append(
                self._build_case(
                    requirement=requirement,
                    criterion_id=criterion_id,
                    test_type=TestType.NEGATIVE,
                    title=f"Negative: {self._short_title(requirement.description)}",
                    objective=(
                        f"Verify constraint handling implied by {requirement.requirement_id} "
                        "without inventing an error message."
                    ),
                    needs_clarification=True if not self._has_explicit_failure(requirement) else needs_clarification,
                    assumptions=self._negative_assumptions(requirement, assumptions),
                    expected_result=self._negative_expected(requirement),
                    steps=self._negative_steps(requirement),
                    test_data=self._safe_test_data(requirement, TestType.NEGATIVE),
                    preconditions=self._preconditions(requirement, True),
                )
            )

        if has_measurement(requirement.description) or self._has_numeric_limit(
            requirement.description
        ):
            cases.append(
                self._build_case(
                    requirement=requirement,
                    criterion_id=criterion_id,
                    test_type=TestType.BOUNDARY,
                    title=f"Boundary: {self._short_title(requirement.description)}",
                    objective=(
                        f"Exercise the stated numeric or measurable limit in "
                        f"{requirement.requirement_id}."
                    ),
                    needs_clarification=needs_clarification,
                    assumptions=assumptions,
                    expected_result=self._boundary_expected(requirement, needs_clarification),
                    steps=self._boundary_steps(requirement, needs_clarification),
                    test_data=self._safe_test_data(requirement, TestType.BOUNDARY),
                    preconditions=self._preconditions(requirement, needs_clarification),
                )
            )

        if self._supports_edge(requirement):
            cases.append(
                self._build_case(
                    requirement=requirement,
                    criterion_id=criterion_id,
                    test_type=TestType.EDGE,
                    title=f"Edge: {self._short_title(requirement.description)}",
                    objective=(
                        f"Cover an edge condition explicitly supported by "
                        f"{requirement.requirement_id}."
                    ),
                    needs_clarification=needs_clarification or True,
                    assumptions=assumptions
                    + [
                        "Edge execution path uses only conditions named in the requirement; "
                        "unspecified outcomes need clarification."
                    ],
                    expected_result=(
                        "Outcome must remain consistent with the stated requirement; "
                        "exact edge behaviour is not invented where unspecified."
                    ),
                    steps=self._edge_steps(requirement),
                    test_data=self._safe_test_data(requirement, TestType.EDGE),
                    preconditions=self._preconditions(requirement, True),
                )
            )

        if self._supports_integration(requirement):
            cases.append(
                self._build_case(
                    requirement=requirement,
                    criterion_id=criterion_id,
                    test_type=TestType.INTEGRATION,
                    title=f"Integration: {self._short_title(requirement.description)}",
                    objective=(
                        f"Verify the cross-component interaction stated in "
                        f"{requirement.requirement_id}."
                    ),
                    needs_clarification=needs_clarification,
                    assumptions=assumptions
                    + [
                        "Integration coverage is limited to interactions named in the requirement."
                    ],
                    expected_result=self._positive_expected(requirement, needs_clarification),
                    steps=self._integration_steps(requirement, needs_clarification),
                    test_data=self._safe_test_data(requirement, TestType.INTEGRATION),
                    preconditions=self._preconditions(requirement, needs_clarification),
                )
            )

        return cases

    def _build_case(
        self,
        *,
        requirement: RequirementItem,
        criterion_id: Optional[str],
        test_type: TestType,
        title: str,
        objective: str,
        needs_clarification: bool,
        assumptions: List[str],
        expected_result: str,
        steps: List[TestCaseStep],
        test_data: List[str],
        preconditions: List[str],
    ) -> TestCase:
        return TestCase(
            test_case_id="TC-PENDING",
            title=title,
            objective=objective,
            requirement_id=requirement.requirement_id,
            acceptance_criterion_id=criterion_id,
            test_type=test_type,
            priority=self._map_priority(requirement, test_type),
            preconditions=preconditions,
            test_data=test_data,
            steps=steps,
            expected_result=expected_result,
            automation_suitability=self._automation_suitability(
                requirement, needs_clarification, test_type
            ),
            assumptions=assumptions,
            needs_clarification=needs_clarification,
        )

    def _positive_steps(
        self, requirement: RequirementItem, needs_clarification: bool
    ) -> List[TestCaseStep]:
        description = requirement.description.strip()
        clarify = (
            "Record whether the observed outcome matches the requirement text; "
            "do not invent unspecified details."
            if needs_clarification
            else f"Confirm the outcome matches: {description}"
        )
        return [
            TestCaseStep(
                step_number=1,
                action=(
                    "Prepare an independently executable scenario that exercises "
                    f"requirement {requirement.requirement_id}."
                ),
                expected_result="Preconditions for the stated requirement are ready.",
            ),
            TestCaseStep(
                step_number=2,
                action=f"Perform the behaviour described by: {description}",
                expected_result=clarify,
            ),
        ]

    def _negative_steps(self, requirement: RequirementItem) -> List[TestCaseStep]:
        description = requirement.description.strip()
        return [
            TestCaseStep(
                step_number=1,
                action=(
                    "Prepare inputs that violate the constraint stated in the requirement "
                    "without inventing extra business rules."
                ),
                expected_result="Constraint-violating inputs are ready for execution.",
            ),
            TestCaseStep(
                step_number=2,
                action=f"Attempt the action related to: {description}",
                expected_result=(
                    "The system does not accept the violated constraint as a successful "
                    "completion of the requirement. Exact error text is not invented."
                ),
            ),
        ]

    def _boundary_steps(
        self, requirement: RequirementItem, needs_clarification: bool
    ) -> List[TestCaseStep]:
        limit = self._extract_measurement_phrase(requirement.description)
        action = (
            f"Execute the requirement using the stated limit ({limit})."
            if limit
            else f"Execute the measurable condition in: {requirement.description.strip()}"
        )
        expected = (
            f"Behaviour at the stated limit remains consistent with: {requirement.description.strip()}"
            if not needs_clarification
            else (
                "Observed behaviour at the stated limit is recorded; "
                "unspecified outcomes are marked for clarification."
            )
        )
        return [
            TestCaseStep(
                step_number=1,
                action="Identify the numeric or measurable limit written in the requirement.",
                expected_result="Only limits present in the requirement text are used.",
            ),
            TestCaseStep(step_number=2, action=action, expected_result=expected),
        ]

    def _edge_steps(self, requirement: RequirementItem) -> List[TestCaseStep]:
        return [
            TestCaseStep(
                step_number=1,
                action=(
                    "Set up the edge condition that is named or clearly implied by "
                    f"requirement {requirement.requirement_id}."
                ),
                expected_result="Edge condition is ready without adding unsupported rules.",
            ),
            TestCaseStep(
                step_number=2,
                action=f"Execute the behaviour for: {requirement.description.strip()}",
                expected_result=(
                    "Result stays within the stated requirement; "
                    "unspecified edge outcomes need clarification."
                ),
            ),
        ]

    def _integration_steps(
        self, requirement: RequirementItem, needs_clarification: bool
    ) -> List[TestCaseStep]:
        description = requirement.description.strip()
        return [
            TestCaseStep(
                step_number=1,
                action=(
                    "Prepare the components or channels named in the requirement "
                    "(for example email, API, or redirect) without adding others."
                ),
                expected_result="Named integration endpoints or channels are available.",
            ),
            TestCaseStep(
                step_number=2,
                action=f"Trigger the integrated behaviour: {description}",
                expected_result=(
                    f"The stated interaction completes as written: {description}"
                    if not needs_clarification
                    else (
                        "Integrated outcome is compared only to the requirement text; "
                        "missing interface details need clarification."
                    )
                ),
            ),
        ]

    def _positive_expected(
        self, requirement: RequirementItem, needs_clarification: bool
    ) -> str:
        if needs_clarification:
            return (
                f"Observed behaviour is consistent with the parts of "
                f"{requirement.requirement_id} that are testable; "
                "ambiguous details are not asserted as pass criteria."
            )
        return f"The system satisfies: {requirement.description.strip()}"

    def _negative_expected(self, requirement: RequirementItem) -> str:
        if self._has_explicit_failure(requirement):
            return (
                "The constraint stated in the requirement is enforced and the action "
                f"does not complete successfully: {requirement.description.strip()}"
            )
        return (
            "The violated constraint prevents successful completion of the requirement. "
            "Exact error messaging and recovery behaviour need clarification because "
            "they are not specified."
        )

    def _boundary_expected(
        self, requirement: RequirementItem, needs_clarification: bool
    ) -> str:
        phrase = self._extract_measurement_phrase(requirement.description)
        if phrase and not needs_clarification:
            return (
                f"Behaviour at the stated limit ({phrase}) satisfies: "
                f"{requirement.description.strip()}"
            )
        return (
            "Behaviour at the stated measurable limit matches the requirement text; "
            "values or outcomes not written in the requirement are not asserted."
        )

    def _preconditions(
        self, requirement: RequirementItem, needs_clarification: bool
    ) -> List[str]:
        preconditions = [
            f"Requirement {requirement.requirement_id} is in scope for this run.",
            "The environment can exercise the behaviour described by the requirement.",
        ]
        if needs_clarification:
            preconditions.append(
                "Clarifications may be required before treating ambiguous details as pass/fail."
            )
        return preconditions

    def _safe_test_data(
        self, requirement: RequirementItem, test_type: TestType
    ) -> List[str]:
        data: List[str] = [
            f"Use only values supported by requirement {requirement.requirement_id}."
        ]
        measurement = self._extract_measurement_phrase(requirement.description)
        if measurement and test_type in {TestType.BOUNDARY, TestType.POSITIVE}:
            data.append(f"Stated measurable value/limit from requirement: {measurement}")
        if test_type == TestType.NEGATIVE:
            data.append(
                "Provide inputs that break the stated constraint only; "
                "do not invent additional invalid categories."
            )
        if test_type == TestType.EDGE:
            data.append(
                "Use edge conditions named in the requirement text only."
            )
        return data

    def _assumptions_for(
        self, requirement: RequirementItem, needs_clarification: bool
    ) -> List[str]:
        assumptions: List[str] = []
        if needs_clarification:
            assumptions.append(
                "Ambiguous or partially testable wording is not expanded into invented rules."
            )
        vague = find_vague_terms(requirement.description)
        if vague:
            quoted = ", ".join(f"'{term}'" for term in vague)
            assumptions.append(
                f"Vague terms ({quoted}) are not turned into concrete expected values."
            )
        return assumptions

    def _negative_assumptions(
        self, requirement: RequirementItem, base: List[str]
    ) -> List[str]:
        assumptions = list(base)
        if not self._has_explicit_failure(requirement):
            assumptions.append(
                "Failure messaging and alternate paths are unspecified and need clarification."
            )
        return assumptions

    def _supports_negative(self, requirement: RequirementItem) -> bool:
        return _CONSTRAINT_PATTERN.search(requirement.description) is not None

    def _supports_edge(self, requirement: RequirementItem) -> bool:
        text = requirement.description
        if _EDGE_PATTERN.search(text):
            return True
        # Expiry and minimum/maximum wording often imply edge coverage.
        return bool(
            re.search(r"\b(expires?|at least|at most|minimum|maximum)\b", text, re.I)
        )

    def _supports_integration(self, requirement: RequirementItem) -> bool:
        return _INTEGRATION_PATTERN.search(requirement.description) is not None

    def _has_explicit_failure(self, requirement: RequirementItem) -> bool:
        return bool(
            re.search(
                r"\b(reject|rejects|must not|cannot|can not|unauthorized|invalid|prevents?)\b",
                requirement.description,
                re.I,
            )
        )

    def _has_numeric_limit(self, text: str) -> bool:
        return _NUMBER_PATTERN.search(text) is not None and bool(
            re.search(
                r"\b(character|characters|minute|minutes|second|seconds|hour|hours|"
                r"percent|%|user|users|request|requests|digit|digits)\b",
                text,
                re.I,
            )
        )

    def _extract_measurement_phrase(self, text: str) -> Optional[str]:
        match = re.search(
            r"\b\d+(?:\.\d+)?\s*(?:"
            r"ms|milliseconds?|seconds?|secs?|minutes?|mins?|hours?|"
            r"%|percent|users|requests|characters?|chars|digits"
            r")\b",
            text,
            re.I,
        )
        if match:
            return match.group(0)
        number = _NUMBER_PATTERN.search(text)
        return number.group(0) if number else None

    def _map_priority(
        self, requirement: RequirementItem, test_type: TestType
    ) -> TestPriority:
        if requirement.priority == Priority.HIGH and test_type == TestType.POSITIVE:
            return TestPriority.CRITICAL
        if requirement.priority == Priority.HIGH:
            return TestPriority.HIGH
        if requirement.priority == Priority.MEDIUM:
            return TestPriority.MEDIUM
        return TestPriority.LOW

    def _automation_suitability(
        self,
        requirement: RequirementItem,
        needs_clarification: bool,
        test_type: TestType,
    ) -> AutomationSuitability:
        if needs_clarification or requirement.testability_status != TestabilityStatus.TESTABLE:
            return AutomationSuitability.PARTIALLY_SUITABLE
        if test_type == TestType.EDGE:
            return AutomationSuitability.PARTIALLY_SUITABLE
        category = getattr(requirement, "category", None)
        if category in {"usability"}:
            return AutomationSuitability.MANUAL_ONLY
        return AutomationSuitability.SUITABLE

    def _criterion_id_for(
        self,
        requirement: RequirementItem,
        analysis: RequirementAnalysisResponse,
    ) -> Optional[str]:
        source = requirement.source_acceptance_criterion
        if source:
            for criterion in analysis.acceptance_criteria:
                if normalize_text(criterion.description) == normalize_text(source):
                    return criterion.criterion_id
        for criterion in analysis.acceptance_criteria:
            if normalize_text(criterion.description) == normalize_text(
                requirement.description
            ):
                return criterion.criterion_id
        return None

    def _is_ambiguous(
        self, requirement: RequirementItem, analysis: RequirementAnalysisResponse
    ) -> bool:
        req_norm = normalize_text(requirement.description)
        for item in analysis.ambiguities:
            if normalize_text(item.statement) == req_norm:
                return True
            if req_norm and normalize_text(item.statement) in req_norm:
                return True
        return bool(find_vague_terms(requirement.description))

    def _ground_case(
        self,
        case: TestCase,
        requirement: RequirementItem,
        analysis: RequirementAnalysisResponse,
    ) -> Optional[TestCase]:
        if requirement.testability_status == TestabilityStatus.NOT_TESTABLE:
            logger.warning(
                "Removed test case for not_testable requirement %s",
                requirement.requirement_id,
            )
            return None

        criterion_id = case.acceptance_criterion_id
        if criterion_id:
            valid = {item.criterion_id for item in analysis.acceptance_criteria}
            if criterion_id not in valid:
                criterion_id = self._criterion_id_for(requirement, analysis)
        else:
            criterion_id = self._criterion_id_for(requirement, analysis)

        needs_clarification = case.needs_clarification or (
            requirement.testability_status != TestabilityStatus.TESTABLE
        )
        expected = case.expected_result.strip()
        if not expected:
            expected = self._positive_expected(requirement, needs_clarification)

        steps = case.steps or self._positive_steps(requirement, needs_clarification)
        normalized_steps: List[TestCaseStep] = []
        for index, step in enumerate(steps, start=1):
            normalized_steps.append(
                step.model_copy(
                    update={
                        "step_number": index,
                        "action": step.action.strip(),
                        "expected_result": step.expected_result.strip(),
                    }
                )
            )

        return case.model_copy(
            update={
                "title": case.title.strip(),
                "objective": case.objective.strip(),
                "requirement_id": requirement.requirement_id,
                "acceptance_criterion_id": criterion_id,
                "expected_result": expected,
                "steps": normalized_steps,
                "needs_clarification": needs_clarification,
                "assumptions": [item.strip() for item in case.assumptions if item.strip()],
                "preconditions": [
                    item.strip() for item in case.preconditions if item.strip()
                ],
                "test_data": [item.strip() for item in case.test_data if item.strip()],
            }
        )

    def _rebuild_skipped(
        self,
        analysis: RequirementAnalysisResponse,
        cases: Sequence[TestCase],
        previous: Sequence[SkippedRequirement],
    ) -> List[SkippedRequirement]:
        covered = {case.requirement_id for case in cases}
        skipped: List[SkippedRequirement] = []
        seen: Set[str] = set()

        for requirement in self._all_requirements(analysis):
            if requirement.requirement_id in covered:
                continue
            if requirement.requirement_id in seen:
                continue
            seen.add(requirement.requirement_id)
            reason = next(
                (
                    item.reason
                    for item in previous
                    if item.requirement_id == requirement.requirement_id
                ),
                None,
            )
            if requirement.testability_status == TestabilityStatus.NOT_TESTABLE:
                reason = (
                    reason
                    or "Requirement is marked not_testable. No expected result was fabricated."
                )
            else:
                reason = (
                    reason
                    or "No independently executable test case could be derived "
                    "from the stated requirement without inventing behaviour."
                )
            skipped.append(
                SkippedRequirement(
                    requirement_id=requirement.requirement_id,
                    description=requirement.description,
                    reason=reason,
                )
            )
        return skipped

    def _assemble(
        self,
        analysis: RequirementAnalysisResponse,
        test_cases: Sequence[TestCase],
        skipped: Sequence[SkippedRequirement],
        *,
        provider: str,
        provider_note: str,
    ) -> TestCaseGenerationResponse:
        indexed = [
            case.model_copy(update={"test_case_id": f"TC-{index:03d}"})
            for index, case in enumerate(test_cases, start=1)
        ]
        status = self._determine_status(indexed, skipped)
        summary = self._summary(analysis, indexed, skipped, status)
        return TestCaseGenerationResponse(
            story_id=analysis.story_id,
            story_summary=analysis.story_summary,
            test_cases=indexed,
            skipped_requirements=list(skipped),
            generation_status=status,
            provider=provider,
            provider_note=provider_note,
            summary=summary,
        )

    def _determine_status(
        self,
        test_cases: Sequence[TestCase],
        skipped: Sequence[SkippedRequirement],
    ) -> GenerationStatus:
        if not test_cases:
            return GenerationStatus.NO_TEST_CASES
        if any(case.needs_clarification for case in test_cases):
            return GenerationStatus.NEEDS_CLARIFICATION
        if skipped:
            return GenerationStatus.PARTIAL
        return GenerationStatus.COMPLETE

    def _summary(
        self,
        analysis: RequirementAnalysisResponse,
        test_cases: Sequence[TestCase],
        skipped: Sequence[SkippedRequirement],
        status: GenerationStatus,
    ) -> str:
        type_counts: Dict[str, int] = {}
        for case in test_cases:
            type_counts[case.test_type.value] = type_counts.get(case.test_type.value, 0) + 1
        type_part = ", ".join(
            f"{count} {name}" for name, count in sorted(type_counts.items())
        ) or "none"
        return (
            f"Generated {len(test_cases)} test case(s) for story {analysis.story_id} "
            f"({type_part}). Skipped {len(skipped)} requirement(s). "
            f"Status: {status.value}."
        )

    def _all_requirements(
        self, analysis: RequirementAnalysisResponse
    ) -> List[RequirementItem]:
        return list(analysis.functional_requirements) + list(
            analysis.non_functional_requirements
        )

    def _requirement_ids(self, analysis: RequirementAnalysisResponse) -> Set[str]:
        return {item.requirement_id for item in self._all_requirements(analysis)}

    def _requirement_lookup(
        self, analysis: RequirementAnalysisResponse
    ) -> Dict[str, RequirementItem]:
        return {item.requirement_id: item for item in self._all_requirements(analysis)}

    def _dedupe_key(self, case: TestCase) -> str:
        return "|".join(
            [
                case.requirement_id,
                case.test_type.value,
                normalize_text(case.title),
                normalize_text(case.objective),
            ]
        )

    def _short_title(self, description: str, limit: int = 72) -> str:
        cleaned = " ".join(description.strip().split())
        if len(cleaned) <= limit:
            return cleaned
        return cleaned[: limit - 1].rstrip() + "…"
