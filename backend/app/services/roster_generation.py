from typing import Any
import hashlib
import json

from app.core.errors import ServiceError
from app.integrations.roster_engine.adapter import RosterEngineAdapter
from app.integrations.roster_engine.exceptions import EngineIntegrationError
from app.integrations.roster_engine.mapper import map_repository_snapshot
from app.repositories.contracts import MasterDataRepository


class RosterGenerationService:
    def __init__(self, repository: MasterDataRepository, engine: RosterEngineAdapter | None = None):
        self.repository = repository
        self.engine = engine or RosterEngineAdapter()

    def generate(self, month: int, year: int) -> dict[str, Any]:
        dataset = map_repository_snapshot(self.repository.snapshot())
        fingerprint = generation_input_fingerprint(dataset)
        try:
            result = self.engine.generate(dataset, month, year)
        except EngineIntegrationError as exc:
            status_code = 422 if exc.code == "UNSUPPORTED_COVERAGE_OVERRIDES" else 500
            raise ServiceError(status_code, exc.code, exc.message) from exc

        assignments = [
            {**item, "status": "assigned"}
            for item in result["assignments"]
        ]
        weekly_offs = []
        for employee_id, weeks in result["weekly_offs"].items():
            for week_start, off_date in weeks.items():
                weekly_offs.append({
                    "employee_id": employee_id,
                    "date": off_date,
                    "week_start": week_start,
                    "status": "weekly_off",
                })
        return {
            "success": result["success"],
            "month": month,
            "year": year,
            "summary": result["summary"],
            "assignments": assignments,
            "weekly_offs": weekly_offs,
            "validation": {
                "is_valid": result["success"] and result["validation"]["valid"],
                "errors": result["validation"]["errors"],
                "audit": result["audit"],
            },
            "diagnostics": result["diagnostics"],
            "master_data_fingerprint": fingerprint,
        }


def generation_input_fingerprint(dataset: dict[str, Any]) -> str:
    """Hash generation inputs only, independent of row order and timestamps."""
    relevant = {
        "employees": [{key: item[key] for key in ("employee_id", "is_active", "weekly_off_per_week", "workable_days")} for item in dataset["employees"]],
        "brands": [{key: item[key] for key in ("brand_id", "is_active")} for item in dataset["brands"]],
        "processes": [{key: item[key] for key in ("process_id", "is_active")} for item in dataset["processes"]],
        "eligibility": [{key: item[key] for key in ("employee_id", "brand_id", "process_id", "is_active")} for item in dataset["employee_assignments"]],
        "rules": [{key: item[key] for key in ("brand_id", "process_id", "operating_days", "public_holiday_policy", "minimum_staffing", "coverage_overrides", "is_active")} for item in dataset["brand_process_rules"]],
        "time_off": [{key: item[key] for key in ("employee_id", "time_off_type", "start_date", "end_date", "status")} for item in dataset["employee_time_off"]],
        "holidays": [{"holiday_date": item["holiday_date"]} for item in dataset["public_holidays"]],
    }
    def canonical(value):
        if isinstance(value, dict):
            return {key: canonical(item) for key, item in sorted(value.items())}
        if isinstance(value, list):
            items = [canonical(item) for item in value]
            return sorted(items, key=lambda item: json.dumps(item, sort_keys=True, separators=(",", ":"), default=str))
        return value

    encoded = json.dumps(canonical(relevant), sort_keys=True, separators=(",", ":"), default=str).encode()
    return hashlib.sha256(encoded).hexdigest()
