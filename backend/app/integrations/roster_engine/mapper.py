from copy import deepcopy
from typing import Any


def map_repository_snapshot(snapshot: dict[str, list[dict[str, Any]]]) -> dict[str, Any]:
    """Map backend records to the exact plain-dictionary keys consumed by the engine."""
    employees = []
    for source in snapshot["employees"]:
        employees.append({
            "employee_id": source["employee_id"],
            "name": source["full_name"],
            "email": source["email"],
            "pod_id": source.get("pod_id"),
            "is_active": source["is_active"],
            "weekly_off_per_week": source["weekly_off_per_week"],
            "workable_days": deepcopy(source["workable_days"]),
        })
    pods = [{
        "pod_id": p.get("pod_id", p["id"]), "pod_name": p["pod_name"],
        "pod_lead_id": p.get("pod_lead_id"), "description": p.get("description"),
        "is_active": p["is_active"],
    } for p in snapshot["pods"]]
    brands = [{
        "brand_id": b.get("brand_id", b["id"]), "brand_name": b["brand_name"],
        "description": b.get("description"), "is_active": b["is_active"],
    } for b in snapshot["brands"]]
    processes = [{
        "process_id": p.get("process_id", p["id"]), "process_name": p["process_name"],
        "description": p.get("description"), "is_active": p["is_active"],
    } for p in snapshot["processes"]]
    eligibility = [{
        "employee_id": item["employee_id"], "brand_id": item["brand_id"],
        "process_id": item["process_id"], "is_active": item["is_active"],
    } for item in snapshot["eligibility"]]
    rules = [{
        "brand_id": rule["brand_id"], "process_id": rule["process_id"],
        "operating_days": deepcopy(rule["operating_days"]),
        "public_holiday_policy": rule["public_holiday_policy"],
        "minimum_staffing": rule["minimum_staffing"],
        "coverage_overrides": deepcopy(rule.get("coverage_overrides", [])),
        "is_active": rule["is_active"],
    } for rule in snapshot["operating_rules"]]
    time_off = [{
        "time_off_id": item.get("time_off_id", item["id"]),
        "employee_id": item["employee_id"],
        "time_off_type": item["time_off_type"],
        "start_date": str(item["start_date"]), "end_date": str(item["end_date"]),
        "status": item["status"], "reason": item.get("reason"),
        "approved_by": item.get("approved_by"),
    } for item in snapshot["time_off"]]
    holidays = [{
        "holiday_id": item.get("holiday_id", item["id"]),
        "holiday_name": item["holiday_name"],
        "holiday_date": str(item["holiday_date"]),
        "description": item.get("description"),
    } for item in snapshot["public_holidays"]]
    return {
        "employees": employees,
        "pods": pods,
        "brands": brands,
        "processes": processes,
        "employee_assignments": eligibility,
        "brand_process_rules": rules,
        "employee_time_off": time_off,
        "public_holidays": holidays,
        "rosters": [],
        "roster_assignments": [],
    }
