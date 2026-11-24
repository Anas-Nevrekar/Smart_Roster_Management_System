"""Child-process entry point. Engine imports and recursion-limit changes stay isolated here."""
import json
import sys
import traceback

from app.scheduling_engine import backtracking, preprocessing, roster_audit, validator, weekly_off


def load_engine():
    """Resolve packaged modules without changing import paths."""
    return {
        "preprocessing": preprocessing,
        "backtracking": backtracking,
        "weekly_off": weekly_off,
        "validator": validator,
        "roster_audit": roster_audit,
    }


def _audit_is_clean(audit):
    return not any((
        audit["requirements_with_gaps"],
        audit["requirements_with_insufficient_available_staff"],
        audit["leave_conflicts"], audit["eligibility_conflicts"],
        audit["inactive_employee_conflicts"], audit["workable_day_conflicts"],
        audit["duplicate_assignments"], audit["weekly_off_overlaps"],
        audit["weekly_off_constraint_conflicts"],
        audit["invalid_requirement_assignments"],
        audit["employees_with_incorrect_weekly_off_counts"],
    ))


def run(payload):
    modules = load_engine()
    data = payload["dataset"]
    month, year = payload["month"], payload["year"]
    if payload.get("mode") == "validate":
        return validate_candidate(
            modules, data, payload["assignments"], payload["weekly_offs"], month, year,
        )
    requirements = modules["preprocessing"].build_daily_requirements(data, month, year)
    state = {"roster": [], "daily_assignments": {}}
    weekly_off_state = modules["weekly_off"].initialize_weekly_off_state(data["employees"])
    result = modules["backtracking"].generate_roster(data, requirements, state, weekly_off_state)
    validation = modules["validator"].validate_roster(data, requirements, state, weekly_off_state, month, year)
    audit = modules["roster_audit"].audit_roster(data, requirements, state["roster"], weekly_off_state, month, year)
    success = bool(result["success"] and validation["valid"] and _audit_is_clean(audit))
    diagnostics = result["errors"]
    if not success and not diagnostics:
        diagnostics = [{"code": "independent_validation_failed", "message": "Generated output did not pass independent validation or audit."}]
    return {
        "success": success,
        "assignments": state["roster"] if success else [],
        "weekly_offs": weekly_off_state if success else {},
        "validation": validation,
        "audit": {
            "requirements_total": audit["requirements_total"],
            "requirements_satisfied": audit["requirements_satisfied"],
            "requirements_with_gaps": audit["requirements_with_gaps"],
            "requirements_with_insufficient_available_staff": audit["requirements_with_insufficient_available_staff"],
            "active_employees_checked": audit["active_employees_checked"],
            "leave_conflicts": audit["leave_conflicts"],
            "eligibility_conflicts": audit["eligibility_conflicts"],
            "inactive_employee_conflicts": audit["inactive_employee_conflicts"],
            "workable_day_conflicts": audit["workable_day_conflicts"],
            "duplicate_assignments": audit["duplicate_assignments"],
            "weekly_off_overlaps": audit["weekly_off_overlaps"],
            "weekly_off_constraint_conflicts": audit["weekly_off_constraint_conflicts"],
            "invalid_requirement_assignments": audit["invalid_requirement_assignments"],
            "weekly_off_count_errors": len(audit["employees_with_incorrect_weekly_off_counts"]),
        },
        "diagnostics": diagnostics,
        "summary": {
            "total_assignments": audit["valid_working_assignments"] if success else 0,
            "total_weekly_offs": audit["weekly_offs"] if success else 0,
            "total_requirements": audit["requirements_total"],
            "requirements_satisfied": audit["requirements_satisfied"] if success else 0,
            "coverage_gaps": audit["requirements_with_gaps"],
            "active_employees": audit["active_employees_checked"],
            "active_brands": sum(1 for x in data["brands"] if x["is_active"]),
            "active_processes": sum(1 for x in data["processes"] if x["is_active"]),
        },
    }


def validate_candidate(modules, data, assignments, weekly_offs, month, year):
    state = {"roster": [], "daily_assignments": {}}
    weekly_off_state = {}
    for item in assignments:
        record = {
            "employee_id": item["employee_id"], "date": item["assignment_date"],
            "brand_id": item["brand_id"], "process_id": item["process_id"],
        }
        state["roster"].append(record)
        state["daily_assignments"].setdefault(record["employee_id"], {}).setdefault(record["date"], []).append(record)
    for item in weekly_offs:
        week_start = modules["weekly_off"].get_week_start(item["assignment_date"])
        weekly_off_state.setdefault(item["employee_id"], {})[week_start] = item["assignment_date"]
    for employee in data["employees"]:
        weekly_off_state.setdefault(employee["employee_id"], {})
    requirements = modules["preprocessing"].build_daily_requirements(data, month, year)
    validation = modules["validator"].validate_roster(data, requirements, state, weekly_off_state, month, year)
    audit = modules["roster_audit"].audit_roster(data, requirements, state["roster"], weekly_off_state, month, year)
    is_valid = bool(validation["valid"] and _audit_is_clean(audit))
    return {
        "valid": is_valid,
        "errors": validation["errors"],
        "audit": _audit_counts(audit),
        "summary": {
            "total_assignments": audit["valid_working_assignments"],
            "total_weekly_offs": audit["weekly_offs"],
            "total_requirements": audit["requirements_total"],
            "requirements_satisfied": audit["requirements_satisfied"],
            "coverage_gaps": audit["requirements_with_gaps"],
            "active_employees": audit["active_employees_checked"],
            "active_brands": sum(1 for x in data["brands"] if x["is_active"]),
            "active_processes": sum(1 for x in data["processes"] if x["is_active"]),
        },
    }


def _audit_counts(audit):
    return {
        "requirements_total": audit["requirements_total"],
        "requirements_satisfied": audit["requirements_satisfied"],
        "requirements_with_gaps": audit["requirements_with_gaps"],
        "requirements_with_insufficient_available_staff": audit["requirements_with_insufficient_available_staff"],
        "active_employees_checked": audit["active_employees_checked"],
        "leave_conflicts": audit["leave_conflicts"],
        "eligibility_conflicts": audit["eligibility_conflicts"],
        "inactive_employee_conflicts": audit["inactive_employee_conflicts"],
        "workable_day_conflicts": audit["workable_day_conflicts"],
        "duplicate_assignments": audit["duplicate_assignments"],
        "weekly_off_overlaps": audit["weekly_off_overlaps"],
        "weekly_off_constraint_conflicts": audit["weekly_off_constraint_conflicts"],
        "invalid_requirement_assignments": audit["invalid_requirement_assignments"],
        "weekly_off_count_errors": len(audit["employees_with_incorrect_weekly_off_counts"]),
    }


def main():
    try:
        payload = json.load(sys.stdin)
        json.dump(run(payload), sys.stdout, separators=(",", ":"))
    except Exception:
        traceback.print_exc(file=sys.stderr)
        sys.stdout.write(json.dumps({"worker_error": "ENGINE_WORKER_FAILURE"}))
        raise SystemExit(1)


if __name__ == "__main__":
    main()
