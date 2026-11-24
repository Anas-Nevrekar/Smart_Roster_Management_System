from fastapi.testclient import TestClient

from app.core.config import Settings
from app.main import create_app


def test_health_ready_and_openapi(client):
    assert client.get("/api/v1/health").status_code == 200
    ready = client.get("/api/v1/ready").json()["data"]
    assert ready["status"] == "ready" and ready["external_persistence"] is False
    assert client.get("/openapi.json").status_code == 200


def test_mongodb_mode_reports_not_ready_and_never_falls_back_to_memory():
    settings = Settings(environment="testing", storage_backend="mongodb", mongodb_uri=None)
    with TestClient(create_app(settings)) as mongo_client:
        assert mongo_client.get("/api/v1/health").status_code == 200
        ready = mongo_client.get("/api/v1/ready")
        assert ready.status_code == 503
        assert ready.json()["error"]["code"] == "DATABASE_UNAVAILABLE"
        assert mongo_client.get("/api/v1/employees").status_code == 503


def test_cors_and_error_shapes(client):
    cors = client.options("/api/v1/employees", headers={"Origin": "http://localhost:5173", "Access-Control-Request-Method": "GET"})
    assert cors.headers["access-control-allow-origin"] == "http://localhost:5173"
    invalid = client.post("/api/v1/employees", json={"employee_id": "X", "full_name": "Missing fields"})
    assert invalid.status_code == 422
    assert invalid.json()["error"]["code"] == "VALIDATION_ERROR"


def test_employee_list_crud_and_validation(client):
    assert client.get("/api/v1/employees").json()["total"] == 32
    assert client.get("/api/v1/employees", params={"pod_id": "POD01"}).json()["total"] == 7
    assert client.get("/api/v1/employees", params={"search": "rahul"}).json()["total"] == 1
    body = {"employee_id": "E900", "full_name": "New Person", "email": "new@example.com", "pod_id": "POD01"}
    created = client.post("/api/v1/employees", json=body)
    assert created.status_code == 201
    assert client.post("/api/v1/employees", json=body).status_code == 409
    assert client.get("/api/v1/employees/not-found").status_code == 404


def test_cross_entity_and_relationship_endpoints(client):
    assert client.post("/api/v1/eligibility", json={"employee_id": "E001", "brand_id": "missing", "process_id": "PR001"}).status_code == 400
    assert client.get("/api/v1/brands/B001/processes").json()["total"] == 3
    assert client.get("/api/v1/pods/POD01/employees").json()["total"] == 7


def test_time_off_and_holidays(client):
    response = client.post("/api/v1/time-off", json={"employee_id": "E001", "time_off_type": "planned_leave", "start_date": "2026-12-10", "end_date": "2026-12-09"})
    assert response.status_code == 422
    created = client.post("/api/v1/public-holidays", json={"holiday_name": "Test", "holiday_date": "2026-12-26"})
    assert created.status_code == 201
    assert client.post("/api/v1/public-holidays", json={"holiday_name": "Duplicate", "holiday_date": "2026-12-26"}).status_code == 409


def test_fresh_app_and_reset(repository):
    repository.create("brands", {"brand_name": "Transient", "is_active": True})
    repository.reset()
    assert len(repository.list("brands")) == 25
    second = InMemoryRepository()
    assert len(second.list("brands")) == 25


def test_sample_data_mapping_and_conflict_fixture(repository):
    assert {key: len(repository.list(key)) for key in ("employees", "pods", "brands", "processes", "eligibility", "operating_rules", "time_off", "public_holidays")} == {
        "employees": 32, "pods": 5, "brands": 25, "processes": 3,
        "eligibility": 94, "operating_rules": 75, "time_off": 2, "public_holidays": 1,
    }
    assert repository.get("employees", "E001")["full_name"] == "Rahul Sharma"
    assert "name" not in repository.get("employees", "E001")
    assert repository.get("time_off", "ATO002")["status"] == "pending"
    conflict = InMemoryRepository(scenario="conflict")
    assert len(conflict.list("time_off")) == 5


def test_eligibility_replacement_is_atomic(client):
    before = client.get("/api/v1/employees/E001/eligibility").json()["data"]
    bad = client.put("/api/v1/employees/E001/eligibility", json={"items": [{"brand_id": "missing", "process_id": "PR001"}]})
    assert bad.status_code == 400
    assert client.get("/api/v1/employees/E001/eligibility").json()["data"] == before
    good = client.put("/api/v1/employees/E001/eligibility", json={"items": [{"brand_id": "B003", "process_id": "PR001"}]})
    assert good.status_code == 200 and good.json()["total"] == 1


def test_employee_update_availability_and_eligibility_crud(client):
    employee = client.get("/api/v1/employees/E001").json()["data"]
    replacement = {key: employee[key] for key in ("employee_id", "full_name", "email", "pod_id", "is_active", "weekly_off_per_week", "workable_days")}
    replacement["full_name"] = "Rahul Updated"
    assert client.put("/api/v1/employees/E001", json=replacement).json()["data"]["full_name"] == "Rahul Updated"
    replacement["employee_id"] = "CHANGED"
    assert client.put("/api/v1/employees/E001", json=replacement).status_code == 400
    availability = client.put("/api/v1/employees/E001/availability", json={"workable_days": ["Monday", "Tuesday"], "weekly_off_per_week": 1})
    assert availability.json()["data"]["workable_days"] == ["Monday", "Tuesday"]
    created = client.post("/api/v1/eligibility", json={"employee_id": "E001", "brand_id": "B003", "process_id": "PR001"})
    assert created.status_code == 201
    item_id = created.json()["data"]["id"]
    assert client.get("/api/v1/brands/B003/eligibility").json()["total"] >= 1
    update = {"employee_id": "E001", "brand_id": "B003", "process_id": "PR002", "is_active": True}
    assert client.put(f"/api/v1/eligibility/{item_id}", json=update).status_code == 200
    assert client.delete(f"/api/v1/eligibility/{item_id}").status_code == 204


