from datetime import date, datetime, timezone

import pytest
from bson import BSON
from bson.codec_options import CodecOptions

from app.core.database import DatabaseConnectionManager
from app.core.database_indexes import INDEXES, ensure_indexes
from app.core.errors import ServiceError
from app.repositories.mongodb import COLLECTION_NAMES, MongoRepository, from_document, to_document
from app.scripts.seed_database import _verify_relationships
from app.repositories.memory import COLLECTIONS, InMemoryRepository


def test_domain_ids_and_date_only_values_round_trip_without_day_shift():
    source = {"id": "A001", "assignment_date": "2026-12-08", "status": "working",
              "created_at": datetime(2026, 11, 23, tzinfo=timezone.utc)}
    stored = to_document("roster_assignments", source)
    assert stored["_id"] == "A001"
    assert stored["assignment_date"] == datetime(2026, 12, 8, tzinfo=timezone.utc)
    restored = from_document("roster_assignments", stored)
    assert restored["id"] == "A001"
    assert restored["assignment_date"] == "2026-12-08"
    assert restored["created_at"].tzinfo == timezone.utc
    assert "_id" not in restored
    decoded = BSON(BSON.encode(stored)).decode(codec_options=CodecOptions(tz_aware=True))
    assert decoded["_id"] == "A001"
    assert decoded["assignment_date"].date().isoformat() == "2026-12-08"


def test_unique_assignment_indexes_allow_multiple_processes_but_reject_exact_duplicates():
    assignment_indexes = INDEXES["roster_assignments"]
    working = next(item for item in assignment_indexes if item["name"] == "uq_assignment_employee_date_pair")
    weekly_off = next(item for item in assignment_indexes if item["name"] == "uq_weekly_off_employee_date")
    assert [field for field, _ in working["keys"]] == ["roster_id", "employee_id", "assignment_date", "brand_id", "process_id"]
    assert working["partialFilterExpression"] == {"status": "working"}
    assert weekly_off["partialFilterExpression"] == {"status": "weekly_off"}
    assert not any(item.get("unique") and item["keys"] == [("roster_id", 1), ("employee_id", 1), ("assignment_date", 1)]
                   and item.get("partialFilterExpression", {}).get("status") == "working" for item in assignment_indexes)


class FakeCollection:
    def __init__(self):
        self.created = []
        self.documents = {}

    def create_index(self, keys, **options):
        self.created.append((keys, options))

    def find_one(self, query):
        return self.documents.get(query.get("_id"))

    def insert_one(self, document):
        self.documents[document["_id"]] = document

    def replace_one(self, query, document, upsert=False):
        self.documents[query["_id"]] = document


class FakeDatabase:
    name = "smart_roster_dev"

    def __init__(self):
        self.collections = {}

    def __getitem__(self, name):
        return self.collections.setdefault(name, FakeCollection())


class FakeAdmin:
    def __init__(self):
        self.pings = 0

    def command(self, command):
        assert command == "ping"
        self.pings += 1
        return {"ok": 1}


class FakeClient:
    def __init__(self, database):
        self.database = database
        self.admin = FakeAdmin()
        self.closed = False

    def __getitem__(self, name):
        assert name == self.database.name
        return self.database

    def close(self):
        self.closed = True


def test_index_creation_is_idempotent_and_connection_manager_reuses_client():
    database = FakeDatabase()
    clients = []

    def factory(uri, **options):
        assert "secret" in uri
        assert options["tz_aware"] is True
        client = FakeClient(database)
        clients.append(client)
        return client

    manager = DatabaseConnectionManager("mongodb://user:secret@host", database.name, client_factory=factory)
    assert manager.connect() is True
    assert manager.connect() is True
    assert len(clients) == 1
    assert clients[0].admin.pings == 1
    assert sum(len(collection.created) for collection in database.collections.values()) == sum(len(items) for items in INDEXES.values())
    assert manager.check_ready() == (True, None)
    assert clients[0].admin.pings == 2
    manager.close()
    assert clients[0].closed


def test_missing_mongodb_configuration_fails_closed_without_memory_fallback():
    manager = DatabaseConnectionManager(None, "smart_roster_dev")
    assert manager.connect() is False
    repository = MongoRepository(manager)
    with pytest.raises(ServiceError) as failure:
        repository.list("employees")
    assert failure.value.status_code == 503
    assert failure.value.code == "DATABASE_UNAVAILABLE"
    assert "MONGODB_URI" in failure.value.message


