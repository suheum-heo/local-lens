"""Live Kakao/Google provider tests using mocked HTTP (no real credentials)."""

from __future__ import annotations

import json

import httpx
import pytest

from app.domain.enums import City, LocationMode
from app.domain.locations import SearchArea
from app.domain.models import KakaoPlaceData
from app.matching.place_matcher import DefaultPlaceMatcher, score_match
from app.providers.errors import ApiCallCounter, ProviderAPIError, ProviderConfigError
from app.providers.google import SEARCH_FIELD_MASK, LiveGooglePlacesProvider
from app.providers.kakao import LiveKakaoLocalProvider


def _area() -> SearchArea:
    return SearchArea(
        label="합정역",
        city=City.SEOUL,
        latitude=37.5496,
        longitude=126.9139,
        radius_m=1000,
        source_mode=LocationMode.STATION,
        source_id="st_hapjeong",
    )


def _kakao_page(
    docs: list[dict],
    *,
    is_end: bool,
    pageable_count: int | None = None,
) -> httpx.Response:
    meta: dict = {"is_end": is_end, "total_count": len(docs)}
    if pageable_count is not None:
        meta["pageable_count"] = pageable_count
    return httpx.Response(200, json={"documents": docs, "meta": meta})


SAMPLE_DOC = {
    "id": "12345",
    "place_name": "합정 맛집",
    "address_name": "서울 마포구 합정동 1",
    "road_address_name": "서울 마포구 양화로 10",
    "x": "126.9145",
    "y": "37.5501",
    "category_name": "음식점 > 한식",
    "place_url": "https://place.map.kakao.com/12345",
}


def _place_new(
    *,
    place_id: str,
    name: str,
    lat: float,
    lng: float,
    address: str = "서울 마포구 양화로 10",
    rating: float | None = 4.5,
    user_rating_count: int | None = 120,
) -> dict:
    place: dict = {
        "id": place_id,
        "name": f"places/{place_id}",
        "displayName": {"text": name, "languageCode": "ko"},
        "formattedAddress": address,
        "location": {"latitude": lat, "longitude": lng},
    }
    if rating is not None:
        place["rating"] = rating
    if user_rating_count is not None:
        place["userRatingCount"] = user_rating_count
    return place


def _search_response(places: list[dict]) -> httpx.Response:
    return httpx.Response(200, json={"places": places})


@pytest.mark.asyncio
async def test_live_kakao_requires_api_key():
    with pytest.raises(ProviderConfigError):
        LiveKakaoLocalProvider(api_key="")


