from datetime import date

from app.integrations.roster_engine.mapper import map_repository_snapshot


def _working(client, roster_id):
    return client.get(f"/api/v1/rosters/{roster_id}/assignments", params={"status": "working"}).json()["data"]


def _available_eligible_assignment(repository, exclude_id=None, require_existing_same_day=False):
    snapshot = repository.snapshot()
    dataset = map_repository_snapshot(snapshot)
    records = [x for x in snapshot["roster_assignments"] if x["roster_id"] == "roster-2026-12"]
    existing = {(x["employee_id"], x["assignment_date"], x.get("brand_id"), x.get("process_id"))
                for x in records if x["status"] == "working" and x["id"] != exclude_id}
    offs = {(x["employee_id"], x["assignment_date"]) for x in records if x["status"] == "weekly_off"}
    employees = {x["employee_id"]: x for x in dataset["employees"]}
    holidays = {x["holiday_date"] for x in dataset["public_holidays"]}
    rules = {(x["brand_id"], x["process_id"]): x for x in dataset["brand_process_rules"] if x["is_active"]}
    for eligibility in dataset["employee_assignments"]:
        employee = employees[eligibility["employee_id"]]
        if not eligibility["is_active"] or not employee["is_active"]:
            continue
        rule = rules.get((eligibility["brand_id"], eligibility["process_id"]))
        if not rule or not rule["is_active"]:
            continue
        for day in range(1, 32):
            assignment_date = date(2026, 12, day)
            iso = assignment_date.isoformat()
            weekday = assignment_date.strftime("%A")
            operates = rule["public_holiday_policy"] == "operate" if iso in holidays else weekday in rule["operating_days"]
            if not operates or weekday not in employee["workable_days"] or (employee["employee_id"], iso) in offs:
                continue
            if any(x["employee_id"] == employee["employee_id"] and x["status"] == "approved" and x["start_date"] <= iso <= x["end_date"] for x in dataset["employee_time_off"]):
                continue
            key = (employee["employee_id"], iso, eligibility["brand_id"], eligibility["process_id"])
            if key in existing:
                continue
            if require_existing_same_day and not any(x[0] == employee["employee_id"] and x[1] == iso for x in existing):
                continue
            return {"employee_id": employee["employee_id"], "assignment_date": iso,
                    "brand_id": eligibility["brand_id"], "process_id": eligibility["process_id"]}
    raise AssertionError("No eligible date found for test assignment")


def test_manual_add_update_delete_and_optimistic_version(draft_roster):
    client, repository, roster_id = draft_roster
    proposed = _available_eligible_assignment(repository, require_existing_same_day=True)
    before_records = repository.list_roster_assignments(roster_id)
    before = len(before_records)
    before_working = sum(item["status"] == "working" for item in before_records)
    created = client.post(f"/api/v1/rosters/{roster_id}/assignments", json=proposed, headers={"If-Match": '"1"'})
    assert created.status_code == 200
    assignment_id = created.json()["assignment"]["id"]
    assert created.json()["roster_version"] == 2
    assert len(repository.list_roster_assignments(roster_id)) == before + 1
    saved_summary = repository.get("rosters", roster_id)["summary"]
    assert saved_summary["total_assignments"] == before_working + 1
    assert saved_summary["total_weekly_offs"] == sum(item["status"] == "weekly_off" for item in before_records)
    assert repository.get("rosters", roster_id)["latest_validation"] is None
    # A second process assignment for the same employee/date is supported.
    same_day = [x for x in _working(client, roster_id) if x["employee_id"] == proposed["employee_id"] and x["assignment_date"] == proposed["assignment_date"]]
    assert len(same_day) > 1
    duplicate = client.post(f"/api/v1/rosters/{roster_id}/assignments", json=proposed, headers={"If-Match": "2"})
    assert duplicate.status_code == 409 and duplicate.json()["error"]["code"] == "DUPLICATE_ASSIGNMENT"
    stale = client.patch(f"/api/v1/rosters/{roster_id}/assignments/{assignment_id}", json={"assignment_date": "2026-12-31"}, headers={"If-Match": "1"})
    assert stale.status_code == 409 and stale.json()["error"]["code"] == "STALE_ROSTER_VERSION"
    moved = client.patch(f"/api/v1/rosters/{roster_id}/assignments/{assignment_id}", json={"assignment_date": "2026-12-31"}, headers={"If-Match": "2"})
    # If New Year's operating calendar closes this pair on the chosen date, try a valid date instead.
    if moved.status_code != 200:
        candidate = _available_eligible_assignment(repository, exclude_id=assignment_id)
        moved = client.patch(f"/api/v1/rosters/{roster_id}/assignments/{assignment_id}", json={"assignment_date": candidate["assignment_date"]}, headers={"If-Match": "2"})
    assert moved.status_code == 200 and moved.json()["roster_version"] == 3
    deleted = client.delete(f"/api/v1/rosters/{roster_id}/assignments/{assignment_id}", headers={"If-Match": "3"})
    assert deleted.status_code == 200 and deleted.json()["roster_version"] == 4
    assert client.delete(f"/api/v1/rosters/{roster_id}/assignments/{assignment_id}", headers={"If-Match": "4"}).status_code == 404


