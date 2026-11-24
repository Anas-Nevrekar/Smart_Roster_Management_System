import unittest
import sys
from time import perf_counter

from app.scheduling_engine.backtracking import generate_roster
from app.scheduling_engine.preprocessing import build_daily_requirements
from app.scheduling_engine.sample_data_fixed import get_dataset
from app.scheduling_engine.validator import validate_roster
from app.scheduling_engine.roster_audit import audit_roster
from app.scheduling_engine.weekly_off import initialize_weekly_off_state


class AssessmentDatasetTests(unittest.TestCase):
    def test_assessment_fixture_references_are_consistent(self):
        data = get_dataset("valid")
        employees = {e["employee_id"]: e for e in data["employees"]}
        pods = {p["pod_id"]: p for p in data["pods"]}
        brands = {b["brand_id"] for b in data["brands"]}
        processes = {p["process_id"] for p in data["processes"]}

        self.assertGreaterEqual(len(employees), 30)
        self.assertEqual(len(employees), len(data["employees"]))
        self.assertEqual(len({e["email"] for e in data["employees"]}), len(employees))
        self.assertTrue(all(e["pod_id"] in pods for e in employees.values()))
        self.assertTrue(all(pod["pod_lead_id"] in employees for pod in pods.values()))

        eligibility = [(a["employee_id"], a["brand_id"], a["process_id"])
                       for a in data["employee_assignments"]]
        self.assertEqual(len(eligibility), len(set(eligibility)))
        self.assertTrue(all(eid in employees and bid in brands and pid in processes
                            for eid, bid, pid in eligibility))

        rules = [(r["brand_id"], r["process_id"])
                 for r in data["brand_process_rules"]]
        self.assertEqual(len(rules), len(set(rules)))
        self.assertTrue(all(bid in brands and pid in processes
                            for bid, pid in rules))
        self.assertTrue(all(isinstance(r["minimum_staffing"], int)
                            and r["minimum_staffing"] > 0
                            for r in data["brand_process_rules"]))

    def test_brand_distribution_is_twenty_dedicated_and_five_shared(self):
        data = get_dataset("valid")
        active_eligibility = [a for a in data["employee_assignments"] if a["is_active"]]
        process_ids = {p["process_id"] for p in data["processes"]}
        employee_ids_by_brand = {}
        for brand in data["brands"]:
            employee_ids_by_brand[brand["brand_id"]] = {
                a["employee_id"] for a in active_eligibility
                if a["brand_id"] == brand["brand_id"]
            }
        dedicated = [brand_id for brand_id, employee_ids in employee_ids_by_brand.items()
                     if len(employee_ids) == 1 and all(
                         any(a["employee_id"] in employee_ids
                             and a["brand_id"] == brand_id
                             and a["process_id"] == process_id
                             for a in active_eligibility)
                         for process_id in process_ids
                     )]
        shared = [ids for ids in employee_ids_by_brand.values() if len(ids) in (2, 3)]
        self.assertEqual(25, len(data["brands"]))
        self.assertEqual(20, len(dedicated))
        self.assertEqual(5, len(shared))
        self.assertAlmostEqual(0.8, len(dedicated) / len(data["brands"]))

    def test_prototype_fixture_remains_available(self):
        self.assertEqual(10, len(get_dataset("prototype")["employees"]))

    def test_expanded_valid_roster_generates_and_validates(self):
        data = get_dataset("valid")
        requirements = build_daily_requirements(data, 12, 2026)
        state = {"roster": [], "daily_assignments": {}}
        offs = initialize_weekly_off_state(data["employees"])

        original_recursion_limit = sys.getrecursionlimit()
        started = perf_counter()
        result = generate_roster(data, requirements, state, offs)
        elapsed = perf_counter() - started
        self.assertEqual(original_recursion_limit, sys.getrecursionlimit())
        validation = validate_roster(data, requirements, state, offs, 12, 2026)
        audit = audit_roster(data, requirements, state["roster"], offs, 12, 2026)

        self.assertTrue(result["success"], result["errors"])
        self.assertTrue(validation["valid"], validation["errors"])
        self.assertEqual(1990, audit["requirements_total"])
        self.assertEqual(1990, audit["requirements_satisfied"])
        self.assertEqual([], audit["staffing_gaps"])
        self.assertEqual([], audit["weekly_off_coverage_gaps"])
        self.assertEqual(2017, audit["valid_working_assignments"])
        self.assertEqual(0, audit["leave_conflicts"])
        self.assertEqual(0, audit["eligibility_conflicts"])
        self.assertEqual(0, audit["duplicate_assignments"])
        self.assertEqual(0, audit["weekly_off_overlaps"])
        self.assertEqual(0, len(audit["employees_with_incorrect_weekly_off_counts"]))
        self.assertIn("2026-11-30", audit["boundary_weekly_offs"])
        self.assertIn("2027-01-01", audit["boundary_weekly_offs"])
        self.assertEqual(sum(r["required_staffing"] for r in requirements),
                         len(state["roster"]))
        active_count = sum(employee["is_active"] for employee in data["employees"])
        self.assertEqual(active_count * 5, sum(map(len, offs.values())))
        self.assertLess(elapsed, 60, f"Roster generation took {elapsed:.1f}s")

        assignment_keys = [(a["employee_id"], a["date"], a["brand_id"], a["process_id"])
                           for a in state["roster"]]
        self.assertEqual(len(assignment_keys), len(set(assignment_keys)))
        self.assertTrue(any(len({a["process_id"] for a in assignments}) > 1
                            for dates in state["daily_assignments"].values()
                            for assignments in dates.values()))

    def test_expanded_conflict_fails_cleanly_with_specific_gap(self):
        data = get_dataset("conflict")
        requirements = build_daily_requirements(data, 12, 2026)
        state = {"roster": [], "daily_assignments": {}}
        offs = initialize_weekly_off_state(data["employees"])
        result = generate_roster(data, requirements, state, offs)

        self.assertFalse(result["success"])
        self.assertEqual([], result["assignments"])
        self.assertEqual([], state["roster"])
        self.assertTrue(all(not weeks for weeks in result["weekly_offs"].values()))
        gap = next(error for error in result["errors"]
                   if error.get("date") == "2026-12-08"
                   and error.get("brand_id") == "B003"
                   and error.get("process_id") == "PR001")
        self.assertEqual("approved_time_off", gap["code"])
        self.assertEqual(2, gap["required_staffing"])
        self.assertEqual(0, gap["available_staffing"])
        self.assertEqual(["E021", "E022", "E023"], gap["unavailable_employee_ids"])


if __name__ == "__main__":
    unittest.main()