@pytest.mark.asyncio
async def test_live_kakao_parses_and_paginates():
    calls = {"n": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        calls["n"] += 1
        assert request.url.path.endswith("/v2/local/search/keyword.json")
        assert request.headers.get("Authorization") == "KakaoAK test-kakao-key"
        page = int(request.url.params.get("page", "1"))
        if page == 1:
            docs = [{**SAMPLE_DOC, "id": "1"}, {**SAMPLE_DOC, "id": "2"}]
            return _kakao_page(docs, is_end=False, pageable_count=17)
        docs = [{**SAMPLE_DOC, "id": "3"}]
        return _kakao_page(docs, is_end=True, pageable_count=17)

    counter = ApiCallCounter()
    provider = LiveKakaoLocalProvider(
        api_key="test-kakao-key",
        transport=httpx.MockTransport(handler),
        counter=counter,
        max_pages=3,
    )
    # Specific dish/name → single origin, no cuisine expansion / broad grid.
    results = await provider.search_restaurants(_area(), "칼국수")
    assert {r.kakao_place_id for r in results} == {"1", "2", "3"}
    assert all(r.rating is None and r.review_count is None for r in results)
    assert counter.kakao_keyword == 2
    assert calls["n"] == 2


@pytest.mark.asyncio
async def test_live_kakao_broad_query_uses_multi_origin_grid():
    origins: set[tuple[str, str]] = set()

    def handler(request: httpx.Request) -> httpx.Response:
        x = request.url.params.get("x", "")
        y = request.url.params.get("y", "")
        origins.add((x, y))
        # Distinct id per origin so merge is observable.
        oid = f"{x}:{y}"
        doc = {
            **SAMPLE_DOC,
            "id": oid,
            "x": x,
            "y": y,
        }
        return _kakao_page([doc], is_end=True)

    counter = ApiCallCounter()
    provider = LiveKakaoLocalProvider(
        api_key="test-kakao-key",
        transport=httpx.MockTransport(handler),
        counter=counter,
        max_pages=1,
    )
    results = await provider.search_restaurants(_area(), "맛집")
    assert len(origins) == 5  # center + 4 cardinals for 1km
    assert len(results) == 5
    assert counter.kakao_keyword == 5


@pytest.mark.asyncio
async def test_live_kakao_auth_error():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(401, json={"message": "Unauthorized"})

    provider = LiveKakaoLocalProvider(
        api_key="bad-key",
        transport=httpx.MockTransport(handler),
    )
    with pytest.raises(ProviderAPIError) as exc:
        await provider.search_restaurants(_area(), "맛집")
    assert "authentication" in exc.value.message.lower()
    assert exc.value.provider == "kakao"


@pytest.mark.asyncio
async def test_live_kakao_rate_limit():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(429, json={"message": "limit"})

    provider = LiveKakaoLocalProvider(
        api_key="test-key",
        transport=httpx.MockTransport(handler),
    )
    with pytest.raises(ProviderAPIError) as exc:
        await provider.search_restaurants(_area(), "맛집")
    assert exc.value.status_code == 429
    assert exc.value.retryable


@pytest.mark.asyncio
async def test_live_kakao_skips_malformed_documents():
    bad = {**SAMPLE_DOC, "id": "ok"}
    broken = {"place_name": "no coords"}

    def handler(request: httpx.Request) -> httpx.Response:
        return _kakao_page([broken, bad], is_end=True)

    provider = LiveKakaoLocalProvider(
        api_key="test-key",
        transport=httpx.MockTransport(handler),
    )
    results = await provider.search_restaurants(_area(), "맛집")
    assert len(results) == 1
    assert results[0].kakao_place_id == "ok"


@pytest.mark.asyncio
async def test_live_google_requires_api_key():
    with pytest.raises(ProviderConfigError):
        LiveGooglePlacesProvider(api_key="")


@pytest.mark.asyncio
async def test_live_google_search_text_parses_and_caches():
    calls = {"n": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        calls["n"] += 1
        assert request.method == "POST"
        assert str(request.url).endswith("/v1/places:searchText")
        assert request.headers.get("X-Goog-Api-Key") == "test-google-key"
        assert request.headers.get("X-Goog-FieldMask") == SEARCH_FIELD_MASK
        body = json.loads(request.content.decode())
        assert "textQuery" in body
        assert body["locationBias"]["circle"]["radius"] == 500.0
        # API key must not appear in the JSON body.
        assert "key" not in body
        return _search_response(
            [
                _place_new(
                    place_id="ChIJ_test",
                    name="합정 맛집",
                    lat=37.5501,
                    lng=126.9145,
                )
            ]
        )

    counter = ApiCallCounter()
    provider = LiveGooglePlacesProvider(
        api_key="test-google-key",
        transport=httpx.MockTransport(handler),
        counter=counter,
    )
    first = await provider.search_places("합정 맛집", 37.5501, 126.9145, "양화로 10")
    second = await provider.search_places("합정 맛집", 37.5501, 126.9145, "양화로 10")
    assert len(first) == 1
    assert first[0].google_place_id == "ChIJ_test"
    assert first[0].rating == 4.5
    assert first[0].user_rating_count == 120
    assert second[0].google_place_id == first[0].google_place_id
    assert calls["n"] == 1
    assert counter.google_search_text == 1
    assert counter.google_details == 0


@pytest.mark.asyncio
async def test_live_google_multiple_candidates_returned():
    def handler(request: httpx.Request) -> httpx.Response:
        return _search_response(
            [
                _place_new(
                    place_id="ChIJ_far",
                    name="다른 식당",
                    lat=37.56,
                    lng=126.93,
                    rating=4.0,
                    user_rating_count=10,
                ),
                _place_new(
                    place_id="ChIJ_near",
                    name="합정 맛집",
                    lat=37.5501,
                    lng=126.9145,
                    rating=4.6,
                    user_rating_count=200,
                ),
            ]
        )

    provider = LiveGooglePlacesProvider(
        api_key="test-google-key",
        transport=httpx.MockTransport(handler),
    )
    places = await provider.search_places("합정 맛집", 37.5501, 126.9145)
    assert len(places) == 2
    assert {p.google_place_id for p in places} == {"ChIJ_far", "ChIJ_near"}


@pytest.mark.asyncio
async def test_live_google_no_candidates():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"places": []})

    provider = LiveGooglePlacesProvider(
        api_key="test-google-key",
        transport=httpx.MockTransport(handler),
    )
    assert await provider.search_places("없는집", 37.55, 126.91) == []


