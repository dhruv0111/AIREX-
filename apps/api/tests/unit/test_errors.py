"""Error model tests (spec §32, AT-015)."""

from __future__ import annotations

from app.core.errors import (
    AuthError,
    ConflictError,
    ForbiddenError,
    NotFoundError,
    ValidationFailure,
)


def test_error_classes_map_to_status_codes():
    assert NotFoundError.status_code == 404
    assert ConflictError.status_code == 409
    assert AuthError.status_code == 401
    assert ForbiddenError.status_code == 403
    assert ValidationFailure.status_code == 400


def test_app_error_carries_message_and_details():
    err = ConflictError(
        "A user with this email already exists.", details={"code": "USER_ALREADY_EXISTS"}
    )
    assert err.message == "A user with this email already exists."
    assert err.details["code"] == "USER_ALREADY_EXISTS"


def test_app_error_default_details():
    err = NotFoundError("nope")
    assert err.details == {}
