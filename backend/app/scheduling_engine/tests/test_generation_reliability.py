import unittest
import sys
from concurrent.futures import ThreadPoolExecutor
from datetime import date, timedelta
from threading import Barrier, Lock
from time import sleep
from unittest.mock import patch

from app.scheduling_engine import backtracking
from app.scheduling_engine.backtracking import generate_roster
from app.scheduling_engine.preprocessing import build_daily_requirements
from app.scheduling_engine.sample_data_fixed import get_dataset
from app.scheduling_engine.weekly_off import initialize_weekly_off_state


class GenerationReliabilityTests(unittest.TestCase):
    def run_generation(self, dataset, requirements):
        state = {"roster": [], "daily_assignments": {}}
        offs = initialize_weekly_off_state(dataset["employees"])
        result = generate_roster(dataset, requirements, state, offs)
        return result, state, offs

    def test_repeated_generation_has_independent_results(self):
        dataset = get_dataset("valid")
        requirements = build_daily_requirements(dataset, 12, 2026)
        first = self.run_generation(dataset, requirements)
        second = self.run_generation(dataset, requirements)

        self.assertTrue(first[0]["success"], first[0]["errors"])
        self.assertTrue(second[0]["success"], second[0]["errors"])
        self.assertEqual(first[0]["assignments"], second[0]["assignments"])
        self.assertEqual(first[0]["weekly_offs"], second[0]["weekly_offs"])
        self.assertIsNot(first[1]["roster"], second[1]["roster"])

    def test_concurrent_calls_are_serialized_while_limit_is_adjusted(self):
        barrier = Barrier(2)
        active_calls = 0
        max_active_calls = 0
        activity_lock = Lock()
        original_search = backtracking._generate_roster
        original_get_candidates = backtracking.get_candidates
        original_recursion_limit = sys.getrecursionlimit()
        observed_recursion_limits = []

        def tracked_search(*args):
            nonlocal active_calls, max_active_calls
            with activity_lock:
                active_calls += 1
                max_active_calls = max(max_active_calls, active_calls)
            sleep(0.03)
            try:
                return original_search(*args)
            finally:
                with activity_lock:
                    active_calls -= 1

        def tracked_get_candidates(*args):
            observed_recursion_limits.append(sys.getrecursionlimit())
            return original_get_candidates(*args)

        # Many distinct process requirements force each search beyond the
        # default recursion depth without adding a per-day work restriction.

        def worker():
            dataset = get_dataset("prototype")
            dataset["employees"] = [e for e in dataset["employees"]
                                    if e["employee_id"] == "E003"]
            process_ids = [f"PX{number:03d}" for number in range(350)]
            dataset["processes"] = [{"process_id": process_id, "is_active": True}
                                    for process_id in process_ids]
            dataset["employee_assignments"] = [{
                "employee_id": "E003", "brand_id": "B003",
                "process_id": process_id, "is_active": True,
            } for process_id in process_ids]
            requirements = [{
                "date": "2026-12-08", "weekday": "Tuesday",
                "brand_id": "B003", "process_id": process_id,
                "required_staffing": 1,
            } for process_id in process_ids]
            state = {"roster": [], "daily_assignments": {}}
            offs = initialize_weekly_off_state(dataset["employees"])
            barrier.wait()
            result = generate_roster(dataset, requirements, state, offs)
            return result, state, offs

        with patch.object(backtracking, "_generate_roster", tracked_search), \
                patch.object(backtracking, "get_candidates", tracked_get_candidates):
            with ThreadPoolExecutor(max_workers=2) as executor:
                futures = [executor.submit(worker) for _ in range(2)]
                outcomes = [future.result(timeout=15) for future in futures]

        self.assertTrue(all(result[0]["success"] for result in outcomes))
        self.assertEqual(2, len(outcomes))
        self.assertEqual(1, max_active_calls)
        self.assertTrue(observed_recursion_limits)
        self.assertTrue(all(limit > original_recursion_limit
                            for limit in observed_recursion_limits))
        self.assertEqual(original_recursion_limit, sys.getrecursionlimit())
        self.assertIsNot(outcomes[0][1], outcomes[1][1])

    def test_assignment_search_failure_is_distinguished_after_complete_off_plans(self):
        dataset = get_dataset("prototype")
        dataset["employees"] = [e for e in dataset["employees"]
                                if e["employee_id"] in {"E003", "E004"}]
        dataset["employee_assignments"] = [
            a for a in dataset["employee_assignments"]
            if a["brand_id"] == "B003" and a["process_id"] == "PR001"
            and a["employee_id"] in {"E003", "E004"}
        ]

        # In four unrelated calendar weeks, make Sunday the sole off option.
        # In the target week, two duplicate staffing rows are individually
        # coverable but cannot both be assigned without duplicate work records.
        other_mondays = [date(2026, 11, 30), date(2026, 12, 14),
                         date(2026, 12, 21), date(2026, 12, 28)]
        for employee_id in ("E003", "E004"):
            for monday in other_mondays:
                for offset in range(6):
                    off_blocked_date = (monday + timedelta(days=offset)).isoformat()
                    dataset["employee_time_off"].append({
                        "employee_id": employee_id, "status": "approved",
                        "time_off_type": "planned_leave",
                        "start_date": off_blocked_date,
                        "end_date": off_blocked_date,
                    })

        row = {"date": "2026-12-08", "weekday": "Tuesday",
               "brand_id": "B003", "process_id": "PR001",
               "required_staffing": 2}
        result, state, offs = self.run_generation(dataset, [dict(row), dict(row)])

        self.assertFalse(result["success"])
        self.assertEqual("assignment_search_failure", result["errors"][0]["code"])
        self.assertGreater(result["errors"][0]["complete_weekly_off_plans"], 0)
        self.assertFalse(result["errors"][0]["exact_cause_established"])
        self.assertEqual([], result["assignments"])
        self.assertEqual([], state["roster"])
        self.assertTrue(all(not weeks for weeks in offs.values()))


if __name__ == "__main__":
    unittest.main()
