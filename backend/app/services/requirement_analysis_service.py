"""Requirement analysis business rules.

The service decides which statements are requirements. A language-model
provider may echo or propose structured JSON, but a statement is kept only
when it appears in the story. Quality attributes become non-functional
requirements only when the story uses that language.
"""

import json
import re
from typing import List, Optional, Sequence

from pydantic import ValidationError

from app.core.logging import get_logger
from app.integrations.llm.base import LLMMessage
from app.schemas.requirements import (
    AcceptanceCriterion,
    Ambiguity,
    AnalysisStatus,
    FunctionalRequirement,
    NonFunctionalRequirement,
    Priority,
    RequirementAnalysisResponse,
    StoryInput,
    TestabilityStatus,
)
from app.services.requirement_rules import (
    build_clarification_questions,
    build_story_summary,
    classify_testability,
    determine_analysis_status,
    find_vague_terms,
    has_measurement,
    is_concrete,
    is_grounded,
    is_quality_only,
    normalize_text,
    split_sentences,
    story_corpus,
    supported_categories,
)

logger = get_logger(__name__)

SYSTEM_PROMPT = (
    "You analyze a software user story for a QA team. Return JSON only. "
    "Extract functional requirements that are explicitly written in the story. "
    "Include a non-functional requirement only when the story states that quality "
    "attribute. Do not invent actors, business rules, scope, or metrics. "
    "Flag vague language as ambiguities and ask clarification questions instead of guessing."
)

_SOURCE_TITLE = "title"
_SOURCE_DESCRIPTION = "description"
_SOURCE_ACCEPTANCE = "acceptance_criteria"


