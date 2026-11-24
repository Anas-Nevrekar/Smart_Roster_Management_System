
from datetime import date


def get_candidates(dataset, target_date, brand_id, process_id):
    """
    Return employees eligible and available for a
    specific brand-process requirement on a given date.
    """

    # Convert date to a consistent string format
    if isinstance(target_date, date):
        target_date = target_date.isoformat()

    candidates = []

    # Find employees eligible for this brand-process
    eligible_employee_ids = {
        assignment["employee_id"]
        for assignment in dataset["employee_assignments"]
        if assignment["brand_id"] == brand_id
        and assignment["process_id"] == process_id
        and assignment["is_active"]
    }

    # Check each eligible employee
    for employee in dataset["employees"]:

        employee_id = employee["employee_id"]

        # Check eligibility
        if employee_id not in eligible_employee_ids:
            continue

        # Check active status
        if not employee["is_active"]:
            continue

        # Check recurring workable days
        weekday = date.fromisoformat(target_date).strftime("%A")

        if weekday not in employee["workable_days"]:
            continue

        # Check approved leave and comp-off
        on_leave = any(
            time_off["employee_id"] == employee_id
            and time_off["status"] == "approved"
            and time_off["start_date"] <= target_date
            and time_off["end_date"] >= target_date
            for time_off in dataset["employee_time_off"]
        )

        if on_leave:
            continue

        candidates.append(employee_id)

    return candidates
