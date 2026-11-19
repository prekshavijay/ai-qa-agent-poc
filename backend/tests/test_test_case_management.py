"""QA review and test case management API tests."""

from __future__ import annotations

import uuid
from copy import deepcopy
from typing import Dict, Optional, Tuple

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)

BASE_ANALYSIS = {
    "story_id": "STORY-MGMT",
    "story_summary": "Reset password flow for management tests.",
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
    ],
    "ambiguities": [],
    "clarification_questions": [],
    "analysis_status": "complete",
    "provider": "mock",
    "provider_note": "Deterministic mock provider. No external language model was called.",
}


def _story_id() -> str:
    return f"STORY-MGMT-{uuid.uuid4().hex[:10]}"


def _generate(story_id: Optional[str] = None) -> Tuple[Dict, Dict]:
    """Generate cases (Step 3 also persists them for QA review)."""
    analysis = deepcopy(BASE_ANALYSIS)
    analysis["story_id"] = story_id or _story_id()
    generation = client.post("/api/test-cases/generate", json=analysis)
    assert generation.status_code == 200, generation.text
    generation_payload = generation.json()
    assert generation_payload["test_cases"]
    return analysis, generation_payload


def _generate_and_save(story_id: Optional[str] = None) -> Tuple[str, Dict, Dict]:
    analysis, generation_payload = _generate(story_id)
    save = client.post(
        "/api/test-case-management/save",
        json={"generation": generation_payload, "analysis": analysis},
    )
    assert save.status_code == 200, save.text
    return analysis["story_id"], generation_payload, save.json()


def _first_case(story_id: str) -> dict:
    response = client.get(f"/api/test-case-management/stories/{story_id}")
    assert response.status_code == 200
    payload = response.json()
    assert payload["test_cases"]
    return payload["test_cases"][0]


def _edit_payload(case: dict, **overrides) -> dict:
    payload = {
        "title": case["title"],
        "objective": case["objective"],
        "test_type": case["test_type"],
        "priority": case["priority"],
        "preconditions": case["preconditions"],
        "test_data": case["test_data"],
        "steps": case["steps"],
        "expected_result": case["expected_result"],
        "automation_suitability": case["automation_suitability"],
        "assumptions": case["assumptions"],
        "needs_clarification": case["needs_clarification"],
        "requirement_id": case["requirement_id"],
        "acceptance_criterion_id": case["acceptance_criterion_id"],
    }
    payload.update(overrides)
    return payload


def test_management_health() -> None:
    response = client.get("/api/test-case-management/health")
    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "ok"
    assert payload["module"] == "test_case_management"


def test_save_generated_test_cases() -> None:
    # Step 3 generate persists cases; verify pending_review records exist.
    analysis, generation = _generate()
    story_id = analysis["story_id"]
    story = client.get(f"/api/test-case-management/stories/{story_id}")
    assert story.status_code == 200
    payload = story.json()
    assert payload["total"] == len(generation["test_cases"])
    assert all(
        item["review_status"] == "pending_review" for item in payload["test_cases"]
    )
    assert all(item["current_version"] == 1 for item in payload["test_cases"])

    # Explicit save endpoint is available and returns the managed cases.
    save = client.post(
        "/api/test-case-management/save",
        json={"generation": generation, "analysis": analysis},
    )
    assert save.status_code == 200
    save_payload = save.json()
    assert save_payload["story_id"] == story_id
    assert save_payload["test_cases"]


def test_retrieve_cases_by_story_id() -> None:
    analysis, generation = _generate()
    story_id = analysis["story_id"]
    response = client.get(f"/api/test-case-management/stories/{story_id}")
    assert response.status_code == 200
    payload = response.json()
    assert payload["story_id"] == story_id
    assert payload["total"] == len(generation["test_cases"])
    assert payload["pending_review"] == payload["total"]
    assert payload["approved"] == 0


def test_update_pending_review_case() -> None:
    story_id, _, _ = _generate_and_save()
    case = _first_case(story_id)
    response = client.put(
        f"/api/test-case-management/{case['test_case_id']}?story_id={story_id}",
        json=_edit_payload(case, title="Updated pending title"),
    )
    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["title"] == "Updated pending title"
    assert payload["review_status"] == "pending_review"
    assert payload["current_version"] == 2
    assert payload["original_version"]["title"] == case["title"]


def test_approve_valid_case() -> None:
    story_id, _, _ = _generate_and_save()
    case = _first_case(story_id)
    response = client.post(
        f"/api/test-case-management/{case['test_case_id']}/approve?story_id={story_id}",
        json={"reviewer_id": None, "comments": "Looks good"},
    )
    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["review_status"] == "approved"


def test_reject_case_with_reason() -> None:
    story_id, _, _ = _generate_and_save()
    case = _first_case(story_id)
    response = client.post(
        f"/api/test-case-management/{case['test_case_id']}/reject?story_id={story_id}",
        json={"comments": "Steps are too vague"},
    )
    assert response.status_code == 200, response.text
    assert response.json()["review_status"] == "rejected"

    # History is retained
    story = client.get(f"/api/test-case-management/stories/{story_id}")
    assert story.status_code == 200
    assert any(
        item["test_case_id"] == case["test_case_id"]
        for item in story.json()["test_cases"]
    )


def test_request_clarification() -> None:
    story_id, _, _ = _generate_and_save()
    case = _first_case(story_id)
    response = client.post(
        f"/api/test-case-management/{case['test_case_id']}/clarify?story_id={story_id}",
        json={"comments": "What happens when the email is unknown?"},
    )
    assert response.status_code == 200, response.text
    assert response.json()["review_status"] == "needs_clarification"


