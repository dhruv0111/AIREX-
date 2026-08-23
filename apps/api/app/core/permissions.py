"""Role-based access control (PRD §7, spec §13, AT-013/014).

Roles: OWNER, ADMIN, ENGINEER, VIEWER.
Capability-based checks are used by services and API dependencies.
"""

from __future__ import annotations

from enum import StrEnum

from app.core.errors import ForbiddenError


class Role(StrEnum):
    OWNER = "OWNER"
    ADMIN = "ADMIN"
    ENGINEER = "ENGINEER"
    VIEWER = "VIEWER"


# Capability strings used across the API.
CAP_MANAGE_ORGANIZATION = "manage_organization"
CAP_MANAGE_USERS = "manage_users"
CAP_MANAGE_PROJECTS = "manage_projects"
CAP_MANAGE_MODELS = "manage_models"
CAP_MANAGE_DATASETS = "manage_datasets"
CAP_RUN_EVALUATIONS = "run_evaluations"
CAP_CREATE_EXPERIMENTS = "create_experiments"
CAP_VIEW_ALL = "view_all"
CAP_VIEW_AUDIT = "view_audit"
# Phase 1 capabilities.
CAP_MANAGE_MEMBERS = "manage_members"
CAP_VIEW_MEMBERS = "view_members"
CAP_MANAGE_PROVIDERS = "manage_providers"
CAP_MANAGE_ENVIRONMENTS = "manage_environments"
CAP_INVOKE_MODELS = "invoke_models"
# Phase 4.
CAP_MANAGE_RUBRICS = "manage_rubrics"
# Phase 5.
CAP_GENERATE_TESTS = "generate_tests"

# Role -> capabilities (least-privilege defaults; see PERMISSION_MATRIX).
_ROLE_CAPABILITIES: dict[Role, set[str]] = {
    Role.OWNER: {
        CAP_MANAGE_ORGANIZATION,
        CAP_MANAGE_USERS,
        CAP_MANAGE_PROJECTS,
        CAP_MANAGE_MODELS,
        CAP_MANAGE_DATASETS,
        CAP_RUN_EVALUATIONS,
        CAP_CREATE_EXPERIMENTS,
        CAP_VIEW_ALL,
        CAP_VIEW_AUDIT,
        CAP_MANAGE_MEMBERS,
        CAP_VIEW_MEMBERS,
        CAP_MANAGE_PROVIDERS,
        CAP_MANAGE_ENVIRONMENTS,
        CAP_INVOKE_MODELS,
        CAP_MANAGE_RUBRICS,
        CAP_GENERATE_TESTS,
    },
    Role.ADMIN: {
        CAP_MANAGE_ORGANIZATION,
        CAP_MANAGE_USERS,
        CAP_MANAGE_PROJECTS,
        CAP_MANAGE_MODELS,
        CAP_MANAGE_DATASETS,
        CAP_RUN_EVALUATIONS,
        CAP_CREATE_EXPERIMENTS,
        CAP_VIEW_ALL,
        CAP_VIEW_AUDIT,
        CAP_MANAGE_MEMBERS,
        CAP_VIEW_MEMBERS,
        CAP_MANAGE_PROVIDERS,
        CAP_MANAGE_ENVIRONMENTS,
        CAP_INVOKE_MODELS,
        CAP_MANAGE_RUBRICS,
        CAP_GENERATE_TESTS,
    },
    Role.ENGINEER: {
        CAP_MANAGE_DATASETS,
        CAP_RUN_EVALUATIONS,
        CAP_CREATE_EXPERIMENTS,
        CAP_VIEW_ALL,
        CAP_VIEW_MEMBERS,
        CAP_INVOKE_MODELS,
        CAP_MANAGE_RUBRICS,
        CAP_GENERATE_TESTS,
    },
    Role.VIEWER: {CAP_VIEW_ALL, CAP_VIEW_MEMBERS},
}


def has_capability(role: Role, capability: str) -> bool:
    return capability in _ROLE_CAPABILITIES.get(role, set())


def require_capability(role: Role, capability: str) -> None:
    """Raise ForbiddenError when the role lacks the capability (AT-013)."""
    if not has_capability(role, capability):
        raise ForbiddenError(
            "You do not have permission to perform this action.",
            details={"required_capability": capability},
        )
