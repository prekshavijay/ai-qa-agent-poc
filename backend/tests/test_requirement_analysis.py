"""Requirement analysis API tests."""

import asyncio
import json

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from app.agents.requirement_analysis_agent import RequirementAnalysisAgent
from app.integrations.llm.base import LLMClient, LLMNotConfiguredError, LLMResponse
from app.main import app
from app.schemas.requirements import RequirementAnalysisResponse, StoryInput

client = TestClient(app)

VALID_STORY = {
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


def _source_text(story: dict) -> str:
    parts = [story.get("title", ""), story.get("description", ""), *story.get("acceptance_criteria", [])]
    return " ".join(part.lower() for part in parts if part)


def _assert_grounded(payload: dict, story: dict) -> None:
    corpus = _source_text(story)
    for item in payload["functional_requirements"] + payload["non_functional_requirements"]:
        assert item["description"].lower() in corpus
    for item in payload["ambiguities"]:
        assert item["statement"].lower() in corpus
    for question in payload["clarification_questions"]:
        assert question.endswith("?")


def test_analyze_valid_story() -> None:
    response = client.post("/api/requirements/analyze", json=VALID_STORY)
    assert response.status_code == 200
    payload = response.json()

    assert payload["story_id"] == "STORY-101"
    assert payload["story_summary"].startswith("Reset password:")
    assert payload["analysis_status"] == "complete"
    assert payload["provider"] == "mock"
    assert "no external language model was called" in payload["provider_note"].lower()
    assert payload["ambiguities"] == []
    assert payload["clarification_questions"] == []
    assert payload["non_functional_requirements"] == []

    descriptions = [item["description"] for item in payload["functional_requirements"]]
    for criterion in VALID_STORY["acceptance_criteria"]:
        assert criterion in descriptions

    ids = [item["requirement_id"] for item in payload["functional_requirements"]]
    assert ids[0] == "FR-001"
    assert len(ids) == len(set(ids))
    for item in payload["functional_requirements"]:
        assert item["testability_status"] == "testable"
        assert item["priority"] in {"high", "medium", "low"}
    _assert_grounded(payload, VALID_STORY)

    criterion_ids = [item["criterion_id"] for item in payload["acceptance_criteria"]]
    assert criterion_ids == ["AC-001", "AC-002", "AC-003"]


def test_empty_title_validation() -> None:
    response = client.post(
        "/api/requirements/analyze",
        json={
            "title": "   ",
            "description": "A user can save a draft.",
            "acceptance_criteria": ["The draft is stored."],
        },
    )
    assert response.status_code == 422
    body = response.json()
    assert body["error"]["code"] == "validation_error"
    assert "title" in json.dumps(body["error"]["details"]).lower()


def test_story_with_no_acceptance_criteria() -> None:
    story = {
        "title": "View order history",
        "description": "A customer can view their past orders on the account page.",
        "acceptance_criteria": [],
    }
    response = client.post("/api/requirements/analyze", json=story)
    assert response.status_code == 200
    payload = response.json()

    assert payload["analysis_status"] == "needs_clarification"
    assert payload["acceptance_criteria"] == []
    assert payload["functional_requirements"]
    assert payload["functional_requirements"][0]["description"] == story["description"]
    assert payload["functional_requirements"][0]["source_acceptance_criterion"] is None
    assert any(
        "acceptance criteria" in question.lower()
        for question in payload["clarification_questions"]
    )
    assert payload["non_functional_requirements"] == []
    _assert_grounded(payload, story)


def test_ambiguous_requirements() -> None:
    story = {
        "title": "Improve search",
        "description": "Search should be fast and user-friendly.",
        "acceptance_criteria": [
            "Results appear quickly",
            "The experience feels modern",
        ],
    }
    response = client.post("/api/requirements/analyze", json=story)
    assert response.status_code == 200
    payload = response.json()

    assert payload["analysis_status"] == "needs_clarification"
    assert len(payload["ambiguities"]) >= 2
    combined = " ".join(
        f"{item['statement']} {item['reason']}" for item in payload["ambiguities"]
    ).lower()
    assert "fast" in combined
    assert "user-friendly" in combined or "user friendly" in combined
    assert payload["clarification_questions"]

    categories = {item["category"] for item in payload["non_functional_requirements"]}
    assert "performance" in categories
    assert "usability" in categories
    for item in payload["functional_requirements"]:
        if "quickly" in item["description"].lower() or "modern" in item["description"].lower():
            assert item["testability_status"] in {"partially_testable", "not_testable"}
    _assert_grounded(payload, story)


def test_missing_description() -> None:
    story = {
        "title": "Export invoices",
        "description": "",
        "acceptance_criteria": [],
    }
    response = client.post("/api/requirements/analyze", json=story)
    assert response.status_code == 200
    payload = response.json()

    assert payload["analysis_status"] == "insufficient_input"
    assert payload["functional_requirements"] == []
    assert payload["non_functional_requirements"] == []
    assert "does not include a description" in payload["story_summary"].lower()
    assert any(
        "description" in question.lower() for question in payload["clarification_questions"]
    )
    _assert_grounded(payload, story)


def test_structured_response_validation() -> None:
    response = client.post("/api/requirements/analyze", json=VALID_STORY)
    assert response.status_code == 200
    payload = response.json()
    validated = RequirementAnalysisResponse.model_validate(payload)
    assert validated.story_id == "STORY-101"
    assert validated.analysis_status.value == "complete"

    incomplete = dict(payload)
    del incomplete["analysis_status"]
    with pytest.raises(ValidationError):
        RequirementAnalysisResponse.model_validate(incomplete)


def test_requirements_health() -> None:
    response = client.get("/api/requirements/health")
    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "ok"
    assert payload["module"] == "requirement_analysis"
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

    agent = RequirementAnalysisAgent(llm_client=UnavailableClient())
    result = asyncio.run(agent.analyze(StoryInput(**VALID_STORY)))
    assert result.provider == "unavailable"
    assert "no requirements were invented" in result.provider_note.lower()
    assert result.functional_requirements
    assert result.analysis_status.value == "complete"


def test_ungrounded_provider_requirement_is_removed() -> None:
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
                "story_summary": "Invented summary about billing exports.",
                "functional_requirements": [
                    {
                        "requirement_id": "FR-999",
                        "description": "The system emails a monthly invoice to finance.",
                        "priority": "high",
                        "source_acceptance_criterion": None,
                        "testability_status": "testable",
                    }
                ],
                "non_functional_requirements": [
                    {
                        "requirement_id": "NFR-999",
                        "description": "The service must be available 99.9 percent of the time.",
                        "priority": "high",
                        "source_acceptance_criterion": None,
                        "testability_status": "testable",
                        "category": "reliability",
                    }
                ],
                "acceptance_criteria": [],
                "ambiguities": [
                    {
                        "ambiguity_id": "AMB-999",
                        "statement": "Make the experience delightful.",
                        "reason": "Invented.",
                        "source": "description",
                    }
                ],
                "clarification_questions": ["Should we add a blockchain audit trail?"],
                "analysis_status": "complete",
                "provider": "test",
                "provider_note": "pretend model",
            }
            return LLMResponse(content=json.dumps(invented), model="test", provider="test")

        async def is_available(self) -> bool:
            return True

    agent = RequirementAnalysisAgent(llm_client=InventingClient())
    result = asyncio.run(agent.analyze(StoryInput(**VALID_STORY)))
    descriptions = [item.description for item in result.functional_requirements]
    assert "The system emails a monthly invoice to finance." not in descriptions
    assert all(
        "99.9" not in item.description for item in result.non_functional_requirements
    )
    assert all("delightful" not in item.statement for item in result.ambiguities)
    assert all("blockchain" not in question.lower() for question in result.clarification_questions)
    assert result.story_summary.startswith("Reset password:")
    for criterion in VALID_STORY["acceptance_criteria"]:
        assert criterion in descriptions
