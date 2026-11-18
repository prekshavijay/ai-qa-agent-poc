"""Test case generation API tests."""

import asyncio
import json
from copy import deepcopy

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from app.agents.test_case_generation_agent import TestCaseGenerationAgent
from app.integrations.llm.base import LLMClient, LLMNotConfiguredError, LLMResponse
from app.main import app
from app.schemas.test_cases import TestCaseGenerationResponse
from app.services.test_case_generation_service import TestCaseGenerationService

client = TestClient(app)

COMPLETE_ANALYSIS = {
    "story_id": "STORY-101",
    "story_summary": "Reset password: A registered user can request a password reset link.",
    "functional_requirements": [
        {
            "requirement_id": "FR-001",
            "description": (
                "Given a registered email, when the user submits the reset form, "
                "then the system sends a reset link to that email."
            ),
            "priority": "high",
            "source_acceptance_criterion": (
                "Given a registered email, when the user submits the reset form, "
                "then the system sends a reset link to that email."
            ),
            "testability_status": "testable",
        },
        {
            "requirement_id": "FR-002",
            "description": "The reset link expires after 30 minutes.",
            "priority": "high",
            "source_acceptance_criterion": "The reset link expires after 30 minutes.",
            "testability_status": "testable",
        },
        {
            "requirement_id": "FR-003",
            "description": "The new password must contain at least 8 characters.",
            "priority": "high",
            "source_acceptance_criterion": (
                "The new password must contain at least 8 characters."
            ),
            "testability_status": "testable",
        },
    ],
    "non_functional_requirements": [],
    "acceptance_criteria": [
        {
            "criterion_id": "AC-001",
            "description": (
                "Given a registered email, when the user submits the reset form, "
                "then the system sends a reset link to that email."
            ),
            "testability_status": "testable",
        },
        {
            "criterion_id": "AC-002",
            "description": "The reset link expires after 30 minutes.",
            "testability_status": "testable",
        },
        {
            "criterion_id": "AC-003",
            "description": "The new password must contain at least 8 characters.",
            "testability_status": "testable",
        },
    ],
    "ambiguities": [],
    "clarification_questions": [],
    "analysis_status": "complete",
    "provider": "mock",
    "provider_note": "Deterministic mock provider. No external language model was called.",
}


def _generate(payload: dict):
    return client.post("/api/test-cases/generate", json=payload)


def test_successful_test_case_generation() -> None:
    response = _generate(COMPLETE_ANALYSIS)
    assert response.status_code == 200
    payload = response.json()

    assert payload["story_id"] == "STORY-101"
    assert payload["provider"] == "mock"
    assert "no external language model was called" in payload["provider_note"].lower()
    assert payload["test_cases"]
    assert payload["generation_status"] in {
        "complete",
        "partial",
        "needs_clarification",
    }
    assert payload["summary"]

    types = {case["test_type"] for case in payload["test_cases"]}
    assert "positive" in types
    assert all(case["test_case_id"].startswith("TC-") for case in payload["test_cases"])
    assert all(case["steps"] for case in payload["test_cases"])


def test_requirement_id_traceability() -> None:
    response = _generate(COMPLETE_ANALYSIS)
    assert response.status_code == 200
    payload = response.json()

    valid_ids = {
        item["requirement_id"] for item in COMPLETE_ANALYSIS["functional_requirements"]
    }
    for case in payload["test_cases"]:
        assert case["requirement_id"] in valid_ids


def test_acceptance_criterion_mapping() -> None:
    response = _generate(COMPLETE_ANALYSIS)
    assert response.status_code == 200
    payload = response.json()

    mapped = [
        case
        for case in payload["test_cases"]
        if case["requirement_id"] == "FR-001"
    ]
    assert mapped
    assert all(case["acceptance_criterion_id"] == "AC-001" for case in mapped)

    valid_criteria = {
        item["criterion_id"] for item in COMPLETE_ANALYSIS["acceptance_criteria"]
    }
    for case in payload["test_cases"]:
        if case["acceptance_criterion_id"] is not None:
            assert case["acceptance_criterion_id"] in valid_criteria


def test_positive_and_negative_cases() -> None:
    response = _generate(COMPLETE_ANALYSIS)
    assert response.status_code == 200
    payload = response.json()

    by_type = {}
    for case in payload["test_cases"]:
        by_type.setdefault(case["test_type"], []).append(case)

    assert by_type.get("positive")
    assert by_type.get("negative")

    password_negatives = [
        case
        for case in by_type["negative"]
        if case["requirement_id"] == "FR-003"
    ]
    assert password_negatives
    assert any(
        "clarification" in " ".join(case["assumptions"]).lower()
        or case["needs_clarification"]
        for case in password_negatives
    )