@pytest.mark.asyncio
async def test_live_google_missing_rating_and_count():
    def handler(request: httpx.Request) -> httpx.Response:
        return _search_response(
            [
                _place_new(
                    place_id="ChIJ_bare",
                    name="합정 맛집",
                    lat=37.5501,
                    lng=126.9145,
                    rating=None,
                    user_rating_count=None,
                )
            ]
        )

    provider = LiveGooglePlacesProvider(
        api_key="test-google-key",
        transport=httpx.MockTransport(handler),
    )
    places = await provider.search_places("합정 맛집", 37.5501, 126.9145)
    assert places[0].rating is None
    assert places[0].user_rating_count is None


@pytest.mark.asyncio
async def test_live_google_malformed_response():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, content=b"not-json", headers={"content-type": "text/plain"})

    provider = LiveGooglePlacesProvider(
        api_key="test-google-key",
        transport=httpx.MockTransport(handler),
    )
    with pytest.raises(ProviderAPIError) as exc:
        await provider.search_places("합정 맛집", 37.55, 126.91)
    assert "malformed" in exc.value.message.lower()


@pytest.mark.asyncio
async def test_live_google_auth_failure():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            403,
            json={"error": {"status": "PERMISSION_DENIED", "message": "secret hint"}},
        )

    provider = LiveGooglePlacesProvider(
        api_key="test-google-key",
        transport=httpx.MockTransport(handler),
    )
    with pytest.raises(ProviderAPIError) as exc:
        await provider.search_places("합정 맛집", 37.55, 126.91)
    assert "GOOGLE_PLACES_API_KEY" in exc.value.message
    assert "secret hint" not in exc.value.message


@pytest.mark.asyncio
async def test_live_google_api_disabled_message():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            403,
            json={
                "error": {
                    "status": "PERMISSION_DENIED",
                    "message": (
                        "Places API (New) has not been used in project 123 before "
                        "or it is disabled. Enable it by visiting…"
                    ),
                }
            },
        )

    provider = LiveGooglePlacesProvider(
        api_key="test-google-key",
        transport=httpx.MockTransport(handler),
    )
    with pytest.raises(ProviderAPIError) as exc:
        await provider.search_places("합정 맛집", 37.55, 126.91)
    assert "Places API (New) is not enabled" in exc.value.message
    assert "123" not in exc.value.message


@pytest.mark.asyncio
async def test_live_google_invalid_key_as_400():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            400,
            json={
                "error": {
                    "status": "INVALID_ARGUMENT",
                    "message": "API key not valid. Please pass a valid API key.",
                }
            },
        )

    provider = LiveGooglePlacesProvider(
        api_key="test-google-key",
        transport=httpx.MockTransport(handler),
    )
    with pytest.raises(ProviderAPIError) as exc:
        await provider.search_places("합정 맛집", 37.55, 126.91)
    assert "valid server key" in exc.value.message


@pytest.mark.asyncio
async def test_live_google_quota_as_403_resource_exhausted():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            403,
            json={"error": {"status": "RESOURCE_EXHAUSTED", "message": "quota"}},
        )

    provider = LiveGooglePlacesProvider(
        api_key="test-google-key",
        transport=httpx.MockTransport(handler),
    )
    with pytest.raises(ProviderAPIError) as exc:
        await provider.search_places("합정 맛집", 37.55, 126.91)
    assert exc.value.status_code == 429
    assert exc.value.retryable


@pytest.mark.asyncio
async def test_live_google_quota_rate_limit():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            429,
            json={"error": {"status": "RESOURCE_EXHAUSTED", "message": "quota"}},
        )

    provider = LiveGooglePlacesProvider(
        api_key="test-google-key",
        transport=httpx.MockTransport(handler),
    )
    with pytest.raises(ProviderAPIError) as exc:
        await provider.search_places("합정 맛집", 37.55, 126.91)
    assert exc.value.status_code == 429
    assert exc.value.retryable


@pytest.mark.asyncio
async def test_live_google_timeout():
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ReadTimeout("slow")

    provider = LiveGooglePlacesProvider(
        api_key="test-google-key",
        transport=httpx.MockTransport(handler),
    )
    with pytest.raises(ProviderAPIError) as exc:
        await provider.search_places("합정 맛집", 37.55, 126.91)
    assert exc.value.status_code == 504


