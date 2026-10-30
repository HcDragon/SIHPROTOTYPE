"""Pagination and allow-listed sorting shared by every list endpoint."""

from collections.abc import Callable
from dataclasses import dataclass
from typing import Annotated

from fastapi import Query
from pydantic import BaseModel

from app.core.errors import ValidationFailed

DEFAULT_PAGE_SIZE = 20
MAX_PAGE_SIZE = 100


@dataclass(frozen=True)
class PageParams:
    page: int
    page_size: int

    @property
    def offset(self) -> int:
        return (self.page - 1) * self.page_size


def page_params(
    page: Annotated[int, Query(ge=1, description="Page number, starting at 1.")] = 1,
    page_size: Annotated[
        int, Query(ge=1, le=MAX_PAGE_SIZE, description="Items per page (max 100).")
    ] = DEFAULT_PAGE_SIZE,
) -> PageParams:
    return PageParams(page=page, page_size=page_size)


class Page[T](BaseModel):
    items: list[T]
    total: int
    page: int
    page_size: int


@dataclass(frozen=True)
class SortSpec:
    field: str
    descending: bool


def parse_sort(value: str, allowed: frozenset[str]) -> SortSpec:
    descending = value.startswith("-")
    field = value[1:] if descending else value
    if field not in allowed:
        raise ValidationFailed(
            details=[
                {
                    "loc": ["query", "sort"],
                    "msg": f"Unsupported sort field. Allowed: {', '.join(sorted(allowed))}.",
                    "type": "sort_field",
                }
            ]
        )
    return SortSpec(field=field, descending=descending)


def sort_param(*allowed: str, default: str) -> Callable[..., SortSpec]:
    """Build a dependency that accepts `sort=<field>` or `sort=-<field>` for allowed fields."""
    allowed_fields = frozenset(allowed)
    description = (
        f"Sort field, one of: {', '.join(sorted(allowed_fields))}. Prefix with '-' for descending."
    )

    def dependency(sort: Annotated[str, Query(description=description)] = default) -> SortSpec:
        return parse_sort(sort, allowed_fields)

    return dependency
