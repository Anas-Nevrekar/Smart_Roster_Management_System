from fastapi import APIRouter
from app.api.routes.health import router as health_router
from app.api.routes.master import router as master_router
from app.api.routes.rosters import router as roster_router
from app.api.routes.roster_edits import router as roster_edits_router

router = APIRouter()
router.include_router(health_router)
router.include_router(master_router)
router.include_router(roster_router)
router.include_router(roster_edits_router)
