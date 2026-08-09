"""Cuisine keyword expansion for Kakao discovery."""

from __future__ import annotations

import httpx
import pytest

from app.providers.cuisine_queries import (
    KAKAO_CATEGORY_CAFE,
    KAKAO_CATEGORY_FOOD,
    expand_food_queries,
    is_cafe_intent,
    kakao_category_group,
    place_matches_food_keyword,
)
from app.providers.errors import ApiCallCounter
from app.providers.kakao import LiveKakaoLocalProvider
from tests.test_live_providers import SAMPLE_DOC, _area, _kakao_page


def test_yangsik_expands_to_family_restaurant_and_pasta():
    terms = expand_food_queries("양식")
    assert terms[0] == "양식"
    assert "패밀리레스토랑" in terms
    assert "파스타" in terms


def test_cafe_stays_coffee_focused():
    terms = expand_food_queries("카페")
    assert terms == ["카페", "커피"]
    assert "디저트" not in terms
    assert "베이커리" not in terms
    assert is_cafe_intent("카페")
    assert is_cafe_intent("커피")
    assert kakao_category_group("카페") == KAKAO_CATEGORY_CAFE
    assert kakao_category_group("맛집") == KAKAO_CATEGORY_FOOD


def test_place_name_query_is_not_expanded():
    assert expand_food_queries("올리앤") == ["올리앤"]


def test_empty_passthrough():
    assert expand_food_queries("") == [""]
    assert expand_food_queries("  ") == [""]


def test_suljip_expands_broadly():
    terms = expand_food_queries("술집")
    assert terms[0] == "술집"
    for expected in ("펍", "호프", "포차", "이자카야", "와인바", "칵테일바"):
        assert expected in terms
    assert kakao_category_group("술집") == KAKAO_CATEGORY_FOOD


def test_pub_stays_beer_pub_focused():
    terms = expand_food_queries("펍")
    assert "펍" in terms
    assert "호프" in terms
    assert "맥주" in terms
    assert "포차" not in terms
    assert "이자카야" not in terms
    assert "와인바" not in terms


def test_bar_alone_is_not_expanded():
    assert expand_food_queries("바") == ["바"]


def test_hof_mirrors_pub_focus():
    terms = expand_food_queries("호프")
    assert terms[0] == "호프"
    assert "펍" in terms
    assert "맥주" in terms
    assert "포차" not in terms


def test_hamburger_does_not_expand_to_yangsik():
    assert expand_food_queries("햄버거") == ["햄버거"]


def test_hamburger_rejects_bare_western_and_bakery():
    assert place_matches_food_keyword(
        "햄버거",
        name="수제버거집",
        category="음식점 > 양식 > 햄버거",
    )
    assert place_matches_food_keyword(
        "햄버거",
        name="맥도날드 합정점",
        category="음식점 > 패스트푸드 > 맥도날드",
    )
    assert not place_matches_food_keyword(
        "햄버거",
        name="뉴욕아파트먼트",
        category="음식점 > 양식",
    )
    assert not place_matches_food_keyword(
        "햄버거",
        name="파리바게뜨 합정점",
        category="음식점 > 간식 > 제과,베이커리 > 파리바게뜨",
    )
    assert not place_matches_food_keyword(
        "햄버거",
        name="안짱",
        category="음식점 > 일식",
    )


def test_pasta_and_ramen_require_dish_tokens():
    assert place_matches_food_keyword(
        "파스타", name="면식당", category="음식점 > 양식 > 파스타"
    )
    assert not place_matches_food_keyword(
        "파스타", name="스테이크하우스", category="음식점 > 양식"
    )
    assert place_matches_food_keyword(
        "라멘", name="이치란", category="음식점 > 일식 > 라멘"
    )
    assert not place_matches_food_keyword(
        "라멘", name="스시명소", category="음식점 > 일식 > 초밥,롤"
    )


def test_umbrella_yangsik_is_not_dish_filtered():
    assert place_matches_food_keyword(
        "양식", name="뉴욕아파트먼트", category="음식점 > 양식"
    )


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


@pytest.mark.asyncio
async def test_live_kakao_cafe_uses_ce7_category():
    seen_categories: set[str] = set()

    def handler(request: httpx.Request) -> httpx.Response:
        seen_categories.add(request.url.params.get("category_group_code", ""))
        doc = {
            **SAMPLE_DOC,
            "id": "cafe1",
            "place_name": "합정 카페",
            "category_name": "음식점 > 카페",
        }
        return _kakao_page([doc], is_end=True)

    provider = LiveKakaoLocalProvider(
        api_key="test-kakao-key",
        transport=httpx.MockTransport(handler),
        counter=ApiCallCounter(),
        max_pages=1,
    )
    results = await provider.search_restaurants(_area(), "카페")
    assert seen_categories == {KAKAO_CATEGORY_CAFE}
    assert results and results[0].name == "합정 카페"


@pytest.mark.asyncio
async def test_live_kakao_filters_offtopic_hamburger_hits():
    def handler(request: httpx.Request) -> httpx.Response:
        docs = [
            {
                **SAMPLE_DOC,
                "id": "burger1",
                "place_name": "합정버거",
                "category_name": "음식점 > 양식 > 햄버거",
            },
            {
                **SAMPLE_DOC,
                "id": "western1",
                "place_name": "뉴욕아파트먼트",
                "category_name": "음식점 > 양식",
            },
            {
                **SAMPLE_DOC,
                "id": "bakery1",
                "place_name": "파리바게뜨 합정점",
                "category_name": "음식점 > 간식 > 제과,베이커리 > 파리바게뜨",
            },
            {
                **SAMPLE_DOC,
                "id": "mcd1",
                "place_name": "맥도날드 합정점",
                "category_name": "음식점 > 패스트푸드 > 맥도날드",
            },
        ]
        return _kakao_page(docs, is_end=True)

    provider = LiveKakaoLocalProvider(
        api_key="test-kakao-key",
        transport=httpx.MockTransport(handler),
        counter=ApiCallCounter(),
        max_pages=1,
    )
    results = await provider.search_restaurants(_area(), "햄버거")
    names = {r.name for r in results}
    assert names == {"합정버거", "맥도날드 합정점"}