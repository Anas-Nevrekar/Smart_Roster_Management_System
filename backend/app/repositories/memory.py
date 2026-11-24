from __future__ import annotations

from copy import deepcopy
from datetime import date, datetime, timezone
from threading import RLock
from typing import Any
from uuid import uuid4

from app.core.errors import ServiceError
from app.scheduling_engine.sample_data_fixed import get_dataset

COLLECTIONS = ("employees", "pods", "brands", "processes", "eligibility", "operating_rules", "time_off", "public_holidays", "rosters", "roster_assignments")


def _fixture_data(scenario: str = "valid") -> dict[str, Any]:
    """Load a fresh development fixture from the bundled engine package."""
    return deepcopy(get_dataset(scenario))


def map_fixture(data: dict[str, Any]) -> dict[str, list[dict[str, Any]]]:
    """Translate fixture names and IDs into the backend's stable API model."""
    now = datetime.now(timezone.utc)

    def stamped(record: dict[str, Any], entity_id: str) -> dict[str, Any]:
        return {"id": entity_id, **record, "created_at": now, "updated_at": now}

    employees = []
    for source in deepcopy(data["employees"]):
        employee = {key: value for key, value in source.items() if key != "name"}
        employee["full_name"] = source["name"]
        employees.append(stamped(employee, source["employee_id"]))
    pods = [stamped(p, p["pod_id"]) for p in deepcopy(data["pods"])]
    brands = [stamped(b, b["brand_id"]) for b in deepcopy(data["brands"])]
    processes = [stamped(p, p["process_id"]) for p in deepcopy(data["processes"])]
    eligibility = []
    for item in deepcopy(data["employee_assignments"]):
        key = f"ELIG-{item['employee_id']}-{item['brand_id']}-{item['process_id']}"
        eligibility.append(stamped(item, key))
    rules = []
    for rule in deepcopy(data["brand_process_rules"]):
        key = f"RULE-{rule['brand_id']}-{rule['process_id']}"
        rules.append(stamped(rule, key))
    time_off = [stamped(item, item["time_off_id"]) for item in deepcopy(data.get("employee_time_off", []))]
    public_holidays = []
    for index, item in enumerate(deepcopy(data.get("public_holidays", [])), start=1):
        entity = dict(item)
        holiday_id = entity.pop("holiday_id", f"HOL{index:03d}")
        public_holidays.append(stamped(entity, holiday_id))
    return dict(employees=employees, pods=pods, brands=brands, processes=processes,
                eligibility=eligibility, operating_rules=rules, time_off=time_off,
                public_holidays=public_holidays)


