import unittest
from datetime import date

from app.scheduling_engine.backtracking import generate_roster
from app.scheduling_engine.validator import validate_roster
from app.scheduling_engine.weekly_off import get_week_start, initialize_weekly_off_state


def sunday_dataset(employee_ids, workable_days=None):
    workable_days = workable_days or [
        "Monday", "Tuesday", "Wednesday", "Thursday",
        "Friday", "Saturday", "Sunday",
    ]
    return {
        "employees": [{
            "employee_id": employee_id,
            "name": employee_id,
            "email": f"{employee_id.lower()}@example.test",
            "pod_id": "P1",
            "is_active": True,
            "weekly_off_per_week": 1,
            "workable_days": workable_days.copy(),
        } for employee_id in employee_ids],
        "pods": [{"pod_id": "P1", "pod_name": "Pod 1",
                  "pod_lead_id": employee_ids[0], "is_active": True}],
        "brands": [{"brand_id": "B1", "brand_name": "Sunday Support",
                    "is_active": True}],
        "processes": [{"process_id": "P1", "process_name": "Support",
                       "is_active": True}],
        "employee_assignments": [{
            "employee_id": employee_id, "brand_id": "B1",
            "process_id": "P1", "is_active": True,
        } for employee_id in employee_ids],
        "brand_process_rules": [{
            "brand_id": "B1", "process_id": "P1",
            "operating_days": ["Sunday"],
            "public_holiday_policy": "closed",
            "minimum_staffing": 2,
            "coverage_overrides": [],
            "is_active": True,
        }],
        "employee_time_off": [],
        "public_holidays": [],
    }


def december_sunday_requirements():
    return [{
        "date": f"2026-12-{day:02d}",
        "weekday": "Sunday",
        "brand_id": "B1",
        "process_id": "P1",
        "required_staffing": 2,
    } for day in (6, 13, 20, 27)]


def sunday_preferred_dataset_and_requirements():
    dataset = sunday_dataset(["E1", "E2", "E3"])
    weekday_processes = ["P2", "P3"]
    dataset["processes"].extend([
        {"process_id": process_id, "process_name": process_id,
         "is_active": True}
        for process_id in weekday_processes
    ])
    dataset["employee_assignments"].extend({
        "employee_id": employee["employee_id"], "brand_id": "B1",
        "process_id": process_id, "is_active": True,
    } for employee in dataset["employees"] for process_id in weekday_processes)
    dataset["brand_process_rules"].extend({
        "brand_id": "B1", "process_id": process_id,
        "operating_days": ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday"],
        "public_holiday_policy": "closed", "minimum_staffing": 1,
        "coverage_overrides": [], "is_active": True,
    } for process_id in weekday_processes)

    requirements = december_sunday_requirements()
    for day in range(1, 32):
        target = date(2026, 12, day)
        if target.strftime("%A") == "Sunday":
            continue
        for process_id in weekday_processes:
            requirements.append({
                "date": target.isoformat(), "weekday": target.strftime("%A"),
                "brand_id": "B1", "process_id": process_id,
                "required_staffing": 1,
            })
    return dataset, requirements


