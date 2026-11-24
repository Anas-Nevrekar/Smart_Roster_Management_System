import pytest
from fastapi.testclient import TestClient
from datetime import datetime, timezone
from app.core.config import Settings
from app.main import create_app
from app.repositories.memory import InMemoryRepository
from app.services.roster_generation import RosterGenerationService


@pytest.fixture
def repository():
    return InMemoryRepository()


@pytest.fixture
def client(repository):
    settings = Settings(environment="testing", allowed_frontend_origins=["http://localhost:5173"])
    return TestClient(create_app(settings, repository))


@pytest.fixture(scope="session")
def generated_december():
    result = RosterGenerationService(InMemoryRepository()).generate(12, 2026)
    assert result["success"]
    return result


@pytest.fixture
def draft_roster(generated_december):
    repository = InMemoryRepository()
    now = datetime.now(timezone.utc)
    roster_id = "roster-2026-12"
    metadata = {"id": roster_id, "month": 12, "year": 2026, "status": "draft",
                "generated_at": now, "published_at": None, "generated_by": None,
                "published_by": None, "created_at": now, "updated_at": now,
                "version": 1, "summary": generated_december["summary"],
                "latest_validation": {"valid": True, "errors": [], "summary": generated_december["summary"], "validated_at": now}}
    assignments = [{"employee_id": x["employee_id"], "assignment_date": x["date"], "status": "working",
                    "brand_id": x["brand_id"], "process_id": x["process_id"]}
                   for x in generated_december["assignments"]]
    assignments.extend({"employee_id": x["employee_id"], "assignment_date": x["date"], "status": "weekly_off",
                        "brand_id": None, "process_id": None} for x in generated_december["weekly_offs"])
    repository.create_roster_with_assignments(metadata, assignments)
    settings = Settings(environment="testing", allowed_frontend_origins=["http://localhost:5173"])
    return TestClient(create_app(settings, repository)), repository, roster_id
