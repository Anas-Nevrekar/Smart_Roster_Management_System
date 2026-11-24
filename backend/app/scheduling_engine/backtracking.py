
from datetime import date, timedelta
from copy import deepcopy
import sys
from threading import RLock

from .candidate_selection import get_candidates
from .assignment import can_assign, make_assignment, undo_assignment

from .weekly_off import (
    get_week_start,
    assign_weekly_off,
    undo_weekly_off
)
from .diagnostics import (
    diagnose_generation_failure,
    diagnose_exhausted_search,
)


_GENERATION_LOCK = RLock()


def generate_roster(
    dataset,
    requirements,
    state,
    weekly_off_state
):
    """Serialize searches because the recursive search adjusts a process-wide limit."""
    with _GENERATION_LOCK:
        return _generate_roster(dataset, requirements, state, weekly_off_state)


def _generate_roster(
    dataset,
    requirements,
    state,
    weekly_off_state
):
    """
    Generate a monthly roster using recursive backtracking.

    Returns a structured result. Search mechanics and pruning are unchanged.
    """

    if not requirements:
        return _failure(state, weekly_off_state, [{
            "code": "no_requirements",
            "message": "No staffing requirements were supplied."
        }])

    # Get the first and last requirement dates
    requirement_dates = [
        date.fromisoformat(req["date"])
        for req in requirements
    ]

    first_date = min(requirement_dates)
    last_date = max(requirement_dates)

    # Ensure requirements belong to one month
    if (first_date.year, first_date.month) != (
        last_date.year, last_date.month
    ):
        raise ValueError("Requirements must belong to one month.")

    # --------------------------------------------------
    # STEP 1: Build complete calendar weeks
    # Include dates outside the month for weekly offs
    # --------------------------------------------------

    month_start = date(first_date.year, first_date.month, 1)

    if first_date.month == 12:
        next_month = date(first_date.year + 1, 1, 1)
    else:
        next_month = date(first_date.year, first_date.month + 1, 1)

    month_end = next_month - timedelta(days=1)

    calendar_start = month_start - timedelta(
        days=month_start.weekday()
    )

    calendar_end = month_end + timedelta(
        days=6 - month_end.weekday()
    )

    weeks = {}

    current_date = calendar_start

    while current_date <= calendar_end:

        week_start = get_week_start(
            current_date.isoformat()
        )

        weeks.setdefault(week_start, []).append(
            current_date.isoformat()
        )

        current_date += timedelta(days=1)

    # --------------------------------------------------
    # STEP 2: Prepare weekly-off decisions
    # --------------------------------------------------

    weekly_off_tasks = []

    active_employees = [
        employee
        for employee in dataset["employees"]
        if employee["is_active"]
    ]

    for employee in active_employees:

        employee_id = employee["employee_id"]
        workable_days = employee["workable_days"]

        for week_start, week_dates in weeks.items():

            possible_dates = []

            for target_date in week_dates:

                weekday = date.fromisoformat(
                    target_date
                ).strftime("%A")

                if weekday not in workable_days:
                    continue

                # Do not select approved leave/comp-off dates
                on_leave = any(
                    time_off["employee_id"] == employee_id
                    and time_off["status"] == "approved"
                    and time_off["start_date"] <= target_date
                    and time_off["end_date"] >= target_date
                    for time_off in dataset["employee_time_off"]
                )

                if on_leave:
                    continue

                possible_dates.append(target_date)

            if not possible_dates:
                return _failure(state, weekly_off_state, [{
                    "code": "no_weekly_off_date",
                    "employee_id": employee_id,
                    "week_start": week_start,
                    "exact_cause_established": True,
                    "message": "No workable date free of approved time off exists in this calendar week."
                }])

            # Prefer dates with fewer staffing requirements
            possible_dates.sort(
                key=lambda target_date: sum(
                    1 for req in requirements
                    if req["date"] == target_date
                )
            )

            weekly_off_tasks.append({
                "employee_id": employee_id,
                "week_start": week_start,
                "possible_dates": possible_dates
            })

    # Employees with fewer possible off dates first
    weekly_off_tasks.sort(
        key=lambda task: len(task["possible_dates"])
    )

    # --------------------------------------------------
    # STEP 3: Check weekly staffing coverage
    # --------------------------------------------------

    search_metrics = {
        "complete_weekly_off_plans": 0,
        "assignment_search_failures": 0,
        "weekly_off_coverage_prunes": 0,
        "weekly_off_pruned_weeks": set(),
    }

    def check_week_coverage(week_start):

        for requirement in requirements:

            requirement_week = get_week_start(
                requirement["date"]
            )

            if requirement_week != week_start:
                continue

            candidates = get_candidates(
                dataset,
                requirement["date"],
                requirement["brand_id"],
                requirement["process_id"]
            )

            valid_candidates = []

            for employee_id in candidates:

                if can_assign(
                    dataset,
                    state,
                    employee_id,
                    requirement,
                    weekly_off_state
                ):
                    valid_candidates.append(employee_id)

            if len(valid_candidates) < requirement["required_staffing"]:
                return False

        return True

    # --------------------------------------------------
    # STEP 4: Assign employees to staffing requirements
    # --------------------------------------------------

    def solve_requirements(requirement_index):

        # All requirements successfully fulfilled
        if requirement_index == len(requirements):
            return True

        requirement = requirements[requirement_index]

        candidates = get_candidates(
            dataset,
            requirement["date"],
            requirement["brand_id"],
            requirement["process_id"]
        )

        required_staffing = requirement["required_staffing"]

        def select_employees(start_index, selected_count):

            if selected_count == required_staffing:
                return solve_requirements(
                    requirement_index + 1
                )

            for i in range(start_index, len(candidates)):

                employee_id = candidates[i]

                if not can_assign(
                    dataset,
                    state,
                    employee_id,
                    requirement,
                    weekly_off_state
                ):
                    continue

                assignment = make_assignment(
                    state,
                    employee_id,
                    requirement
                )

                if select_employees(i + 1, selected_count + 1):
                    return True

                # Undo assignment during backtracking
                undo_assignment(state, assignment)

            return False

        return select_employees(0, 0)

    # --------------------------------------------------
    # STEP 5: Backtrack through weekly-off decisions
    # --------------------------------------------------

    def select_weekly_offs(task_index):

        # All weekly offs selected
        if task_index == len(weekly_off_tasks):
            search_metrics["complete_weekly_off_plans"] += 1
            solved = solve_requirements(0)
            if not solved:
                search_metrics["assignment_search_failures"] += 1
            return solved

        task = weekly_off_tasks[task_index]

        employee_id = task["employee_id"]
        week_start = task["week_start"]

        for off_date in task["possible_dates"]:

            assigned = assign_weekly_off(
                weekly_off_state,
                employee_id,
                off_date
            )

            if not assigned:
                continue

            # Check whether staffing remains possible
            if check_week_coverage(week_start):

                if select_weekly_offs(task_index + 1):
                    return True
            else:
                # A single pruned branch is only an observation. It becomes a
                # final category only if exhaustive search finds no full plan.
                search_metrics["weekly_off_coverage_prunes"] += 1
                search_metrics["weekly_off_pruned_weeks"].add(week_start)

            # Undo weekly-off decision
            undo_weekly_off(
                weekly_off_state,
                employee_id,
                off_date
            )

        return False

    previous_recursion_limit = sys.getrecursionlimit()
    required_recursion_limit = (
        sum(req["required_staffing"] + 2 for req in requirements)
        + len(weekly_off_tasks) + 100
    )
    if required_recursion_limit > previous_recursion_limit:
        sys.setrecursionlimit(required_recursion_limit)
    try:
        generated = select_weekly_offs(0)
    finally:
        if required_recursion_limit > previous_recursion_limit:
            sys.setrecursionlimit(previous_recursion_limit)

    if generated:
        return {
            "success": True,
            "assignments": deepcopy(state["roster"]),
            "weekly_offs": deepcopy(weekly_off_state),
            "errors": [],
        }

    errors = diagnose_generation_failure(dataset, requirements)
    if not errors:
        errors.extend(diagnose_exhausted_search(search_metrics))
    return _failure(state, weekly_off_state, errors)


def _failure(state, weekly_off_state, errors):
    """Return a clean failed result after ensuring no partial output remains."""
    state["roster"].clear()
    state["daily_assignments"].clear()
    for employee_weeks in weekly_off_state.values():
        employee_weeks.clear()
    return {
        "success": False,
        "assignments": [],
        "weekly_offs": deepcopy(weekly_off_state),
        "errors": errors,
    }
