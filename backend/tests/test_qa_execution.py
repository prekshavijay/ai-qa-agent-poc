"""QA execution run API tests."""

from __future__ import annotations

import uuid
from copy import deepcopy
from typing import Dict, List, Optional, Tuple

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)

BASE_ANALYSIS = {
    "story_id": "STORY-EXEC",
    "story_summary": "Reset password flow for execution tests.",
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
    return f"STORY-EXEC-{uuid.uuid4().hex[:10]}"


def _generate(story_id: Optional[str] = None) -> Tuple[str, List[dict]]:
    analysis = deepcopy(BASE_ANALYSIS)
    analysis["story_id"] = story_id or _story_id()
    response = client.post("/api/test-cases/generate", json=analysis)
    assert response.status_code == 200, response.text
    story = client.get(f"/api/test-case-management/stories/{analysis['story_id']}")
    assert story.status_code == 200, story.text
    cases = story.json()["test_cases"]
    assert len(cases) >= 3
    return analysis["story_id"], cases


def _approve(story_id: str, test_case_id: str) -> dict:
    response = client.post(
        f"/api/test-case-management/{test_case_id}/approve?story_id={story_id}",
        json={"comments": "Approved for execution"},
    )
    assert response.status_code == 200, response.text
    assert response.json()["review_status"] == "approved"
    return response.json()


def _approve_many(story_id: str, cases: List[dict], count: int) -> List[dict]:
    approved = []
    for case in cases[:count]:
        approved.append(_approve(story_id, case["test_case_id"]))
    return approved


def _edit_payload(case: dict, **overrides: object) -> dict:
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


def _create_run(story_id: str, test_case_ids: List[str], **extra: object):
    body: Dict[str, object] = {
        "story_id": story_id,
        "test_case_ids": test_case_ids,
        "trigger_source": "manual",
    }
    body.update(extra)
    return client.post("/api/qa-execution/runs", json=body)


def _runs_for(story_id: str) -> dict:
    response = client.get("/api/qa-execution/runs", params={"story_id": story_id})
    assert response.status_code == 200, response.text
    return response.json()


def _result_for(run: dict, test_case_id: str) -> dict:
    matches = [
        item for item in run["results"] if item["test_case_id"] == test_case_id
    ]
    assert len(matches) == 1
    return matches[0]


def test_execution_health() -> None:
    response = client.get("/api/qa-execution/health")
    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "ok"
    assert payload["module"] == "qa_execution"
    assert "not implemented" in payload["note"].lower()


def test_create_run_with_approved_cases_starts_not_run() -> None:
    story_id, cases = _generate()
    approved = _approve_many(story_id, cases, 2)
    response = _create_run(
        story_id, [item["test_case_id"] for item in approved]
    )
    assert response.status_code == 200, response.text
    payload = response.json()

    assert payload["story_id"] == story_id
    assert payload["run_id"].startswith("RUN-")
    assert payload["status"] == "queued"
    assert payload["trigger_source"] == "manual"
    assert payload["started_at"]
    assert payload["completed_at"] is None
    assert payload["total_test_cases"] == 2
    assert payload["passed_count"] == 0
    assert payload["failed_count"] == 0
    assert payload["blocked_count"] == 0
    assert payload["not_run_count"] == 2
    assert len(payload["results"]) == 2
    assert {item["status"] for item in payload["results"]} == {"not_run"}
    assert all(item["duration_seconds"] is None for item in payload["results"])
    for item in payload["results"]:
        source = next(
            case for case in approved if case["test_case_id"] == item["test_case_id"]
        )
        assert item["approved_version_number"] == source["current_version"]
        assert item["title"] == source["title"]
        assert item["approved_version_id"] > 0

    stored = client.get(f"/api/qa-execution/runs/{payload['run_id']}")
    assert stored.status_code == 200
    assert stored.json()["run_id"] == payload["run_id"]

    still_approved = client.get(
        f"/api/test-case-management/{approved[0]['test_case_id']}?story_id={story_id}"
    )
    assert still_approved.status_code == 200
    assert still_approved.json()["review_status"] == "approved"


def test_reject_unapproved_test_cases() -> None:
    story_id, cases = _generate()
    pending = cases[0]
    rejected = cases[1]
    clarified = cases[2]

    reject = client.post(
        f"/api/test-case-management/{rejected['test_case_id']}/reject?story_id={story_id}",
        json={"comments": "Not ready for execution"},
    )
    assert reject.status_code == 200, reject.text
    clarify = client.post(
        f"/api/test-case-management/{clarified['test_case_id']}/clarify?story_id={story_id}",
        json={"comments": "Need a clearer expected result"},
    )
    assert clarify.status_code == 200, clarify.text

    response = _create_run(
        story_id,
        [
            pending["test_case_id"],
            rejected["test_case_id"],
            clarified["test_case_id"],
        ],
    )
    assert response.status_code == 422
    body = response.json()["error"]
    assert body["code"] == "test_case_not_approved"
    statuses = {
        item["test_case_id"]: item["review_status"] for item in body["details"]["test_cases"]
    }
    assert statuses[pending["test_case_id"]] == "pending_review"
    assert statuses[rejected["test_case_id"]] == "rejected"
    assert statuses[clarified["test_case_id"]] == "needs_clarification"
    assert _runs_for(story_id)["total"] == 0


def test_reject_invalid_test_case_ids() -> None:
    story_id, cases = _generate()
    approved = _approve(story_id, cases[0]["test_case_id"])
    response = _create_run(
        story_id,
        [approved["test_case_id"], "TC-DOES-NOT-EXIST", ""],
    )
    assert response.status_code == 422
    # Blank ids fail request validation before the run is considered.
    assert response.json()["error"]["code"] == "validation_error"
    assert _runs_for(story_id)["total"] == 0

    missing = _create_run(story_id, [approved["test_case_id"], "TC-DOES-NOT-EXIST"])
    assert missing.status_code == 422
    error = missing.json()["error"]
    assert error["code"] == "invalid_test_case_ids"
    assert error["details"]["test_case_ids"] == ["TC-DOES-NOT-EXIST"]
    assert _runs_for(story_id)["total"] == 0


def test_preserve_approved_version_after_later_edit() -> None:
    story_id, cases = _generate()
    approved = _approve(story_id, cases[0]["test_case_id"])
    created = _create_run(story_id, [approved["test_case_id"]])
    assert created.status_code == 200, created.text
    pinned = created.json()["results"][0]
    original_title = approved["title"]
    assert pinned["title"] == original_title
    assert pinned["approved_version_number"] == approved["current_version"]

    edited = client.put(
        f"/api/test-case-management/{approved['test_case_id']}?story_id={story_id}",
        json=_edit_payload(approved, title="Draft created after approval"),
    )
    assert edited.status_code == 200, edited.text
    assert edited.json()["review_status"] == "pending_review"
    assert edited.json()["current_version"] == approved["current_version"] + 1
    assert edited.json()["title"] == "Draft created after approval"

    detail = client.get(f"/api/qa-execution/runs/{created.json()['run_id']}")
    assert detail.status_code == 200
    stored = detail.json()["results"][0]
    assert stored["id"] == pinned["id"]
    assert stored["approved_version_id"] == pinned["approved_version_id"]
    assert stored["approved_version_number"] == pinned["approved_version_number"]
    assert stored["title"] == original_title
    assert stored["expected_result"] == approved["expected_result"]

    versions = client.get(
        f"/api/test-case-management/{approved['test_case_id']}/versions"
        f"?story_id={story_id}"
    )
    assert versions.status_code == 200
    snapshot = next(
        item
        for item in versions.json()
        if item["version_number"] == pinned["approved_version_number"]
    )
    assert snapshot["is_approved_snapshot"] is True
    assert snapshot["title"] == original_title

    again = _create_run(story_id, [approved["test_case_id"]])
    assert again.status_code == 422
    assert again.json()["error"]["code"] == "test_case_not_approved"


def test_record_results_recalculates_counts_and_completion() -> None:
    story_id, cases = _generate()
    approved = _approve_many(story_id, cases, 3)
    created = _create_run(story_id, [item["test_case_id"] for item in approved])
    assert created.status_code == 200, created.text
    run_id = created.json()["run_id"]
    ids = [item["test_case_id"] for item in approved]

    passed = client.post(
        f"/api/qa-execution/runs/{run_id}/results",
        json={
            "test_case_id": ids[0],
            "status": "passed",
            "actual_result": "Observed the expected reset email.",
            "evidence": {"source": "manual"},
            "started_at": "2026-11-18T10:00:00Z",
            "completed_at": "2026-11-18T10:00:05Z",
        },
    )
    assert passed.status_code == 200, passed.text
    after_pass = passed.json()
    assert after_pass["status"] == "running"
    assert after_pass["completed_at"] is None
    assert after_pass["passed_count"] == 1
    assert after_pass["failed_count"] == 0
    assert after_pass["blocked_count"] == 0
    assert after_pass["not_run_count"] == 2
    passed_row = _result_for(after_pass, ids[0])
    assert passed_row["status"] == "passed"
    assert passed_row["actual_result"] == "Observed the expected reset email."
    assert passed_row["evidence"] == {"source": "manual"}
    assert passed_row["duration_seconds"] == 5.0
    assert len(after_pass["results"]) == 3

    failed = client.post(
        f"/api/qa-execution/runs/{run_id}/results",
        json={
            "test_case_id": ids[1],
            "status": "failed",
            "error_details": "Reset link was missing.",
        },
    )
    assert failed.status_code == 200, failed.text
    after_fail = failed.json()
    assert after_fail["status"] == "running"
    assert after_fail["completed_at"] is None
    assert after_fail["passed_count"] == 1
    assert after_fail["failed_count"] == 1
    assert after_fail["blocked_count"] == 0
    assert after_fail["not_run_count"] == 1
    assert _result_for(after_fail, ids[1])["error_details"] == "Reset link was missing."

    blocked = client.post(
        f"/api/qa-execution/runs/{run_id}/results",
        json={
            "test_case_id": ids[2],
            "status": "blocked",
            "actual_result": "Mail service was unavailable.",
        },
    )
    assert blocked.status_code == 200, blocked.text
    after_block = blocked.json()
    assert after_block["status"] == "completed"
    assert after_block["completed_at"]
    assert after_block["passed_count"] == 1
    assert after_block["failed_count"] == 1
    assert after_block["blocked_count"] == 1
    assert after_block["not_run_count"] == 0
    assert after_block["total_test_cases"] == 3
    assert {
        item["status"] for item in after_block["results"]
    } == {"passed", "failed", "blocked"}


def test_run_stays_incomplete_while_not_run_remains() -> None:
    story_id, cases = _generate()
    approved = _approve_many(story_id, cases, 2)
    created = _create_run(story_id, [item["test_case_id"] for item in approved])
    assert created.status_code == 200, created.text
    run_id = created.json()["run_id"]

    response = client.post(
        f"/api/qa-execution/runs/{run_id}/results",
        json={"test_case_id": approved[0]["test_case_id"], "status": "passed"},
    )
    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["not_run_count"] == 1
    assert payload["status"] != "completed"
    assert payload["completed_at"] is None


def test_reject_result_for_case_not_in_run() -> None:
    story_id, cases = _generate()
    included = _approve(story_id, cases[0]["test_case_id"])
    outsider = _approve(story_id, cases[1]["test_case_id"])
    created = _create_run(story_id, [included["test_case_id"]])
    assert created.status_code == 200, created.text
    run_id = created.json()["run_id"]

    response = client.post(
        f"/api/qa-execution/runs/{run_id}/results",
        json={"test_case_id": outsider["test_case_id"], "status": "passed"},
    )
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "test_case_not_in_run"

    detail = client.get(f"/api/qa-execution/runs/{run_id}")
    assert detail.status_code == 200
    payload = detail.json()
    assert payload["passed_count"] == 0
    assert payload["not_run_count"] == 1
    assert [item["test_case_id"] for item in payload["results"]] == [
        included["test_case_id"]
    ]
    assert payload["results"][0]["status"] == "not_run"


def test_duplicate_test_case_ids_rejected_and_updates_do_not_duplicate_rows() -> None:
    story_id, cases = _generate()
    approved = _approve(story_id, cases[0]["test_case_id"])
    duplicate = _create_run(
        story_id, [approved["test_case_id"], approved["test_case_id"]]
    )
    assert duplicate.status_code == 422
    assert duplicate.json()["error"]["code"] == "duplicate_test_case"
    assert duplicate.json()["error"]["details"]["test_case_ids"] == [
        approved["test_case_id"]
    ]
    assert _runs_for(story_id)["total"] == 0

    created = _create_run(story_id, [approved["test_case_id"]])
    assert created.status_code == 200, created.text
    run_id = created.json()["run_id"]
    original_id = created.json()["results"][0]["id"]

    first = client.post(
        f"/api/qa-execution/runs/{run_id}/results",
        json={"test_case_id": approved["test_case_id"], "status": "passed"},
    )
    assert first.status_code == 200, first.text
    second = client.post(
        f"/api/qa-execution/runs/{run_id}/results",
        json={
            "test_case_id": approved["test_case_id"],
            "status": "failed",
            "error_details": "Retried and failed.",
        },
    )
    assert second.status_code == 200, second.text
    payload = second.json()
    assert len(payload["results"]) == 1
    assert payload["results"][0]["id"] == original_id
    assert payload["results"][0]["status"] == "failed"
    assert payload["passed_count"] == 0
    assert payload["failed_count"] == 1
    assert payload["not_run_count"] == 0
    assert payload["status"] == "completed"
    assert first.json()["results"][0]["id"] == original_id


def test_list_runs_filters_by_story_id() -> None:
    first_story, first_cases = _generate()
    second_story, second_cases = _generate()
    first_approved = _approve(first_story, first_cases[0]["test_case_id"])
    second_approved = _approve(second_story, second_cases[0]["test_case_id"])
    first_run = _create_run(first_story, [first_approved["test_case_id"]])
    second_run = _create_run(second_story, [second_approved["test_case_id"]])
    assert first_run.status_code == 200
    assert second_run.status_code == 200

    filtered = _runs_for(first_story)
    assert filtered["total"] == 1
    assert filtered["runs"][0]["run_id"] == first_run.json()["run_id"]
    assert filtered["runs"][0]["story_id"] == first_story
    assert "results" not in filtered["runs"][0]


def test_invalid_execution_payloads() -> None:
    story_id, cases = _generate()
    approved = _approve(story_id, cases[0]["test_case_id"])
    created = _create_run(story_id, [approved["test_case_id"]])
    assert created.status_code == 200, created.text
    run_id = created.json()["run_id"]

    empty = client.post(
        "/api/qa-execution/runs",
        json={"story_id": story_id, "test_case_ids": []},
    )
    assert empty.status_code == 422

    webhook = _create_run(
        story_id,
        [approved["test_case_id"]],
        trigger_source="webhook",
    )
    assert webhook.status_code == 422

    bad_status = client.post(
        f"/api/qa-execution/runs/{run_id}/results",
        json={"test_case_id": approved["test_case_id"], "status": "skipped"},
    )
    assert bad_status.status_code == 422

    bad_evidence = client.post(
        f"/api/qa-execution/runs/{run_id}/results",
        json={
            "test_case_id": approved["test_case_id"],
            "status": "passed",
            "evidence": ["not-an-object"],
        },
    )
    assert bad_evidence.status_code == 422

    backwards = client.post(
        f"/api/qa-execution/runs/{run_id}/results",
        json={
            "test_case_id": approved["test_case_id"],
            "status": "passed",
            "started_at": "2026-11-18T10:00:05Z",
            "completed_at": "2026-11-18T10:00:00Z",
        },
    )
    assert backwards.status_code == 422
    assert backwards.json()["error"]["code"] == "validation_error"

    missing_run = client.get("/api/qa-execution/runs/RUN-DOES-NOT-EXIST")
    assert missing_run.status_code == 404
    assert missing_run.json()["error"]["code"] == "not_found"

    detail = client.get(f"/api/qa-execution/runs/{run_id}")
    assert detail.status_code == 200
    assert detail.json()["status"] == "queued"
    assert detail.json()["results"][0]["status"] == "not_run"
