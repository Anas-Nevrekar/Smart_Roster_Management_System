from datetime import date
from typing import Any

from app.core.errors import ServiceError
from app.repositories.contracts import CollectionName, MasterDataRepository
from app.repositories.memory import COLLECTIONS

REFS = {"employees": "INVALID_EMPLOYEE_REFERENCE", "pods": "INVALID_POD_REFERENCE", "brands": "INVALID_BRAND_REFERENCE", "processes": "INVALID_PROCESS_REFERENCE"}


class MasterDataService:
    def __init__(self, repo: MasterDataRepository):
        self.repo = repo

    def list(self, collection: CollectionName, filters: dict[str, Any] | None = None) -> list[dict[str, Any]]:
        rows = self.repo.list(collection)
        filters = filters or {}
        for key, value in filters.items():
            if value is None or value == "":
                continue
            if key == "search":
                term = str(value).casefold()
                rows = [r for r in rows if any(term in str(r.get(f, "")).casefold() for f in ("employee_id", "full_name", "email"))]
            elif key in {"start_date", "end_date"}:
                bound = date.fromisoformat(str(value))
                rows = [r for r in rows if (date.fromisoformat(str(r["start_date"])) <= bound if key == "start_date" else date.fromisoformat(str(r["end_date"])) >= bound)]
            elif key == "year":
                rows = [r for r in rows if date.fromisoformat(str(r["holiday_date"])).year == int(value)]
            else:
                rows = [r for r in rows if r.get(key) == value]
        return rows

    def get(self, collection: CollectionName, entity_id: str) -> dict[str, Any]:
        self._collection(collection)
        result = self.repo.get(collection, entity_id)
        if result is None:
            raise ServiceError(404, "RESOURCE_NOT_FOUND", "The requested resource was not found.")
        return result

    def create(self, collection: CollectionName, values: dict[str, Any]) -> dict[str, Any]:
        self._collection(collection)
        self._validate(collection, values)
        return self.repo.create(collection, values)

    def update(self, collection: CollectionName, entity_id: str, values: dict[str, Any]) -> dict[str, Any]:
        current = self.get(collection, entity_id)
        if collection == "employees" and values.get("employee_id", current["employee_id"]) != current["employee_id"]:
            raise ServiceError(400, "EMPLOYEE_ID_IMMUTABLE", "employee_id cannot be changed after creation.")
        self._validate(collection, values, exclude_id=entity_id)
        result = self.repo.update(collection, entity_id, values)
        assert result is not None
        return result

    def delete(self, collection: CollectionName, entity_id: str) -> bool:
        self.get(collection, entity_id)
        references = {
            "pods": any(e.get("pod_id") == entity_id for e in self.repo.list("employees")),
            "brands": any(x.get("brand_id") == entity_id for x in self.repo.list("eligibility") + self.repo.list("operating_rules")),
            "processes": any(x.get("process_id") == entity_id for x in self.repo.list("eligibility") + self.repo.list("operating_rules")),
            "employees": any(x.get("employee_id") == entity_id for x in self.repo.list("eligibility") + self.repo.list("time_off")),
        }.get(collection, False)
        if references:
            if collection in {"pods", "brands", "processes"}:
                self.repo.update(collection, entity_id, {"is_active": False})
                return False
            raise ServiceError(409, "RESOURCE_IN_USE", "This resource is referenced by existing records and cannot be deleted.")
        return self.repo.delete(collection, entity_id)

    def _validate(self, collection: CollectionName, values: dict[str, Any], exclude_id: str | None = None) -> None:
        rows = [r for r in self.repo.list(collection) if r.get("id") != exclude_id]
        if collection in {"eligibility", "operating_rules"}:
            fields = ("employee_id", "brand_id", "process_id") if collection == "eligibility" else ("brand_id", "process_id")
            if all(field in values for field in fields):
                if any(all(row.get(field) == values[field] for field in fields) for row in rows):
                    code = "DUPLICATE_ELIGIBILITY" if collection == "eligibility" else "DUPLICATE_OPERATING_RULE"
                    raise ServiceError(409, code, "This relationship already exists.")
        unique = {
            "employees": [("employee_id", "DUPLICATE_EMPLOYEE_ID"), ("email", "DUPLICATE_EMAIL")],
            "pods": [("pod_name", "DUPLICATE_POD_NAME")],
            "brands": [("brand_name", "DUPLICATE_BRAND_NAME")],
            "processes": [("process_name", "DUPLICATE_PROCESS_NAME")],
            "public_holidays": [("holiday_date", "DUPLICATE_HOLIDAY_DATE")],
        }.get(collection, [])
        for field, code in unique:
            if field in values:
                for row in rows:
                    same = row.get(field) == values[field]
                    if same:
                        raise ServiceError(409, code, f"A record with this {field.replace('_', ' ')} already exists.")
        refs = {"employees": [("pod_id", "pods")], "pods": [("pod_lead_id", "employees")], "eligibility": [("employee_id", "employees"), ("brand_id", "brands"), ("process_id", "processes")], "operating_rules": [("brand_id", "brands"), ("process_id", "processes")], "time_off": [("employee_id", "employees")]}.get(collection, [])
        for field, target in refs:
            value = values.get(field)
            if value is None:
                continue
            item = self.repo.get(target, value)
            if item is None:
                label = {"employees": "employee", "pods": "pod", "brands": "brand", "processes": "process"}[target]
                raise ServiceError(400, REFS[target], f"The referenced {label} does not exist.")
            if collection == "pods" and field == "pod_lead_id" and not item.get("is_active", True):
                raise ServiceError(400, "INVALID_POD_LEAD", "An inactive employee cannot be a pod lead.")
        if collection == "time_off" and values.get("end_date") and values.get("start_date"):
            if date.fromisoformat(str(values["end_date"])) < date.fromisoformat(str(values["start_date"])):
                raise ServiceError(400, "INVALID_DATE_RANGE", "end_date cannot be before start_date.")

    @staticmethod
    def _collection(collection: CollectionName) -> None:
        if collection not in COLLECTIONS:
            raise ValueError(f"Unknown collection: {collection}")