def test_boundary_and_edge_cases_where_supported() -> None:
    response = _generate(COMPLETE_ANALYSIS)
    assert response.status_code == 200
    payload = response.json()

    types_by_requirement = {}
    for case in payload["test_cases"]:
        types_by_requirement.setdefault(case["requirement_id"], set()).add(
            case["test_type"]
        )

    assert "boundary" in types_by_requirement["FR-002"]
    assert "boundary" in types_by_requirement["FR-003"]
    assert "edge" in types_by_requirement["FR-002"]
    assert "integration" in types_by_requirement["FR-001"]


def test_ambiguous_requirements() -> None:
    analysis = {
        "story_id": "STORY-AMB",
        "story_summary": "Improve search: Search should be fast and user-friendly.",
        "functional_requirements": [
            {
                "requirement_id": "FR-001",
                "description": "Results appear quickly",
                "priority": "high",
                "source_acceptance_criterion": "Results appear quickly",
                "testability_status": "partially_testable",
            }
        ],
        "non_functional_requirements": [
            {
                "requirement_id": "NFR-001",
                "description": "Search should be fast and user-friendly.",
                "priority": "medium",
                "source_acceptance_criterion": None,
                "testability_status": "not_testable",
                "category": "performance",
            }
        ],
        "acceptance_criteria": [
            {
                "criterion_id": "AC-001",
                "description": "Results appear quickly",
                "testability_status": "partially_testable",
            }
        ],
        "ambiguities": [
            {
                "ambiguity_id": "AMB-001",
                "statement": "Results appear quickly",
                "reason": "Contains vague language ('quickly').",
                "source": "acceptance_criteria",
            }
        ],
        "clarification_questions": [
            'What measurable outcome replaces the vague statement: "Results appear quickly"?'
        ],
        "analysis_status": "needs_clarification",
        "provider": "mock",
        "provider_note": "Deterministic mock provider. No external language model was called.",
    }

    response = _generate(analysis)
    assert response.status_code == 200
    payload = response.json()

    skipped_ids = {item["requirement_id"] for item in payload["skipped_requirements"]}
    assert "NFR-001" in skipped_ids
    assert all(
        "not_testable" in item["reason"].lower() or "fabricated" in item["reason"].lower()
        for item in payload["skipped_requirements"]
        if item["requirement_id"] == "NFR-001"
    )

    fr_cases = [case for case in payload["test_cases"] if case["requirement_id"] == "FR-001"]
    assert fr_cases
    assert all(case["needs_clarification"] for case in fr_cases)
    assert payload["generation_status"] == "needs_clarification"


def test_empty_requirements() -> None:
    analysis = {
        "story_id": "STORY-EMPTY",
        "story_summary": "'Export invoices' does not include a description.",
        "functional_requirements": [],
        "non_functional_requirements": [],
        "acceptance_criteria": [],
        "ambiguities": [],
        "clarification_questions": ["What user or system behavior should the story description cover?"],
        "analysis_status": "insufficient_input",
        "provider": "mock",
        "provider_note": "Deterministic mock provider. No external language model was called.",
    }
    response = _generate(analysis)
    assert response.status_code == 200
    payload = response.json()
    assert payload["test_cases"] == []
    assert payload["generation_status"] == "no_test_cases"
    assert payload["skipped_requirements"] == []


def test_invalid_input() -> None:
    response = _generate({"story_id": "STORY-X"})
    assert response.status_code == 422
    body = response.json()
    assert body["error"]["code"] == "validation_error"

    blank = deepcopy(COMPLETE_ANALYSIS)
    blank["story_id"] = "   "
    response = _generate(blank)
    assert response.status_code == 422


def test_duplicate_prevention() -> None:
    service = TestCaseGenerationService()
    from app.schemas.requirements import RequirementAnalysisResponse

    analysis = RequirementAnalysisResponse.model_validate(COMPLETE_ANALYSIS)
    draft = service.build_draft(analysis)
    duplicated = draft.model_copy(
        update={"test_cases": list(draft.test_cases) + list(draft.test_cases)}
    )
    envelope = {
        "mock": True,
        "note": "Deterministic mock provider. No external language model was called.",
        "generation": duplicated.model_dump(mode="json"),
    }
    result = service.validate_structured_output(
        json.dumps(envelope),
        analysis,
        draft,
        provider="mock",
    )
    keys = {
        (case.requirement_id, case.test_type.value, case.title.lower())
        for case in result.test_cases
    }
    assert len(keys) == len(result.test_cases)


