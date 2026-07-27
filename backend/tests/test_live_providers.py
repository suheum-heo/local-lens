"""Live Kakao/Google provider tests using mocked HTTP (no real credentials)."""

from __future__ import annotations

import httpx
import pytest

from app.domain.enums import City, LocationMode
from app.domain.locations import SearchArea
from app.matching.place_matcher import DefaultPlaceMatcher
from app.providers.errors import ApiCallCounter, ProviderAPIError, ProviderConfigError
from app.providers.google import LiveGooglePlacesProvider
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


def _kakao_page(docs: list[dict], *, is_end: bool) -> httpx.Response:
    return httpx.Response(
        200,
        json={"documents": docs, "meta": {"is_end": is_end, "total_count": len(docs)}},
    )


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
            return _kakao_page(docs, is_end=False)
        docs = [{**SAMPLE_DOC, "id": "3"}]
        return _kakao_page(docs, is_end=True)

    counter = ApiCallCounter()
    provider = LiveKakaoLocalProvider(
        api_key="test-kakao-key",
        transport=httpx.MockTransport(handler),
        counter=counter,
        max_pages=3,
    )
    results = await provider.search_restaurants(_area(), "맛집")
    assert {r.kakao_place_id for r in results} == {"1", "2", "3"}
    assert all(r.rating is None and r.review_count is None for r in results)
    assert counter.kakao_keyword == 2
    assert calls["n"] == 2


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
async def test_live_google_find_place_parses_and_caches():
    calls = {"n": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        calls["n"] += 1
        assert "key" in request.url.params
        # Ensure we do not accidentally echo the key into assertions beyond presence.
        return httpx.Response(
            200,
            json={
                "status": "OK",
                "candidates": [
                    {
                        "place_id": "ChIJ_test",
                        "name": "합정 맛집",
                        "formatted_address": "서울 마포구 양화로 10",
                        "geometry": {"location": {"lat": 37.5501, "lng": 126.9145}},
                        "rating": 4.5,
                        "user_ratings_total": 120,
                    }
                ],
            },
        )

    counter = ApiCallCounter()
    provider = LiveGooglePlacesProvider(
        api_key="test-google-key",
        transport=httpx.MockTransport(handler),
        counter=counter,
    )
    first = await provider.find_place("합정 맛집", 37.5501, 126.9145, "양화로 10")
    second = await provider.find_place("합정 맛집", 37.5501, 126.9145, "양화로 10")
    assert first is not None
    assert first.google_place_id == "ChIJ_test"
    assert first.rating == 4.5
    assert first.user_rating_count == 120
    assert second is first or second == first
    assert calls["n"] == 1
    assert counter.google_find_place == 1


@pytest.mark.asyncio
async def test_live_google_zero_results():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"status": "ZERO_RESULTS", "candidates": []})

    provider = LiveGooglePlacesProvider(
        api_key="test-google-key",
        transport=httpx.MockTransport(handler),
    )
    assert await provider.find_place("없는집", 37.55, 126.91) is None


@pytest.mark.asyncio
async def test_live_google_request_denied():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={"status": "REQUEST_DENIED", "error_message": "secret hint"},
        )

    provider = LiveGooglePlacesProvider(
        api_key="test-google-key",
        transport=httpx.MockTransport(handler),
    )
    with pytest.raises(ProviderAPIError) as exc:
        await provider.find_place("합정 맛집", 37.55, 126.91)
    assert "GOOGLE_PLACES_API_KEY" in exc.value.message
    assert "secret hint" not in exc.value.message


@pytest.mark.asyncio
async def test_live_google_over_query_limit():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"status": "OVER_QUERY_LIMIT"})

    provider = LiveGooglePlacesProvider(
        api_key="test-google-key",
        transport=httpx.MockTransport(handler),
    )
    with pytest.raises(ProviderAPIError) as exc:
        await provider.find_place("합정 맛집", 37.55, 126.91)
    assert exc.value.status_code == 429


@pytest.mark.asyncio
async def test_matcher_skips_details_when_find_has_scores():
    class TrackingGoogle(LiveGooglePlacesProvider):
        def __init__(self) -> None:
            self.details_calls = 0

            def handler(request: httpx.Request) -> httpx.Response:
                if "findplacefromtext" in str(request.url):
                    return httpx.Response(
                        200,
                        json={
                            "status": "OK",
                            "candidates": [
                                {
                                    "place_id": "ChIJ_ok",
                                    "name": "합정 맛집",
                                    "formatted_address": "서울 마포구 양화로 10",
                                    "geometry": {
                                        "location": {"lat": 37.5501, "lng": 126.9145}
                                    },
                                    "rating": 4.6,
                                    "user_ratings_total": 80,
                                }
                            ],
                        },
                    )
                self.details_calls += 1
                return httpx.Response(200, json={"status": "OK", "result": {}})

            super().__init__(
                api_key="test-google-key",
                transport=httpx.MockTransport(handler),
            )

    google = TrackingGoogle()
    matcher = DefaultPlaceMatcher(google)
    from app.domain.models import KakaoPlaceData

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
    assert google.details_calls == 0


@pytest.mark.asyncio
async def test_live_google_details_parses_reviews():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "status": "OK",
                "result": {
                    "place_id": "ChIJ_details",
                    "name": "테스트",
                    "formatted_address": "서울",
                    "geometry": {"location": {"lat": 37.55, "lng": 126.91}},
                    "rating": 4.2,
                    "user_ratings_total": 10,
                    "reviews": [
                        {"language": "ko", "rating": 5, "text": "좋아요"},
                    ],
                },
            },
        )

    provider = LiveGooglePlacesProvider(
        api_key="test-google-key",
        transport=httpx.MockTransport(handler),
    )
    details = await provider.get_place_details("ChIJ_details")
    assert details is not None
    assert details.user_rating_count == 10
    assert details.review_metadata[0]["text"] == "좋아요"


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
