import sys

import pytest
from fastapi.testclient import TestClient

from app.core.config import Settings
from app.integrations.roster_engine.adapter import RosterEngineAdapter
from app.integrations.roster_engine.exceptions import EngineIntegrationError
from app.integrations.roster_engine.mapper import map_repository_snapshot
from app.main import create_app
from app.repositories.memory import InMemoryRepository


def test_repository_mapper_preserves_engine_inputs():
    repository = InMemoryRepository()
    dataset = map_repository_snapshot(repository.snapshot())
    assert len(dataset["employees"]) == 32
    assert len(dataset["pods"]) == 5
    assert len(dataset["brands"]) == 25
    assert len(dataset["processes"]) == 3
    assert len(dataset["employee_assignments"]) == 94
    assert len(dataset["brand_process_rules"]) == 75
    assert len(dataset["employee_time_off"]) == 2
    assert len(dataset["public_holidays"]) == 1
    assert dataset["employees"][0]["employee_id"] == "E001"
    assert dataset["employees"][0]["name"] == "Rahul Sharma"
    assert any(not x["is_active"] for x in dataset["employees"])
    assert next(x for x in dataset["employee_time_off"] if x["time_off_id"] == "ATO001")["status"] == "approved"
    assert next(x for x in dataset["employee_time_off"] if x["time_off_id"] == "ATO002")["status"] == "pending"
    assert dataset["public_holidays"][0]["holiday_date"] == "2026-12-25"
    # Eligibility remains per brand-process, so employees may receive multiple assignments on one date.
    assert len({(x["employee_id"], x["brand_id"], x["process_id"]) for x in dataset["employee_assignments"]}) == 94


def test_valid_december_generation_matches_engine_baseline(client, repository):
    before = repository.snapshot()
    original_path = list(sys.path)
    response = client.post("/api/v1/rosters/generate", json={"month": 12, "year": 2026})
    assert response.status_code == 200
    result = response.json()
    assert result["success"] is True
    assert result["summary"] == {
        "total_assignments": 2017,
        "total_weekly_offs": 155,
        "total_requirements": 1990,
        "requirements_satisfied": 1990,
        "coverage_gaps": 0,
        "active_employees": 31,
        "active_brands": 25,
        "active_processes": 3,
    }
    assert len(result["assignments"]) == 2017
    assert len(result["weekly_offs"]) == 155
    assert result["validation"]["is_valid"] is True
    assert result["validation"]["errors"] == []
    assert result["validation"]["audit"] == {
        "requirements_total": 1990,
        "requirements_satisfied": 1990,
        "requirements_with_gaps": 0,
        "requirements_with_insufficient_available_staff": 0,
        "active_employees_checked": 31,
        "leave_conflicts": 0,
        "eligibility_conflicts": 0,
        "inactive_employee_conflicts": 0,
        "workable_day_conflicts": 0,
        "duplicate_assignments": 0,
        "weekly_off_overlaps": 0,
        "weekly_off_constraint_conflicts": 0,
        "invalid_requirement_assignments": 0,
        "weekly_off_count_errors": 0,
    }
    assert result["diagnostics"] == []
    assert result["roster"]["id"] == "roster-2026-12"
    assert result["roster"]["status"] == "draft"
    assert result["roster"]["version"] == 1
    assert result["roster"]["assignment_count"] == 2017
    assert result["roster"]["weekly_off_count"] == 155
    assert result["roster"]["master_data_stale"] is False
    assigned_by_employee_day = {}
    for assignment in result["assignments"]:
        assigned_by_employee_day.setdefault((assignment["employee_id"], assignment["date"]), []).append(assignment)
    assert any(len(items) > 1 and len({a["process_id"] for a in items}) > 1 for items in assigned_by_employee_day.values())
    after = repository.snapshot()
    assert after["rosters"] and len(after["rosters"]) == 1
    assert len(after["roster_assignments"]) == 2172
    assert all(after[key] == before[key] for key in before if key not in {"rosters", "roster_assignments"})
    assert "backtracking" not in sys.modules
    assert sys.path == original_path
    roster_id = result["roster"]["id"]
    assert client.post("/api/v1/rosters/generate", json={"month": 12, "year": 2026}).status_code == 409
    listed = client.get("/api/v1/rosters", params={"status": "draft", "year": 2026}).json()
    assert listed["total"] == 1 and listed["data"][0]["id"] == roster_id
    assert client.get(f"/api/v1/rosters/{roster_id}").json()["data"]["assignment_count"] == 2017
    assert client.get("/api/v1/rosters/missing").status_code == 404
    assignments = client.get(f"/api/v1/rosters/{roster_id}/assignments", params={"employee_id": "E021", "status": "working"}).json()
    assert assignments["total"] > 0
    assert all(x["employee_id"] == "E021" and x["status"] == "working" and x["employee_name"] for x in assignments["data"])
    assert client.get(f"/api/v1/rosters/{roster_id}/assignments", params={"pod_id": "POD04"}).json()["total"] > 0
    offs = client.get(f"/api/v1/rosters/{roster_id}/weekly-offs", params={"employee_id": "E021"}).json()
    assert offs["total"] == 5 and all(x["status"] == "weekly_off" for x in offs["data"])
    coverage = client.get(f"/api/v1/rosters/{roster_id}/coverage").json()
    assert coverage["summary"] == {"total_requirements": 1990, "requirements_satisfied": 1990, "coverage_gaps": 0, "total_working_assignments": 2017, "total_weekly_offs": 155}
    assert any(x["status"] == "not_operating" for x in coverage["data"])
    assert all(client.get(f"/api/v1/rosters/{roster_id}/views/{view}").status_code == 200 for view in ("company", "pod", "brand", "process", "employee"))
    employee_view = client.get(f"/api/v1/rosters/{roster_id}/views/employee").json()["data"]
    e021 = next(x for x in employee_view["employees"] if x["employee_id"] == "E021")
    assert any(len([a for a in e021["assignments"] if a["assignment_date"] == day]) > 1 for day in {a["assignment_date"] for a in e021["assignments"]})
    validation = client.post(f"/api/v1/rosters/{roster_id}/validate").json()
    assert validation["valid"] is True and validation["errors"] == [] and validation["version"] == 1
    published = client.post(f"/api/v1/rosters/{roster_id}/publish", json={"published_by": "manager-1"})
    assert published.status_code == 200
    assert published.json()["data"]["status"] == "published"
    assert published.json()["data"]["published_by"] == "manager-1"
    assert client.get("/api/v1/rosters", params={"status": "published"}).json()["total"] == 1


