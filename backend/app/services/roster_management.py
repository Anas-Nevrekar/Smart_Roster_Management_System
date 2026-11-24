from collections import defaultdict
from copy import deepcopy
import calendar
from datetime import date, datetime, timezone
from typing import Any
from uuid import uuid4

from app.core.errors import ServiceError
from app.integrations.roster_engine.adapter import RosterEngineAdapter
from app.integrations.roster_engine.exceptions import EngineIntegrationError
from app.integrations.roster_engine.mapper import map_repository_snapshot
from app.repositories.contracts import MasterDataRepository
from app.services.roster_generation import RosterGenerationService, generation_input_fingerprint


class RosterManagementService:
    def __init__(self, repository: MasterDataRepository, engine: RosterEngineAdapter | None = None):
        self.repository = repository
        self.engine = engine or RosterEngineAdapter()

    def generate_and_save(self, month: int, year: int, generated_by: str | None = None) -> dict[str, Any]:
        if self.repository.get_roster_by_month_year(month, year):
            raise ServiceError(409, "ROSTER_ALREADY_EXISTS", "A roster already exists for this month and year.")
        generated = RosterGenerationService(self.repository, self.engine).generate(month, year)
        if not generated["success"] or not generated["validation"]["is_valid"]:
            return generated
        now = datetime.now(timezone.utc)
        roster_id = f"roster-{year:04d}-{month:02d}"
        roster = {
            "id": roster_id, "month": month, "year": year, "status": "draft",
            "generated_at": now, "published_at": None,
            "generated_by": generated_by, "published_by": None,
            "created_at": now, "updated_at": now, "version": 1,
            "master_data_fingerprint": generated["master_data_fingerprint"],
            "summary": deepcopy(generated["summary"]),
            "latest_validation": {
                "valid": True, "errors": [], "summary": deepcopy(generated["summary"]),
                "validated_at": now,
            },
        }
        records = [
            {"employee_id": x["employee_id"], "assignment_date": x["date"],
             "status": "working", "brand_id": x["brand_id"], "process_id": x["process_id"]}
            for x in generated["assignments"]
        ]
        records.extend(
            {"employee_id": x["employee_id"], "assignment_date": x["date"],
             "status": "weekly_off", "brand_id": None, "process_id": None}
            for x in generated["weekly_offs"]
        )
        saved = self.repository.create_roster_with_assignments(roster, records)
        persisted = self.repository.list_roster_assignments(roster_id)
        expected_working = generated["summary"]["total_assignments"]
        expected_offs = generated["summary"]["total_weekly_offs"]
        actual_working = sum(x["status"] == "working" for x in persisted)
        actual_offs = sum(x["status"] == "weekly_off" for x in persisted)
        if (actual_working, actual_offs) != (expected_working, expected_offs):
            self.repository.rollback_roster_creation(roster_id)
            raise ServiceError(500, "ROSTER_SAVE_INCOMPLETE", "The generated roster could not be saved completely.")
        generated["roster"] = self._metadata(saved, persisted)
        return generated

    def regenerate(self, roster_id: str, expected_version: int | None) -> dict[str, Any]:
        existing = self._get_raw_roster(roster_id)
        if existing["status"] != "draft":
            raise ServiceError(409, "ROSTER_IMMUTABLE", "Published rosters cannot be regenerated.")
        if expected_version is None:
            raise ServiceError(428, "ROSTER_VERSION_REQUIRED", "Send the current roster version in the If-Match header.")
        if existing["version"] != expected_version:
            raise ServiceError(409, "STALE_ROSTER_VERSION", "The roster changed since it was read. Refresh and retry.")

        generated = RosterGenerationService(self.repository, self.engine).generate(existing["month"], existing["year"])
        if not generated["success"] or not generated["validation"]["is_valid"]:
            generated["roster"] = self.get_roster(roster_id)
            return generated

        now = datetime.now(timezone.utc)
        records = [
            {"employee_id": item["employee_id"], "assignment_date": item["date"], "status": "working",
             "brand_id": item["brand_id"], "process_id": item["process_id"]}
            for item in generated["assignments"]
        ]
        records.extend(
            {"employee_id": item["employee_id"], "assignment_date": item["date"], "status": "weekly_off",
             "brand_id": None, "process_id": None}
            for item in generated["weekly_offs"]
        )
        updated = self.repository.replace_roster_assignments(
            roster_id, expected_version, records, generated_at=now,
            summary=generated["summary"], master_data_fingerprint=generated["master_data_fingerprint"],
        )
        persisted = self.repository.list_roster_assignments(roster_id)
        generated["roster"] = self._metadata(updated, persisted)
        return generated

    def list_rosters(self, month=None, year=None, status_filter=None) -> list[dict[str, Any]]:
        rosters = self.repository.list("rosters")
        if month is not None:
            rosters = [x for x in rosters if x["month"] == month]
        if year is not None:
            rosters = [x for x in rosters if x["year"] == year]
        if status_filter is not None:
            rosters = [x for x in rosters if x["status"] == status_filter]
        rosters.sort(key=lambda x: (x["year"], x["month"]), reverse=True)
        return [self._metadata(x, self.repository.list_roster_assignments(x["id"])) for x in rosters]

    def get_roster(self, roster_id: str) -> dict[str, Any]:
        roster = self.repository.get("rosters", roster_id)
        if roster is None:
            raise ServiceError(404, "RESOURCE_NOT_FOUND", "The requested roster was not found.")
        assignments = self.repository.list_roster_assignments(roster_id)
        return self._metadata(roster, assignments)

    def assignments(self, roster_id: str, filters: dict[str, Any] | None = None) -> list[dict[str, Any]]:
        self.get_roster(roster_id)
        rows = self.repository.list_roster_assignments(roster_id)
        filters = filters or {}
        employees = {x["employee_id"]: x for x in self.repository.list("employees")}
        pods = {x["pod_id"]: x for x in self.repository.list("pods")}
        brands = {x["brand_id"]: x for x in self.repository.list("brands")}
        processes = {x["process_id"]: x for x in self.repository.list("processes")}
        enriched = []
        for row in rows:
            employee = employees.get(row["employee_id"], {})
            pod = pods.get(employee.get("pod_id"), {})
            brand = brands.get(row.get("brand_id"), {})
            process = processes.get(row.get("process_id"), {})
            item = {**row, "employee_name": employee.get("full_name"), "pod_id": employee.get("pod_id"),
                    "pod_name": pod.get("pod_name"), "brand_name": brand.get("brand_name"),
                    "process_name": process.get("process_name")}
            if filters.get("employee_id") and row["employee_id"] != filters["employee_id"]:
                continue
            if filters.get("pod_id") and employee.get("pod_id") != filters["pod_id"]:
                continue
            if filters.get("brand_id") and row.get("brand_id") != filters["brand_id"]:
                continue
            if filters.get("process_id") and row.get("process_id") != filters["process_id"]:
                continue
            if filters.get("status") and row["status"] != filters["status"]:
                continue
            assignment_date = date.fromisoformat(row["assignment_date"])
            if filters.get("start_date") and assignment_date < filters["start_date"]:
                continue
            if filters.get("end_date") and assignment_date > filters["end_date"]:
                continue
            enriched.append(item)
        return sorted(enriched, key=lambda x: (x["assignment_date"], x["employee_id"], x["brand_id"] or "", x["process_id"] or ""))

    def weekly_offs(self, roster_id: str, employee_id=None, pod_id=None, start_date=None, end_date=None) -> list[dict[str, Any]]:
        rows = self.assignments(roster_id, {"status": "weekly_off", "employee_id": employee_id, "pod_id": pod_id,
                                           "start_date": start_date, "end_date": end_date})
        return rows

    def coverage(self, roster_id: str, snapshot: dict[str, list[dict[str, Any]]] | None = None) -> dict[str, Any]:
        roster = self.get_roster(roster_id)
        snapshot = snapshot or self.repository.snapshot()
        data = map_repository_snapshot(snapshot)
        if any(rule.get("coverage_overrides") for rule in data["brand_process_rules"]):
            raise ServiceError(422, "UNSUPPORTED_COVERAGE_OVERRIDES", "Coverage cannot be calculated while date-specific overrides are configured.")
        saved = self.repository.list_roster_assignments(roster_id)
        eligible = {(x["employee_id"], x["brand_id"], x["process_id"]) for x in data["employee_assignments"] if x["is_active"]}
        employees = {x["employee_id"]: x for x in data["employees"]}
        active_employee_ids = {x["employee_id"] for x in data["employees"] if x["is_active"]}
        approved_off = [x for x in data["employee_time_off"] if x["status"] == "approved"]
        weekly_off_dates = {(x["employee_id"], x["assignment_date"]) for x in saved if x["status"] == "weekly_off"}
        brands = {x["brand_id"]: x["brand_name"] for x in data["brands"]}
        processes = {x["process_id"]: x["process_name"] for x in data["processes"]}
        active_brand_ids = {x["brand_id"] for x in data["brands"] if x["is_active"]}
        active_process_ids = {x["process_id"] for x in data["processes"] if x["is_active"]}
        holidays = {x["holiday_date"] for x in data["public_holidays"]}
        actual = defaultdict(set)
        for item in saved:
            if item["status"] == "working" and item.get("brand_id") and item.get("process_id"):
                employee = employees.get(item["employee_id"], {})
                assignment_day = date.fromisoformat(item["assignment_date"])
                on_approved_leave = any(x["employee_id"] == item["employee_id"] and x["start_date"] <= item["assignment_date"] <= x["end_date"] for x in approved_off)
                available = (assignment_day.strftime("%A") in employee.get("workable_days", [])
                             and not on_approved_leave
                             and (item["employee_id"], item["assignment_date"]) not in weekly_off_dates)
                if (item["employee_id"] in active_employee_ids and available
                        and (item["employee_id"], item["brand_id"], item["process_id"]) in eligible):
                    actual[(item["assignment_date"], item["brand_id"], item["process_id"])].add(item["employee_id"])
        rows = []
        required_count = satisfied = gaps = 0
        for day in range(1, calendar.monthrange(roster["year"], roster["month"])[1] + 1):
            day_value = date(roster["year"], roster["month"], day)
            day_str, weekday = day_value.isoformat(), day_value.strftime("%A")
            holiday = day_str in holidays
            for rule in data["brand_process_rules"]:
                brand_id, process_id = rule["brand_id"], rule["process_id"]
                if not rule["is_active"] or brand_id not in active_brand_ids or process_id not in active_process_ids:
                    continue
                operates = rule["public_holiday_policy"] == "operate" if holiday else weekday in rule["operating_days"]
                count = len(actual[(day_str, brand_id, process_id)])
                if not operates:
                    rows.append({"date": day_str, "brand_id": brand_id, "brand_name": brands.get(brand_id, brand_id),
                                 "process_id": process_id, "process_name": processes.get(process_id, process_id),
                                 "required_staffing": None, "actual_staffing": count, "staffing_gap": 0,
                                 "status": "not_operating"})
                    continue
                required = rule["minimum_staffing"]
                gap = max(0, required - count)
                status = "understaffed" if gap else "satisfied"
                required_count += 1
                gaps += bool(gap)
                satisfied += not bool(gap)
                rows.append({"date": day_str, "brand_id": brand_id, "brand_name": brands.get(brand_id, brand_id),
                             "process_id": process_id, "process_name": processes.get(process_id, process_id),
                             "required_staffing": required, "actual_staffing": count,
                             "staffing_gap": gap, "status": status})
        return {"data": rows, "summary": {"total_requirements": required_count,
                "requirements_satisfied": satisfied, "coverage_gaps": gaps,
                "total_working_assignments": sum(x["status"] == "working" for x in saved),
                "total_weekly_offs": sum(x["status"] == "weekly_off" for x in saved)}}

    def view(self, roster_id: str, view_name: str) -> dict[str, Any]:
        roster = self.get_roster(roster_id)
        records = self.assignments(roster_id)
        working = [x for x in records if x["status"] == "working"]
        offs = [x for x in records if x["status"] == "weekly_off"]
        employees = {x["employee_id"]: x for x in self.repository.list("employees")}
        roster_employee_ids = {x["employee_id"] for x in records}
        pods = {x["pod_id"]: x for x in self.repository.list("pods")}
        brands = {x["brand_id"]: x for x in self.repository.list("brands")}
        processes = {x["process_id"]: x for x in self.repository.list("processes")}
        if view_name == "company":
            visible_employee_ids = roster_employee_ids | {key for key, value in employees.items() if value.get("is_active", True)}
            groups = [self._employee_view(key, employees.get(key, {}), working, offs, pods) for key in sorted(visible_employee_ids)]
            return {"view": view_name, "roster": roster, "assignments": working, "weekly_offs": offs,
                    "employee_groups": groups}
        if view_name == "employee":
            grouped = {}
            visible_employee_ids = roster_employee_ids | {key for key, value in employees.items() if value.get("is_active", True)}
            for employee_id in sorted(visible_employee_ids):
                employee = employees.get(employee_id, {})
                grouped[employee_id] = {"employee_id": employee_id, "employee_name": employee.get("full_name"),
                    "pod_id": employee.get("pod_id"), "pod_name": pods.get(employee.get("pod_id"), {}).get("pod_name"),
                    "assignments": [], "weekly_offs": []}
            for row in working:
                grouped[row["employee_id"]]["assignments"].append(row)
            for row in offs:
                grouped[row["employee_id"]]["weekly_offs"].append(row)
            return {"view": view_name, "roster": roster, "employees": list(grouped.values())}
        if view_name == "pod":
            groups = {}
            visible_employee_ids = roster_employee_ids | {key for key, value in employees.items() if value.get("is_active", True)}
            for employee_id in sorted(visible_employee_ids):
                employee = employees.get(employee_id, {})
                pod_id = employee.get("pod_id") or "unassigned"
                pod = pods.get(pod_id, {"pod_id": pod_id, "pod_name": "Unassigned", "pod_lead_id": None})
                groups.setdefault(pod_id, {"pod": pod, "pod_lead": employees.get(pod.get("pod_lead_id")), "employees": []})
                groups[pod_id]["employees"].append(self._employee_view(employee_id, employee, working, offs, pods))
            return {"view": view_name, "roster": roster, "pods": list(groups.values())}
        if view_name == "brand":
            groups = {}
            for rule in self.repository.list("operating_rules"):
                brand_id, process_id = rule["brand_id"], rule["process_id"]
                brand = brands.get(brand_id, {"brand_id": brand_id, "brand_name": None})
                process = processes.get(process_id, {"process_id": process_id, "process_name": None})
                group = groups.setdefault(brand_id, {"brand": brand, "processes": {}})
                group["processes"].setdefault(process_id, {"process": process, "assignments": []})
            for item in working:
                brand_id = item["brand_id"]
                brand = brands.get(brand_id, {"brand_id": brand_id, "brand_name": item.get("brand_name")})
                group = groups.setdefault(brand_id, {"brand": brand, "processes": {}})
                process_id = item["process_id"]
                process = processes.get(process_id, {"process_id": process_id, "process_name": item.get("process_name")})
                process_group = group["processes"].setdefault(process_id, {"process": process, "assignments": []})
                process_group["assignments"].append(item)
            results = []
            for group in groups.values():
                process_groups = []
                for process_group in group["processes"].values():
                    owners = {item["employee_id"] for item in process_group["assignments"]}
                    process_groups.append({**process_group, "weekly_offs": [x for x in offs if x["employee_id"] in owners]})
                results.append({"brand": group["brand"], "processes": process_groups})
            return {"view": view_name, "roster": roster, "brands": results}
        if view_name == "process":
            groups = {}
            for rule in self.repository.list("operating_rules"):
                process_id, brand_id = rule["process_id"], rule["brand_id"]
                process = processes.get(process_id, {"process_id": process_id, "process_name": None})
                brand = brands.get(brand_id, {"brand_id": brand_id, "brand_name": None})
                group = groups.setdefault(process_id, {"process": process, "brands": {}})
                group["brands"].setdefault(brand_id, {"brand": brand, "assignments": []})
            for item in working:
                process_id = item["process_id"]
                process = processes.get(process_id, {"process_id": process_id, "process_name": item.get("process_name")})
                group = groups.setdefault(process_id, {"process": process, "brands": {}})
                brand_id = item["brand_id"]
                brand = brands.get(brand_id, {"brand_id": brand_id, "brand_name": item.get("brand_name")})
                brand_group = group["brands"].setdefault(brand_id, {"brand": brand, "assignments": []})
                brand_group["assignments"].append(item)
            results = []
            for group in groups.values():
                brand_groups = []
                for brand_group in group["brands"].values():
                    owners = {item["employee_id"] for item in brand_group["assignments"]}
                    brand_groups.append({**brand_group, "weekly_offs": [x for x in offs if x["employee_id"] in owners]})
                results.append({"process": group["process"], "brands": brand_groups})
            return {"view": view_name, "roster": roster, "processes": results}
        raise ValueError(f"Unknown roster view: {view_name}")

    def validate(self, roster_id: str) -> dict[str, Any]:
        roster = self._get_raw_roster(roster_id)
        snapshot = self.repository.snapshot()
        dataset = map_repository_snapshot(snapshot)
        rows = self.repository.list_roster_assignments(roster_id)
        try:
            result = self.engine.validate(
                dataset,
                [{"employee_id": x["employee_id"], "assignment_date": x["assignment_date"],
                  "brand_id": x["brand_id"], "process_id": x["process_id"]}
                 for x in rows if x["status"] == "working"],
                [{"employee_id": x["employee_id"], "assignment_date": x["assignment_date"]}
                 for x in rows if x["status"] == "weekly_off"],
                roster["month"], roster["year"],
            )
        except EngineIntegrationError as exc:
            raise ServiceError(422 if exc.code == "UNSUPPORTED_COVERAGE_OVERRIDES" else 500, exc.code, exc.message) from exc
        now = datetime.now(timezone.utc)
        validation = {"valid": result["valid"], "errors": result["errors"], "warnings": [],
                      "summary": result["summary"], "audit": result["audit"], "validated_at": now}
        saved = self.repository.save_roster_validation(roster_id, roster["version"], validation)
        return {"success": True, "roster_id": roster_id, "valid": result["valid"],
                "errors": result["errors"], "warnings": [], "summary": result["summary"],
                "diagnostics": result["errors"], "validated_at": now, "version": saved["version"]}

    def publish(self, roster_id: str, published_by: str | None = None) -> dict[str, Any]:
        roster = self._get_raw_roster(roster_id)
        if roster["status"] != "draft":
            raise ServiceError(409, "ROSTER_ALREADY_PUBLISHED", "Only draft rosters can be published.")
        validation = self.validate(roster_id)
        if not validation["valid"]:
            raise ServiceError(409, "ROSTER_INVALID", "This roster failed fresh validation and cannot be published.", validation)
        updated = self.repository.publish_roster(roster_id, roster["version"], published_by, {
            "valid": True, "errors": [], "warnings": [], "summary": validation["summary"],
            "validated_at": validation["validated_at"],
        })
        return self._metadata(updated, self.repository.list_roster_assignments(roster_id))

    def _get_raw_roster(self, roster_id: str) -> dict[str, Any]:
        roster = self.repository.get("rosters", roster_id)
        if roster is None:
            raise ServiceError(404, "RESOURCE_NOT_FOUND", "The requested roster was not found.")
        return roster

    def _metadata(self, roster: dict[str, Any], assignments: list[dict[str, Any]]) -> dict[str, Any]:
        fingerprint = roster.get("master_data_fingerprint")
        current_fingerprint = generation_input_fingerprint(map_repository_snapshot(self.repository.snapshot()))
        return {**roster, "assignment_count": sum(x["status"] == "working" for x in assignments),
                "weekly_off_count": sum(x["status"] == "weekly_off" for x in assignments),
                "master_data_stale": current_fingerprint != fingerprint if fingerprint else None}

    @staticmethod
    def _employee_view(employee_id, employee, working, offs, pods=None):
        pod_id = employee.get("pod_id")
        pod = (pods or {}).get(pod_id, {})
        return {"employee_id": employee_id, "employee_name": employee.get("full_name"),
                "pod_id": pod_id, "pod_name": pod.get("pod_name"),
                "assignments": [x for x in working if x["employee_id"] == employee_id],
                "weekly_offs": [x for x in offs if x["employee_id"] == employee_id]}
