"""RBAC permission tests (AT-013/014)."""

from __future__ import annotations

import pytest

from app.core.errors import ForbiddenError
from app.core.permissions import (
    CAP_MANAGE_PROJECTS,
    CAP_VIEW_ALL,
    Role,
    has_capability,
    require_capability,
)


def test_owner_has_all_capabilities():
    for capability in (CAP_MANAGE_PROJECTS, CAP_VIEW_ALL):
        assert has_capability(Role.OWNER, capability) is True


def test_admin_can_manage_projects():
    assert has_capability(Role.ADMIN, CAP_MANAGE_PROJECTS) is True


def test_viewer_cannot_manage_projects():
    assert has_capability(Role.VIEWER, CAP_MANAGE_PROJECTS) is False


def test_viewer_can_view():
    assert has_capability(Role.VIEWER, CAP_VIEW_ALL) is True


def test_engineer_can_run_but_not_manage_projects():
    assert has_capability(Role.ENGINEER, CAP_VIEW_ALL) is True
    assert has_capability(Role.ENGINEER, CAP_MANAGE_PROJECTS) is False


def test_require_capability_raises_for_viewer():
    with pytest.raises(ForbiddenError):
        require_capability(Role.VIEWER, CAP_MANAGE_PROJECTS)


def test_require_capability_passes_for_owner():
    require_capability(Role.OWNER, CAP_MANAGE_PROJECTS)  # no exception