class InMemoryRepository:
    """Mutable process-local store with an independent seeded snapshot."""

    def __init__(self, scenario: str = "valid", seed: bool = True):
        self.scenario = scenario
        mapped = map_fixture(_fixture_data(scenario)) if seed else {name: [] for name in COLLECTIONS}
        mapped.setdefault("rosters", [])
        mapped.setdefault("roster_assignments", [])
        initial = {name: {item["id"]: item for item in mapped[name]} for name in COLLECTIONS}
        self._initial = deepcopy(initial)
        self._data = deepcopy(initial)
        self._lock = RLock()

    def list(self, collection: str) -> list[dict[str, Any]]:
        self._check(collection)
        with self._lock:
            return deepcopy(list(self._data[collection].values()))

    def get(self, collection: str, entity_id: str) -> dict[str, Any] | None:
        self._check(collection)
        with self._lock:
            item = self._data[collection].get(entity_id)
            return deepcopy(item) if item is not None else None

    def create(self, collection: str, record: dict[str, Any]) -> dict[str, Any]:
        self._check(collection)
        with self._lock:
            item = deepcopy(record)
            item.setdefault("id", str(uuid4()))
            item.setdefault("created_at", datetime.now(timezone.utc))
            item["updated_at"] = datetime.now(timezone.utc)
            if item["id"] in self._data[collection]:
                raise ServiceError(409, "DUPLICATE_RESOURCE", "A resource with this identifier already exists.")
            self._data[collection][item["id"]] = item
            return deepcopy(item)

    def update(self, collection: str, entity_id: str, record: dict[str, Any]) -> dict[str, Any] | None:
        self._check(collection)
        with self._lock:
            old = self._data[collection].get(entity_id)
            if old is None:
                return None
            item = {**old, **deepcopy(record), "id": entity_id, "created_at": old["created_at"], "updated_at": datetime.now(timezone.utc)}
            self._data[collection][entity_id] = item
            return deepcopy(item)

    def delete(self, collection: str, entity_id: str) -> bool:
        self._check(collection)
        with self._lock:
            return self._data[collection].pop(entity_id, None) is not None

    def replace_employee_eligibility(self, employee_id: str, items: list[dict[str, Any]]) -> list[dict[str, Any]]:
        with self._lock:
            for key, row in list(self._data["eligibility"].items()):
                if row["employee_id"] == employee_id:
                    del self._data["eligibility"][key]
            now = datetime.now(timezone.utc)
            result = []
            for source in items:
                row = deepcopy(source)
                row.setdefault("id", str(uuid4()))
                row["employee_id"] = employee_id
                row.setdefault("created_at", now)
                row["updated_at"] = now
                self._data["eligibility"][row["id"]] = row
                result.append(deepcopy(row))
            return result

    def set_pod_membership(self, pod_id: str, employee_ids: list[str]) -> list[dict[str, Any]]:
        with self._lock:
            selected = set(employee_ids)
            now = datetime.now(timezone.utc)
            for row in self._data["employees"].values():
                if row.get("pod_id") == pod_id or row["id"] in selected:
                    row["pod_id"] = pod_id if row["id"] in selected else None
                    row["updated_at"] = now
            return deepcopy([self._data["employees"][employee_id] for employee_id in employee_ids])

    def reset(self) -> None:
        with self._lock:
            self._data = deepcopy(self._initial)

    def _check(self, collection: str) -> None:
        if collection not in COLLECTIONS:
            raise ValueError(f"Unknown repository collection: {collection}")

    def snapshot(self) -> dict[str, list[dict[str, Any]]]:
        with self._lock:
            return {name: deepcopy(list(self._data[name].values())) for name in COLLECTIONS}

    def get_roster_by_month_year(self, month: int, year: int) -> dict[str, Any] | None:
        with self._lock:
            roster = next((x for x in self._data["rosters"].values() if x["month"] == month and x["year"] == year), None)
            return deepcopy(roster) if roster else None

    def create_roster_with_assignments(self, roster: dict[str, Any], assignments: list[dict[str, Any]]) -> dict[str, Any]:
        """Insert roster metadata and its assignments as one locked operation."""
        with self._lock:
            if any(x["month"] == roster["month"] and x["year"] == roster["year"] for x in self._data["rosters"].values()):
                raise ServiceError(409, "ROSTER_ALREADY_EXISTS", "A roster already exists for this month and year.")
            if roster["id"] in self._data["rosters"]:
                raise ServiceError(409, "ROSTER_ALREADY_EXISTS", "A roster already exists for this month and year.")
            normalized = [self._prepare_assignment(x, roster["id"]) for x in assignments]
            self._validate_assignment_set(normalized)
            if {x["id"] for x in normalized} & self._data["roster_assignments"].keys():
                raise ServiceError(409, "DUPLICATE_ASSIGNMENT_ID", "Assignment identifiers must be unique.")
            self._data["rosters"][roster["id"]] = deepcopy(roster)
            for item in normalized:
                self._data["roster_assignments"][item["id"]] = item
            return deepcopy(roster)

    def list_roster_assignments(self, roster_id: str) -> list[dict[str, Any]]:
        with self._lock:
            return deepcopy([x for x in self._data["roster_assignments"].values() if x["roster_id"] == roster_id])

    def replace_roster_assignments(self, roster_id: str, expected_version: int, assignments: list[dict[str, Any]], *, generated_at=None, summary=None, master_data_fingerprint=None) -> dict[str, Any]:
        """Compare-and-swap a draft's full assignment set and metadata atomically."""
        with self._lock:
            roster = self._require_editable_roster(roster_id, expected_version)
            normalized = [self._prepare_assignment(x, roster_id) for x in assignments]
            self._validate_assignment_set(normalized)
            other_ids = {x["id"] for x in self._data["roster_assignments"].values() if x["roster_id"] != roster_id}
            if {x["id"] for x in normalized} & other_ids:
                raise ServiceError(409, "DUPLICATE_ASSIGNMENT_ID", "Assignment identifiers must be unique.")
            replacement = {x["id"]: x for x in normalized}
            for assignment_id, existing in list(self._data["roster_assignments"].items()):
                if existing["roster_id"] == roster_id:
                    del self._data["roster_assignments"][assignment_id]
            self._data["roster_assignments"].update(replacement)
            if generated_at is not None:
                roster["generated_at"] = generated_at
            if summary is not None:
                roster["summary"] = deepcopy(summary)
            if master_data_fingerprint is not None:
                roster["master_data_fingerprint"] = master_data_fingerprint
            roster["latest_validation"] = None
            roster["version"] += 1
            roster["updated_at"] = datetime.now(timezone.utc)
            self._data["rosters"][roster_id] = roster
            return deepcopy(roster)

    def save_roster_validation(self, roster_id: str, expected_version: int, validation: dict[str, Any]) -> dict[str, Any]:
        with self._lock:
            roster = self._require_version(roster_id, expected_version)
            roster["latest_validation"] = deepcopy(validation)
            roster["updated_at"] = datetime.now(timezone.utc)
            self._data["rosters"][roster_id] = roster
            return deepcopy(roster)

    def publish_roster(self, roster_id: str, expected_version: int, published_by: str | None, validation: dict[str, Any]) -> dict[str, Any]:
        with self._lock:
            roster = self._require_editable_roster(roster_id, expected_version)
            roster.update({
                "status": "published",
                "published_at": datetime.now(timezone.utc),
                "published_by": published_by,
                "latest_validation": deepcopy(validation),
                "version": roster["version"] + 1,
                "updated_at": datetime.now(timezone.utc),
            })
            self._data["rosters"][roster_id] = roster
            return deepcopy(roster)

    def rollback_roster_creation(self, roster_id: str) -> None:
        with self._lock:
            self._data["rosters"].pop(roster_id, None)
            for assignment_id, assignment in list(self._data["roster_assignments"].items()):
                if assignment["roster_id"] == roster_id:
                    del self._data["roster_assignments"][assignment_id]

    def _require_version(self, roster_id: str, expected_version: int) -> dict[str, Any]:
        roster = self._data["rosters"].get(roster_id)
        if roster is None:
            raise ServiceError(404, "RESOURCE_NOT_FOUND", "The requested roster was not found.")
        if roster["version"] != expected_version:
            raise ServiceError(409, "STALE_ROSTER_VERSION", "The roster changed since it was read. Refresh and retry.")
        return roster

    def _require_editable_roster(self, roster_id: str, expected_version: int) -> dict[str, Any]:
        roster = self._require_version(roster_id, expected_version)
        if roster["status"] != "draft":
            raise ServiceError(409, "ROSTER_IMMUTABLE", "Published rosters cannot be edited.")
        return roster

    @staticmethod
    def _prepare_assignment(record: dict[str, Any], roster_id: str) -> dict[str, Any]:
        item = deepcopy(record)
        item["roster_id"] = roster_id
        item.setdefault("id", str(uuid4()))
        item.setdefault("created_at", datetime.now(timezone.utc))
        item["updated_at"] = datetime.now(timezone.utc)
        item.setdefault("brand_id", None)
        item.setdefault("process_id", None)
        return item

    @staticmethod
    def _validate_assignment_set(assignments: list[dict[str, Any]]) -> None:
        keys = set()
        weekly_off_dates = set()
        working_dates = set()
        for item in assignments:
            owner_date = (item["employee_id"], item["assignment_date"])
            if item["status"] == "working":
                key = (*owner_date, item.get("brand_id"), item.get("process_id"))
                if not key[2] or not key[3]:
                    raise ServiceError(422, "INVALID_ASSIGNMENT", "Working assignments require a brand and process.")
                if key in keys:
                    raise ServiceError(409, "DUPLICATE_ASSIGNMENT", "Duplicate employee, date, brand, and process assignment.")
                keys.add(key)
                working_dates.add(owner_date)
            elif item["status"] == "weekly_off":
                if item.get("brand_id") is not None or item.get("process_id") is not None:
                    raise ServiceError(422, "INVALID_WEEKLY_OFF", "Weekly-off records cannot include a brand or process.")
                if owner_date in weekly_off_dates:
                    raise ServiceError(409, "DUPLICATE_WEEKLY_OFF", "Duplicate weekly-off record for the employee and date.")
                weekly_off_dates.add(owner_date)
            else:
                raise ServiceError(422, "INVALID_ASSIGNMENT_STATUS", "Assignment status must be working or weekly_off.")
        if weekly_off_dates & working_dates:
            raise ServiceError(409, "WEEKLY_OFF_OVERLAP", "An employee cannot have a working assignment on a weekly-off date.")
        ids = [item["id"] for item in assignments]
        if len(ids) != len(set(ids)):
            raise ServiceError(409, "DUPLICATE_ASSIGNMENT_ID", "Assignment identifiers must be unique.")