def test_repository_implements_every_existing_operation_and_maps_all_collections():
    manager = DatabaseConnectionManager(None, "smart_roster_dev")
    repository = MongoRepository(manager)
    required = {"list", "get", "create", "update", "delete", "reset", "snapshot",
                "replace_employee_eligibility", "set_pod_membership",
                "get_roster_by_month_year", "create_roster_with_assignments", "list_roster_assignments",
                "replace_roster_assignments", "save_roster_validation", "publish_roster", "rollback_roster_creation"}
    assert required <= set(dir(repository))
    assert set(COLLECTIONS) == set(COLLECTION_NAMES)
    assert COLLECTION_NAMES["eligibility"] == "employee_assignments"
    assert COLLECTION_NAMES["operating_rules"] == "brand_process_rules"
    assert COLLECTION_NAMES["time_off"] == "employee_time_off"


def test_fixture_relationships_are_consistent_before_seed():
    _verify_relationships(InMemoryRepository().snapshot())


def test_fixture_upsert_is_idempotent_and_preserves_created_at():
    database = FakeDatabase()
    manager = DatabaseConnectionManager("mongodb://user:secret@host", database.name,
                                        client_factory=lambda uri, **kwargs: FakeClient(database))
    assert manager.connect()
    repository = MongoRepository(manager)
    first = {"id": "E001", "employee_id": "E001", "full_name": "Example", "email": "example@example.com"}
    assert repository.upsert_seed_record("employees", first) == "inserted"
    created_at = database["employees"].documents["E001"]["created_at"]
    assert repository.upsert_seed_record("employees", first) == "unchanged"
    changed = {**first, "full_name": "Updated Example"}
    assert repository.upsert_seed_record("employees", changed) == "updated"
    stored = database["employees"].documents["E001"]
    assert stored["created_at"] == created_at
    assert stored["full_name"] == "Updated Example"
    manager.close()


def test_seed_is_non_destructive_by_default_and_reset_is_test_database_only():
    database = FakeDatabase()
    client = FakeClient(database)
    manager = DatabaseConnectionManager("mongodb://user:secret@host", database.name, client_factory=lambda uri, **kwargs: client)
    assert manager.connect()
    repository = MongoRepository(manager)
    with pytest.raises(ServiceError) as failure:
        repository.reset()
    assert failure.value.code == "RESET_NOT_ALLOWED"


