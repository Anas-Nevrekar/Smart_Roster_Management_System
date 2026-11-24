"""Synchronous PyMongo implementation of the shared repository contract."""
from __future__ import annotations

from copy import deepcopy
from datetime import date, datetime, time, timezone
from typing import Any
from uuid import uuid4

from app.core.database import DatabaseConnectionManager
from app.core.errors import ServiceError
from app.repositories.memory import COLLECTIONS, InMemoryRepository

COLLECTION_NAMES = {
    "employees": "employees",
    "pods": "pods",
    "brands": "brands",
    "processes": "processes",
    "eligibility": "employee_assignments",
    "operating_rules": "brand_process_rules",
    "time_off": "employee_time_off",
    "public_holidays": "public_holidays",
    "rosters": "rosters",
    "roster_assignments": "roster_assignments",
}
DATE_FIELDS = {
    "time_off": ("start_date", "end_date"),
    "public_holidays": ("holiday_date",),
    "roster_assignments": ("assignment_date",),
}


def _bson_date(value: Any):
    if isinstance(value, datetime):
        return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value.astimezone(timezone.utc)
    if isinstance(value, date):
        return datetime.combine(value, time.min, tzinfo=timezone.utc)
    if isinstance(value, str):
        return datetime.combine(date.fromisoformat(value), time.min, tzinfo=timezone.utc)
    return value


def to_document(collection: str, record: dict[str, Any]) -> dict[str, Any]:
    """Map a repository record to BSON fields while retaining stable domain IDs."""
    document = deepcopy(record)
    entity_id = str(document.pop("id", document.get("_id", uuid4())))
    document.pop("_id", None)
    document["_id"] = entity_id
    for field in DATE_FIELDS.get(collection, ()):
        if field in document and document[field] is not None:
            document[field] = _bson_date(document[field])
    for field in ("created_at", "updated_at", "generated_at", "published_at"):
        value = document.get(field)
        if isinstance(value, datetime):
            document[field] = value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value.astimezone(timezone.utc)
    return document


def from_document(collection: str, document: dict[str, Any] | None) -> dict[str, Any] | None:
    if document is None:
        return None
    record = deepcopy(document)
    entity_id = record.pop("_id", record.get("id"))
    record["id"] = str(entity_id)
    for field in DATE_FIELDS.get(collection, ()):
        value = record.get(field)
        if isinstance(value, datetime):
            record[field] = value.date().isoformat()
        elif isinstance(value, date):
            record[field] = value.isoformat()
    for field in ("created_at", "updated_at", "generated_at", "published_at"):
        value = record.get(field)
        if isinstance(value, datetime) and value.tzinfo is None:
            record[field] = value.replace(tzinfo=timezone.utc)
    return record


def _duplicate_key(exc: Exception) -> bool:
    return type(exc).__name__ == "DuplicateKeyError" or getattr(exc, "code", None) == 11000


