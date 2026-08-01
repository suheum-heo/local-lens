"""Cuisine keyword expansion for Kakao discovery."""

from __future__ import annotations

import httpx
import pytest

from app.providers.cuisine_queries import expand_food_queries
from app.providers.errors import ApiCallCounter
from app.providers.kakao import LiveKakaoLocalProvider
from tests.test_live_providers import SAMPLE_DOC, _area, _kakao_page


def test_yangsik_expands_to_family_restaurant_and_pasta():
    terms = expand_food_queries("양식")
    assert terms[0] == "양식"
    assert "패밀리레스토랑" in terms
    assert "파스타" in terms


def test_place_name_query_is_not_expanded():
    assert expand_food_queries("올리앤") == ["올리앤"]


def test_empty_passthrough():
    assert expand_food_queries("") == [""]
    assert expand_food_queries("  ") == [""]


@pytest.mark.asyncio
async def test_live_kakao_fans_out_cuisine_expansions():
    seen_queries: set[str] = set()

    def handler(request: httpx.Request) -> httpx.Response:
        q = request.url.params.get("query", "")
        seen_queries.add(q)
        # Keep Hapjeong coords so radius filter accepts the mock docs.
        doc = {**SAMPLE_DOC, "id": q or "empty", "place_name": q}
        return _kakao_page([doc], is_end=True)

    provider = LiveKakaoLocalProvider(
        api_key="test-kakao-key",
        transport=httpx.MockTransport(handler),
        counter=ApiCallCounter(),
        max_pages=1,
    )
    results = await provider.search_restaurants(_area(), "양식")
    assert "양식" in seen_queries
    assert "패밀리레스토랑" in seen_queries
    assert "파스타" in seen_queries
    assert {r.name for r in results} >= {"양식", "패밀리레스토랑", "파스타"}