def test_invalid_manual_changes_do_not_mutate_roster(draft_roster):
    client, repository, roster_id = draft_roster
    repository.create("employees", {"employee_id": "E900", "full_name": "Tuesday Restricted", "email": "e900@example.com",
        "pod_id": None, "is_active": True, "weekly_off_per_week": 1, "workable_days": ["Monday"]})
    repository.create("eligibility", {"employee_id": "E900", "brand_id": "B001", "process_id": "PR001", "is_active": True})
    initial = repository.snapshot()
    invalids = [
        ({"employee_id": "missing", "assignment_date": "2026-12-01", "brand_id": "B001", "process_id": "PR001"}, "INVALID_EMPLOYEE"),
        ({"employee_id": "E032", "assignment_date": "2026-12-01", "brand_id": "B025", "process_id": "PR001"}, "INVALID_EMPLOYEE"),
        ({"employee_id": "E900", "assignment_date": "2026-12-01", "brand_id": "B001", "process_id": "PR001"}, "NON_WORKABLE_DAY"),
        ({"employee_id": "E001", "assignment_date": "2026-12-01", "brand_id": "B002", "process_id": "PR001"}, "INVALID_ELIGIBILITY"),
        ({"employee_id": "E021", "assignment_date": "2026-12-09", "brand_id": "B003", "process_id": "PR001"}, "APPROVED_TIME_OFF_CONFLICT"),
        ({"employee_id": "E021", "assignment_date": "2026-12-25", "brand_id": "B003", "process_id": "PR002"}, "CLOSED_OPERATING_DAY"),
        ({"employee_id": "E021", "assignment_date": "2027-01-01", "brand_id": "B003", "process_id": "PR001"}, "ASSIGNMENT_OUTSIDE_ROSTER_MONTH"),
    ]
    off = next(x for x in repository.list_roster_assignments(roster_id) if x["status"] == "weekly_off" and x["employee_id"] == "E021")
    invalids.append(({"employee_id": "E021", "assignment_date": off["assignment_date"], "brand_id": "B003", "process_id": "PR001"}, "WEEKLY_OFF_CONFLICT"))
    for payload, expected_code in invalids:
        response = client.post(f"/api/v1/rosters/{roster_id}/assignments", json=payload, headers={"If-Match": "1"})
        assert response.status_code in (409, 422), (expected_code, response.text)
        assert response.json()["error"]["code"] == expected_code, response.json()
        assert repository.snapshot() == initial
    no_version = client.post(f"/api/v1/rosters/{roster_id}/assignments", json=invalids[0][0])
    assert no_version.status_code == 428


def test_delete_that_creates_staffing_gap_is_rejected(draft_roster):
    client, repository, roster_id = draft_roster
    assignment = next(x for x in repository.list_roster_assignments(roster_id)
                      if x["status"] == "working" and x["employee_id"] == "E001" and x["brand_id"] == "B001" and x["process_id"] == "PR001")
    before = repository.snapshot()
    response = client.delete(f"/api/v1/rosters/{roster_id}/assignments/{assignment['id']}", headers={"If-Match": "1"})
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "STAFFING_GAP"
    assert repository.snapshot() == before


def test_change_impact_previews_all_supported_change_types_without_mutation(draft_roster):
    client, repository, roster_id = draft_roster
    before = repository.snapshot()
    assignments = [x for x in before["roster_assignments"] if x["roster_id"] == roster_id and x["status"] == "working"]
    target = next(x for x in assignments if x["employee_id"] == "E021")
    employee = next(x for x in before["employees"] if x["employee_id"] == "E021")
    weekday = date.fromisoformat(target["assignment_date"]).strftime("%A")
    availability_days = [x for x in employee["workable_days"] if x != weekday]
    eligibility = next(x for x in before["eligibility"] if x["employee_id"] == target["employee_id"] and x["brand_id"] == target["brand_id"] and x["process_id"] == target["process_id"])
    rule = next(x for x in before["operating_rules"] if x["brand_id"] == "B001" and x["process_id"] == "PR001")
    changes = [
        {"change_type": "availability", "employee_id": "E021", "workable_days": availability_days},
        {"change_type": "time_off", "employee_id": target["employee_id"], "time_off_type": "planned_leave", "start_date": target["assignment_date"], "end_date": target["assignment_date"], "status": "approved"},
        {"change_type": "eligibility", "employee_id": eligibility["employee_id"], "brand_id": eligibility["brand_id"], "process_id": eligibility["process_id"], "is_active": False},
        {"change_type": "operating_rule", "brand_id": rule["brand_id"], "process_id": rule["process_id"], "operating_days": rule["operating_days"], "public_holiday_policy": rule["public_holiday_policy"], "minimum_staffing": 3, "coverage_overrides": [], "is_active": True},
    ]
    responses = [client.post(f"/api/v1/rosters/{roster_id}/check-impact", json={"change": change}) for change in changes]
    assert all(response.status_code == 200 for response in responses)
    assert all(response.json()["valid"] is False and response.json()["conflicts"] for response in responses)
    assert responses[-1].json()["staffing_impact"]
    assert all(response.json()["current_version"] == 1 for response in responses)
    assert repository.snapshot() == before


def test_published_roster_cannot_be_edited(draft_roster):
    client, repository, roster_id = draft_roster
    published = client.post(f"/api/v1/rosters/{roster_id}/publish", json={"published_by": "manager"})
    assert published.status_code == 200
    response = client.post(f"/api/v1/rosters/{roster_id}/assignments",
        json={"employee_id": "E001", "assignment_date": "2026-12-01", "brand_id": "B001", "process_id": "PR001"},
        headers={"If-Match": str(published.json()["data"]["version"])})
    assert response.status_code == 409 and response.json()["error"]["code"] == "ROSTER_IMMUTABLE"