class WeeklyOffCoverageTests(unittest.TestCase):
    def test_single_sunday_process_allows_shared_off_days_elsewhere(self):
        dataset = sunday_dataset(["E1", "E2", "E3"])
        requirements = december_sunday_requirements()
        state = {"roster": [], "daily_assignments": {}}
        offs = initialize_weekly_off_state(dataset["employees"])

        result = generate_roster(dataset, requirements, state, offs)

        self.assertTrue(result["success"], result["errors"])
        self.assertEqual(1, len({weeks["2026-11-30"] for weeks in offs.values()}))
        self.assertTrue(all(sum(a["date"] == requirement["date"]
                               for a in state["roster"]) >= 2
                            for requirement in requirements))
        validation = validate_roster(dataset, requirements, state, offs, 12, 2026)
        self.assertEqual([], validation["errors"])

    def test_shared_weekly_off_date_is_valid_when_sunday_coverage_remains(self):
        dataset, requirements = sunday_preferred_dataset_and_requirements()
        state = {"roster": [], "daily_assignments": {}}
        offs = initialize_weekly_off_state(dataset["employees"])

        result = generate_roster(dataset, requirements, state, offs)

        self.assertTrue(result["success"], result["errors"])
        for requirement in requirements:
            assigned = [a for a in state["roster"]
                        if a["date"] == requirement["date"]]
            self.assertGreaterEqual(len(assigned), 2)
            off_employees = {employee_id for employee_id, weeks in offs.items()
                             if weeks.get(get_week_start(requirement["date"]))
                             == requirement["date"]}
            self.assertTrue(off_employees.isdisjoint({a["employee_id"] for a in assigned}))

        # The search may give everyone the same off day when that day has no
        # coverage requirement. Distinct off dates are not a constraint.
        self.assertEqual(15, sum(len(weeks) for weeks in offs.values()))
        self.assertEqual(1, len({weeks["2026-11-30"] for weeks in offs.values()}))
        # Sunday is the lowest-requirement off candidate in each relevant week.
        # The first employee gets it; later employees are backtracked away from
        # Sunday once taking it would drop coverage below two.
        sunday_off_counts = [sum(weeks.get(get_week_start(day)) == day
                                 for weeks in offs.values())
                             for day in ("2026-12-13", "2026-12-20", "2026-12-27")]
        self.assertTrue(all(count == 1 for count in sunday_off_counts))
        validation = validate_roster(dataset, requirements, state, offs, 12, 2026)
        self.assertEqual([], validation["errors"])

    def test_weekly_offs_cannot_leave_sunday_requirement_uncovered(self):
        dataset = sunday_dataset(["E1", "E2"], workable_days=["Sunday"])
        requirements = december_sunday_requirements()
        state = {"roster": [], "daily_assignments": {}}
        offs = initialize_weekly_off_state(dataset["employees"])

        result = generate_roster(dataset, requirements, state, offs)

        self.assertFalse(result["success"])
        self.assertEqual("weekly_off_allocation_conflict", result["errors"][0]["code"])
        self.assertEqual([], result["assignments"])
        self.assertEqual([], state["roster"])
        self.assertTrue(all(not weeks for weeks in offs.values()))

    def test_validator_detects_coverage_gap_from_shared_sunday_offs(self):
        dataset = sunday_dataset(["E1", "E2", "E3"])
        requirements = december_sunday_requirements()
        offs = initialize_weekly_off_state(dataset["employees"])
        for employee_id in offs:
            for week_start, day in zip(
                ("2026-11-30", "2026-12-07", "2026-12-14", "2026-12-21"),
                ("2026-12-06", "2026-12-13", "2026-12-20", "2026-12-27"),
            ):
                offs[employee_id][week_start] = day
        state = {"roster": [], "daily_assignments": {}}

        validation = validate_roster(dataset, requirements, state, offs, 12, 2026)

        gaps = [error for error in validation["errors"]
                if error["code"] == "insufficient_staffing"]
        self.assertEqual(4, len(gaps))
        self.assertTrue(all(error["actual"] == 0 and error["expected"] == 2
                            for error in gaps))

    def test_validator_detects_employee_working_on_weekly_off(self):
        dataset = sunday_dataset(["E1", "E2", "E3"])
        requirements = december_sunday_requirements()
        offs = initialize_weekly_off_state(dataset["employees"])
        offs["E1"]["2026-11-30"] = "2026-12-06"
        state = {"roster": [{"employee_id": "E1", "date": "2026-12-06",
                             "brand_id": "B1", "process_id": "P1"}],
                 "daily_assignments": {}}

        validation = validate_roster(dataset, requirements, state, offs, 12, 2026)

        self.assertIn("weekly_off_overlap", {e["code"] for e in validation["errors"]})


if __name__ == "__main__":
    unittest.main()
