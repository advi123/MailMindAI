"""
MailMind AI - Centralized Exception Handling.

Architectural Decision Rationale:
---------------------------------
1. Decoupled Domain Errors: Domain services should throw custom domain exceptions (e.g. AppValidationError)
   rather than importing HTTP or FastAPI constructs. This keeps business logic independent of the web transport layer.
2. Predictable API Contract: Centralized exception handlers catch both custom domain exceptions and unhandled
   system errors, translating them into a uniform JSON response payload schema:
   {
       "error": {
           "code": "ERROR_CODE",
           "message": "Human-readable description",
           "timestamp": "2026-07-23T20:30:00Z"
       }
   }
3. Security & Safety: Unhandled server errors (500) log details internally via structured logging,
   while masking sensitive stack traces in production API responses to prevent information leakage.
"""

from datetime import datetime, timezone
from typing import Any

from fastapi import Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from app.core.logging import get_logger

logger = get_logger("app.exceptions")

# HTTP 422 Unprocessable Content Status Code
HTTP_422_UNPROCESSABLE_CONTENT = getattr(status, "HTTP_422_UNPROCESSABLE_CONTENT", 422)


class BaseAppException(Exception):
    """
    Abstract base exception for all custom MailMind AI backend errors.
    """

    def __init__(
        self,
        message: str,
        code: str = "INTERNAL_SERVER_ERROR",
        status_code: int = status.HTTP_500_INTERNAL_SERVER_ERROR,
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(message)
        self.message = message
        self.code = code
        self.status_code = status_code
        self.details = details or {}


class NotFoundError(BaseAppException):
    """Raised when a requested resource is not found."""

    def __init__(
        self,
        message: str = "Requested resource not found",
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(
            message=message,
            code="RESOURCE_NOT_FOUND",
            status_code=status.HTTP_404_NOT_FOUND,
            details=details,
        )


class ServiceUnavailableError(BaseAppException):
    """Raised when an external or internal core service is unready or unreachable."""

    def __init__(
        self,
        message: str = "Service temporarily unavailable",
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(
            message=message,
            code="SERVICE_UNAVAILABLE",
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            details=details,
        )


class AppValidationError(BaseAppException):
    """Raised when input validation fails in business logic."""

    def __init__(
        self,
        message: str = "Invalid input parameter",
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(
            message=message,
            code="VALIDATION_ERROR",
            status_code=HTTP_422_UNPROCESSABLE_CONTENT,
            details=details,
        )


# ============================================================================
# Centralized FastAPI Exception Handlers
# ============================================================================


def create_error_response(
    status_code: int, code: str, message: str, details: dict[str, Any] | None = None
) -> JSONResponse:
    """Helper to build standardized JSON error payload."""
    content = {
        "error": {
            "code": code,
            "message": message,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
    }
    if details:
        content["error"]["details"] = details
    return JSONResponse(status_code=status_code, content=content)


async def app_exception_handler(
    request: Request, exc: BaseAppException
) -> JSONResponse:
    """Handles all custom BaseAppException subclasses."""
    logger.warning(
        f"Domain exception caught: {exc.code} - {exc.message} on path {request.url.path}"
    )
    return create_error_response(
        status_code=exc.status_code,
        code=exc.code,
        message=exc.message,
        details=exc.details,
    )


async def validation_exception_handler(
    request: Request, exc: RequestValidationError
) -> JSONResponse:
    """Handles FastAPI Pydantic request body/query validation errors."""
    logger.warning(f"Validation error on path {request.url.path}: {exc.errors()}")
    return create_error_response(
        status_code=HTTP_422_UNPROCESSABLE_CONTENT,
        code="VALIDATION_ERROR",
        message="Request payload or parameter validation failed",
        details={"errors": exc.errors()},
    )


async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """Fallback handler for unhandled unexpected exceptions (500)."""
    logger.exception(
        f"Unhandled exception on {request.url.path}"
    )
    return create_error_response(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        code="INTERNAL_SERVER_ERROR",
        message="An unexpected internal error occurred.",
    )
