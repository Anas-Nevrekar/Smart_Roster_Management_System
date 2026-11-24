"""Build evidence-based explanations after roster search is exhausted."""

from datetime import date


def diagnose_generation_failure(dataset, requirements):
    """Describe static staffing gaps without treating failed branches as facts."""
    employees = {e["employee_id"]: e for e in dataset["employees"]}
    eligibility = {}
    for record in dataset["employee_assignments"]:
        if record["is_active"]:
            eligibility.setdefault((record["brand_id"], record["process_id"]), set()).add(
                record["employee_id"]
            )

    errors = []
    for requirement in requirements:
        day = requirement["date"]
        brand_id = requirement["brand_id"]
        process_id = requirement["process_id"]
        required = requirement["required_staffing"]
        eligible_ids = sorted(
            employee_id for employee_id in eligibility.get((brand_id, process_id), set())
            if employee_id in employees and employees[employee_id]["is_active"]
        )
        if not eligible_ids:
            errors.append(_requirement_error(
                "no_eligible_employees", requirement, required, [],
                "No active employees have an active eligibility assignment."
            ))
            continue

        weekday = date.fromisoformat(day).strftime("%A")
        workable_ids = [employee_id for employee_id in eligible_ids
                        if weekday in employees[employee_id]["workable_days"]]
        leave_by_employee = {}
        for time_off in dataset["employee_time_off"]:
            if (time_off["employee_id"] in workable_ids
                    and time_off["status"] == "approved"
                    and time_off["start_date"] <= day <= time_off["end_date"]):
                leave_by_employee[time_off["employee_id"]] = time_off.get("time_off_type")
        available_ids = [employee_id for employee_id in workable_ids
                         if employee_id not in leave_by_employee]

        if not available_ids and len(leave_by_employee) == len(workable_ids) and workable_ids:
            errors.append(_requirement_error(
                "approved_time_off", requirement, required, [],
                "All otherwise available eligible employees have approved time off.",
                unavailable_employee_ids=sorted(leave_by_employee),
                time_off_types=sorted({kind for kind in leave_by_employee.values() if kind}),
            ))
        elif len(available_ids) < required:
            errors.append(_requirement_error(
                "insufficient_staffing", requirement, required, available_ids,
                "Fewer eligible employees are available after activity, workable-day, and approved-time-off checks.",
                eligible_employee_ids=eligible_ids,
                approved_time_off_employee_ids=sorted(leave_by_employee),
                time_off_types=sorted({kind for kind in leave_by_employee.values() if kind}),
            ))

    return errors


def diagnose_exhausted_search(metrics):
    """Classify the exhausted search by its furthest proven search stage.

    Branch-level coverage failures are summarized only after the entire search
    has failed. They are never emitted as standalone final causes.
    """
    complete_plans = metrics["complete_weekly_off_plans"]
    assignment_failures = metrics["assignment_search_failures"]
    coverage_prunes = metrics["weekly_off_coverage_prunes"]

    if complete_plans == 0 and coverage_prunes:
        return [{
            "code": "weekly_off_allocation_conflict",
            "message": (
                "Exhaustive search found no complete weekly-off plan that "
                "preserved all individual staffing coverage checks. The "
                "specific branch failures below were not treated as standalone causes."
            ),
            "complete_weekly_off_plans": 0,
            "weekly_off_coverage_prunes": coverage_prunes,
            "weeks_with_pruned_branches": sorted(metrics["weekly_off_pruned_weeks"]),
            "exact_cause_established": False,
        }]

    if complete_plans:
        return [{
            "code": "assignment_search_failure",
            "message": (
                "Exhaustive search found complete weekly-off plans, but none "
                "could be completed into a roster. The failure is in the "
                "combined assignment search; no single requirement was proven "
                "to be the unique cause."
            ),
            "complete_weekly_off_plans": complete_plans,
            "assignment_search_failures": assignment_failures,
            "weekly_off_coverage_prunes": coverage_prunes,
            "exact_cause_established": False,
        }]

    return [{
        "code": "search_failure_unclassified",
        "message": (
            "The complete search failed, but its counters do not establish "
            "whether weekly-off allocation or assignment selection was the "
            "blocking stage."
        ),
        "complete_weekly_off_plans": complete_plans,
        "weekly_off_coverage_prunes": coverage_prunes,
        "exact_cause_established": False,
    }]


def _requirement_error(code, requirement, required, available_ids, message, **details):
    return {
        "code": code,
        "date": requirement["date"],
        "weekday": requirement.get("weekday") or date.fromisoformat(
            requirement["date"]
        ).strftime("%A"),
        "brand_id": requirement["brand_id"],
        "process_id": requirement["process_id"],
        "required_staffing": required,
        "available_staffing": len(available_ids),
        "available_employee_ids": available_ids,
        "exact_cause_established": True,
        "message": message,
        **details,
    }
