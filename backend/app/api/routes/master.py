from datetime import date
from typing import Any

from fastapi import APIRouter, Depends, Query, Response, status

from app.api.deps import get_repository, get_service
from app.core.errors import ServiceError
from app.repositories.contracts import MasterDataRepository
from app.services.master_data import MasterDataService
from app.schemas.entities import (
    AvailabilityUpdate, BrandCreate, BrandUpdate, EmployeeCreate, EmployeeStatus,
    EmployeeUpdate, EligibilityCreate, EligibilityReplacement, EligibilityUpdate,
    Membership, OperatingRuleCreate, OperatingRuleUpdate, PodCreate, PodLead,
    PodUpdate, ProcessCreate, ProcessUpdate, PublicHolidayCreate,
    PublicHolidayUpdate, TimeOffCreate, TimeOffUpdate,
)

router = APIRouter(tags=["Employees", "Pods", "Brands", "Processes", "Eligibility", "Operating Rules", "Time Off", "Public Holidays"])


def envelope(data: Any):
    return {"success": True, "data": data}


def list_response(data: list[Any]):
    return {"success": True, "data": data, "total": len(data)}


def dump(model):
    return model.model_dump(mode="json")


# List endpoints with explicit query parameters keep the OpenAPI contract clear.
@router.get("/employees", summary="List employees", tags=["Employees"])
def employees(pod_id: str | None = None, is_active: bool | None = None, search: str | None = None, service: MasterDataService = Depends(get_service)):
    return list_response(service.list("employees", {"pod_id": pod_id, "is_active": is_active, "search": search}))

@router.post("/employees", status_code=201, summary="Create employee", tags=["Employees"])
def employee_create(payload: EmployeeCreate, service: MasterDataService = Depends(get_service)):
    return envelope(service.create("employees", dump(payload)))

@router.get("/employees/{entity_id}", summary="Get employee", tags=["Employees"])
def employee_get(entity_id: str, service: MasterDataService = Depends(get_service)):
    return envelope(service.get("employees", entity_id))

@router.put("/employees/{entity_id}", summary="Replace employee", tags=["Employees"])
def employee_update(entity_id: str, payload: EmployeeUpdate, service: MasterDataService = Depends(get_service)):
    return envelope(service.update("employees", entity_id, dump(payload)))

@router.patch("/employees/{entity_id}/status", summary="Activate or deactivate employee", tags=["Employees"])
def employee_status(entity_id: str, payload: EmployeeStatus, service: MasterDataService = Depends(get_service)):
    return envelope(service.update("employees", entity_id, dump(payload)))

@router.get("/employees/{entity_id}/eligibility", summary="Get employee eligibility", tags=["Employees"])
def employee_eligibility(entity_id: str, service: MasterDataService = Depends(get_service), repo: MasterDataRepository = Depends(get_repository)):
    service.get("employees", entity_id)
    return list_response([x for x in repo.list("eligibility") if x["employee_id"] == entity_id])

@router.put("/employees/{entity_id}/eligibility", summary="Replace employee eligibility", tags=["Employees"])
def replace_employee_eligibility(entity_id: str, payload: EligibilityReplacement, service: MasterDataService = Depends(get_service), repo: MasterDataRepository = Depends(get_repository)):
    service.get("employees", entity_id)
    items = [dump(x) for x in payload.items]
    combos = [(x["brand_id"], x["process_id"]) for x in items]
    if len(combos) != len(set(combos)):
        raise ServiceError(409, "DUPLICATE_ELIGIBILITY", "Eligibility combinations must be unique.")
    for item in items:
        for field, collection in (("brand_id", "brands"), ("process_id", "processes")):
            if repo.get(collection, item[field]) is None:
                code = "INVALID_BRAND_REFERENCE" if collection == "brands" else "INVALID_PROCESS_REFERENCE"
                raise ServiceError(400, code, f"The referenced {collection[:-1]} does not exist.")
    result = repo.replace_employee_eligibility(entity_id, items)
    return list_response(result)

@router.get("/employees/{entity_id}/availability", summary="Get employee availability and time off", tags=["Employees"])
def employee_availability(entity_id: str, service: MasterDataService = Depends(get_service), repo: MasterDataRepository = Depends(get_repository)):
    emp = service.get("employees", entity_id)
    return envelope({"workable_days": emp["workable_days"], "weekly_off_per_week": emp["weekly_off_per_week"], "time_off": [x for x in repo.list("time_off") if x["employee_id"] == entity_id]})

