
from datetime import date, timedelta


def get_week_start(off_date):
    """
    Return the Monday of the calendar week
    containing the supplied date.
    """

    current_date = date.fromisoformat(off_date)

    monday = current_date - timedelta(
        days=current_date.weekday()
    )

    return monday.isoformat()


def initialize_weekly_off_state(employees):
    """
    Initialize weekly-off tracking for all employees.
    Each employee has a separate record for each week.
    """

    weekly_off_state = {}

    for employee in employees:
        employee_id = employee["employee_id"]

        weekly_off_state[employee_id] = {}

    return weekly_off_state


def assign_weekly_off(weekly_off_state, employee_id, off_date):
    """
    Record an employee's weekly off.

    Returns False if the employee already has
    a weekly off in that calendar week.
    """

    if employee_id not in weekly_off_state:
        return False

    week_start = get_week_start(off_date)

    if week_start in weekly_off_state[employee_id]:
        return False

    weekly_off_state[employee_id][week_start] = off_date

    return True


def has_weekly_off(weekly_off_state, employee_id, target_date):
    """
    Check whether an employee has already been
    assigned a weekly off on the target date.
    """

    if employee_id not in weekly_off_state:
        return False

    week_start = get_week_start(target_date)

    return (
        weekly_off_state[employee_id].get(week_start)
        == target_date
    )


def has_weekly_off_in_week(
    weekly_off_state,
    employee_id,
    target_date
):
    """
    Check whether an employee already has
    a weekly off in the target date's calendar week.
    """

    if employee_id not in weekly_off_state:
        return False

    week_start = get_week_start(target_date)

    return week_start in weekly_off_state[employee_id]


def undo_weekly_off(weekly_off_state, employee_id, off_date):
    """
    Undo a weekly-off decision during backtracking.
    """

    week_start = get_week_start(off_date)

    if (
        employee_id in weekly_off_state
        and weekly_off_state[employee_id].get(week_start)
        == off_date
    ):
        del weekly_off_state[employee_id][week_start]


def reset_weekly_off_state(weekly_off_state):
    """
    Clear all weekly-off tracking.
    """

    for employee_id in weekly_off_state:
        weekly_off_state[employee_id].clear()
