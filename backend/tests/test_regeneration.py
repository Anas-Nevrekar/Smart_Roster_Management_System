from copy import deepcopy
import pytest

from app.services.roster_generation import RosterGenerationService


def small_generation(*, success=True, fingerprint="fresh"):
    return {
        "success": success, "month": 12, "year": 2026,
        "summary": {"total_assignments": 1 if success else 0, "total_weekly_offs": 1 if success else 0,
                    "total_requirements": 1, "requirements_satisfied": 1 if success else 0,
                    "coverage_gaps": 0 if success else 1, "active_employees": 1,
                    "active_brands": 1, "active_processes": 1},
        "assignments": ([{"employee_id": "E001", "date": "2026-12-01", "brand_id": "B001",
                          "process_id": "PR001", "status": "assigned"}] if success else []),
        "weekly_offs": ([{"employee_id": "E001", "date": "2026-12-02", "week_start": "2026-11-30",
                           "status": "weekly_off"}] if success else []),
        "validation": {"is_valid": success, "errors": [], "audit": {}},
        "diagnostics": [] if success else [{"code": "staffing_gap", "date": "2026-12-03", "message": "No available employee."}],
        "master_data_fingerprint": fingerprint,
    }


def test_regenerate_success_atomically_replaces_work_and_offs(draft_roster, monkeypatch):
    client, repository, roster_id = draft_roster
    old = repository.get("rosters", roster_id)
    monkeypatch.setattr(RosterGenerationService, "generate", lambda self, month, year: small_generation())
    response = client.post(f"/api/v1/rosters/{roster_id}/regenerate", headers={"If-Match": "1"}, json={})
    assert response.status_code == 200
    result = response.json()
    assert result["success"] is True
    assert result["roster"]["id"] == roster_id and result["roster"]["status"] == "draft"
    assert result["roster"]["version"] == 2
    assert result["roster"]["generated_at"] != old["generated_at"].isoformat().replace("+00:00", "Z")
    saved = repository.list_roster_assignments(roster_id)
    assert {(x["status"], x["employee_id"], x["assignment_date"]) for x in saved} == {
        ("working", "E001", "2026-12-01"), ("weekly_off", "E001", "2026-12-02")}
    assert repository.get("rosters", roster_id)["latest_validation"] is None
    assert repository.get("rosters", roster_id)["summary"]["total_assignments"] == 1
    assert result["roster"]["assignment_count"] == 1 and result["roster"]["weekly_off_count"] == 1


def test_failed_regeneration_returns_diagnostics_and_preserves_draft_exactly(draft_roster, monkeypatch):
    client, repository, roster_id = draft_roster
    before_roster = repository.get("rosters", roster_id)
    before_assignments = repository.list_roster_assignments(roster_id)
    failed = small_generation(success=False)
    monkeypatch.setattr(RosterGenerationService, "generate", lambda self, month, year: deepcopy(failed))
    response = client.post(f"/api/v1/rosters/{roster_id}/regenerate", headers={"If-Match": "1"}, json={})
    assert response.status_code == 200
    assert response.json()["success"] is False
    assert response.json()["diagnostics"][0]["code"] == "staffing_gap"
    assert response.json()["roster"]["version"] == 1
    assert repository.get("rosters", roster_id) == before_roster
    assert repository.list_roster_assignments(roster_id) == before_assignments


def test_regeneration_requires_version_and_rejects_missing_published_and_stale(draft_roster, monkeypatch):
    client, repository, roster_id = draft_roster
    assert client.post("/api/v1/rosters/missing/regenerate").status_code == 404
    assert client.post(f"/api/v1/rosters/{roster_id}/regenerate").status_code == 428
    assert client.post(f"/api/v1/rosters/{roster_id}/regenerate", headers={"If-Match": "99"}).status_code == 409
    repository.update("rosters", roster_id, {"status": "published"})
    assert client.post(f"/api/v1/rosters/{roster_id}/regenerate", headers={"If-Match": "1"}).status_code == 409
    monkeypatch.setattr(RosterGenerationService, "generate", lambda self, month, year: pytest.fail("must not generate"))


def test_concurrent_roster_change_during_generation_is_not_overwritten(draft_roster, monkeypatch):
    client, repository, roster_id = draft_roster
    original = repository.list_roster_assignments(roster_id)
    changed = deepcopy(original)
    changed.pop()
    def generate_during_request(self, month, year):
        repository.replace_roster_assignments(roster_id, 1, changed)
        return small_generation()
    monkeypatch.setattr(RosterGenerationService, "generate", generate_during_request)
    response = client.post(f"/api/v1/rosters/{roster_id}/regenerate", headers={"If-Match": "1"}, json={})
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "STALE_ROSTER_VERSION"
    assert repository.get("rosters", roster_id)["version"] == 2
    current = repository.list_roster_assignments(roster_id)
    fields = ("id", "employee_id", "assignment_date", "status", "brand_id", "process_id")
    assert [{key: item[key] for key in fields} for item in current] == [{key: item[key] for key in fields} for item in changed]


def test_master_data_stale_fingerprint_ignores_irrelevant_fields_and_detects_rule_change(draft_roster, generated_december):
    client, repository, roster_id = draft_roster
    repository.update("rosters", roster_id, {"master_data_fingerprint": generated_december["master_data_fingerprint"]})
    assert client.get(f"/api/v1/rosters/{roster_id}").json()["data"]["master_data_stale"] is False
    repository.update("employees", "E001", {"email": "new-address@example.com"})
    assert client.get(f"/api/v1/rosters/{roster_id}").json()["data"]["master_data_stale"] is False
    rule = repository.get("operating_rules", "RULE-B001-PR001")
    repository.update("operating_rules", rule["id"], {"minimum_staffing": rule["minimum_staffing"] + 1})
    assert client.get(f"/api/v1/rosters/{roster_id}").json()["data"]["master_data_stale"] is True


def test_brand_view_contains_only_actual_assignments_and_configured_processes(draft_roster):
    client, repository, roster_id = draft_roster
    view = client.get(f"/api/v1/rosters/{roster_id}/views/brand").json()["data"]
    pureglow = next(item for item in view["brands"] if item["brand"]["brand_id"] == "B003")
    assert {item["process"]["process_id"] for item in pureglow["processes"]} == {"PR001", "PR002", "PR003"}
    for process in pureglow["processes"]:
        expected = {item["employee_id"] for item in repository.list_roster_assignments(roster_id)
                    if item["status"] == "working" and item["brand_id"] == "B003" and item["process_id"] == process["process"]["process_id"]}
        assert {item["employee_id"] for item in process["assignments"]} == expected
        assert all(item["employee_id"] in expected for item in process["weekly_offs"])
    pod_view = client.get(f"/api/v1/rosters/{roster_id}/views/pod").json()["data"]
    assert all("pod_id" in row and "pod_name" in row for pod in pod_view["pods"] for row in pod["employees"])
