import unittest
from datetime import date, timedelta

from app.scheduling_engine.backtracking import generate_roster
from app.scheduling_engine.preprocessing import build_daily_requirements
from app.scheduling_engine.sample_data_fixed import get_dataset
from app.scheduling_engine.validator import validate_roster
from app.scheduling_engine.weekly_off import initialize_weekly_off_state


class RosterValidationTests(unittest.TestCase):
    def generate(self, scenario="prototype"):
        dataset = get_dataset(scenario)
        requirements = build_daily_requirements(dataset, 12, 2026)
        state = {"roster": [], "daily_assignments": {}}
        offs = initialize_weekly_off_state(dataset["employees"])
        result = generate_roster(dataset, requirements, state, offs)
        return dataset, requirements, state, offs, result

    def test_december_roster_is_valid_and_keeps_boundary_week_offs(self):
        dataset, requirements, state, offs, result = self.generate()
        self.assertTrue(result["success"])
        self.assertTrue(result["assignments"])
        self.assertTrue(result["weekly_offs"])
        self.assertEqual([], result["errors"])
        result = validate_roster(dataset, requirements, state, offs, 12, 2026)
        self.assertTrue(result["valid"], result["errors"])
        off_dates = [d for weeks in offs.values() for d in weeks.values()]
        self.assertIn("2026-11-30", off_dates)
        self.assertIn("2027-01-01", off_dates)
        self.assertEqual(50, len(off_dates))
        for week_start in next(iter(offs.values())):
            self.assertEqual(1, len({weeks[week_start] for weeks in offs.values()}))

    def test_conflict_fails_without_partial_roster(self):
        dataset, requirements, state, offs, result = self.generate("prototype_conflict")
        self.assertFalse(result["success"])
        self.assertEqual([], result["assignments"])
        diagnostic = next(e for e in result["errors"]
                          if e["date"] == "2026-12-08" and e["brand_id"] == "B003"
                          and e["process_id"] == "PR001")
        self.assertEqual("approved_time_off", diagnostic["code"])
        self.assertEqual(2, diagnostic["required_staffing"])
        self.assertEqual(0, diagnostic["available_staffing"])
        self.assertEqual(["E003", "E004", "E005"],
                         diagnostic["unavailable_employee_ids"])
        self.assertEqual([], state["roster"])
        result = validate_roster(dataset, requirements, state, offs, 12, 2026)
        gap = [e for e in result["errors"] if e["code"] == "insufficient_staffing"
               and e["date"] == "2026-12-08" and e["brand_id"] == "B003"
               and e["process_id"] == "PR001"]
        self.assertTrue(gap)
        self.assertEqual(0, gap[0]["actual"])

    def test_validator_reports_inactive_duplicate_and_off_overlap(self):
        dataset, requirements, state, offs, result = self.generate()
        self.assertTrue(result["success"])
        original = state["roster"][0]
        state["roster"].extend([dict(original), dict(original)])
        dataset["employees"][0]["is_active"] = False
        offs[original["employee_id"]]["2026-11-30"] = original["date"]

        result = validate_roster(dataset, requirements, state, offs, 12, 2026)
        codes = {entry["code"] for entry in result["errors"]}
        self.assertIn("duplicate_assignment", codes)
        self.assertIn("inactive_or_unknown_employee", codes)
        self.assertIn("weekly_off_overlap", codes)

    def test_no_eligibility_and_static_insufficiency_diagnostics(self):
        from app.scheduling_engine.diagnostics import diagnose_generation_failure

        dataset = get_dataset("prototype")
        requirement = {"date": "2026-12-08", "weekday": "Tuesday",
                       "brand_id": "B003", "process_id": "PR001",
                       "required_staffing": 2}
        dataset["employee_assignments"] = [
            a for a in dataset["employee_assignments"]
            if not (a["brand_id"] == "B003" and a["process_id"] == "PR001")
        ]
        error = diagnose_generation_failure(dataset, [requirement])[0]
        self.assertEqual("no_eligible_employees", error["code"])

        dataset = get_dataset("prototype")
        dataset["employee_time_off"] = [
            {"employee_id": employee_id, "status": "approved",
             "time_off_type": "comp_off", "start_date": "2026-12-08",
             "end_date": "2026-12-08"}
            for employee_id in ("E003", "E004")
        ]
        error = diagnose_generation_failure(dataset, [requirement])[0]
        self.assertEqual("insufficient_staffing", error["code"])
        self.assertEqual(1, error["available_staffing"])
        self.assertEqual(["comp_off"], error["time_off_types"])

    def test_no_weekly_off_date_is_reported(self):
        dataset = get_dataset("prototype")
        dataset["employee_time_off"] = [{
            "employee_id": "E001", "status": "approved",
            "start_date": "2026-11-30", "end_date": "2026-12-06",
            "time_off_type": "planned_leave",
        }]
        requirements = build_daily_requirements(dataset, 12, 2026)
        state = {"roster": [], "daily_assignments": {}}
        offs = initialize_weekly_off_state(dataset["employees"])
        result = generate_roster(dataset, requirements, state, offs)
        self.assertFalse(result["success"])
        self.assertEqual("no_weekly_off_date", result["errors"][0]["code"])
        self.assertEqual("E001", result["errors"][0]["employee_id"])

    def test_exhausted_weekly_off_search_is_not_reported_as_a_single_bad_branch(self):
        dataset = get_dataset("prototype")
        # Only two eligible employees can cover this process, and it operates
        # every day of this week. Their required weekly offs make full coverage
        # impossible, although each day is individually coverable without offs.
        dataset["employee_assignments"] = [
            a for a in dataset["employee_assignments"]
            if (a["brand_id"], a["process_id"]) != ("B003", "PR001")
            or a["employee_id"] in {"E003", "E004"}
        ]
        dataset["employees"] = [e for e in dataset["employees"]
                                if e["employee_id"] in {"E003", "E004"}]
        # Keep the unrelated monthly weekly-off choices deterministic so this
        # regression exercises the constrained week without a huge search tree.
        outside_weeks = [date(2026, 11, 30), date(2026, 12, 14),
                         date(2026, 12, 21), date(2026, 12, 28)]
        for employee_id in ("E003", "E004"):
            for monday in outside_weeks:
                for offset in range(6):  # leave Sunday as the only off option
                    day_text = (monday + timedelta(days=offset)).isoformat()
                    dataset["employee_time_off"].append({
                        "employee_id": employee_id, "status": "approved",
                        "start_date": day_text, "end_date": day_text,
                        "time_off_type": "planned_leave",
                    })
        requirements = [{
            "date": f"2026-12-{day:02d}",
            "weekday": date(2026, 12, day).strftime("%A"),
            "brand_id": "B003", "process_id": "PR001",
            "required_staffing": 2,
        } for day in range(7, 14)]
        state = {"roster": [], "daily_assignments": {}}
        offs = initialize_weekly_off_state(dataset["employees"])
        result = generate_roster(dataset, requirements, state, offs)
        self.assertFalse(result["success"])
        self.assertEqual("weekly_off_allocation_conflict", result["errors"][0]["code"])
        self.assertEqual([], result["assignments"])


if __name__ == "__main__":
    unittest.main()