class MongoRepository:
    """Persistent repository; database work is performed by sync FastAPI routes' threadpool."""

    def __init__(self, manager: DatabaseConnectionManager):
        self.manager = manager

    def _database(self):
        return self.manager.require_database()

    @staticmethod
    def _name(collection: str) -> str:
        if collection not in COLLECTION_NAMES:
            raise ValueError(f"Unknown repository collection: {collection}")
        return COLLECTION_NAMES[collection]

    def _collection(self, collection: str):
        return self._database()[self._name(collection)]

    def _failure(self, exc: Exception, collection: str | None = None) -> ServiceError:
        if _duplicate_key(exc):
            details = getattr(exc, "details", None) or {}
            pattern = details.get("keyPattern", {})
            field = next(iter(pattern), "")
            codes = {
                ("employees", "employee_id"): "DUPLICATE_EMPLOYEE_ID",
                ("employees", "email"): "DUPLICATE_EMAIL",
                ("pods", "pod_name"): "DUPLICATE_POD_NAME",
                ("brands", "brand_name"): "DUPLICATE_BRAND_NAME",
                ("processes", "process_name"): "DUPLICATE_PROCESS_NAME",
                ("public_holidays", "holiday_date"): "DUPLICATE_HOLIDAY_DATE",
                ("eligibility", "employee_id"): "DUPLICATE_ELIGIBILITY",
                ("operating_rules", "brand_id"): "DUPLICATE_OPERATING_RULE",
                ("rosters", "month"): "ROSTER_ALREADY_EXISTS",
                ("roster_assignments", "status"): "DUPLICATE_WEEKLY_OFF",
                ("roster_assignments", "process_id"): "DUPLICATE_ASSIGNMENT",
            }
            if collection == "roster_assignments" and "assignment_date" in pattern:
                code = "DUPLICATE_ASSIGNMENT" if "process_id" in pattern else "DUPLICATE_WEEKLY_OFF"
            else:
                code = codes.get((collection, field), "DUPLICATE_RESOURCE")
            messages = {
                "ROSTER_ALREADY_EXISTS": "A roster already exists for this month and year.",
                "DUPLICATE_ASSIGNMENT": "Duplicate employee, date, brand, and process assignment.",
                "DUPLICATE_WEEKLY_OFF": "Duplicate weekly-off record for the employee and date.",
            }
            return ServiceError(409, code, messages.get(code, "A record with the same unique values already exists."))
        self.manager.mark_unavailable()
        return ServiceError(503, "DATABASE_UNAVAILABLE", "MongoDB could not complete the request. Check database readiness and retry.")

    def _transaction(self, operation, collection: str | None = None):
        database = self._database()
        try:
            with self.manager.client.start_session() as session:
                return session.with_transaction(lambda active: operation(database, active))
        except ServiceError:
            raise
        except Exception as exc:
            raise self._failure(exc, collection) from exc

    def list(self, collection: str) -> list[dict[str, Any]]:
        try:
            name = self._name(collection)
            return [from_document(collection, row) for row in self._collection(collection).find({}).sort("_id", 1)]
        except ServiceError:
            raise
        except Exception as exc:
            raise self._failure(exc, collection) from exc

    def get(self, collection: str, entity_id: str) -> dict[str, Any] | None:
        try:
            row = self._collection(collection).find_one({"_id": str(entity_id)})
            return from_document(collection, row)
        except ServiceError:
            raise
        except Exception as exc:
            raise self._failure(exc, collection) from exc

    def create(self, collection: str, record: dict[str, Any]) -> dict[str, Any]:
        try:
            item = deepcopy(record)
            item.setdefault("id", str(uuid4()))
            now = datetime.now(timezone.utc)
            item.setdefault("created_at", now)
            item["updated_at"] = now
            document = to_document(collection, item)
            self._collection(collection).insert_one(document)
            return from_document(collection, document)
        except ServiceError:
            raise
        except Exception as exc:
            raise self._failure(exc, collection) from exc

    def update(self, collection: str, entity_id: str, record: dict[str, Any]) -> dict[str, Any] | None:
        try:
            values = deepcopy(record)
            values.pop("id", None)
            values.pop("_id", None)
            values.pop("created_at", None)
            for field in DATE_FIELDS.get(collection, ()):
                if field in values and values[field] is not None:
                    values[field] = _bson_date(values[field])
            result = self._collection(collection).update_one(
                {"_id": str(entity_id)}, {"$set": values, "$currentDate": {"updated_at": True}},
            )
            if not result.matched_count:
                return None
            return self.get(collection, entity_id)
        except ServiceError:
            raise
        except Exception as exc:
            raise self._failure(exc, collection) from exc

    def delete(self, collection: str, entity_id: str) -> bool:
        try:
            return bool(self._collection(collection).delete_one({"_id": str(entity_id)}).deleted_count)
        except ServiceError:
            raise
        except Exception as exc:
            raise self._failure(exc, collection) from exc

    def replace_employee_eligibility(self, employee_id: str, items: list[dict[str, Any]]) -> list[dict[str, Any]]:
        now = datetime.now(timezone.utc)
        documents = []
        for source in items:
            record = {**deepcopy(source), "id": source.get("id", str(uuid4())), "employee_id": employee_id}
            record.setdefault("created_at", now)
            record["updated_at"] = now
            documents.append(to_document("eligibility", record))

        def replace(database, session):
            database["employee_assignments"].delete_many({"employee_id": employee_id}, session=session)
            if documents:
                database["employee_assignments"].insert_many(documents, ordered=True, session=session)
            return [from_document("eligibility", row) for row in documents]

        return self._transaction(replace, "eligibility")

    def set_pod_membership(self, pod_id: str, employee_ids: list[str]) -> list[dict[str, Any]]:
        now = datetime.now(timezone.utc)
        selected = list(dict.fromkeys(employee_ids))

        def replace(database, session):
            database["employees"].update_many(
                {"pod_id": pod_id, "_id": {"$nin": selected}},
                {"$set": {"pod_id": None, "updated_at": now}}, session=session,
            )
            if selected:
                database["employees"].update_many(
                    {"_id": {"$in": selected}}, {"$set": {"pod_id": pod_id, "updated_at": now}}, session=session,
                )
            return [from_document("employees", row) for row in database["employees"].find({"_id": {"$in": selected}}, session=session)]

        return self._transaction(replace, "employees")

    def reset(self) -> None:
        """Clear only the isolated integration-test database; never dev or production data."""
        database = self._database()
        if database.name != "smart_roster_test":
            raise ServiceError(403, "RESET_NOT_ALLOWED", "Repository reset is restricted to smart_roster_test.")
        try:
            for collection in COLLECTION_NAMES.values():
                database[collection].delete_many({})
        except Exception as exc:
            raise self._failure(exc) from exc

    def snapshot(self) -> dict[str, list[dict[str, Any]]]:
        return {collection: self.list(collection) for collection in COLLECTIONS}

    def get_roster_by_month_year(self, month: int, year: int) -> dict[str, Any] | None:
        try:
            row = self._collection("rosters").find_one({"month": month, "year": year})
            return from_document("rosters", row)
        except ServiceError:
            raise
        except Exception as exc:
            raise self._failure(exc, "rosters") from exc

    def list_roster_assignments(self, roster_id: str) -> list[dict[str, Any]]:
        try:
            rows = self._collection("roster_assignments").find({"roster_id": roster_id}).sort(
                [("assignment_date", 1), ("employee_id", 1), ("brand_id", 1), ("process_id", 1)],
            )
            return [from_document("roster_assignments", row) for row in rows]
        except ServiceError:
            raise
        except Exception as exc:
            raise self._failure(exc, "roster_assignments") from exc

    @staticmethod
    def _normalize_assignments(roster_id: str, assignments: list[dict[str, Any]]) -> list[dict[str, Any]]:
        normalized = [InMemoryRepository._prepare_assignment(row, roster_id) for row in assignments]
        InMemoryRepository._validate_assignment_set(normalized)
        return normalized

    def create_roster_with_assignments(self, roster: dict[str, Any], assignments: list[dict[str, Any]]) -> dict[str, Any]:
        normalized = self._normalize_assignments(roster["id"], assignments)
        roster_document = to_document("rosters", roster)
        assignment_documents = [to_document("roster_assignments", row) for row in normalized]

        def insert(database, session):
            database["rosters"].insert_one(roster_document, session=session)
            if assignment_documents:
                database["roster_assignments"].insert_many(assignment_documents, ordered=True, session=session)
            return from_document("rosters", roster_document)

        try:
            return self._transaction(insert, "rosters")
        except ServiceError:
            raise
        except Exception as exc:
            raise self._failure(exc, "rosters") from exc

    def replace_roster_assignments(self, roster_id: str, expected_version: int, assignments: list[dict[str, Any]], *, generated_at=None, summary=None, master_data_fingerprint=None) -> dict[str, Any]:
        normalized = self._normalize_assignments(roster_id, assignments)
        assignment_documents = [to_document("roster_assignments", row) for row in normalized]
        changes: dict[str, Any] = {"updated_at": datetime.now(timezone.utc), "latest_validation": None}
        if generated_at is not None:
            changes["generated_at"] = generated_at
        if summary is not None:
            changes["summary"] = deepcopy(summary)
        if master_data_fingerprint is not None:
            changes["master_data_fingerprint"] = master_data_fingerprint

        def replace(database, session):
            current = database["rosters"].find_one_and_update(
                {"_id": roster_id, "version": expected_version, "status": "draft"},
                {"$set": changes, "$inc": {"version": 1}}, return_document=True, session=session,
            )
            if current is None:
                self._raise_roster_conflict(database, roster_id, expected_version, session)
            database["roster_assignments"].delete_many({"roster_id": roster_id}, session=session)
            if assignment_documents:
                database["roster_assignments"].insert_many(assignment_documents, ordered=True, session=session)
            return from_document("rosters", current)

        try:
            return self._transaction(replace, "roster_assignments")
        except ServiceError:
            raise
        except Exception as exc:
            raise self._failure(exc, "roster_assignments") from exc

    def save_roster_validation(self, roster_id: str, expected_version: int, validation: dict[str, Any]) -> dict[str, Any]:
        try:
            now = datetime.now(timezone.utc)
            row = self._collection("rosters").find_one_and_update(
                {"_id": roster_id, "version": expected_version},
                {"$set": {"latest_validation": deepcopy(validation), "updated_at": now}},
                return_document=True,
            )
            if row is None:
                self._raise_roster_conflict(self._database(), roster_id, expected_version)
            return from_document("rosters", row)
        except ServiceError:
            raise
        except Exception as exc:
            raise self._failure(exc, "rosters") from exc

    def publish_roster(self, roster_id: str, expected_version: int, published_by: str | None, validation: dict[str, Any]) -> dict[str, Any]:
        now = datetime.now(timezone.utc)

        def publish(database, session):
            row = database["rosters"].find_one_and_update(
                {"_id": roster_id, "version": expected_version, "status": "draft"},
                {"$set": {"status": "published", "published_at": now, "published_by": published_by,
                          "latest_validation": deepcopy(validation), "updated_at": now},
                 "$inc": {"version": 1}},
                return_document=True, session=session,
            )
            if row is None:
                self._raise_roster_conflict(database, roster_id, expected_version, session)
            return from_document("rosters", row)

        return self._transaction(publish, "rosters")

    @staticmethod
    def _raise_roster_conflict(database, roster_id: str, expected_version: int, session=None) -> None:
        existing = database["rosters"].find_one({"_id": roster_id}, session=session)
        if existing is None:
            raise ServiceError(404, "RESOURCE_NOT_FOUND", "The requested roster was not found.")
        if existing.get("version") != expected_version:
            raise ServiceError(409, "STALE_ROSTER_VERSION", "The roster changed since it was read. Refresh and retry.")
        if existing.get("status") != "draft":
            raise ServiceError(409, "ROSTER_IMMUTABLE", "Published rosters cannot be edited.")
        raise ServiceError(409, "ROSTER_UPDATE_CONFLICT", "The roster changed while the operation was being saved.")

    def rollback_roster_creation(self, roster_id: str) -> None:
        def rollback(database, session):
            database["roster_assignments"].delete_many({"roster_id": roster_id}, session=session)
            database["rosters"].delete_one({"_id": roster_id}, session=session)

        self._transaction(rollback, "rosters")

    def upsert_seed_record(self, collection: str, record: dict[str, Any]) -> str:
        """Insert or update one known fixture row without deleting user-created records."""
        try:
            coll = self._collection(collection)
            document = to_document(collection, record)
            now = datetime.now(timezone.utc)
            document.setdefault("created_at", now)
            document.setdefault("updated_at", now)
            existing = coll.find_one({"_id": document["_id"]})
            if existing is None:
                coll.insert_one(document)
                return "inserted"
            comparable_existing = {k: v for k, v in existing.items() if k not in {"created_at", "updated_at"}}
            comparable_new = {k: v for k, v in document.items() if k not in {"created_at", "updated_at"}}
            if comparable_existing == comparable_new:
                return "unchanged"
            document["created_at"] = existing.get("created_at", document.get("created_at"))
            document["updated_at"] = datetime.now(timezone.utc)
            coll.replace_one({"_id": document["_id"]}, document, upsert=True)
            return "updated"
        except ServiceError:
            raise
        except Exception as exc:
            raise self._failure(exc, collection) from exc
