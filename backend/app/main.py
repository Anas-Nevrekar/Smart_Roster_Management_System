from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.router import router
from app.core.config import Settings, get_settings
from app.core.database import DatabaseConnectionManager
from app.core.errors import ServiceError, http_error_handler, service_error_handler, unexpected_error_handler, validation_error_handler
from app.repositories.contracts import MasterDataRepository
from app.repositories.memory import InMemoryRepository
from app.repositories.mongodb import MongoRepository


def create_app(settings: Settings | None = None, repository: MasterDataRepository | None = None) -> FastAPI:
    settings = settings or get_settings()
    manager = None
    owns_manager = False
    if repository is not None:
        selected_repository = repository
        if isinstance(repository, MongoRepository):
            manager = repository.manager
            selected_backend = "mongodb"
        else:
            selected_backend = "injected"
    elif settings.storage_backend == "memory":
        selected_repository = InMemoryRepository()
        selected_backend = "memory"
    else:
        manager = DatabaseConnectionManager(settings.mongodb_uri, settings.mongodb_database)
        owns_manager = True
        selected_repository = MongoRepository(manager)
        selected_backend = "mongodb"

    @asynccontextmanager
    async def lifespan(application: FastAPI):
        if manager is not None:
            # Keep the API process alive in a degraded state so /ready can explain
            # connectivity failures. Requests never fall back to process memory.
            manager.connect()
        try:
            yield
        finally:
            if manager is not None and owns_manager:
                manager.close()

    application = FastAPI(
        title=settings.app_name,
        version=settings.app_version,
        description="Backend API for managing employees, brands, processes, pods, availability, operating rules, and monthly rosters.",
        docs_url="/docs" if settings.environment != "production" else None,
        redoc_url="/redoc" if settings.environment != "production" else None,
        openapi_url="/openapi.json" if settings.environment != "production" else None,
        debug=settings.debug,
        lifespan=lifespan,
    )
    application.state.settings = settings
    application.state.repository = selected_repository
    application.state.storage_backend = selected_backend
    if manager is not None:
        application.state.database_manager = manager
    application.add_middleware(
        CORSMiddleware,
        allow_origins=settings.allowed_frontend_origins,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
        allow_headers=["Authorization", "Content-Type", "If-Match"],
    )
    application.add_exception_handler(ServiceError, service_error_handler)
    application.add_exception_handler(StarletteHTTPException, http_error_handler)
    application.add_exception_handler(RequestValidationError, validation_error_handler)
    application.add_exception_handler(Exception, unexpected_error_handler)
    application.include_router(router, prefix=settings.api_prefix)
    return application


from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException

app = create_app()
