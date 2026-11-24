"""Independent, per-requirement audit for a generated roster."""

import calendar
from collections import Counter
from datetime import date, timedelta


def audit_roster(dataset, requirements, assignments, weekly_off_state, month, year):
    """Count only unique assignments that satisfy employee and availability rules."""
    employees = {employee["employee_id"]: employee for employee in dataset["employees"]}
    eligible = {
        (record["employee_id"], record["brand_id"], record["process_id"])
        for record in dataset["employee_assignments"] if record["is_active"]
    }
    assignment_counts = Counter()
    seen = set()
    duplicates = 0
    leave_conflicts = 0
    eligibility_conflicts = 0
    inactive_conflicts = 0
    workable_day_conflicts = 0
    weekly_off_overlaps = 0
    invalid_requirement_assignments = 0
    valid_assignment_count = 0

    requirement_keys = {
        (req["date"], req["brand_id"], req["process_id"])
        for req in requirements
    }
    off_dates = {
        (employee_id, off_date)
        for employee_id, weeks in weekly_off_state.items()
        for off_date in weeks.values()
    }

    for assignment in assignments:
        employee_id = assignment["employee_id"]
        day = assignment["date"]
        brand_id = assignment["brand_id"]
        process_id = assignment["process_id"]
        key = (day, brand_id, process_id)
        unique_key = (employee_id, *key)
        employee = employees.get(employee_id)
        valid = True

        if unique_key in seen:
            duplicates += 1
            valid = False
        seen.add(unique_key)

        if key not in requirement_keys:
            invalid_requirement_assignments += 1
            valid = False
        if (employee_id, brand_id, process_id) not in eligible:
            eligibility_conflicts += 1
            valid = False
        if employee is None or not employee["is_active"]:
            inactive_conflicts += 1
            valid = False
        elif date.fromisoformat(day).strftime("%A") not in employee["workable_days"]:
            workable_day_conflicts += 1
            valid = False

        if any(time_off["employee_id"] == employee_id
               and time_off["status"] == "approved"
               and time_off["start_date"] <= day <= time_off["end_date"]
               for time_off in dataset["employee_time_off"]):
            leave_conflicts += 1
            valid = False
        if (employee_id, day) in off_dates:
            weekly_off_overlaps += 1
            valid = False

        if valid:
            assignment_counts[key] += 1
            valid_assignment_count += 1

    requirement_results = []
    staffing_gaps = []
    weekly_off_coverage_gaps = []
    for requirement in requirements:
        day = requirement["date"]
        weekday = requirement.get("weekday") or date.fromisoformat(day).strftime("%A")
        brand_id = requirement["brand_id"]
        process_id = requirement["process_id"]
        required = requirement["required_staffing"]
        actual = assignment_counts[(day, brand_id, process_id)]
        available_ids = []
        for employee_id, employee in employees.items():
            if not employee["is_active"]:
                continue
            if (employee_id, brand_id, process_id) not in eligible:
                continue
            if weekday not in employee["workable_days"]:
                continue
            if any(time_off["employee_id"] == employee_id
                   and time_off["status"] == "approved"
                   and time_off["start_date"] <= day <= time_off["end_date"]
                   for time_off in dataset["employee_time_off"]):
                continue
            if (employee_id, day) in off_dates:
                continue
            available_ids.append(employee_id)

        row = {
            "date": day,
            "weekday": weekday,
            "brand_id": brand_id,
            "process_id": process_id,
            "required_staffing": required,
            "actual_staffing": actual,
            "difference": actual - required,
            "available_eligible_staffing": len(available_ids),
            "available_eligible_employee_ids": sorted(available_ids),
        }
        requirement_results.append(row)
        if actual < required:
            staffing_gaps.append(row)
        if len(available_ids) < required:
            weekly_off_coverage_gaps.append(row)

    month_start = date(year, month, 1)
    month_end = date(year, month, calendar.monthrange(year, month)[1])
    intersecting_weeks = set()
    cursor = month_start
    while cursor <= month_end:
        intersecting_weeks.add(_week_start(cursor.isoformat()))
        cursor = date.fromordinal(cursor.toordinal() + 1)

    weekly_off_count_errors = []
    weekly_off_constraint_conflicts = 0
    for employee in dataset["employees"]:
        if not employee["is_active"]:
            continue
        employee_id = employee["employee_id"]
        offs = weekly_off_state.get(employee_id, {})
        expected = employee.get("weekly_off_per_week", 1)
        for week_start in sorted(intersecting_weeks):
            dates = [off_date for off_date in offs.values()
                     if _week_start(off_date) == week_start]
            if len(dates) != expected:
                weekly_off_count_errors.append({
                    "employee_id": employee_id,
                    "week_start": week_start,
                    "expected": expected,
                    "actual": len(dates),
                })
        for off_date in offs.values():
            weekday = date.fromisoformat(off_date).strftime("%A")
            if weekday not in employee["workable_days"]:
                weekly_off_constraint_conflicts += 1
            if any(time_off["employee_id"] == employee_id
                   and time_off["status"] == "approved"
                   and time_off["start_date"] <= off_date <= time_off["end_date"]
                   for time_off in dataset["employee_time_off"]):
                weekly_off_constraint_conflicts += 1

    satisfied = len(requirements) - len(staffing_gaps)
    return {
        "requirements_total": len(requirements),
        "requirements_satisfied": satisfied,
        "requirements_with_gaps": len(staffing_gaps),
        "staffing_gaps": staffing_gaps,
        "requirements_with_insufficient_available_staff": len(weekly_off_coverage_gaps),
        "weekly_off_coverage_gaps": weekly_off_coverage_gaps,
        "requirement_results": requirement_results,
        "working_assignments": len(assignments),
        "valid_working_assignments": valid_assignment_count,
        "weekly_offs": sum(len(weeks) for weeks in weekly_off_state.values()),
        "active_employees_checked": sum(e["is_active"] for e in dataset["employees"]),
        "employees_with_incorrect_weekly_off_counts": weekly_off_count_errors,
        "leave_conflicts": leave_conflicts,
        "eligibility_conflicts": eligibility_conflicts,
        "inactive_employee_conflicts": inactive_conflicts,
        "workable_day_conflicts": workable_day_conflicts,
        "duplicate_assignments": duplicates,
        "weekly_off_overlaps": weekly_off_overlaps,
        "weekly_off_constraint_conflicts": weekly_off_constraint_conflicts,
        "invalid_requirement_assignments": invalid_requirement_assignments,
        "boundary_weekly_offs": sorted({
            off_date for weeks in weekly_off_state.values()
            for off_date in weeks.values()
            if off_date < month_start.isoformat() or off_date > month_end.isoformat()
        }),
    }


def _week_start(iso_date):
    value = date.fromisoformat(iso_date)
    return (value - timedelta(days=value.weekday())).isoformat()
