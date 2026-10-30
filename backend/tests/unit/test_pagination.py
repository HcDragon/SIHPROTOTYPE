from typing import Annotated

import pytest
from fastapi import APIRouter, Depends
from fastapi.testclient import TestClient

from app.core.errors import ValidationFailed
from app.core.pagination import PageParams, SortSpec, page_params, parse_sort, sort_param
from app.main import create_app


def _client(settings) -> TestClient:
    app = create_app(settings)
    router = APIRouter()

    @router.get("/_test/items")
    def items(
        page: Annotated[PageParams, Depends(page_params)],
        sort: Annotated[SortSpec, Depends(sort_param("name", "created_at", default="name"))],
    ):
        return {
            "page": page.page,
            "page_size": page.page_size,
            "sort": [sort.field, sort.descending],
        }

    app.include_router(router, prefix="/api/v1")
    return TestClient(app)


def test_defaults(settings):
    body = _client(settings).get("/api/v1/_test/items").json()
    assert body == {"page": 1, "page_size": 20, "sort": ["name", False]}


def test_page_size_above_limit_rejected(settings):
    response = _client(settings).get("/api/v1/_test/items?page_size=500")
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "validation_error"


def test_page_zero_rejected(settings):
    assert _client(settings).get("/api/v1/_test/items?page=0").status_code == 422


def test_descending_sort(settings):
    body = _client(settings).get("/api/v1/_test/items?sort=-created_at").json()
    assert body["sort"] == ["created_at", True]


def test_unknown_sort_field_rejected(settings):
    response = _client(settings).get("/api/v1/_test/items?sort=password_hash")
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "validation_error"


def test_offset():
    assert PageParams(page=3, page_size=20).offset == 40


def test_parse_sort_unit():
    assert parse_sort("-email", frozenset({"email"})) == SortSpec("email", True)
    with pytest.raises(ValidationFailed):
        parse_sort("nope", frozenset({"email"}))
