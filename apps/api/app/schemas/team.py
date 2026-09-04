"""Pydantic schemas for Teams, Team Members, and Project Access (Phase 13)."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID
from pydantic import BaseModel, ConfigDict, Field


class TeamCreate(BaseModel):
    name: str = Field(..., min_length=2, max_length=255)
    description: str | None = None


class TeamUpdate(BaseModel):
    name: str | None = None
    description: str | None = None


class TeamMemberCreate(BaseModel):
    user_id: UUID
    role: str = Field(default="MEMBER")  # LEAD, MEMBER


class TeamMemberResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    team_id: UUID
    user_id: UUID
    role: str
    user_email: str | None = None
    user_name: str | None = None
    created_at: datetime


class TeamProjectAccessCreate(BaseModel):
    project_id: UUID
    permission_role: str = Field(default="ENGINEER")  # VIEWER, ENGINEER, ADMIN


class TeamProjectAccessResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    team_id: UUID
    project_id: UUID
    permission_role: str
    project_name: str | None = None
    created_at: datetime


class UserProjectAccessCreate(BaseModel):
    user_id: UUID
    permission_role: str = Field(default="ENGINEER")


class UserProjectAccessResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    user_id: UUID
    project_id: UUID
    permission_role: str
    created_at: datetime


class TeamResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    organization_id: UUID
    name: str
    slug: str
    description: str | None = None
    members_count: int = 0
    projects_count: int = 0
    created_at: datetime
    updated_at: datetime


class AccessResolutionResponse(BaseModel):
    user_id: UUID
    project_id: UUID
    effective_role: str | None
    access_type: str  # DIRECT_ACCESS, TEAM_ACCESS, ORGANIZATION_ACCESS, NO_ACCESS
