from datetime import datetime, timezone

import pytest
from fastapi.testclient import TestClient

from app.core.config import Settings
from app.core.errors import ServiceError
from app.main import create_app
from app.repositories.memory import InMemoryRepository


def draft(roster_id="roster-2026-02", month=2, year=2026):
    now = datetime.now(timezone.utc)
    return {"id": roster_id, "month": month, "year": year, "status": "draft",
            "generated_at": now, "published_at": None, "generated_by": None,
            "published_by": None, "created_at": now, "updated_at": now,
            "version": 1, "summary": {}, "latest_validation": None}


def test_atomic_roster_creation_rolls_back_on_duplicate_or_weekly_off_overlap():
    repository = InMemoryRepository()
    valid_assignment = {"employee_id": "E001", "assignment_date": "2026-02-02", "status": "working", "brand_id": "B001", "process_id": "PR001"}
    off = {"employee_id": "E001", "assignment_date": "2026-02-02", "status": "weekly_off", "brand_id": None, "process_id": None}
    with pytest.raises(ServiceError) as error:
        repository.create_roster_with_assignments(draft(), [valid_assignment, off])
    assert error.value.code == "WEEKLY_OFF_OVERLAP"
    assert repository.list("rosters") == []
    assert repository.list("roster_assignments") == []
    repository.create_roster_with_assignments(draft(), [valid_assignment])
    with pytest.raises(ServiceError) as duplicate:
        repository.create_roster_with_assignments(draft("other-roster"), [])
    assert duplicate.value.code == "ROSTER_ALREADY_EXISTS"


def test_failed_validation_blocks_publish_and_preserves_draft():
    repository = InMemoryRepository()
    repository.create_roster_with_assignments(draft(), [])
    client = TestClient(create_app(Settings(environment="testing"), repository))
    response = client.post("/api/v1/rosters/roster-2026-02/publish", json={"published_by": "manager"})
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "ROSTER_INVALID"
    roster = repository.get("rosters", "roster-2026-02")
    assert roster["status"] == "draft" and roster["version"] == 1


def test_repository_reset_and_application_instances_are_isolated():
    first = InMemoryRepository()
    now = datetime.now(timezone.utc)
    first.create_roster_with_assignments(draft("roster-2026-03", 3), [])
    second = InMemoryRepository()
    assert second.list("rosters") == []
    first.reset()
    assert first.list("rosters") == [] and first.list("roster_assignments") == []