@router.put("/employees/{entity_id}/availability", summary="Update employee availability", tags=["Employees"])
def update_employee_availability(entity_id: str, payload: AvailabilityUpdate, service: MasterDataService = Depends(get_service)):
    service.get("employees", entity_id)
    return envelope(service.update("employees", entity_id, dump(payload)))


@router.get("/pods", summary="List pods", tags=["Pods"])
def pods(service: MasterDataService = Depends(get_service)):
    return list_response(service.list("pods"))

@router.post("/pods", status_code=201, summary="Create pod", tags=["Pods"])
def pod_create(payload: PodCreate, service: MasterDataService = Depends(get_service)):
    return envelope(service.create("pods", dump(payload)))

@router.get("/pods/{entity_id}", summary="Get pod", tags=["Pods"])
def pod_get(entity_id: str, service: MasterDataService = Depends(get_service)):
    return envelope(service.get("pods", entity_id))

@router.put("/pods/{entity_id}", summary="Replace pod", tags=["Pods"])
def pod_update(entity_id: str, payload: PodUpdate, service: MasterDataService = Depends(get_service)):
    return envelope(service.update("pods", entity_id, dump(payload)))

@router.patch("/pods/{entity_id}/lead", summary="Set pod lead", tags=["Pods"])
def pod_lead(entity_id: str, payload: PodLead, service: MasterDataService = Depends(get_service)):
    return envelope(service.update("pods", entity_id, dump(payload)))

@router.get("/pods/{entity_id}/employees", summary="List pod employees", tags=["Pods"])
def pod_employees(entity_id: str, service: MasterDataService = Depends(get_service), repo: MasterDataRepository = Depends(get_repository)):
    service.get("pods", entity_id)
    return list_response([x for x in repo.list("employees") if x.get("pod_id") == entity_id])

@router.put("/pods/{entity_id}/employees", summary="Replace pod membership", tags=["Pods"])
def pod_membership(entity_id: str, payload: Membership, service: MasterDataService = Depends(get_service), repo: MasterDataRepository = Depends(get_repository)):
    service.get("pods", entity_id)
    if len(payload.employee_ids) != len(set(payload.employee_ids)):
        raise ServiceError(409, "DUPLICATE_MEMBERSHIP", "Employee IDs must be unique.")
    all_employees = {x["id"]: x for x in repo.list("employees")}
    missing = [x for x in payload.employee_ids if x not in all_employees]
    if missing:
        raise ServiceError(400, "INVALID_EMPLOYEE_REFERENCE", "One or more employees do not exist.")
    conflicts = [x for x in payload.employee_ids if all_employees[x].get("pod_id") not in (None, entity_id)]
    if conflicts:
        raise ServiceError(409, "EMPLOYEE_ALREADY_ASSIGNED", "An employee already belongs to another pod.")
    updated = {item["id"]: item for item in repo.set_pod_membership(entity_id, payload.employee_ids)}
    return list_response([updated[x] for x in payload.employee_ids])

@router.delete("/pods/{entity_id}", summary="Delete or deactivate pod", tags=["Pods"])
def pod_delete(entity_id: str, service: MasterDataService = Depends(get_service)):
    deleted = service.delete("pods", entity_id)
    if not deleted:
        return envelope({"id": entity_id, "is_active": False})
    return Response(status_code=204)


def register_simple(entity: str, path: str, create_model, update_model, tag: str):
    def list_items(service: MasterDataService = Depends(get_service)):
        return list_response(service.list(entity))
    list_items.__name__ = f"list_{entity}"
    create_name = f"create_{entity[:-1]}"
    get_name = f"get_{entity[:-1]}"
    update_name = f"update_{entity[:-1]}"
    router.get(path, summary=f"List {tag.lower()}", tags=[tag])(list_items)

    @router.post(path, status_code=201, summary=f"Create {tag.lower()[:-1]}", tags=[tag])
    def create_item(payload: create_model, service: MasterDataService = Depends(get_service)):
        return envelope(service.create(entity, dump(payload)))
    create_item.__name__ = create_name
    @router.get(path + "/{entity_id}", summary=f"Get {tag.lower()[:-1]}", tags=[tag])
    def get_item(entity_id: str, service: MasterDataService = Depends(get_service)):
        return envelope(service.get(entity, entity_id))
    get_item.__name__ = get_name
    @router.put(path + "/{entity_id}", summary=f"Replace {tag.lower()[:-1]}", tags=[tag])
    def update_item(entity_id: str, payload: update_model, service: MasterDataService = Depends(get_service)):
        return envelope(service.update(entity, entity_id, dump(payload)))
    update_item.__name__ = update_name