@pytest.mark.mongodb
def test_mongodb_persistence_and_transaction_integration():
    import os

    uri = os.getenv("MONGODB_TEST_URI")
    if not uri:
        pytest.skip("Set MONGODB_TEST_URI to run isolated MongoDB integration tests.")
    pytest.importorskip("pymongo")
    database_name = os.getenv("MONGODB_TEST_DATABASE", "smart_roster_test")
    if database_name != "smart_roster_test":
        pytest.fail("MongoDB integration tests are restricted to smart_roster_test.")

    manager = DatabaseConnectionManager(uri, database_name)
    if not manager.connect():
        pytest.fail("Could not connect to the dedicated MongoDB test database.")
    repository = MongoRepository(manager)
    try:
        repository.reset()
        pod = repository.create("pods", {"id": "POD-TEST", "pod_id": "POD-TEST", "pod_name": "Mongo Test Pod", "is_active": True})
        assert repository.get("pods", pod["id"])["pod_name"] == "Mongo Test Pod"
        assert repository.update("pods", pod["id"], {"description": "updated"})["description"] == "updated"
        assert repository.delete("pods", pod["id"])
        brand = repository.create("brands", {"id": "B-TEST", "brand_id": "B-TEST", "brand_name": "Mongo Test Brand", "is_active": True})
        process = repository.create("processes", {"id": "PR-TEST", "process_id": "PR-TEST", "process_name": "Mongo Test Process", "is_active": True})
        eligibility = repository.create("eligibility", {"id": "EL-TEST", "employee_id": "E001", "brand_id": brand["id"], "process_id": process["id"], "is_active": True})
        rule = repository.create("operating_rules", {"id": "RULE-TEST", "brand_id": brand["id"], "process_id": process["id"], "operating_days": ["Monday"], "public_holiday_policy": "closed", "minimum_staffing": 1, "coverage_overrides": [], "is_active": True})
        time_off = repository.create("time_off", {"id": "TO-TEST", "employee_id": "E001", "time_off_type": "planned_leave", "start_date": "2026-12-10", "end_date": "2026-12-11", "status": "pending"})
        holiday = repository.create("public_holidays", {"id": "HOL-TEST", "holiday_name": "Mongo Test Holiday", "holiday_date": "2026-12-25"})
        assert repository.get("eligibility", eligibility["id"])["employee_id"] == "E001"
        assert repository.update("operating_rules", rule["id"], {"minimum_staffing": 2})["minimum_staffing"] == 2
        assert repository.get("time_off", time_off["id"])["start_date"] == "2026-12-10"
        assert repository.get("public_holidays", holiday["id"])["holiday_date"] == "2026-12-25"
        assert repository.delete("eligibility", eligibility["id"])
        assert repository.delete("operating_rules", rule["id"])
        assert repository.delete("time_off", time_off["id"])
        assert repository.delete("public_holidays", holiday["id"])
        assert repository.delete("brands", brand["id"])
        assert repository.delete("processes", process["id"])

        employee = repository.create("employees", {
            "employee_id": "E001", "full_name": "Integration Test", "email": "mongo-test@example.com",
            "pod_id": None, "is_active": True, "weekly_off_per_week": 1, "workable_days": ["Monday"],
        })
        assert repository.get("employees", "E001")["id"] == employee["id"]
        repository.update("employees", "E001", {"full_name": "Updated"})
        assert repository.get("employees", "E001")["full_name"] == "Updated"
        repository.replace_employee_eligibility("E001", [{"brand_id": "B1", "process_id": "P1", "is_active": True}])
        assert len([row for row in repository.list("eligibility") if row["employee_id"] == "E001"]) == 1
        member_pod = repository.create("pods", {"id": "POD-MEMBER", "pod_id": "POD-MEMBER", "pod_name": "Membership test", "is_active": True})
        assert repository.set_pod_membership(member_pod["id"], ["E001"])[0]["pod_id"] == member_pod["id"]

        now = datetime.now(timezone.utc)
        roster = {"id": "roster-2026-12", "month": 12, "year": 2026, "status": "draft", "version": 1,
                  "generated_at": now, "published_at": None, "generated_by": None, "published_by": None,
                  "created_at": now, "updated_at": now, "summary": {}, "latest_validation": None}
        rows = [
            {"employee_id": "E001", "assignment_date": date(2026, 12, 7), "status": "working", "brand_id": "B1", "process_id": "P1"},
            {"employee_id": "E001", "assignment_date": date(2026, 12, 7), "status": "working", "brand_id": "B2", "process_id": "P2"},
            {"employee_id": "E001", "assignment_date": date(2026, 12, 8), "status": "weekly_off", "brand_id": None, "process_id": None},
        ]
        repository.create_roster_with_assignments(roster, rows)
        assert len(repository.list_roster_assignments(roster["id"])) == 3
        updated = repository.replace_roster_assignments(roster["id"], 1, rows[:2], summary={"total_assignments": 2})
        assert updated["version"] == 2
        with pytest.raises(ServiceError) as stale:
            repository.replace_roster_assignments(roster["id"], 1, rows)
        assert stale.value.code == "STALE_ROSTER_VERSION"
        repository.save_roster_validation(roster["id"], 2, {"valid": True})
        published = repository.publish_roster(roster["id"], 2, "test", {"valid": True})
        assert published["status"] == "published" and published["version"] == 3

        # A new client observes records saved by the first application process.
        restarted = DatabaseConnectionManager(uri, database_name)
        assert restarted.connect()
        assert MongoRepository(restarted).get("rosters", roster["id"])["status"] == "published"
        restarted.client.drop_database(database_name)
        restarted.close()
    finally:
        if manager.client is not None:
            manager.client.drop_database(database_name)
        manager.close()


