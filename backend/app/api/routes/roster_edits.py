from fastapi import APIRouter, Depends, Header

from app.api.deps import get_repository
from app.core.errors import ServiceError
from app.repositories.contracts import MasterDataRepository
from app.schemas.roster_changes import (
    AssignmentCreate, AssignmentPatch, ChangeImpactRequest, ChangeImpactResponse,
)
from app.services.roster_changes import RosterChangeService

router = APIRouter(tags=["Roster Editing"])


def _version(if_match: str | None) -> int:
    if if_match is None:
        raise ServiceError(428, "ROSTER_VERSION_REQUIRED", "Send the current roster version in the If-Match header.")
    try:
        return int(if_match.strip().strip('"'))
    except ValueError as exc:
        raise ServiceError(400, "INVALID_ROSTER_VERSION", "If-Match must contain the integer roster version.") from exc


@router.post("/rosters/{roster_id}/assignments", summary="Add a working roster assignment")
def add_assignment(
    roster_id: str,
    payload: AssignmentCreate,
    if_match: str | None = Header(None, alias="If-Match"),
    repository: MasterDataRepository = Depends(get_repository),
):
    return RosterChangeService(repository).add_assignment(roster_id, _version(if_match), payload)


@router.patch("/rosters/{roster_id}/assignments/{assignment_id}", summary="Update a working roster assignment")
def update_assignment(
    roster_id: str,
    assignment_id: str,
    payload: AssignmentPatch,
    if_match: str | None = Header(None, alias="If-Match"),
    repository: MasterDataRepository = Depends(get_repository),
):
    return RosterChangeService(repository).update_assignment(roster_id, assignment_id, _version(if_match), payload)


@router.delete("/rosters/{roster_id}/assignments/{assignment_id}", summary="Delete a working roster assignment")
def delete_assignment(
    roster_id: str,
    assignment_id: str,
    if_match: str | None = Header(None, alias="If-Match"),
    repository: MasterDataRepository = Depends(get_repository),
):
    return RosterChangeService(repository).delete_assignment(roster_id, assignment_id, _version(if_match))


@router.post("/rosters/{roster_id}/check-impact", response_model=ChangeImpactResponse, summary="Preview a master-data change against a saved roster")
def check_impact(
    roster_id: str,
    payload: ChangeImpactRequest,
    repository: MasterDataRepository = Depends(get_repository),
):
    return RosterChangeService(repository).check_impact(roster_id, payload)