register_simple("brands", "/brands", BrandCreate, BrandUpdate, "Brands")
register_simple("processes", "/processes", ProcessCreate, ProcessUpdate, "Processes")

@router.patch("/brands/{entity_id}/status", summary="Activate or deactivate brand", tags=["Brands"])
def brand_status(entity_id: str, payload: EmployeeStatus, service: MasterDataService = Depends(get_service)):
    return envelope(service.update("brands", entity_id, dump(payload)))

@router.get("/brands/{entity_id}/employees", summary="List eligible brand employees", tags=["Brands"])
def brand_employees(entity_id: str, service: MasterDataService = Depends(get_service), repo: MasterDataRepository = Depends(get_repository)):
    service.get("brands", entity_id)
    employee_ids = {x["employee_id"] for x in repo.list("eligibility") if x["brand_id"] == entity_id and x.get("is_active", True)}
    return list_response([x for x in repo.list("employees") if x["id"] in employee_ids])

@router.get("/brands/{entity_id}/processes", summary="List processes configured for brand", tags=["Brands"])
def brand_processes(entity_id: str, service: MasterDataService = Depends(get_service), repo: MasterDataRepository = Depends(get_repository)):
    service.get("brands", entity_id)
    process_ids = {x["process_id"] for x in repo.list("operating_rules") if x["brand_id"] == entity_id}
    return list_response([x for x in repo.list("processes") if x["id"] in process_ids])

@router.patch("/processes/{entity_id}/status", summary="Activate or deactivate process", tags=["Processes"])
def process_status(entity_id: str, payload: EmployeeStatus, service: MasterDataService = Depends(get_service)):
    return envelope(service.update("processes", entity_id, dump(payload)))


@router.get("/eligibility", summary="List eligibility records", tags=["Eligibility"])
def eligibility(service: MasterDataService = Depends(get_service), employee_id: str | None = None, brand_id: str | None = None, process_id: str | None = None):
    return list_response(service.list("eligibility", {"employee_id": employee_id, "brand_id": brand_id, "process_id": process_id}))

@router.post("/eligibility", status_code=201, summary="Create eligibility record", tags=["Eligibility"])
def eligibility_create(payload: EligibilityCreate, service: MasterDataService = Depends(get_service)):
    return envelope(service.create("eligibility", dump(payload)))

@router.put("/eligibility/{entity_id}", summary="Replace eligibility record", tags=["Eligibility"])
def eligibility_update(entity_id: str, payload: EligibilityUpdate, service: MasterDataService = Depends(get_service)):
    return envelope(service.update("eligibility", entity_id, dump(payload)))

@router.delete("/eligibility/{entity_id}", status_code=204, summary="Delete eligibility record", tags=["Eligibility"])
def eligibility_delete(entity_id: str, service: MasterDataService = Depends(get_service)):
    service.delete("eligibility", entity_id)
    return Response(status_code=204)

@router.get("/brands/{brand_id}/eligibility", summary="List eligibility for brand", tags=["Eligibility"])
def brand_eligibility(brand_id: str, service: MasterDataService = Depends(get_service), repo: MasterDataRepository = Depends(get_repository)):
    service.get("brands", brand_id)
    return list_response([x for x in repo.list("eligibility") if x["brand_id"] == brand_id])


@router.get("/operating-rules", summary="List operating rules", tags=["Operating Rules"])
def rules(service: MasterDataService = Depends(get_service), repo: MasterDataRepository = Depends(get_repository)):
    rows = service.list("operating_rules")
    brands = {x["id"]: x["brand_name"] for x in repo.list("brands")}
    processes = {x["id"]: x["process_name"] for x in repo.list("processes")}
    return list_response([{**x, "brand_name": brands.get(x["brand_id"]), "process_name": processes.get(x["process_id"])} for x in rows])

@router.post("/operating-rules", status_code=201, summary="Create operating rule", tags=["Operating Rules"])
def rule_create(payload: OperatingRuleCreate, service: MasterDataService = Depends(get_service)):
    return envelope(service.create("operating_rules", dump(payload)))