def test_prevent_approval_when_needs_clarification() -> None:
    story_id, _, _ = _generate_and_save()
    case = _first_case(story_id)
    clarify = client.post(
        f"/api/test-case-management/{case['test_case_id']}/clarify?story_id={story_id}",
        json={"comments": "Need expected error text"},
    )
    assert clarify.status_code == 200

    approve = client.post(
        f"/api/test-case-management/{case['test_case_id']}/approve?story_id={story_id}",
        json={},
    )
    assert approve.status_code == 409
    assert approve.json()["error"]["code"] == "clarification_required"


def test_edit_approved_creates_new_version() -> None:
    story_id, _, _ = _generate_and_save()
    case = _first_case(story_id)
    approve = client.post(
        f"/api/test-case-management/{case['test_case_id']}/approve?story_id={story_id}",
        json={},
    )
    assert approve.status_code == 200

    edited = client.put(
        f"/api/test-case-management/{case['test_case_id']}?story_id={story_id}",
        json=_edit_payload(case, title="Post-approval edit"),
    )
    assert edited.status_code == 200, edited.text
    payload = edited.json()
    assert payload["current_version"] == 2
    assert payload["review_status"] == "pending_review"
    assert payload["title"] == "Post-approval edit"


def test_previous_approved_version_unchanged() -> None:
    story_id, _, _ = _generate_and_save()
    case = _first_case(story_id)
    original_title = case["title"]

    approve = client.post(
        f"/api/test-case-management/{case['test_case_id']}/approve?story_id={story_id}",
        json={},
    )
    assert approve.status_code == 200

    edited = client.put(
        f"/api/test-case-management/{case['test_case_id']}?story_id={story_id}",
        json=_edit_payload(case, title="Changed after approval"),
    )
    assert edited.status_code == 200

    versions = client.get(
        f"/api/test-case-management/{case['test_case_id']}/versions?story_id={story_id}"
    )
    assert versions.status_code == 200
    payload = versions.json()
    assert len(payload) >= 2
    version_one = next(item for item in payload if item["version_number"] == 1)
    assert version_one["title"] == original_title
    assert version_one["is_approved_snapshot"] is True


def test_invalid_requirement_mapping_rejected() -> None:
    story_id, _, _ = _generate_and_save()
    case = _first_case(story_id)
    response = client.put(
        f"/api/test-case-management/{case['test_case_id']}?story_id={story_id}",
        json=_edit_payload(case, requirement_id="FR-DOES-NOT-EXIST"),
    )
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "invalid_requirement_mapping"


def test_duplicate_generation_does_not_create_duplicates() -> None:
    analysis, generation = _generate()
    story_id = analysis["story_id"]

    first = client.get(f"/api/test-case-management/stories/{story_id}")
    assert first.status_code == 200
    assert first.json()["total"] == len(generation["test_cases"])

    second = client.post(
        "/api/test-case-management/save",
        json={"generation": generation, "analysis": analysis},
    )
    assert second.status_code == 200
    second_payload = second.json()
    assert second_payload["saved_count"] == 0
    assert second_payload["skipped_duplicates"] == len(generation["test_cases"])

    story = client.get(f"/api/test-case-management/stories/{story_id}")
    assert story.status_code == 200
    assert story.json()["total"] == len(generation["test_cases"])


def test_review_history_maintained() -> None:
    story_id, _, _ = _generate_and_save()
    case = _first_case(story_id)
    client.post(
        f"/api/test-case-management/{case['test_case_id']}/approve?story_id={story_id}",
        json={"comments": "Approved in test"},
    )
    reviews = client.get(
        f"/api/test-case-management/{case['test_case_id']}/reviews?story_id={story_id}"
    )
    assert reviews.status_code == 200
    actions = {item["review_action"] for item in reviews.json()}
    assert "save" in actions
    assert "approve" in actions


def test_version_history_maintained() -> None:
    story_id, _, _ = _generate_and_save()
    case = _first_case(story_id)
    client.put(
        f"/api/test-case-management/{case['test_case_id']}?story_id={story_id}",
        json=_edit_payload(case, title="Draft edit"),
    )
    versions = client.get(
        f"/api/test-case-management/{case['test_case_id']}/versions?story_id={story_id}"
    )
    assert versions.status_code == 200
    payload = versions.json()
    assert len(payload) == 2
    assert payload[0]["is_original"] is True


def test_approved_test_case_retrieval() -> None:
    story_id, _, _ = _generate_and_save()
    case = _first_case(story_id)
    client.post(
        f"/api/test-case-management/{case['test_case_id']}/approve?story_id={story_id}",
        json={},
    )
    response = client.get(f"/api/test-case-management/stories/{story_id}/approved")
    assert response.status_code == 200
    approved = response.json()
    assert len(approved) == 1
    assert approved[0]["test_case_id"] == case["test_case_id"]
    assert approved[0]["review_status"] == "approved"


def test_reject_requires_comments() -> None:
    story_id, _, _ = _generate_and_save()
    case = _first_case(story_id)
    response = client.post(
        f"/api/test-case-management/{case['test_case_id']}/reject?story_id={story_id}",
        json={"comments": "   "},
    )
    assert response.status_code == 422


def test_get_single_test_case() -> None:
    story_id, _, _ = _generate_and_save()
    case = _first_case(story_id)
    response = client.get(
        f"/api/test-case-management/{case['test_case_id']}?story_id={story_id}"
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["test_case_id"] == case["test_case_id"]
    assert "id" not in payload