class RequirementAnalysisService:
    """Build, validate, and ground a requirement analysis for one story."""

    def build_draft(self, story: StoryInput) -> RequirementAnalysisResponse:
        functional = self._functional_requirements(story)
        non_functional = self._non_functional_requirements(story)
        ambiguities = self._ambiguities(story)
        return self._assemble(
            story,
            functional,
            non_functional,
            ambiguities,
            provider="deterministic",
            provider_note="Draft produced from the story text before provider review.",
        )

    def build_messages(
        self,
        story: StoryInput,
        draft: RequirementAnalysisResponse,
    ) -> List[LLMMessage]:
        payload = {
            "task": "analyze_requirements",
            "instructions": (
                "Return the draft_analysis JSON without adding requirements. "
                "Do not invent behavior that is absent from the story."
            ),
            "story": story.model_dump(mode="json"),
            "draft_analysis": draft.model_dump(mode="json"),
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
        story: StoryInput,
        draft: RequirementAnalysisResponse,
        *,
        provider: str,
    ) -> RequirementAnalysisResponse:
        """Parse provider JSON, drop anything the story does not support, and recompute status."""
        provider_name = provider or "unspecified"
        note = "Structured output was checked against the story text."
        analysis_payload, provider_name, note = self._unwrap_provider_payload(
            content,
            provider_name,
            note,
        )
        if analysis_payload is None:
            return self.apply_provider(draft, provider_name, note)

        try:
            parsed = RequirementAnalysisResponse.model_validate(analysis_payload)
        except ValidationError as exc:
            logger.warning("Provider output failed schema validation: %s", exc)
            return self.apply_provider(
                draft,
                provider_name,
                "Deterministic analysis was kept because the provider output did not match the schema.",
            )

        corpus = self._corpus(story)
        functional = self._merge_functional(
            draft.functional_requirements,
            parsed.functional_requirements,
            corpus,
            story,
        )
        non_functional = self._merge_non_functional(
            draft.non_functional_requirements,
            parsed.non_functional_requirements,
            corpus,
        )
        ambiguities = self._merge_ambiguities(
            draft.ambiguities,
            parsed.ambiguities,
            corpus,
        )
        return self._assemble(
            story,
            functional,
            non_functional,
            ambiguities,
            provider=provider_name,
            provider_note=note,
        )

    def apply_provider(
        self,
        analysis: RequirementAnalysisResponse,
        provider: str,
        provider_note: str,
    ) -> RequirementAnalysisResponse:
        return analysis.model_copy(
            update={"provider": provider, "provider_note": provider_note}
        )

    def _unwrap_provider_payload(
        self,
        content: str,
        provider_name: str,
        note: str,
    ) -> tuple:
        try:
            payload = json.loads(content)
        except json.JSONDecodeError:
            logger.warning("Provider returned non-JSON output. Using deterministic analysis.")
            return (
                None,
                provider_name,
                "Deterministic analysis was kept because the provider output was not valid JSON.",
            )

        if not isinstance(payload, dict):
            logger.warning("Provider returned a non-object payload. Using deterministic analysis.")
            return (
                None,
                provider_name,
                "Deterministic analysis was kept because the provider output was not a JSON object.",
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
            return payload.get("analysis"), provider_name, note

        return payload, provider_name, note

    def _functional_requirements(self, story: StoryInput) -> List[FunctionalRequirement]:
        requirements: List[FunctionalRequirement] = []
        for criterion in story.acceptance_criteria:
            requirements.append(
                self._functional(
                    description=criterion,
                    priority=Priority.HIGH,
                    source=criterion,
                )
            )

        covered = [item.description for item in requirements]
        for sentence in split_sentences(story.description):
            if self._already_covered(sentence, covered):
                continue
            if is_quality_only(sentence):
                continue
            if not is_concrete(sentence):
                continue
            requirements.append(
                self._functional(
                    description=sentence,
                    priority=Priority.MEDIUM,
                    source=None,
                )
            )
            covered.append(sentence)
        return requirements

    def _functional(
        self,
        *,
        description: str,
        priority: Priority,
        source: Optional[str],
    ) -> FunctionalRequirement:
        return FunctionalRequirement(
            requirement_id="FR-PENDING",
            description=description,
            priority=priority,
            source_acceptance_criterion=source,
            testability_status=TestabilityStatus(classify_testability(description)),
        )

    def _non_functional_requirements(
        self, story: StoryInput
    ) -> List[NonFunctionalRequirement]:
        statements = self._candidate_statements(story)
        requirements: List[NonFunctionalRequirement] = []
        seen = set()
        for source_name, text in statements:
            for category in supported_categories(text):
                key = (normalize_text(text), category)
                if key in seen:
                    continue
                seen.add(key)
                source = text if source_name == _SOURCE_ACCEPTANCE else None
                priority = Priority.LOW
                testability = TestabilityStatus(classify_testability(text))
                if category == "security" and testability == TestabilityStatus.TESTABLE:
                    priority = Priority.HIGH
                elif testability != TestabilityStatus.NOT_TESTABLE:
                    priority = Priority.MEDIUM
                requirements.append(
                    NonFunctionalRequirement(
                        requirement_id="NFR-PENDING",
                        description=text,
                        priority=priority,
                        source_acceptance_criterion=source,
                        testability_status=testability,
                        category=category,
                    )
                )
        return requirements

    def _ambiguities(self, story: StoryInput) -> List[Ambiguity]:
        ambiguities: List[Ambiguity] = []
        seen = set()
        for source_name, text in self._candidate_statements(story):
            terms = find_vague_terms(text)
            key = normalize_text(text)
            if not terms or key in seen:
                continue
            seen.add(key)
            quoted = ", ".join(f"'{term}'" for term in terms)
            ambiguities.append(
                Ambiguity(
                    ambiguity_id="AMB-PENDING",
                    statement=text,
                    reason=f"Contains vague language ({quoted}) that is not measurable.",
                    source=source_name,  # type: ignore[arg-type]
                )
            )
        return ambiguities

    def _candidate_statements(self, story: StoryInput) -> List[tuple]:
        statements: List[tuple] = []
        if story.title.strip():
            statements.append((_SOURCE_TITLE, story.title.strip()))
        for sentence in split_sentences(story.description):
            statements.append((_SOURCE_DESCRIPTION, sentence))
        for criterion in story.acceptance_criteria:
            statements.append((_SOURCE_ACCEPTANCE, criterion))
        return statements

    def _assemble(
        self,
        story: StoryInput,
        functional: Sequence[FunctionalRequirement],
        non_functional: Sequence[NonFunctionalRequirement],
        ambiguities: Sequence[Ambiguity],
        *,
        provider: str,
        provider_note: str,
    ) -> RequirementAnalysisResponse:
        indexed_functional = self._index_functional(list(functional), story)
        indexed_non_functional = self._index_non_functional(list(non_functional))
        indexed_ambiguities = self._index_ambiguities(list(ambiguities))
        questions = build_clarification_questions(
            title=story.title,
            description=story.description,
            acceptance_criteria=story.acceptance_criteria,
            ambiguous_statements=[item.statement for item in indexed_ambiguities],
        )
        status = AnalysisStatus(
            determine_analysis_status(
                description=story.description,
                acceptance_criteria=story.acceptance_criteria,
                title=story.title,
                ambiguity_count=len(indexed_ambiguities),
                testability_statuses=[
                    item.testability_status.value for item in indexed_functional
                ],
            )
        )
        return RequirementAnalysisResponse(
            story_id=self._story_id(story),
            story_summary=build_story_summary(story.title, story.description),
            functional_requirements=indexed_functional,
            non_functional_requirements=indexed_non_functional,
            acceptance_criteria=self._acceptance_criteria(story),
            ambiguities=indexed_ambiguities,
            clarification_questions=questions,
            analysis_status=status,
            provider=provider,
            provider_note=provider_note,
        )

    def _index_functional(
        self,
        items: List[FunctionalRequirement],
        story: StoryInput,
    ) -> List[FunctionalRequirement]:
        indexed: List[FunctionalRequirement] = []
        for index, item in enumerate(items, start=1):
            source = self._matching_criterion(item, story)
            description = item.description.strip()
            indexed.append(
                item.model_copy(
                    update={
                        "requirement_id": f"FR-{index:03d}",
                        "description": description,
                        "source_acceptance_criterion": source,
                        "testability_status": TestabilityStatus(
                            classify_testability(description)
                        ),
                        "priority": Priority.HIGH if source else Priority.MEDIUM,
                    }
                )
            )
        return indexed

    def _index_non_functional(
        self, items: List[NonFunctionalRequirement]
    ) -> List[NonFunctionalRequirement]:
        indexed: List[NonFunctionalRequirement] = []
        for item in items:
            description = item.description.strip()
            categories = supported_categories(description)
            if not categories:
                logger.warning(
                    "Skipped non-functional requirement with no supporting quality language: %s",
                    description[:160],
                )
                continue
            index = len(indexed) + 1
            category = item.category if item.category in categories else categories[0]
            testability = TestabilityStatus(classify_testability(description))
            if category == "security" and testability == TestabilityStatus.TESTABLE:
                priority = Priority.HIGH
            elif testability == TestabilityStatus.NOT_TESTABLE:
                priority = Priority.LOW
            else:
                priority = Priority.MEDIUM
            indexed.append(
                item.model_copy(
                    update={
                        "requirement_id": f"NFR-{index:03d}",
                        "description": description,
                        "category": category,
                        "testability_status": testability,
                        "priority": priority,
                    }
                )
            )
        return indexed

    def _index_ambiguities(self, items: List[Ambiguity]) -> List[Ambiguity]:
        indexed: List[Ambiguity] = []
        for index, item in enumerate(items, start=1):
            terms = find_vague_terms(item.statement)
            quoted = ", ".join(f"'{term}'" for term in terms) or "unspecified language"
            indexed.append(
                item.model_copy(
                    update={
                        "ambiguity_id": f"AMB-{index:03d}",
                        "reason": (
                            f"Contains vague language ({quoted}) that is not measurable."
                        ),
                    }
                )
            )
        return indexed

    def _acceptance_criteria(self, story: StoryInput) -> List[AcceptanceCriterion]:
        return [
            AcceptanceCriterion(
                criterion_id=f"AC-{index:03d}",
                description=criterion,
                testability_status=TestabilityStatus(classify_testability(criterion)),
            )
            for index, criterion in enumerate(story.acceptance_criteria, start=1)
        ]

    def _merge_functional(
        self,
        draft_items: Sequence[FunctionalRequirement],
        parsed_items: Sequence[FunctionalRequirement],
        corpus: str,
        story: StoryInput,
    ) -> List[FunctionalRequirement]:
        return self._merge_by_description(
            list(draft_items),
            list(parsed_items),
            corpus,
            story,
        )

    def _merge_by_description(
        self,
        draft_items: List[FunctionalRequirement],
        parsed_items: List[FunctionalRequirement],
        corpus: str,
        story: StoryInput,
    ) -> List[FunctionalRequirement]:
        merged: List[FunctionalRequirement] = []
        seen = set()
        for item in list(draft_items) + list(parsed_items):
            description = item.description.strip()
            key = normalize_text(description)
            if not key or key in seen:
                continue
            if not is_grounded(description, corpus):
                logger.warning(
                    "Removed functional requirement not present in the story: %s",
                    description[:160],
                )
                continue
            if not self._allowed_functional(description, story):
                logger.warning(
                    "Removed functional requirement that is not an acceptance criterion "
                    "or a concrete story statement: %s",
                    description[:160],
                )
                continue
            seen.add(key)
            merged.append(item.model_copy(update={"description": description}))
        return merged

    def _allowed_functional(self, description: str, story: StoryInput) -> bool:
        normalized = normalize_text(description)
        for criterion in story.acceptance_criteria:
            if normalize_text(criterion) == normalized:
                return True
        for sentence in split_sentences(story.description):
            if normalize_text(sentence) != normalized:
                continue
            if is_quality_only(sentence):
                return False
            return is_concrete(sentence) or has_measurement(sentence)
        return False

    def _merge_non_functional(
        self,
        draft_items: Sequence[NonFunctionalRequirement],
        parsed_items: Sequence[NonFunctionalRequirement],
        corpus: str,
    ) -> List[NonFunctionalRequirement]:
        merged: List[NonFunctionalRequirement] = []
        seen = set()
        for item in list(draft_items) + list(parsed_items):
            description = item.description.strip()
            categories = supported_categories(description)
            if not categories:
                logger.warning(
                    "Removed non-functional requirement with no quality attribute "
                    "in the story: %s",
                    description[:160],
                )
                continue
            category = item.category if item.category in categories else categories[0]
            key = (normalize_text(description), category)
            if key in seen:
                continue
            if not is_grounded(description, corpus):
                logger.warning(
                    "Removed non-functional requirement not present in the story: %s",
                    description[:160],
                )
                continue
            seen.add(key)
            merged.append(
                item.model_copy(update={"description": description, "category": category})
            )
        return merged

    def _merge_ambiguities(
        self,
        draft_items: Sequence[Ambiguity],
        parsed_items: Sequence[Ambiguity],
        corpus: str,
    ) -> List[Ambiguity]:
        merged: List[Ambiguity] = []
        seen = set()
        for item in list(draft_items) + list(parsed_items):
            statement = item.statement.strip()
            key = normalize_text(statement)
            if not key or key in seen:
                continue
            if not is_grounded(statement, corpus) or not find_vague_terms(statement):
                logger.warning(
                    "Removed ambiguity that is not a vague statement in the story: %s",
                    statement[:160],
                )
                continue
            seen.add(key)
            merged.append(item.model_copy(update={"statement": statement}))
        return merged

    def _matching_criterion(
        self, item: FunctionalRequirement, story: StoryInput
    ) -> Optional[str]:
        normalized = normalize_text(item.description)
        for criterion in story.acceptance_criteria:
            if normalize_text(criterion) == normalized:
                return criterion
        source = item.source_acceptance_criterion
        if source:
            for criterion in story.acceptance_criteria:
                if normalize_text(criterion) == normalize_text(source):
                    return criterion
        return None

    def _already_covered(self, sentence: str, existing: Sequence[str]) -> bool:
        normalized = normalize_text(sentence)
        for other in existing:
            other_normalized = normalize_text(other)
            if (
                normalized == other_normalized
                or normalized in other_normalized
                or other_normalized in normalized
            ):
                return True
        return False

    def _story_id(self, story: StoryInput) -> str:
        if story.story_id:
            return story.story_id
        slug = re.sub(r"[^a-z0-9]+", "-", story.title.lower()).strip("-")
        return f"local-{slug[:48] or 'untitled'}"

    def _corpus(self, story: StoryInput) -> str:
        return story_corpus(story.title, story.description, story.acceptance_criteria)
