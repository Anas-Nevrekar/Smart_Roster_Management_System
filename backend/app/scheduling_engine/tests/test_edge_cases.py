import unittest
from copy import deepcopy

from app.scheduling_engine.assignment import can_assign, make_assignment
from app.scheduling_engine.backtracking import generate_roster
from app.scheduling_engine.candidate_selection import get_candidates
from app.scheduling_engine.preprocessing import build_daily_requirements
from app.scheduling_engine.sample_data_fixed import get_dataset
from app.scheduling_engine.validator import validate_roster
from app.scheduling_engine.weekly_off import (
    assign_weekly_off,
    initialize_weekly_off_state,
)


def requirement(day="2026-12-08", brand="B003", process="PR001", staffing=1):
    return {"date": day, "brand_id": brand, "process_id": process,
            "required_staffing": staffing}


class SchedulingEdgeCaseTests(unittest.TestCase):
    def setUp(self):
        self.dataset = get_dataset("prototype")
        self.state = {"roster": [], "daily_assignments": {}}
        self.offs = initialize_weekly_off_state(self.dataset["employees"])

    def can(self, employee_id, req=None):
        return can_assign(self.dataset, self.state, employee_id,
                          req or requirement(), self.offs)

    def generate(self, dataset, requirements):
        state = {"roster": [], "daily_assignments": {}}
        offs = initialize_weekly_off_state(dataset["employees"])
        result = generate_roster(dataset, requirements, state, offs)
        return result, state, offs

    # Eligibility and same-day assignment cases
    def test_employee_can_work_multiple_processes_same_day(self):
        first = requirement(brand="B001", process="PR001")
        second = requirement(brand="B001", process="PR002")
        self.assertTrue(self.can("E001", first))
        self.assertTrue(self.can("E001", second))
        make_assignment(self.state, "E001", first)
        self.assertTrue(self.can("E001", second))
        make_assignment(self.state, "E001", second)
        self.assertEqual(2, len(self.state["roster"]))

    def test_ineligible_brand_process_is_rejected(self):
        self.assertFalse(self.can("E003", requirement(brand="B001")))

    def test_inactive_employee_is_rejected(self):
        self.dataset["employees"][0]["is_active"] = False
        self.assertFalse(self.can("E001", requirement(brand="B001")))

    def test_duplicate_assignment_is_rejected(self):
        req = requirement()
        make_assignment(self.state, "E003", req)
        self.assertFalse(self.can("E003", req))

    def test_employee_can_work_across_brands_when_eligible(self):
        self.dataset["employee_assignments"].append({
            "employee_id": "E003", "brand_id": "B001",
            "process_id": "PR001", "is_active": True,
        })
        self.assertTrue(self.can("E003", requirement(brand="B003")))
        self.assertTrue(self.can("E003", requirement(brand="B001")))

    # Leave, comp-off, and recurring availability
    def test_approved_planned_leave_blocks_candidate(self):
        self.dataset["employee_time_off"] = [{
            "employee_id": "E003", "time_off_type": "planned_leave",
            "status": "approved", "start_date": "2026-12-08",
            "end_date": "2026-12-08",
        }]
        self.assertFalse(self.can("E003"))

    def test_approved_comp_off_blocks_candidate(self):
        self.dataset["employee_time_off"] = [{
            "employee_id": "E003", "time_off_type": "comp_off",
            "status": "approved", "start_date": "2026-12-08",
            "end_date": "2026-12-08",
        }]
        self.assertFalse(self.can("E003"))

    def test_pending_leave_does_not_block_candidate(self):
        self.dataset["employee_time_off"] = [{
            "employee_id": "E003", "time_off_type": "planned_leave",
            "status": "pending", "start_date": "2026-12-08",
            "end_date": "2026-12-08",
        }]
        self.assertIn("E003", get_candidates(self.dataset, "2026-12-08", "B003", "PR001"))

    def test_rejected_leave_does_not_block_candidate(self):
        self.dataset["employee_time_off"] = [{
            "employee_id": "E003", "time_off_type": "planned_leave",
            "status": "rejected", "start_date": "2026-12-08",
            "end_date": "2026-12-08",
        }]
        self.assertIn("E003", get_candidates(self.dataset, "2026-12-08", "B003", "PR001"))

    def test_can_assign_enforces_workable_days_directly(self):
        self.dataset["employees"][2]["workable_days"] = ["Monday"]
        self.assertFalse(self.can("E003"))

    # Weekly-off handling
    def test_generated_roster_has_one_off_for_each_active_employee_week(self):
        requirements = build_daily_requirements(self.dataset, 12, 2026)
        result, state, offs = self.generate(self.dataset, requirements)
        self.assertTrue(result["success"], result["errors"])
        self.assertEqual(50, sum(map(len, offs.values())))
        self.assertTrue(all(len(weeks) == 5 for weeks in offs.values()))

    def test_second_off_in_same_week_is_rejected(self):
        self.assertTrue(assign_weekly_off(self.offs, "E003", "2026-12-07"))
        self.assertFalse(assign_weekly_off(self.offs, "E003", "2026-12-08"))

    def test_assignment_on_weekly_off_date_is_rejected(self):
        assign_weekly_off(self.offs, "E003", "2026-12-08")
        self.assertFalse(self.can("E003"))

    def test_weekly_off_choice_is_backtracked_away_from_required_day(self):
        # E003 is the sole eligible employee, so its off cannot land on the
        # required date. The search must select another date in that week.
        self.dataset["employee_assignments"] = [
            a for a in self.dataset["employee_assignments"]
            if (a["brand_id"], a["process_id"]) != ("B003", "PR001")
            or a["employee_id"] == "E003"
        ]
        requirements = [requirement(staffing=1)]
        result, state, offs = self.generate(self.dataset, requirements)
        self.assertTrue(result["success"], result["errors"])
        self.assertNotEqual("2026-12-08", offs["E003"]["2026-12-07"])

    def test_failure_clears_weekly_off_decisions(self):
        result, state, offs = self.generate(get_dataset("prototype_conflict"),
            build_daily_requirements(get_dataset("prototype_conflict"), 12, 2026))
        self.assertFalse(result["success"])
        self.assertEqual([], result["assignments"])
        self.assertTrue(all(not weeks for weeks in result["weekly_offs"].values()))

    def test_month_boundary_week_offs_are_retained(self):
        requirements = build_daily_requirements(self.dataset, 12, 2026)
        result, _, offs = self.generate(self.dataset, requirements)
        self.assertTrue(result["success"])
        self.assertIn("2026-11-30", [w["2026-11-30"] for w in offs.values()])
        self.assertIn("2027-01-01", [w["2026-12-28"] for w in offs.values()])

    # Operating calendars and public holidays
    def test_closed_public_holiday_rule_is_omitted(self):
        reqs = build_daily_requirements(self.dataset, 12, 2026)
        self.assertNotIn(("B002", "PR001"), {
            (r["brand_id"], r["process_id"]) for r in reqs
            if r["date"] == "2026-12-25"
        })

    def test_operating_public_holiday_rule_is_included(self):
        reqs = build_daily_requirements(self.dataset, 12, 2026)
        self.assertIn(("B001", "PR001"), {
            (r["brand_id"], r["process_id"]) for r in reqs
            if r["date"] == "2026-12-25"
        })

    def test_processes_under_brand_have_different_holiday_policies(self):
        reqs = build_daily_requirements(self.dataset, 12, 2026)
        holiday = {(r["brand_id"], r["process_id"]) for r in reqs
                   if r["date"] == "2026-12-25"}
        self.assertIn(("B003", "PR001"), holiday)
        self.assertNotIn(("B003", "PR002"), holiday)

    def test_operating_day_restrictions_are_respected(self):
        reqs = build_daily_requirements(self.dataset, 12, 2026)
        self.assertFalse(any(r["date"] == "2026-12-06" for r in reqs))

    # Staffing and independent validation
    def test_small_sufficient_staffing_case_succeeds(self):
        result, _, _ = self.generate(self.dataset, [requirement(staffing=2)])
        self.assertTrue(result["success"], result["errors"])

    def test_static_insufficient_staffing_fails(self):
        data = deepcopy(self.dataset)
        data["employee_assignments"] = [
            a for a in data["employee_assignments"]
            if not (a["brand_id"] == "B003" and a["process_id"] == "PR001")
        ]
        result, state, _ = self.generate(data, [requirement(staffing=2)])
        self.assertFalse(result["success"])
        self.assertEqual([], result["assignments"])
        self.assertEqual([], state["roster"])

    def test_independent_validator_detects_ineligible_assignment(self):
        requirements = build_daily_requirements(self.dataset, 12, 2026)
        state = {"roster": [dict(employee_id="E001", date="2026-12-08",
                                 brand_id="B003", process_id="PR001")],
                 "daily_assignments": {}}
        result = validate_roster(self.dataset, requirements, state, self.offs, 12, 2026)
        codes = {e["code"] for e in result["errors"]}
        self.assertIn("ineligible_assignment", codes)
        self.assertIn("insufficient_staffing", codes)

    def test_independent_validator_detects_approved_leave(self):
        self.dataset["employee_time_off"] = [{
            "employee_id": "E003", "status": "approved",
            "time_off_type": "comp_off", "start_date": "2026-12-08",
            "end_date": "2026-12-08",
        }]
        requirements = build_daily_requirements(self.dataset, 12, 2026)
        state = {"roster": [dict(employee_id="E003", date="2026-12-08",
                                 brand_id="B003", process_id="PR001")],
                 "daily_assignments": {}}
        result = validate_roster(self.dataset, requirements, state, self.offs, 12, 2026)
        self.assertIn("approved_time_off", {e["code"] for e in result["errors"]})

    def test_independent_validator_detects_unworkable_day(self):
        self.dataset["employees"][2]["workable_days"] = ["Monday"]
        requirements = build_daily_requirements(self.dataset, 12, 2026)
        state = {"roster": [dict(employee_id="E003", date="2026-12-08",
                                 brand_id="B003", process_id="PR001")],
                 "daily_assignments": {}}
        result = validate_roster(self.dataset, requirements, state, self.offs, 12, 2026)
        self.assertIn("unworkable_day", {e["code"] for e in result["errors"]})

    def test_independent_validator_detects_closed_holiday_assignment(self):
        requirements = build_daily_requirements(self.dataset, 12, 2026)
        state = {"roster": [dict(employee_id="E002", date="2026-12-25",
                                 brand_id="B002", process_id="PR001")],
                 "daily_assignments": {}}
        result = validate_roster(self.dataset, requirements, state, self.offs, 12, 2026)
        self.assertIn("closed_operating_day", {e["code"] for e in result["errors"]})

    def test_independent_validator_detects_closed_weekday_assignment(self):
        requirements = build_daily_requirements(self.dataset, 12, 2026)
        state = {"roster": [dict(employee_id="E003", date="2026-12-06",
                                 brand_id="B003", process_id="PR001")],
                 "daily_assignments": {}}
        result = validate_roster(self.dataset, requirements, state, self.offs, 12, 2026)
        error = next(e for e in result["errors"] if e["code"] == "closed_operating_day")
        self.assertEqual("Sunday", error["weekday"])

    def test_generated_roster_passes_independent_validation(self):
        requirements = build_daily_requirements(self.dataset, 12, 2026)
        result, state, offs = self.generate(self.dataset, requirements)
        self.assertTrue(result["success"], result["errors"])
        validated = validate_roster(self.dataset, requirements, state, offs, 12, 2026)
        self.assertEqual([], validated["errors"])


if __name__ == "__main__":
    unittest.main()
