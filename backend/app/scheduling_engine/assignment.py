
from datetime import date

from .weekly_off import has_weekly_off


def make_assignment(state, employee_id, requirement):
    """
    Assign an employee to a brand-process requirement
    for a specific date.
    """

    assignment = {
        "employee_id": employee_id,
        "date": requirement["date"],
        "brand_id": requirement["brand_id"],
        "process_id": requirement["process_id"]
    }

    state["roster"].append(assignment)

    state["daily_assignments"].setdefault(
        employee_id, {}
    ).setdefault(
        requirement["date"], []
    ).append(assignment)

    return assignment


def undo_assignment(state, assignment):
    """
    Remove an assignment from the roster and daily tracking.
    """

    state["roster"].remove(assignment)

    employee_id = assignment["employee_id"]
    assignment_date = assignment["date"]

    state["daily_assignments"][employee_id][assignment_date].remove(
        assignment
    )

    # Clean up empty date and employee entries
    if not state["daily_assignments"][employee_id][assignment_date]:
        del state["daily_assignments"][employee_id][assignment_date]

    if not state["daily_assignments"][employee_id]:
        del state["daily_assignments"][employee_id]


def can_assign(dataset, state, employee_id, requirement, weekly_off_state):
    """
    Validate whether an employee can be assigned
    to a brand-process requirement on a specific date.
    """

    assignment_date = requirement["date"]
    brand_id = requirement["brand_id"]
    process_id = requirement["process_id"]

    # 1. Check whether employee exists and is active
    employee = next(
        (
            emp for emp in dataset["employees"]
            if emp["employee_id"] == employee_id
        ),
        None
    )

    if employee is None or not employee["is_active"]:
        return False

    # Keep this check here as well as in candidate selection so direct/manual
    # assignment validation cannot bypass recurring availability rules.
    weekday = date.fromisoformat(assignment_date).strftime("%A")
    if weekday not in employee["workable_days"]:
        return False

    # 2. Check employee eligibility
    eligible = any(
        assignment["employee_id"] == employee_id
        and assignment["brand_id"] == brand_id
        and assignment["process_id"] == process_id
        and assignment["is_active"]
        for assignment in dataset["employee_assignments"]
    )

    if not eligible:
        return False

    # 3. Check approved leave or comp-off
    on_leave = any(
        time_off["employee_id"] == employee_id
        and time_off["status"] == "approved"
        and time_off["start_date"] <= assignment_date
        and time_off["end_date"] >= assignment_date
        for time_off in dataset["employee_time_off"]
    )

    if on_leave:
        return False

    # 4. Check weekly off
    if has_weekly_off(
        weekly_off_state,
        employee_id,
        assignment_date
    ):
        return False

    # 5. Prevent duplicate brand-process assignment
    existing_assignments = state["daily_assignments"].get(
        employee_id, {}
    ).get(assignment_date, [])

    for assignment in existing_assignments:
        if (
            assignment["brand_id"] == brand_id
            and assignment["process_id"] == process_id
        ):
            return False

    return True