def test_pod_membership_and_lead_validation(client):
    duplicate = client.post("/api/v1/pods", json={"pod_name": "Operations Pod 1"})
    assert duplicate.status_code == 409
    invalid_members = client.put("/api/v1/pods/POD01/employees", json={"employee_ids": ["E001", "missing"]})
    assert invalid_members.status_code == 400
    assert client.get("/api/v1/employees/E001").json()["data"]["pod_id"] == "POD01"
    assert client.patch("/api/v1/employees/E032/status", json={"is_active": False}).status_code == 200
    assert client.patch("/api/v1/pods/POD01/lead", json={"pod_lead_id": "E032"}).status_code == 400


def test_pod_create_update_and_safe_deactivation(client):
    pod = client.post("/api/v1/pods", json={"pod_name": "New Team", "pod_lead_id": "E031"})
    assert pod.status_code == 201
    pod_id = pod.json()["data"]["id"]
    update = {"pod_name": "Renamed Team", "pod_lead_id": "E031", "is_active": True, "description": "Updated"}
    assert client.put(f"/api/v1/pods/{pod_id}", json=update).status_code == 200
    assert client.delete("/api/v1/pods/POD01").status_code == 200
    assert client.get("/api/v1/pods/POD01").json()["data"]["is_active"] is False
    assert client.delete(f"/api/v1/pods/{pod_id}").status_code == 204


def test_brands_processes_rules_and_status(client):
    assert client.patch("/api/v1/brands/B001/status", json={"is_active": False}).status_code == 200
    assert client.patch("/api/v1/processes/PR001/status", json={"is_active": False}).status_code == 200
    duplicate = client.post("/api/v1/operating-rules", json={"brand_id": "B001", "process_id": "PR001", "operating_days": ["Monday"], "public_holiday_policy": "operate", "minimum_staffing": 1})
    assert duplicate.status_code == 409
    invalid = client.post("/api/v1/operating-rules", json={"brand_id": "B001", "process_id": "PR002", "operating_days": ["Funday"], "public_holiday_policy": "open", "minimum_staffing": -1})
    assert invalid.status_code == 422


def test_time_off_approval_filtering_and_delete(client):
    created = client.post("/api/v1/time-off", json={"employee_id": "E001", "time_off_type": "comp_off", "start_date": "2026-12-18", "end_date": "2026-12-18"})
    item_id = created.json()["data"]["id"]
    assert created.json()["data"]["status"] == "pending"
    approved = client.patch(f"/api/v1/time-off/{item_id}/approve", params={"approved_by": "manager-1"})
    assert approved.json()["data"]["status"] == "approved"
    assert approved.json()["data"]["approved_by"] == "manager-1"
    assert client.get("/api/v1/time-off", params={"employee_id": "E001", "status": "approved"}).json()["total"] == 1
    assert client.delete(f"/api/v1/time-off/{item_id}").status_code == 204
    rejected = client.post("/api/v1/time-off", json={"employee_id": "E001", "time_off_type": "planned_leave", "start_date": "2026-12-20", "end_date": "2026-12-20"}).json()["data"]
    assert client.patch(f"/api/v1/time-off/{rejected['id']}/reject").json()["data"]["status"] == "rejected"


def test_brand_process_and_holiday_crud(client):
    brand = client.post("/api/v1/brands", json={"brand_name": "Test Brand"})
    assert brand.status_code == 201
    assert client.put(f"/api/v1/brands/{brand.json()['data']['id']}", json={"brand_name": "Renamed Brand", "is_active": True}).status_code == 200
    process = client.post("/api/v1/processes", json={"process_name": "Quality"})
    assert process.status_code == 201
    rule = client.post("/api/v1/operating-rules", json={"brand_id": brand.json()["data"]["id"], "process_id": process.json()["data"]["id"], "operating_days": ["Monday"], "public_holiday_policy": "closed", "minimum_staffing": 0, "coverage_overrides": [{"date": "2026-12-01", "minimum_staffing": 2}]})
    assert rule.status_code == 201
    assert client.get("/api/v1/operating-rules").json()["data"][-1]["brand_name"] == "Renamed Brand"
    assert client.delete(f"/api/v1/operating-rules/{rule.json()['data']['id']}").status_code == 204


def test_holiday_filter_update_and_delete(client):
    holiday = client.get("/api/v1/public-holidays", params={"year": 2026}).json()["data"][0]
    changed = client.put(f"/api/v1/public-holidays/{holiday['id']}", json={"holiday_name": "Year End", "holiday_date": "2026-12-25"})
    assert changed.status_code == 200 and changed.json()["data"]["holiday_name"] == "Year End"
    assert client.delete(f"/api/v1/public-holidays/{holiday['id']}").status_code == 204


def test_unexpected_error_is_safe(client):
    client.app.add_api_route("/boom", lambda: (_ for _ in ()).throw(RuntimeError("private detail")))
    from fastapi.testclient import TestClient
    response = TestClient(client.app, raise_server_exceptions=False).get("/boom")
    assert response.status_code == 500
    assert response.json()["error"]["code"] == "INTERNAL_SERVER_ERROR"
    assert "private detail" not in response.text


from app.repositories.memory import InMemoryRepository
