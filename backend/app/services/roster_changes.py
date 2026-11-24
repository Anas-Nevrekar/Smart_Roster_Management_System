from copy import deepcopy
from datetime import date
import json
from typing import Any
from uuid import uuid4

from app.core.errors import ServiceError
from app.integrations.roster_engine.adapter import RosterEngineAdapter
from app.integrations.roster_engine.exceptions import EngineIntegrationError
from app.integrations.roster_engine.mapper import map_repository_snapshot
from app.repositories.contracts import MasterDataRepository
from app.schemas.roster_changes import (
    AssignmentCreate, AssignmentPatch, AvailabilityImpact, ChangeImpactRequest,
    EligibilityImpact, OperatingRuleImpact, TimeOffImpact,
)
from app.services.roster_management import RosterManagementService

ERROR_CODES = {
    "ineligible_assignment": "INVALID_ELIGIBILITY",
    "inactive_or_unknown_employee": "INVALID_EMPLOYEE",
    "inactive_or_missing_operating_rule": "INVALID_BRAND_OR_PROCESS",
    "approved_time_off": "APPROVED_TIME_OFF_CONFLICT",
    "weekly_off_overlap": "WEEKLY_OFF_CONFLICT",
    "weekly_off_on_approved_time_off": "APPROVED_TIME_OFF_CONFLICT",
    "unworkable_day": "NON_WORKABLE_DAY",
    "closed_operating_day": "CLOSED_OPERATING_DAY",
    "duplicate_assignment": "DUPLICATE_ASSIGNMENT",
    "insufficient_staffing": "STAFFING_GAP",
    "invalid_requirement": "ASSIGNMENT_OUTSIDE_OR_INVALID_OPERATING_DAY",
}

MESSAGES = {
    "INVALID_ELIGIBILITY": "The employee is not eligible for this brand and process.",
    "INVALID_EMPLOYEE": "The employee is missing or inactive.",
    "INVALID_BRAND_OR_PROCESS": "The brand-process operating rule is unavailable or inactive.",
    "APPROVED_TIME_OFF_CONFLICT": "The employee has approved time off for this date.",
    "WEEKLY_OFF_CONFLICT": "The employee is on a weekly off for this date.",
    "NON_WORKABLE_DAY": "The assignment date is not a workable weekday for the employee.",
    "CLOSED_OPERATING_DAY": "The brand-process does not operate on this date.",
    "DUPLICATE_ASSIGNMENT": "This employee already has this brand-process assignment on this date.",
    "STAFFING_GAP": "The change would leave a required staffing gap.",
    "ASSIGNMENT_OUTSIDE_OR_INVALID_OPERATING_DAY": "The assignment does not match a requirement in this roster month.",
}