@pytest.mark.mongodb
def test_mongodb_backed_api_generation_views_validation_edit_and_publish():
    import os
    from fastapi.testclient import TestClient

    uri = os.getenv("MONGODB_TEST_URI")
    if not uri:
        pytest.skip("Set MONGODB_TEST_URI to run isolated MongoDB integration tests.")
    pytest.importorskip("pymongo")
    database_name = os.getenv("MONGODB_TEST_DATABASE", "smart_roster_test")
    if database_name != "smart_roster_test":
        pytest.fail("MongoDB integration tests are restricted to smart_roster_test.")

    from app.core.config import Settings
    from app.main import create_app
    from app.repositories.memory import map_fixture
    from app.scheduling_engine.sample_data_fixed import get_dataset

    manager = DatabaseConnectionManager(uri, database_name)
    if not manager.connect():
        pytest.fail("Could not connect to the dedicated MongoDB test database.")
    repository = MongoRepository(manager)
    try:
        repository.reset()
        fixture = map_fixture(get_dataset("valid"))
        for logical in ("employees", "pods", "brands", "processes", "eligibility", "operating_rules", "time_off", "public_holidays"):
            for record in fixture[logical]:
                repository.upsert_seed_record(logical, record)
        assert len(repository.list("employees")) == 32
        assert len(repository.list("eligibility")) == 94

        settings = Settings(environment="testing", storage_backend="mongodb", mongodb_uri=uri,
                            mongodb_database=database_name)
        with TestClient(create_app(settings, repository)) as client:
            assert client.get("/api/v1/ready").json()["data"]["external_persistence"] is True
            generated = client.post("/api/v1/rosters/generate", json={"month": 12, "year": 2026})
            assert generated.status_code == 200
            assert generated.json()["summary"] == {
                "total_assignments": 2017, "total_weekly_offs": 155, "total_requirements": 1990,
                "requirements_satisfied": 1990, "coverage_gaps": 0, "active_employees": 31,
                "active_brands": 25, "active_processes": 3,
            }
            roster_id = generated.json()["roster"]["id"]
            metadata = client.get(f"/api/v1/rosters/{roster_id}").json()["data"]
            assert metadata["assignment_count"] == 2172
            assert client.get(f"/api/v1/rosters/{roster_id}/assignments").json()["total"] == 2172
            assert client.get(f"/api/v1/rosters/{roster_id}/weekly-offs").json()["total"] == 155
            assert client.get(f"/api/v1/rosters/{roster_id}/coverage").json()["summary"]["coverage_gaps"] == 0
            for view in ("company", "pod", "brand", "process", "employee"):
                assert client.get(f"/api/v1/rosters/{roster_id}/views/{view}").status_code == 200

            employee_master = repository.get("employees", "E001")
            impact = client.post(f"/api/v1/rosters/{roster_id}/check-impact", json={"change": {
                "change_type": "availability", "employee_id": "E001",
                "workable_days": employee_master["workable_days"],
                "weekly_off_per_week": employee_master["weekly_off_per_week"],
            }})
            assert impact.status_code == 200 and impact.json()["valid"] is True

            assignments = client.get(f"/api/v1/rosters/{roster_id}/assignments").json()["data"]
            assignment = next(row for row in assignments if row["status"] == "working")
            version = metadata["version"]
            edited = client.patch(
                f"/api/v1/rosters/{roster_id}/assignments/{assignment['id']}",
                headers={"If-Match": str(version)},
                json={"employee_id": assignment["employee_id"]},
            )
            assert edited.status_code == 200
            assert edited.json()["roster_version"] == version + 1
            stale = client.delete(
                f"/api/v1/rosters/{roster_id}/assignments/{assignment['id']}",
                headers={"If-Match": str(version)},
            )
            assert stale.status_code == 409
            eligible_pairs = {(row["employee_id"], row["brand_id"], row["process_id"])
                              for row in repository.list("eligibility") if row["is_active"]}
            employees = [row for row in repository.list("employees") if row["is_active"]]
            invalid = next((employee_row, brand_row, process_row)
                           for employee_row in employees
                           for brand_row in repository.list("brands")
                           for process_row in repository.list("processes")
                           if (employee_row["employee_id"], brand_row["brand_id"], process_row["process_id"]) not in eligible_pairs)
            before_invalid = len(repository.list_roster_assignments(roster_id))
            rejected = client.post(f"/api/v1/rosters/{roster_id}/assignments",
                                   headers={"If-Match": str(version + 1)},
                                   json={"employee_id": invalid[0]["employee_id"], "assignment_date": "2026-12-01",
                                         "brand_id": invalid[1]["brand_id"], "process_id": invalid[2]["process_id"]})
            assert rejected.status_code == 409
            assert len(repository.list_roster_assignments(roster_id)) == before_invalid
            validated = client.post(f"/api/v1/rosters/{roster_id}/validate")
            assert validated.status_code == 200 and validated.json()["valid"] is True
            published = client.post(f"/api/v1/rosters/{roster_id}/publish", json={"published_by": "integration-test"})
            assert published.status_code == 200
            assert published.json()["data"]["status"] == "published"

        # A separate repository/client observes the saved records after app restart.
        restarted = DatabaseConnectionManager(uri, database_name)
        assert restarted.connect()
        assert MongoRepository(restarted).get("rosters", "roster-2026-12")["status"] == "published"
        assert len(MongoRepository(restarted).list_roster_assignments("roster-2026-12")) == 2172
        restarted.client.drop_database(database_name)
        restarted.close()
    finally:
        if manager.client is not None:
            manager.client.drop_database(database_name)
        manager.close()
