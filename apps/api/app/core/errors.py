"""Standardized error model (PRD §63, spec §32).

Every error is returned as:
    {"error": {"code": ..., "message": ..., "details": {}, "request_id": ...}}

No internal stack traces are ever returned to clients.
"""

from __future__ import annotations

from typing import Any

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse


class AppError(Exception):
    """Base application error mapped to the standard envelope."""

    status_code: int = 500
    code: str = "INTERNAL_ERROR"

    def __init__(self, message: str, *, details: dict[str, Any] | None = None) -> None:
        super().__init__(message)
        self.message = message
        self.details = details or {}


class NotFoundError(AppError):
    status_code = 404
    code = "NOT_FOUND"


class ConflictError(AppError):
    status_code = 409
    code = "CONFLICT"


class ValidationFailure(AppError):
    status_code = 400
    code = "VALIDATION_ERROR"


class AuthError(AppError):
    status_code = 401
    code = "AUTH_INVALID_CREDENTIALS"


class ForbiddenError(AppError):
    status_code = 403
    code = "AUTHZ_FORBIDDEN"


class RateLimitError(AppError):
    status_code = 429
    code = "RATE_LIMIT_API"


class NotImplementedFeature(AppError):
    status_code = 501
    code = "NOT_IMPLEMENTED"


# ---- Phase 2: dataset management error codes (spec §54) ----
class DatasetNotFoundError(AppError):
    status_code = 404
    code = "DATASET_NOT_FOUND"


class DatasetArchivedError(AppError):
    status_code = 409
    code = "DATASET_ARCHIVED"


class DatasetVersionNotFoundError(AppError):
    status_code = 404
    code = "DATASET_VERSION_NOT_FOUND"


class DatasetVersionImmutableError(AppError):
    status_code = 409
    code = "DATASET_VERSION_IMMUTABLE"


class InvalidDatasetFormatError(AppError):
    status_code = 400
    code = "INVALID_DATASET_FORMAT"


class InvalidDatasetSchemaError(AppError):
    status_code = 400
    code = "INVALID_DATASET_SCHEMA"


class DatasetTooLargeError(AppError):
    status_code = 413
    code = "DATASET_TOO_LARGE"


class TooManyRecordsError(AppError):
    status_code = 400
    code = "TOO_MANY_RECORDS"


class InvalidDatasetEncodingError(AppError):
    status_code = 400
    code = "INVALID_DATASET_ENCODING"


class DuplicateDatasetVersionError(AppError):
    status_code = 409
    code = "DUPLICATE_DATASET_VERSION"


class InvalidTestCaseError(AppError):
    status_code = 400
    code = "INVALID_TEST_CASE"


def _envelope(
    *,
    code: str,
    message: str,
    request_id: str,
    details: dict[str, Any] | None = None,
    status_code: int = 500,
) -> JSONResponse:
    return JSONResponse(
        status_code=status_code,
        content={
            "error": {
                "code": code,
                "message": message,
                "details": details or {},
                "request_id": request_id,
            }
        },
    )


def register_error_handlers(app: FastAPI) -> None:
    """Register global error handlers producing the standard envelope."""

    @app.exception_handler(AppError)
    async def app_error_handler(request: Request, exc: AppError) -> JSONResponse:
        request_id = request.state.request_id
        return _envelope(
            code=exc.code,
            message=exc.message,
            details=exc.details,
            request_id=request_id,
            status_code=exc.status_code,
        )

    @app.exception_handler(RequestValidationError)
    async def validation_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
        request_id = request.state.request_id
        # FastAPI error dicts can carry non-JSON-serializable ctx values (e.g. a
        # ValueError raised by a validator). Convert them to strings so the error
        # envelope always serializes (AT-P1-002). Request-validation errors use
        # 400 VALIDATION_ERROR per ERROR_CONTRACTS (Phase 0 contract).
        errors: list[dict[str, Any]] = []
        for err in exc.errors():
            sanitized = dict(err)
            ctx = sanitized.get("ctx")
            if isinstance(ctx, dict):
                sanitized["ctx"] = {k: str(v) for k, v in ctx.items()}
            elif ctx is not None:
                sanitized["ctx"] = str(ctx)
            errors.append(sanitized)
        return _envelope(
            code="VALIDATION_ERROR",
            message="Request validation failed.",
            details={"errors": errors},
            request_id=request_id,
            status_code=400,
        )

    @app.exception_handler(Exception)
    async def unhandled_handler(request: Request, exc: Exception) -> JSONResponse:
        # Log full detail server-side; return safe error to the client.
        import logging

        logging.getLogger("airex.api").exception(
            "Unhandled error",
            exc_info=exc,
            extra={"request_id": request.state.request_id},
        )
        request_id = request.state.request_id
        return _envelope(
            code="INTERNAL_ERROR",
            message="An unexpected error occurred.",
            request_id=request_id,
            status_code=500,
        )
