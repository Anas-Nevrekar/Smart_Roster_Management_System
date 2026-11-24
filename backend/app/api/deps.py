from fastapi import Request
from app.repositories.contracts import MasterDataRepository
from app.services.master_data import MasterDataService


def get_repository(request: Request) -> MasterDataRepository:
    return request.app.state.repository


def get_service(request: Request) -> MasterDataService:
    return MasterDataService(get_repository(request))