class RosterChangeService:
    def __init__(self, repository: MasterDataRepository, engine: RosterEngineAdapter | None = None):
        self.repository = repository
        self.engine = engine or RosterEngineAdapter()

    def add_assignment(self, roster_id: str, expected_version: int, payload: AssignmentCreate) -> dict[str, Any]:
        roster, records, data = self._draft_snapshot(roster_id, expected_version)
        assignment_date = payload.assignment_date.isoformat()
        self._assert_month(roster, assignment_date)
        record = {"id": str(uuid4()), "roster_id": roster_id, "employee_id": payload.employee_id,
                  "assignment_date": assignment_date, "status": "working", "brand_id": payload.brand_id,
                  "process_id": payload.process_id}
        candidate = [*records, record]
        validation = self._validate_candidate(data, candidate, roster)
        self._reject_invalid(validation)
        updated_roster = self.repository.replace_roster_assignments(roster_id, expected_version, candidate, summary=validation["summary"])
        enriched = RosterManagementService(self.repository, self.engine).assignments(roster_id, {"employee_id": payload.employee_id, "start_date": payload.assignment_date, "end_date": payload.assignment_date})
        saved = next(x for x in enriched if x["id"] == record["id"])
        return {"success": True, "assignment": saved, "roster_version": updated_roster["version"],
                "validation": {"valid": True, "errors": [], "summary": validation["summary"]}}

    def update_assignment(self, roster_id: str, assignment_id: str, expected_version: int, payload: AssignmentPatch) -> dict[str, Any]:
        roster, records, data = self._draft_snapshot(roster_id, expected_version)
        current = next((x for x in records if x["id"] == assignment_id), None)
        if current is None:
            raise ServiceError(404, "RESOURCE_NOT_FOUND", "The requested assignment was not found.")
        if current["status"] != "working":
            raise ServiceError(409, "WEEKLY_OFF_IMMUTABLE", "Weekly-off records cannot be changed through assignment endpoints.")
        changes = payload.model_dump(mode="json", exclude_unset=True)
        assignment_date = changes.get("assignment_date", current["assignment_date"])
        self._assert_month(roster, assignment_date)
        candidate = deepcopy(records)
        edited = next(x for x in candidate if x["id"] == assignment_id)
        edited.update(changes)
        validation = self._validate_candidate(data, candidate, roster)
        self._reject_invalid(validation)
        updated_roster = self.repository.replace_roster_assignments(roster_id, expected_version, candidate, summary=validation["summary"])
        saved = self.repository.get("roster_assignments", assignment_id)
        enriched = next(x for x in RosterManagementService(self.repository, self.engine).assignments(roster_id) if x["id"] == assignment_id)
        return {"success": True, "assignment": enriched, "roster_version": updated_roster["version"],
                "validation": {"valid": True, "errors": [], "summary": validation["summary"]}}

    def delete_assignment(self, roster_id: str, assignment_id: str, expected_version: int) -> dict[str, Any]:
        roster, records, data = self._draft_snapshot(roster_id, expected_version)
        current = next((x for x in records if x["id"] == assignment_id), None)
        if current is None:
            raise ServiceError(404, "RESOURCE_NOT_FOUND", "The requested assignment was not found.")
        if current["status"] != "working":
            raise ServiceError(409, "WEEKLY_OFF_IMMUTABLE", "Weekly-off records cannot be changed through assignment endpoints.")
        candidate = [x for x in records if x["id"] != assignment_id]
        validation = self._validate_candidate(data, candidate, roster)
        self._reject_invalid(validation)
        updated_roster = self.repository.replace_roster_assignments(roster_id, expected_version, candidate, summary=validation["summary"])
        return {"success": True, "deleted_assignment_id": assignment_id,
                "roster_version": updated_roster["version"],
                "validation": {"valid": True, "errors": [], "summary": validation["summary"]}}

    def check_impact(self, roster_id: str, request: ChangeImpactRequest) -> dict[str, Any]:
        snapshot = self.repository.snapshot()
        roster = self._roster_from_snapshot(snapshot, roster_id)
        records = [x for x in snapshot["roster_assignments"] if x["roster_id"] == roster_id]
        before = deepcopy(snapshot)
        proposed = deepcopy(snapshot)
        self._apply_change(proposed, request.change)
        before_data = map_repository_snapshot(before)
        after_data = map_repository_snapshot(proposed)
        working = [self._engine_assignment(x) for x in records if x["status"] == "working"]
        offs = [self._engine_weekly_off(x) for x in records if x["status"] == "weekly_off"]
        before_validation = self._validate(before_data, working, offs, roster)
        after_validation = self._validate(after_data, working, offs, roster)
        before_coverage = RosterManagementService(self.repository, self.engine).coverage(roster_id, before)["data"]
        after_coverage = RosterManagementService(self.repository, self.engine).coverage(roster_id, proposed)["data"]
        before_rows = {(x["date"], x["brand_id"], x["process_id"]): x for x in before_coverage}
        after_rows = {(x["date"], x["brand_id"], x["process_id"]): x for x in after_coverage}
        staffing_impact = []
        for key, after_row in after_rows.items():
            prior = before_rows.get(key)
            if prior and any(prior[field] != after_row[field] for field in ("required_staffing", "actual_staffing", "staffing_gap", "status")):
                staffing_impact.append({"date": after_row["date"], "brand_id": after_row["brand_id"],
                    "brand_name": after_row["brand_name"], "process_id": after_row["process_id"],
                    "process_name": after_row["process_name"], "before": {k: prior[k] for k in ("required_staffing", "actual_staffing", "staffing_gap", "status")},
                    "after": {k: after_row[k] for k in ("required_staffing", "actual_staffing", "staffing_gap", "status")}})
        before_error_keys = {self._error_key(x) for x in before_validation["errors"]}
        new_errors = [x for x in after_validation["errors"] if self._error_key(x) not in before_error_keys]
        added_gaps = [x for x in staffing_impact if x["after"]["status"] == "understaffed" and x["before"]["status"] != "understaffed"]
        conflicts = [self._diagnostic(x) for x in new_errors]
        existing_gap_keys = {(x.get("date"), x.get("brand_id"), x.get("process_id")) for x in new_errors if x.get("code") == "insufficient_staffing"}
        for gap in added_gaps:
            if (gap["date"], gap["brand_id"], gap["process_id"]) in existing_gap_keys:
                continue
            conflicts.append({"code": "STAFFING_GAP", "date": gap["date"], "brand_id": gap["brand_id"],
                "process_id": gap["process_id"], "required_staffing": gap["after"]["required_staffing"],
                "actual_staffing": gap["after"]["actual_staffing"], "message": "The proposed change creates a staffing gap."})
        affected_dates = {x["date"] for x in conflicts if x.get("date")}
        affected_dates.update(x["date"] for x in staffing_impact)
        employee_ids = {x["employee_id"] for x in conflicts if x.get("employee_id")}
        if isinstance(request.change, (AvailabilityImpact, TimeOffImpact, EligibilityImpact)):
            employee_ids.add(request.change.employee_id)
        brand_ids = {x["brand_id"] for x in conflicts if x.get("brand_id")}
        process_ids = {x["process_id"] for x in conflicts if x.get("process_id")}
        if isinstance(request.change, (EligibilityImpact, OperatingRuleImpact)):
            brand_ids.add(request.change.brand_id)
            process_ids.add(request.change.process_id)
        brand_ids.update(x["brand_id"] for x in staffing_impact)
        process_ids.update(x["process_id"] for x in staffing_impact)
        return {
            "valid": bool(after_validation["valid"] and not added_gaps),
            "change_type": request.change.change_type,
            "roster_id": roster_id,
            "current_version": roster["version"],
            "affected_dates": sorted(affected_dates),
            "affected_employees": sorted(employee_ids),
            "affected_brands": sorted(brand_ids),
            "affected_processes": sorted(process_ids),
            "staffing_impact": staffing_impact,
            "conflicts": conflicts,
            "warnings": [self._diagnostic(x) for x in before_validation["errors"]],
            "summary": {"new_conflicts": len(conflicts), "coverage_changes": len(staffing_impact),
                        "new_coverage_gaps": len(added_gaps), "valid": bool(after_validation["valid"] and not added_gaps)},
        }

    def _draft_snapshot(self, roster_id, expected_version):
        roster = self._roster(roster_id)
        self._check_version(roster, expected_version)
        if roster["status"] != "draft":
            raise ServiceError(409, "ROSTER_IMMUTABLE", "Published rosters cannot be edited.")
        snapshot = self.repository.snapshot()
        return roster, self.repository.list_roster_assignments(roster_id), map_repository_snapshot(snapshot)

    def _validate_candidate(self, dataset, records, roster):
        try:
            return self._validate(dataset,
                [self._engine_assignment(x) for x in records if x["status"] == "working"],
                [self._engine_weekly_off(x) for x in records if x["status"] == "weekly_off"], roster)
        except EngineIntegrationError as exc:
            raise ServiceError(422 if exc.code == "UNSUPPORTED_COVERAGE_OVERRIDES" else 500, exc.code, exc.message) from exc

    def _validate(self, dataset, working, offs, roster):
        try:
            return self.engine.validate(dataset, working, offs, roster["month"], roster["year"])
        except EngineIntegrationError as exc:
            raise ServiceError(422 if exc.code == "UNSUPPORTED_COVERAGE_OVERRIDES" else 500, exc.code, exc.message) from exc

    @staticmethod
    def _reject_invalid(validation):
        if validation["valid"]:
            return
        conflicts = [RosterChangeService._diagnostic(x) for x in validation["errors"]]
        priority = ("DUPLICATE_ASSIGNMENT", "INVALID_EMPLOYEE", "INVALID_ELIGIBILITY",
                    "APPROVED_TIME_OFF_CONFLICT", "WEEKLY_OFF_CONFLICT", "NON_WORKABLE_DAY",
                    "CLOSED_OPERATING_DAY", "STAFFING_GAP", "ASSIGNMENT_OUTSIDE_OR_INVALID_OPERATING_DAY")
        codes = {x["code"] for x in conflicts}
        code = next((x for x in priority if x in codes), "ROSTER_CHANGE_REJECTED")
        raise ServiceError(409, code, "The proposed roster change failed full-roster validation.",
                           {"conflicts": conflicts, "validation": validation})

    @staticmethod
    def _diagnostic(error):
        api_code = ERROR_CODES.get(error.get("code"), error.get("code", "ROSTER_VALIDATION_ERROR").upper())
        diagnostic = {**error, "engine_code": error.get("code"), "code": api_code,
                      "message": MESSAGES.get(api_code, "The roster violates a mandatory scheduling constraint.")}
        if "expected" in error:
            diagnostic["required_staffing"] = error["expected"]
        if "actual" in error:
            diagnostic["actual_staffing"] = error["actual"]
        return diagnostic

    @staticmethod
    def _error_key(error):
        return json.dumps(error, sort_keys=True, separators=(",", ":"))

    @staticmethod
    def _engine_assignment(record):
        return {"employee_id": record["employee_id"], "assignment_date": record["assignment_date"],
                "brand_id": record["brand_id"], "process_id": record["process_id"]}

    @staticmethod
    def _engine_weekly_off(record):
        return {"employee_id": record["employee_id"], "assignment_date": record["assignment_date"]}

    @staticmethod
    def _assert_month(roster, assignment_date):
        value = date.fromisoformat(str(assignment_date))
        if (value.year, value.month) != (roster["year"], roster["month"]):
            raise ServiceError(422, "ASSIGNMENT_OUTSIDE_ROSTER_MONTH", "Assignment date must belong to the roster month.")

    def _roster(self, roster_id):
        roster = self.repository.get("rosters", roster_id)
        if roster is None:
            raise ServiceError(404, "RESOURCE_NOT_FOUND", "The requested roster was not found.")
        return roster

    @staticmethod
    def _check_version(roster, expected_version):
        if roster["version"] != expected_version:
            raise ServiceError(409, "STALE_ROSTER_VERSION", "The roster changed since it was read. Refresh and retry.")

    def _roster_from_snapshot(self, snapshot, roster_id):
        roster = next((x for x in snapshot["rosters"] if x["id"] == roster_id), None)
        if roster is None:
            raise ServiceError(404, "RESOURCE_NOT_FOUND", "The requested roster was not found.")
        return roster

    def _apply_change(self, snapshot, change):
        if isinstance(change, AvailabilityImpact):
            employee = self._by_id(snapshot["employees"], change.employee_id, "employee")
            employee["workable_days"] = change.workable_days
            if change.weekly_off_per_week is not None:
                employee["weekly_off_per_week"] = change.weekly_off_per_week
            return change.employee_id
        if isinstance(change, TimeOffImpact):
            self._by_id(snapshot["employees"], change.employee_id, "employee")
            values = change.model_dump(mode="json", exclude={"change_type", "time_off_id"})
            if change.time_off_id:
                item = next((x for x in snapshot["time_off"] if x.get("time_off_id", x["id"]) == change.time_off_id or x["id"] == change.time_off_id), None)
                if item is None:
                    raise ServiceError(404, "RESOURCE_NOT_FOUND", "The requested time-off record was not found.")
                item.update(values)
                return change.time_off_id
            record_id = str(uuid4())
            snapshot["time_off"].append({"id": record_id, "time_off_id": record_id, **values})
            return record_id
        if isinstance(change, EligibilityImpact):
            self._by_id(snapshot["employees"], change.employee_id, "employee")
            self._by_id(snapshot["brands"], change.brand_id, "brand")
            self._by_id(snapshot["processes"], change.process_id, "process")
            item = next((x for x in snapshot["eligibility"] if x["employee_id"] == change.employee_id and x["brand_id"] == change.brand_id and x["process_id"] == change.process_id), None)
            if item:
                item["is_active"] = change.is_active
            else:
                snapshot["eligibility"].append({"id": str(uuid4()), "employee_id": change.employee_id,
                    "brand_id": change.brand_id, "process_id": change.process_id, "is_active": change.is_active})
            return change.employee_id
        if isinstance(change, OperatingRuleImpact):
            self._by_id(snapshot["brands"], change.brand_id, "brand")
            self._by_id(snapshot["processes"], change.process_id, "process")
            item = next((x for x in snapshot["operating_rules"] if x["brand_id"] == change.brand_id and x["process_id"] == change.process_id), None)
            values = change.model_dump(mode="json", exclude={"change_type"})
            if item:
                item.update(values)
            else:
                snapshot["operating_rules"].append({"id": str(uuid4()), **values})
            return change.brand_id
        raise ServiceError(422, "UNSUPPORTED_CHANGE_TYPE", "This proposed master-data change type is not supported.")

    @staticmethod
    def _by_id(items, entity_id, label):
        item = next((x for x in items if x["id"] == entity_id), None)
        if item is None:
            raise ServiceError(400, f"INVALID_{label.upper()}_REFERENCE", f"The referenced {label} does not exist.")
        return item
