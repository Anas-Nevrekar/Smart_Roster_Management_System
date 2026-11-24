from datetime import date
from typing import Any, Literal

from fastapi import APIRouter, Depends, Header, Query

from app.api.deps import get_repository
from app.repositories.contracts import MasterDataRepository
from app.schemas.rosters import (
    CoverageResponse, GenerateRosterRequest, GenerateRosterResponse,
    PublishRosterRequest, RosterAssignmentsResponse, RosterListResponse,
    RosterResponse, ValidateRosterResponse,
)
from app.services.roster_management import RosterManagementService

router = APIRouter(tags=["Rosters"])


def _expected_version(if_match: str | None) -> int | None:
    from app.core.errors import ServiceError
    if if_match is None:
        return None
    try:
        return int(if_match.strip().strip('"'))
    except ValueError as exc:
        raise ServiceError(400, "INVALID_ROSTER_VERSION", "If-Match must contain the integer roster version.") from exc


@router.post("/rosters/generate", response_model=GenerateRosterResponse, summary="Generate and save a monthly draft roster", status_code=200)
def generate_roster(payload: GenerateRosterRequest, repository: MasterDataRepository = Depends(get_repository)):
    return RosterManagementService(repository).generate_and_save(payload.month, payload.year, payload.generated_by)


@router.post("/rosters/{roster_id}/regenerate", response_model=GenerateRosterResponse, summary="Safely regenerate an existing draft roster")
def regenerate_roster(roster_id: str, if_match: str | None = Header(None, alias="If-Match"), repository: MasterDataRepository = Depends(get_repository)):
    return RosterManagementService(repository).regenerate(roster_id, _expected_version(if_match))


@router.get("/rosters", response_model=RosterListResponse, summary="List saved rosters")
def list_rosters(
    month: int | None = Query(None, ge=1, le=12),
    year: int | None = Query(None, ge=2000, le=2100),
    roster_status: Literal["draft", "published"] | None = Query(None, alias="status"),
    repository: MasterDataRepository = Depends(get_repository),
):
    rows = RosterManagementService(repository).list_rosters(month, year, roster_status)
    return {"success": True, "data": rows, "total": len(rows)}


@router.get("/rosters/{roster_id}", response_model=RosterResponse, summary="Get saved roster details")
def get_roster(roster_id: str, repository: MasterDataRepository = Depends(get_repository)):
    return {"success": True, "data": RosterManagementService(repository).get_roster(roster_id)}


@router.get("/rosters/{roster_id}/assignments", response_model=RosterAssignmentsResponse, summary="List roster assignments")
def get_assignments(
    roster_id: str,
    employee_id: str | None = None,
    brand_id: str | None = None,
    process_id: str | None = None,
    pod_id: str | None = None,
    start_date: date | None = None,
    end_date: date | None = None,
    assignment_status: Literal["working", "weekly_off"] | None = Query(None, alias="status"),
    repository: MasterDataRepository = Depends(get_repository),
):
    filters = {"employee_id": employee_id, "brand_id": brand_id, "process_id": process_id,
               "pod_id": pod_id, "start_date": start_date, "end_date": end_date, "status": assignment_status}
    rows = RosterManagementService(repository).assignments(roster_id, filters)
    return {"success": True, "data": rows, "total": len(rows)}


@router.get("/rosters/{roster_id}/weekly-offs", response_model=RosterAssignmentsResponse, summary="List roster weekly offs")
def get_weekly_offs(
    roster_id: str,
    employee_id: str | None = None,
    pod_id: str | None = None,
    start_date: date | None = None,
    end_date: date | None = None,
    repository: MasterDataRepository = Depends(get_repository),
):
    rows = RosterManagementService(repository).weekly_offs(roster_id, employee_id, pod_id, start_date, end_date)
    return {"success": True, "data": rows, "total": len(rows)}


@router.get("/rosters/{roster_id}/coverage", response_model=CoverageResponse, summary="Calculate roster staffing coverage")
def get_coverage(roster_id: str, repository: MasterDataRepository = Depends(get_repository)):
    result = RosterManagementService(repository).coverage(roster_id)
    return {"success": True, **result}


def _view(view_name: str, roster_id: str, repository: MasterDataRepository):
    return {"success": True, "data": RosterManagementService(repository).view(roster_id, view_name)}


@router.get("/rosters/{roster_id}/views/company", summary="Get company-wide roster view")
def company_view(roster_id: str, repository: MasterDataRepository = Depends(get_repository)):
    return _view("company", roster_id, repository)


@router.get("/rosters/{roster_id}/views/pod", summary="Get pod-wise roster view")
def pod_view(roster_id: str, repository: MasterDataRepository = Depends(get_repository)):
    return _view("pod", roster_id, repository)


@router.get("/rosters/{roster_id}/views/brand", summary="Get brand-wise roster view")
def brand_view(roster_id: str, repository: MasterDataRepository = Depends(get_repository)):
    return _view("brand", roster_id, repository)


@router.get("/rosters/{roster_id}/views/process", summary="Get process-wise roster view")
def process_view(roster_id: str, repository: MasterDataRepository = Depends(get_repository)):
    return _view("process", roster_id, repository)


@router.get("/rosters/{roster_id}/views/employee", summary="Get employee-wise roster view")
def employee_view(roster_id: str, repository: MasterDataRepository = Depends(get_repository)):
    return _view("employee", roster_id, repository)


@router.post("/rosters/{roster_id}/validate", response_model=ValidateRosterResponse, summary="Validate a saved roster")
def validate_roster(roster_id: str, repository: MasterDataRepository = Depends(get_repository)):
    return RosterManagementService(repository).validate(roster_id)


@router.post("/rosters/{roster_id}/publish", response_model=RosterResponse, summary="Validate and publish a roster")
def publish_roster(roster_id: str, payload: PublishRosterRequest | None = None, repository: MasterDataRepository = Depends(get_repository)):
    updated = RosterManagementService(repository).publish(roster_id, payload.published_by if payload else None)
    return {"success": True, "data": updated}
