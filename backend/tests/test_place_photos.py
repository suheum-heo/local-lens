"""Place photo metadata parsing + secure backend photo proxy tests (mocked HTTP)."""

from __future__ import annotations

import httpx
import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.providers.errors import ApiCallCounter, ProviderAPIError
from app.providers.google import SEARCH_FIELD_MASK, LiveGooglePlacesProvider, _normalize_place
from app.providers.place_photos import (
    build_photo_proxy_url,
    extract_first_photo,
    fetch_place_photo_media,
    is_mock_photo_name,
    is_valid_photo_name,
)


VALID_PHOTO = "places/ChIJtestplace/photos/ABC123photoRef"


def test_photo_name_validation():
    assert is_valid_photo_name(VALID_PHOTO)
    assert is_mock_photo_name("places/ChIJx/photos/mock_rep_1")
    assert not is_valid_photo_name("https://evil.example/img.jpg")
    assert not is_valid_photo_name("places/../photos/x")
    assert not is_valid_photo_name("places/ChIJ/photos/x?key=secret")
    assert not is_valid_photo_name("places/ChIJ/photos/has space")


def test_extract_first_photo_parses_attributions():
    name, attrs = extract_first_photo(
        [
            {
                "name": VALID_PHOTO,
                "widthPx": 1200,
                "heightPx": 900,
                "authorAttributions": [
                    {"displayName": "Ada", "uri": "https://maps.google.com"},
                    {"displayName": "Bob"},
                ],
            },
            {"name": "places/ChIJother/photos/zzz"},
        ]
    )
    assert name == VALID_PHOTO
    assert attrs == ["Ada", "Bob"]


def test_extract_first_photo_empty():
    assert extract_first_photo(None) == (None, [])
    assert extract_first_photo([]) == (None, [])
    assert extract_first_photo([{"name": "not-a-valid-name"}]) == (None, [])


def test_build_photo_proxy_url_has_no_api_key():
    url = build_photo_proxy_url(VALID_PHOTO)
    assert url.startswith("/api/restaurants/photo?photo_name=")
    assert "key=" not in url.lower()
    assert "AIza" not in url


def test_normalize_place_includes_photo():
    place = _normalize_place(
        {
            "id": "ChIJtestplace",
            "displayName": {"text": "테스트"},
            "formattedAddress": "서울",
            "location": {"latitude": 37.5, "longitude": 127.0},
            "rating": 4.5,
            "userRatingCount": 10,
            "photos": [
                {
                    "name": VALID_PHOTO,
                    "authorAttributions": [{"displayName": "Chris"}],
                }
            ],
        },
        fallback_name="x",
    )
    assert place is not None
    assert place.photo_name == VALID_PHOTO
    assert place.photo_attributions == ["Chris"]


@pytest.mark.asyncio
async def test_text_search_parses_photos_and_field_mask():
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.headers.get("X-Goog-FieldMask") == SEARCH_FIELD_MASK
        assert "places.photos" in SEARCH_FIELD_MASK
        assert "reviews" not in SEARCH_FIELD_MASK
        return httpx.Response(
            200,
            json={
                "places": [
                    {
                        "id": "ChIJwithphoto",
                        "displayName": {"text": "포토맛집"},
                        "formattedAddress": "서울",
                        "location": {"latitude": 37.55, "longitude": 126.91},
                        "rating": 4.4,
                        "userRatingCount": 80,
                        "photos": [
                            {
                                "name": "places/ChIJwithphoto/photos/refOne",
                                "authorAttributions": [{"displayName": "Dana"}],
                            }
                        ],
                    },
                    {
                        "id": "ChIJnophoto",
                        "displayName": {"text": "노포토"},
                        "formattedAddress": "서울",
                        "location": {"latitude": 37.55, "longitude": 126.92},
                        "rating": 4.1,
                        "userRatingCount": 20,
                    },
                ]
            },
        )

    provider = LiveGooglePlacesProvider(
        api_key="test-google-key",
        transport=httpx.MockTransport(handler),
    )
    places = await provider.search_places("포토맛집", 37.55, 126.91)
    assert places[0].photo_name == "places/ChIJwithphoto/photos/refOne"
    assert places[0].photo_attributions == ["Dana"]
    assert places[1].photo_name is None