@router.get("/operating-rules/{entity_id}", summary="Get operating rule", tags=["Operating Rules"])
def rule_get(entity_id: str, service: MasterDataService = Depends(get_service)):
    return envelope(service.get("operating_rules", entity_id))

@router.put("/operating-rules/{entity_id}", summary="Replace operating rule", tags=["Operating Rules"])
def rule_update(entity_id: str, payload: OperatingRuleUpdate, service: MasterDataService = Depends(get_service)):
    return envelope(service.update("operating_rules", entity_id, dump(payload)))

@router.delete("/operating-rules/{entity_id}", summary="Delete operating rule", tags=["Operating Rules"])
def rule_delete(entity_id: str, service: MasterDataService = Depends(get_service)):
    service.delete("operating_rules", entity_id)
    return Response(status_code=204)


@router.get("/time-off", summary="List time-off requests", tags=["Time Off"])
def time_off(service: MasterDataService = Depends(get_service), employee_id: str | None = None, status_filter: str | None = Query(None, alias="status"), time_off_type: str | None = None, start_date: date | None = None, end_date: date | None = None):
    return list_response(service.list("time_off", {"employee_id": employee_id, "status": status_filter, "time_off_type": time_off_type, "start_date": start_date, "end_date": end_date}))

@router.post("/time-off", status_code=201, summary="Create time-off request", tags=["Time Off"])
def time_off_create(payload: TimeOffCreate, service: MasterDataService = Depends(get_service)):
    return envelope(service.create("time_off", dump(payload)))

@router.get("/time-off/{entity_id}", summary="Get time-off request", tags=["Time Off"])
def time_off_get(entity_id: str, service: MasterDataService = Depends(get_service)):
    return envelope(service.get("time_off", entity_id))

@router.put("/time-off/{entity_id}", summary="Replace time-off request", tags=["Time Off"])
def time_off_update(entity_id: str, payload: TimeOffUpdate, service: MasterDataService = Depends(get_service)):
    return envelope(service.update("time_off", entity_id, dump(payload)))

def decide_time_off(entity_id: str, decision: str, approved_by: str | None, service: MasterDataService):
    item = service.get("time_off", entity_id)
    values = {**item, "status": decision}
    if decision == "approved" and approved_by is not None:
        values["approved_by"] = approved_by
    return envelope(service.update("time_off", entity_id, values))

@router.patch("/time-off/{entity_id}/approve", summary="Approve time-off request", tags=["Time Off"])
def time_off_approve(entity_id: str, service: MasterDataService = Depends(get_service), approved_by: str | None = None):
    return decide_time_off(entity_id, "approved", approved_by, service)

@router.patch("/time-off/{entity_id}/reject", summary="Reject time-off request", tags=["Time Off"])
def time_off_reject(entity_id: str, service: MasterDataService = Depends(get_service)):
    return decide_time_off(entity_id, "rejected", None, service)

@router.delete("/time-off/{entity_id}", status_code=204, summary="Delete time-off request", tags=["Time Off"])
def time_off_delete(entity_id: str, service: MasterDataService = Depends(get_service)):
    service.delete("time_off", entity_id)
    return Response(status_code=204)


@router.get("/public-holidays", summary="List public holidays", tags=["Public Holidays"])
def holidays(year: int | None = None, service: MasterDataService = Depends(get_service)):
    return list_response(service.list("public_holidays", {"year": year}))

@router.post("/public-holidays", status_code=201, summary="Create public holiday", tags=["Public Holidays"])
def holiday_create(payload: PublicHolidayCreate, service: MasterDataService = Depends(get_service)):
    return envelope(service.create("public_holidays", dump(payload)))

@router.get("/public-holidays/{entity_id}", summary="Get public holiday", tags=["Public Holidays"])
def holiday_get(entity_id: str, service: MasterDataService = Depends(get_service)):
    return envelope(service.get("public_holidays", entity_id))

@router.put("/public-holidays/{entity_id}", summary="Replace public holiday", tags=["Public Holidays"])
def holiday_update(entity_id: str, payload: PublicHolidayUpdate, service: MasterDataService = Depends(get_service)):
    return envelope(service.update("public_holidays", entity_id, dump(payload)))

@router.delete("/public-holidays/{entity_id}", status_code=204, summary="Delete public holiday", tags=["Public Holidays"])
def holiday_delete(entity_id: str, service: MasterDataService = Depends(get_service)):
    service.delete("public_holidays", entity_id)
    return Response(status_code=204)