@pytest.mark.asyncio
async def test_matcher_picks_best_of_multiple_candidates():
    def handler(request: httpx.Request) -> httpx.Response:
        return _search_response(
            [
                _place_new(
                    place_id="ChIJ_wrong",
                    name="완전 다른 이름",
                    lat=37.56,
                    lng=126.93,
                    address="서울 마포구 다른로 99",
                    rating=5.0,
                    user_rating_count=999,
                ),
                _place_new(
                    place_id="ChIJ_correct",
                    name="합정 맛집",
                    lat=37.5501,
                    lng=126.9145,
                    address="서울 마포구 양화로 10",
                    rating=4.4,
                    user_rating_count=50,
                ),
            ]
        )

    provider = LiveGooglePlacesProvider(
        api_key="test-google-key",
        transport=httpx.MockTransport(handler),
    )
    matcher = DefaultPlaceMatcher(provider)
    kakao = KakaoPlaceData(
        kakao_place_id="k1",
        name="합정 맛집",
        address="서울 마포구 합정동 1",
        road_address="서울 마포구 양화로 10",
        latitude=37.5501,
        longitude=126.9145,
        category="음식점",
        place_url="https://place.map.kakao.com/k1",
    )
    result = await matcher.match(kakao)
    assert result.matched is True
    assert result.google is not None
    assert result.google.google_place_id == "ChIJ_correct"
    # Sanity: correct candidate scores higher than the distractor.
    candidates = await provider.search_places(
        kakao.name, kakao.latitude, kakao.longitude, kakao.road_address
    )
    by_id = {c.google_place_id: c for c in candidates}
    assert score_match(kakao, by_id["ChIJ_correct"]) > score_match(
        kakao, by_id["ChIJ_wrong"]
    )


@pytest.mark.asyncio
async def test_matcher_skips_details_when_search_has_scores():
    details_calls = {"n": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        if request.method == "POST":
            return _search_response(
                [
                    _place_new(
                        place_id="ChIJ_ok",
                        name="합정 맛집",
                        lat=37.5501,
                        lng=126.9145,
                        rating=4.6,
                        user_rating_count=80,
                    )
                ]
            )
        details_calls["n"] += 1
        return httpx.Response(200, json=_place_new(place_id="ChIJ_ok", name="합정 맛집", lat=37.5501, lng=126.9145))

    counter = ApiCallCounter()
    provider = LiveGooglePlacesProvider(
        api_key="test-google-key",
        transport=httpx.MockTransport(handler),
        counter=counter,
    )
    matcher = DefaultPlaceMatcher(provider)
    kakao = KakaoPlaceData(
        kakao_place_id="k1",
        name="합정 맛집",
        address="서울 마포구 합정동 1",
        road_address="서울 마포구 양화로 10",
        latitude=37.5501,
        longitude=126.9145,
        category="음식점",
        place_url="https://place.map.kakao.com/k1",
    )
    result = await matcher.match(kakao)
    assert result.matched is True
    assert result.google is not None
    assert result.google.rating == 4.6
    assert details_calls["n"] == 0
    assert counter.google_search_text == 1
    assert counter.google_details == 0


@pytest.mark.asyncio
async def test_matcher_fetches_details_when_search_missing_scores():
    def handler(request: httpx.Request) -> httpx.Response:
        if request.method == "POST":
            return _search_response(
                [
                    _place_new(
                        place_id="ChIJ_need_details",
                        name="합정 맛집",
                        lat=37.5501,
                        lng=126.9145,
                        rating=None,
                        user_rating_count=None,
                    )
                ]
            )
        assert request.method == "GET"
        assert "ChIJ_need_details" in str(request.url)
        assert request.headers.get("X-Goog-FieldMask")
        return httpx.Response(
            200,
            json=_place_new(
                place_id="ChIJ_need_details",
                name="합정 맛집",
                lat=37.5501,
                lng=126.9145,
                rating=4.1,
                user_rating_count=22,
            ),
        )

    counter = ApiCallCounter()
    provider = LiveGooglePlacesProvider(
        api_key="test-google-key",
        transport=httpx.MockTransport(handler),
        counter=counter,
    )
    matcher = DefaultPlaceMatcher(provider)
    kakao = KakaoPlaceData(
        kakao_place_id="k1",
        name="합정 맛집",
        address="서울 마포구 합정동 1",
        road_address="서울 마포구 양화로 10",
        latitude=37.5501,
        longitude=126.9145,
        category="음식점",
        place_url="https://place.map.kakao.com/k1",
    )
    result = await matcher.match(kakao)
    assert result.matched is True
    assert result.google is not None
    assert result.google.rating == 4.1
    assert result.google.user_rating_count == 22
    assert counter.google_search_text == 1
    assert counter.google_details == 1


def test_factory_live_missing_keys(monkeypatch):
    from app.config import Settings
    from app.providers import factory as factory_mod

    monkeypatch.setattr(
        factory_mod,
        "settings",
        Settings(provider_mode="live", kakao_rest_api_key="", google_places_api_key=""),
    )
    with pytest.raises(ProviderConfigError):
        factory_mod.get_kakao_provider()
    with pytest.raises(ProviderConfigError):
        factory_mod.get_google_provider()