def test_structured_response_validation() -> None:
    response = _generate(COMPLETE_ANALYSIS)
    assert response.status_code == 200
    payload = response.json()
    validated = TestCaseGenerationResponse.model_validate(payload)
    assert validated.story_id == "STORY-101"

    incomplete = dict(payload)
    del incomplete["generation_status"]
    with pytest.raises(ValidationError):
        TestCaseGenerationResponse.model_validate(incomplete)


def test_test_cases_health() -> None:
    response = client.get("/api/test-cases/health")
    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "ok"
    assert payload["module"] == "test_case_generation"
    assert payload["llm_provider"] == "mock"
    assert payload["mock_implementation"] is True
    assert "no external language model" in payload["note"].lower()


def test_provider_failure_keeps_deterministic_draft() -> None:
    class UnavailableClient(LLMClient):
        provider_name = "unconfigured"

        async def complete(
            self,
            messages: list,
            *,
            model: str = None,
            temperature: float = 0.2,
            max_tokens: int = None,
            **kwargs: object,
        ) -> LLMResponse:
            del messages, model, temperature, max_tokens, kwargs
            raise LLMNotConfiguredError("provider is not configured")

        async def is_available(self) -> bool:
            return False

    from app.schemas.requirements import RequirementAnalysisResponse

    agent = TestCaseGenerationAgent(llm_client=UnavailableClient())
    result = asyncio.run(
        agent.generate(RequirementAnalysisResponse.model_validate(COMPLETE_ANALYSIS))
    )
    assert result.provider == "unavailable"
    assert "no test behaviour was invented" in result.provider_note.lower()
    assert result.test_cases


def test_invented_requirement_mapping_is_removed() -> None:
    class InventingClient(LLMClient):
        provider_name = "test"

        async def complete(
            self,
            messages: list,
            *,
            model: str = None,
            temperature: float = 0.2,
            max_tokens: int = None,
            **kwargs: object,
        ) -> LLMResponse:
            del messages, model, temperature, max_tokens, kwargs
            invented = {
                "story_id": "STORY-101",
                "story_summary": "Invented",
                "test_cases": [
                    {
                        "test_case_id": "TC-999",
                        "title": "Invented billing export",
                        "objective": "Invented objective",
                        "requirement_id": "FR-999",
                        "acceptance_criterion_id": "AC-999",
                        "test_type": "positive",
                        "priority": "critical",
                        "preconditions": [],
                        "test_data": [],
                        "steps": [
                            {
                                "step_number": 1,
                                "action": "Export invoices",
                                "expected_result": "File downloaded",
                            }
                        ],
                        "expected_result": "Invented pass",
                        "automation_suitability": "suitable",
                        "assumptions": [],
                        "needs_clarification": False,
                    }
                ],
                "skipped_requirements": [],
                "generation_status": "complete",
                "provider": "test",
                "provider_note": "pretend model",
                "summary": "Invented summary",
            }
            return LLMResponse(content=json.dumps(invented), model="test", provider="test")

        async def is_available(self) -> bool:
            return True

    from app.schemas.requirements import RequirementAnalysisResponse

    agent = TestCaseGenerationAgent(llm_client=InventingClient())
    result = asyncio.run(
        agent.generate(RequirementAnalysisResponse.model_validate(COMPLETE_ANALYSIS))
    )
    assert all(case.requirement_id != "FR-999" for case in result.test_cases)
    assert all(case.requirement_id.startswith("FR-") for case in result.test_cases)
    assert result.story_summary.startswith("Reset password:")


def test_end_to_end_analyze_then_generate() -> None:
    story = {
        "story_id": "STORY-101",
        "project_id": "PROJ-1",
        "title": "Reset password",
        "description": (
            "A registered user can request a password reset link and set a new password."
        ),
        "acceptance_criteria": [
            "Given a registered email, when the user submits the reset form, then the system sends a reset link to that email.",
            "The reset link expires after 30 minutes.",
            "The new password must contain at least 8 characters.",
        ],
    }
    analysis_response = client.post("/api/requirements/analyze", json=story)
    assert analysis_response.status_code == 200
    analysis = analysis_response.json()

    generation_response = _generate(analysis)
    assert generation_response.status_code == 200
    payload = generation_response.json()
    assert payload["story_id"] == "STORY-101"
    assert payload["test_cases"]
    valid_ids = {
        item["requirement_id"]
        for item in analysis["functional_requirements"]
        + analysis["non_functional_requirements"]
    }
    for case in payload["test_cases"]:
        assert case["requirement_id"] in valid_ids