@pytest.mark.asyncio
async def test_fetch_mock_photo_does_not_call_google():
    calls = {"n": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        calls["n"] += 1
        return httpx.Response(500)

    counter = ApiCallCounter()
    media = await fetch_place_photo_media(
        "places/ChIJhp_samgyeopsal/photos/mock_rep_hp001",
        api_key="should-not-be-used",
        transport=httpx.MockTransport(handler),
        counter=counter,
    )
    assert calls["n"] == 0
    assert media.content_type == "image/svg+xml"
    assert b"<svg" in media.content
    assert counter.google_place_photo == 1
    assert b"should-not-be-used" not in media.content
    assert b"AIza" not in media.content


@pytest.mark.asyncio
async def test_fetch_live_photo_streams_image_and_counts():
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path.endswith("/media")
        assert request.url.params.get("maxWidthPx") == "800"
        # Key is server-side only; ensure request uses it but response body has no key.
        assert request.url.params.get("key") == "test-google-key"
        return httpx.Response(
            200,
            content=b"\xff\xd8\xfffakejpeg",
            headers={"content-type": "image/jpeg"},
        )

    counter = ApiCallCounter()
    # Force live path even if settings are mock: non-mock photo name + inject key.
    # Temporarily bypass mock mode by using a non-mock name and patching settings
    # via calling with api_key while settings.use_mock_providers may be true.
    # When use_mock_providers is True, fetch_place_photo_media short-circuits —
    # so monkeypatch settings for this test.
    from app.providers import place_photos as pp

    original = pp.settings

    class _LiveSettings:
        use_mock_providers = False
        google_places_api_key = "test-google-key"

    pp.settings = _LiveSettings()  # type: ignore[assignment]
    try:
        media = await fetch_place_photo_media(
            VALID_PHOTO,
            api_key="test-google-key",
            transport=httpx.MockTransport(handler),
            counter=counter,
        )
    finally:
        pp.settings = original

    assert media.content_type == "image/jpeg"
    assert media.content.startswith(b"\xff\xd8")
    assert counter.google_place_photo == 1


@pytest.mark.asyncio
async def test_fetch_live_photo_404():
    from app.providers import place_photos as pp

    original = pp.settings

    class _LiveSettings:
        use_mock_providers = False
        google_places_api_key = "test-google-key"

    pp.settings = _LiveSettings()  # type: ignore[assignment]
    try:
        with pytest.raises(ProviderAPIError) as exc:
            await fetch_place_photo_media(
                VALID_PHOTO,
                api_key="test-google-key",
                transport=httpx.MockTransport(
                    lambda r: httpx.Response(404, json={"error": {"status": "NOT_FOUND"}})
                ),
            )
        assert exc.value.status_code == 404
    finally:
        pp.settings = original


@pytest.mark.asyncio
async def test_fetch_live_photo_auth_error():
    from app.providers import place_photos as pp

    original = pp.settings

    class _LiveSettings:
        use_mock_providers = False
        google_places_api_key = "bad-key"

    pp.settings = _LiveSettings()  # type: ignore[assignment]
    try:
        with pytest.raises(ProviderAPIError) as exc:
            await fetch_place_photo_media(
                VALID_PHOTO,
                api_key="bad-key",
                transport=httpx.MockTransport(lambda r: httpx.Response(403)),
            )
        assert "authentication" in exc.value.message.lower()
    finally:
        pp.settings = original


@pytest.mark.asyncio
async def test_fetch_live_photo_quota():
    from app.providers import place_photos as pp

    original = pp.settings

    class _LiveSettings:
        use_mock_providers = False
        google_places_api_key = "test-google-key"

    pp.settings = _LiveSettings()  # type: ignore[assignment]
    try:
        with pytest.raises(ProviderAPIError) as exc:
            await fetch_place_photo_media(
                VALID_PHOTO,
                api_key="test-google-key",
                transport=httpx.MockTransport(lambda r: httpx.Response(429)),
            )
        assert exc.value.status_code == 429
    finally:
        pp.settings = original


@pytest.mark.asyncio
async def test_fetch_live_photo_timeout():
    from app.providers import place_photos as pp

    original = pp.settings

    class _LiveSettings:
        use_mock_providers = False
        google_places_api_key = "test-google-key"

    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.TimeoutException("slow")

    pp.settings = _LiveSettings()  # type: ignore[assignment]
    try:
        with pytest.raises(ProviderAPIError) as exc:
            await fetch_place_photo_media(
                VALID_PHOTO,
                api_key="test-google-key",
                transport=httpx.MockTransport(handler),
            )
        assert exc.value.status_code == 504
    finally:
        pp.settings = original


def test_photo_proxy_rejects_invalid_name():
    client = TestClient(app)
    res = client.get(
        "/api/restaurants/photo",
        params={"photo_name": "https://evil.example/x.jpg"},
    )
    assert res.status_code == 400
    assert "AIza" not in res.text
    assert "GOOGLE" not in res.text


def test_photo_proxy_serves_mock_svg():
    client = TestClient(app)
    res = client.get(
        "/api/restaurants/photo",
        params={"photo_name": "places/ChIJhp_samgyeopsal/photos/mock_rep_hp001"},
    )
    assert res.status_code == 200
    assert "image/svg" in res.headers["content-type"]
    assert b"<svg" in res.content
    assert b"AIza" not in res.content
    body = res.text
    assert "test-google-key" not in body
    assert "GOOGLE_PLACES_API_KEY" not in body


@pytest.mark.asyncio
async def test_orchestrator_sets_photo_proxy_fields_without_api_key():
    from app.domain.contracts import SearchRequest
    from app.domain.enums import City, LocationMode
    from app.domain.locations import StationLocation
    from app.providers.mock_google import MockGooglePlacesProvider
    from app.providers.mock_kakao import MockKakaoLocalProvider
    from app.services.search_orchestrator import SearchOrchestrator

    orch = SearchOrchestrator(
        kakao=MockKakaoLocalProvider(),
        google=MockGooglePlacesProvider(),
        enable_kakao_enrichment=False,
    )
    result = await orch.search(
        SearchRequest(
            city=City.SEOUL,
            mode=LocationMode.STATION,
            query="맛집",
            locations=[
                StationLocation(
                    station_id="st_hapjeong",
                    station_name="합정역",
                    city=City.SEOUL,
                    latitude=37.5496,
                    longitude=126.9139,
                    radius_m=1000,
                )
            ],
        )
    )
    payload = result.model_dump(mode="json", by_alias=True)
    text = str(payload)
    assert "AIza" not in text
    assert "GOOGLE_PLACES_API_KEY" not in text

    with_photo = [r for r in payload["results"] if r.get("photo_url")]
    without = [r for r in payload["results"] if not r.get("photo_url")]
    assert with_photo, "expected at least one mock restaurant with photo"
    assert without, "expected at least one restaurant without photo"
    for r in with_photo:
        assert r["photo_url"].startswith("/api/restaurants/photo?photo_name=")
        assert "key=" not in r["photo_url"].lower()
        assert r["photo_name"]
        google = r.get("google") or {}
        assert "key=" not in str(google).lower()
        assert "photoUri" not in google
