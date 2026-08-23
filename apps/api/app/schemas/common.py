"""Common response envelope schemas (spec §31–§32)."""

from __future__ import annotations

from typing import TypeVar

from pydantic import BaseModel

from app.core.logging import request_id_ctx

T = TypeVar("T")


class Meta(BaseModel):
    request_id: str


class ListMeta(Meta):
    page: int
    page_size: int
    total: int


class ApiResponse[T](BaseModel):
    data: T
    meta: Meta


class ListResponse[T](BaseModel):
    data: list[T]
    meta: ListMeta


class ErrorDetail(BaseModel):
    code: str
    message: str
    details: dict = {}
    request_id: str


class ErrorResponse(BaseModel):
    error: ErrorDetail


def current_request_id() -> str:
    return request_id_ctx.get()


def ok(data: object) -> dict:
    return {"data": data, "meta": {"request_id": current_request_id()}}


def ok_list(items: list, page: int, page_size: int, total: int) -> dict:
    return {
        "data": items,
        "meta": {
            "page": page,
            "page_size": page_size,
            "total": total,
            "request_id": current_request_id(),
        },
    }
