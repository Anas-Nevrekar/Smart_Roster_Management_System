
from app.scheduling_engine.sample_data_fixed import get_dataset
from app.scheduling_engine.preprocessing import build_daily_requirements
from app.scheduling_engine.weekly_off import initialize_weekly_off_state
from app.scheduling_engine.backtracking import generate_roster
from app.scheduling_engine.validator import validate_roster
from app.scheduling_engine.roster_audit import audit_roster


def generate(dataset):
    requirements = build_daily_requirements(dataset, 12, 2026)
    state = {"roster": [], "daily_assignments": {}}
    weekly_off_state = initialize_weekly_off_state(dataset["employees"])
    result = generate_roster(dataset, requirements, state, weekly_off_state)
    return requirements, state, weekly_off_state, result


def print_valid_audit():
    dataset = get_dataset("valid")
    requirements, state, offs, result = generate(dataset)

    print("Expanded December 2026 roster")
    print("Generation successful:", result["success"])
    if not result["success"]:
        print("Diagnostics:", result["errors"])
        return

    audit = audit_roster(dataset, requirements, state["roster"], offs, 12, 2026)
    validation = validate_roster(dataset, requirements, state, offs, 12, 2026)
    print("Daily requirements:", audit["requirements_total"])
    print("Requirements satisfied:", audit["requirements_satisfied"])
    print("Requirements with staffing gaps:", audit["requirements_with_gaps"])
    print("Requirements below minimum available staffing:",
          audit["requirements_with_insufficient_available_staff"])
    print("Total working assignments:", audit["working_assignments"])
    print("Valid working assignments:", audit["valid_working_assignments"])
    print("Total weekly offs:", audit["weekly_offs"])
    print("Active employees checked:", audit["active_employees_checked"])
    print("Employees with incorrect weekly-off counts:",
          len(audit["employees_with_incorrect_weekly_off_counts"]))
    print("Leave conflicts:", audit["leave_conflicts"])
    print("Eligibility conflicts:", audit["eligibility_conflicts"])
    print("Inactive employee conflicts:", audit["inactive_employee_conflicts"])
    print("Workable-day conflicts:", audit["workable_day_conflicts"])
    print("Duplicate assignments:", audit["duplicate_assignments"])
    print("Weekly-off overlaps:", audit["weekly_off_overlaps"])
    print("Weekly-off constraint conflicts:", audit["weekly_off_constraint_conflicts"])
    print("Independent validator errors:", len(validation["errors"]))
    print("Boundary weekly offs:", ", ".join(audit["boundary_weekly_offs"]) or "none")

    if audit["staffing_gaps"]:
        print("Staffing gaps:")
        for gap in audit["staffing_gaps"]:
            print(
                f"  {gap['date']} {gap['weekday']} | brand {gap['brand_id']} "
                f"process {gap['process_id']} | required {gap['required_staffing']} "
                f"actual {gap['actual_staffing']}"
            )


def print_conflict_scenario():
    dataset = get_dataset("conflict")
    requirements, state, offs, result = generate(dataset)
    print("\nExpanded conflict scenario")
    print("Generation successful:", result["success"])
    print("Partial assignments:", len(result["assignments"]))
    print("Partial weekly offs:", sum(len(weeks) for weeks in result["weekly_offs"].values()))
    for error in result["errors"]:
        if (error.get("date"), error.get("brand_id"), error.get("process_id")) == (
            "2026-12-08", "B003", "PR001"
        ):
            print("PureGlow Customer Support diagnostic:", error)


def main():
    print_valid_audit()
    print_conflict_scenario()


if __name__ == "__main__":
    main()