def test_conflict_fixture_returns_failure_without_partial_output():
    repository = InMemoryRepository(scenario="conflict")
    app = create_app(Settings(environment="testing"), repository)
    with TestClient(app) as client:
        response = client.post("/api/v1/rosters/generate", json={"month": 12, "year": 2026})
    result = response.json()
    assert response.status_code == 200
    assert result["success"] is False
    assert result["assignments"] == []
    assert result["weekly_offs"] == []
    assert result["validation"]["is_valid"] is False
    assert repository.list("rosters") == [] and repository.list("roster_assignments") == []
    diagnostic = next(d for d in result["diagnostics"] if d.get("date") == "2026-12-08" and d.get("brand_id") == "B003" and d.get("process_id") == "PR001")
    assert diagnostic["code"] == "approved_time_off"
    assert diagnostic["required_staffing"] == 2
    assert diagnostic["available_staffing"] == 0
    assert diagnostic["unavailable_employee_ids"] == ["E021", "E022", "E023"]


@pytest.mark.parametrize("body", [{"month": 0, "year": 2026}, {"month": 13, "year": 2026}, {"month": 12, "year": 1999}, {"month": 12, "year": 2101}])
def test_invalid_generation_period_is_rejected(client, body):
    response = client.post("/api/v1/rosters/generate", json=body)
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "VALIDATION_ERROR"


def test_unsupported_coverage_override_is_not_silently_ignored():
    dataset = map_repository_snapshot(InMemoryRepository().snapshot())
    dataset["brand_process_rules"][0]["coverage_overrides"] = [{"date": "2026-12-01", "minimum_staffing": 3}]
    with pytest.raises(EngineIntegrationError, match="does not apply date-specific"):
        RosterEngineAdapter().generate(dataset, 12, 2026)
