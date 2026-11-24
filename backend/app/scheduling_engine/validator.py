"""Independent validation for a generated monthly roster."""

import calendar
from collections import Counter
from datetime import date, timedelta


def validate_roster(dataset, requirements, state, weekly_off_state, month, year):
    """Return ``{"valid": bool, "errors": [...]}`` for a roster result.

    The supplied assignments and weekly-off decisions are read independently;
    this function does not repair or mutate either state.
    """
    month_start = date(year, month, 1)
    month_end = date(year, month, calendar.monthrange(year, month)[1])
    employees = {e["employee_id"]: e for e in dataset["employees"]}
    eligible = {(a["employee_id"], a["brand_id"], a["process_id"])
                for a in dataset["employee_assignments"] if a["is_active"]}
    required = {(r["date"], r["brand_id"], r["process_id"]): r
                for r in requirements}
    active_rules = {(r["brand_id"], r["process_id"]): r
                    for r in dataset["brand_process_rules"] if r["is_active"]}
    active_brands = {b["brand_id"] for b in dataset["brands"] if b["is_active"]}
    active_processes = {p["process_id"] for p in dataset["processes"] if p["is_active"]}
    public_holidays = {h["holiday_date"] for h in dataset["public_holidays"]}
    scheduled_off_dates = {
        (emp_id, off_day)
        for emp_id, weeks in weekly_off_state.items()
        for off_day in weeks.values()
    }
    errors = []
    seen = set()
    counts = Counter()

    def error(code, **details):
        errors.append({"code": code, **details})

    for assignment in state.get("roster", []):
        emp_id, day = assignment["employee_id"], assignment["date"]
        key = (day, assignment["brand_id"], assignment["process_id"])
        duplicate_key = (emp_id, *key)
        assignment_valid = True
        if duplicate_key in seen:
            error("duplicate_assignment", employee_id=emp_id, date=day,
                  brand_id=key[1], process_id=key[2])
            assignment_valid = False
        seen.add(duplicate_key)
        if key not in required:
            error("invalid_requirement", employee_id=emp_id, date=day,
                  brand_id=key[1], process_id=key[2])
            assignment_valid = False
        rule = active_rules.get((key[1], key[2]))
        if (rule is None or key[1] not in active_brands
                or key[2] not in active_processes):
            error("inactive_or_missing_operating_rule", employee_id=emp_id,
                  date=day, brand_id=key[1], process_id=key[2])
            assignment_valid = False
        else:
            weekday = date.fromisoformat(day).strftime("%A")
            operates = (rule["public_holiday_policy"] == "operate"
                        if day in public_holidays
                        else weekday in rule["operating_days"])
            if not operates:
                error("closed_operating_day", employee_id=emp_id, date=day,
                      weekday=weekday, brand_id=key[1], process_id=key[2])
                assignment_valid = False
        if (emp_id, key[1], key[2]) not in eligible:
            error("ineligible_assignment", employee_id=emp_id, date=day,
                  brand_id=key[1], process_id=key[2])
            assignment_valid = False
        employee = employees.get(emp_id)
        if employee is None or not employee["is_active"]:
            error("inactive_or_unknown_employee", employee_id=emp_id, date=day)
            assignment_valid = False
        elif date.fromisoformat(day).strftime("%A") not in employee["workable_days"]:
            error("unworkable_day", employee_id=emp_id, date=day)
            assignment_valid = False
        for leave in dataset["employee_time_off"]:
            if (leave["employee_id"] == emp_id and leave["status"] == "approved"
                    and leave["start_date"] <= day <= leave["end_date"]):
                error("approved_time_off", employee_id=emp_id, date=day)
                assignment_valid = False
                break
        if (emp_id, day) in scheduled_off_dates:
            error("weekly_off_overlap", employee_id=emp_id, date=day)
            assignment_valid = False
        if assignment_valid:
            counts[key] += 1

    for key, requirement in required.items():
        actual = counts[key]
        if actual < requirement["required_staffing"]:
            error("insufficient_staffing", date=key[0], brand_id=key[1],
                  process_id=key[2], expected=requirement["required_staffing"],
                  actual=actual)

    off_dates = set()
    for emp_id, weeks in weekly_off_state.items():
        employee = employees.get(emp_id)
        if employee is None:
            continue
        max_offs = employee.get("weekly_off_per_week", 1)
        for week_start, off_day in weeks.items():
            if date.fromisoformat(week_start).weekday() != 0:
                error("invalid_week_start", employee_id=emp_id, week_start=week_start)
            if get_week(off_day) != week_start:
                error("weekly_off_wrong_week", employee_id=emp_id,
                      week_start=week_start, date=off_day)
            if employee and date.fromisoformat(off_day).strftime("%A") not in employee["workable_days"]:
                error("unworkable_weekly_off", employee_id=emp_id, date=off_day)
            if any(t["employee_id"] == emp_id and t["status"] == "approved"
                   and t["start_date"] <= off_day <= t["end_date"]
                   for t in dataset["employee_time_off"]):
                error("weekly_off_on_approved_time_off", employee_id=emp_id, date=off_day)
            off_dates.add((emp_id, off_day))
        counts_per_week = Counter(get_week(d) for d in weeks.values())
        for week_start, actual in counts_per_week.items():
            if actual > max_offs:
                error("too_many_weekly_offs", employee_id=emp_id,
                      week_start=week_start, expected=max_offs, actual=actual)

    # Monthly generation requires an off during each calendar week intersecting
    # this month. Boundary dates outside the roster month are not monthly offs.
    weeks = set()
    cursor = month_start
    while cursor <= month_end:
        weeks.add(get_week(cursor.isoformat()))
        cursor = date.fromordinal(cursor.toordinal() + 1)
    for emp_id, employee in employees.items():
        if not employee["is_active"]:
            continue
        for week_start in weeks:
            month_offs = [d for (owner, d) in off_dates if owner == emp_id
                          and get_week(d) == week_start]
            expected = employee.get("weekly_off_per_week", 1)
            if len(month_offs) != expected:
                error("weekly_off_count", employee_id=emp_id, week_start=week_start,
                      expected=expected, actual=len(month_offs))

    return {"valid": not errors, "errors": errors}


def get_week(day):
    value = date.fromisoformat(day)
    return (value - timedelta(days=value.weekday())).isoformat()
