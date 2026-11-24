
from .candidate_selection import get_candidates
from .assignment import can_assign, make_assignment


def allocate_staff(
    dataset,
    state,
    requirement,
    weekly_off_state
):
    """
    Select and assign the required number of employees
    for a brand-process requirement.

    Returns:
        True  -> Staffing requirement successfully fulfilled.
        False -> Not enough valid employees available.
    """

    required_staffing = requirement["required_staffing"]

    # 1. Find eligible candidates
    candidates = get_candidates(
        dataset,
        requirement["date"],
        requirement["brand_id"],
        requirement["process_id"]
    )

    # 2. Filter candidates using assignment validation
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

    # 3. Check whether enough employees are available
    if len(valid_candidates) < required_staffing:
        return False

    # 4. Assign the required number of employees
    selected_employees = valid_candidates[:required_staffing]

    for employee_id in selected_employees:
        make_assignment(state, employee_id, requirement)

    return True
