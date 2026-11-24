from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

router = APIRouter(tags=["Health"])


@router.get("/health", summary="Check application health")
def health(request: Request):
    settings = request.app.state.settings
    return {"success": True, "data": {"status": "ok", "application": settings.app_name, "version": settings.app_version}}


@router.get("/ready", summary="Check application readiness", description="Checks the configured persistent database when MongoDB storage is enabled.")
def ready(request: Request):
    if request.app.state.storage_backend == "mongodb":
        manager = request.app.state.database_manager
        ready, _reason = manager.check_ready()
        if not ready:
            return JSONResponse(status_code=503, content={
                "success": False,
                "error": {"code": "DATABASE_UNAVAILABLE", "message": "MongoDB is not ready. Check MONGODB_URI, Atlas network access, and database user permissions."},
                "data": {"status": "not_ready", "external_persistence": True, "database": "unavailable"},
            })
        return {"success": True, "data": {"status": "ready", "external_persistence": True, "database": "connected"}}
    return {"success": True, "data": {"status": "ready", "external_persistence": False}}
