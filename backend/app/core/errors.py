from fastapi import Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from fastapi.encoders import jsonable_encoder
from starlette.exceptions import HTTPException as StarletteHTTPException
import logging

logger = logging.getLogger(__name__)


class ServiceError(Exception):
    def __init__(self, status_code: int, code: str, message: str, details=None):
        self.status_code, self.code, self.message = status_code, code, message
        self.details = details


async def service_error_handler(request: Request, exc: ServiceError):
    error = {"code": exc.code, "message": exc.message}
    if exc.details is not None:
        error["details"] = jsonable_encoder(exc.details)
    return JSONResponse(status_code=exc.status_code, content={"success": False, "error": error})


async def http_error_handler(request: Request, exc: StarletteHTTPException):
    code = "RESOURCE_NOT_FOUND" if exc.status_code == 404 else "HTTP_ERROR"
    message = exc.detail if isinstance(exc.detail, str) else "The request could not be completed."
    return JSONResponse(status_code=exc.status_code, content={"success": False, "error": {"code": code, "message": message}})


async def validation_error_handler(request: Request, exc: RequestValidationError):
    return JSONResponse(status_code=422, content=jsonable_encoder({"success": False, "error": {"code": "VALIDATION_ERROR", "message": "Request validation failed.", "details": exc.errors()}}))


async def unexpected_error_handler(request: Request, exc: Exception):
    logger.exception("Unhandled API error", exc_info=exc)
    return JSONResponse(status_code=500, content={"success": False, "error": {"code": "INTERNAL_SERVER_ERROR", "message": "An unexpected server error occurred."}})
