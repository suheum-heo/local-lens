"""Live Google Places API (New) provider (requires GOOGLE_PLACES_API_KEY).

Endpoints:
  POST https://places.googleapis.com/v1/places:searchText
  GET  https://places.googleapis.com/v1/places/{place_id}

Text Search field mask (matching + scoring + one photo resource; no reviews):
  places.id,places.displayName,places.formattedAddress,
  places.location,places.rating,places.userRatingCount,places.photos

Place Details is only used when Text Search omitted rating or userRatingCount.
Photos are requested on Details only when the cached place still lacks a photo.
Reviews are not requested — LocalLens scoring uses rating + review count only.
"""

from __future__ import annotations

import logging
from typing import Any

import httpx

from app.config import settings
from app.domain.models import GooglePlaceData
from app.providers.base import GooglePlacesProvider
from app.providers.errors import ApiCallCounter, ProviderAPIError, ProviderConfigError
from app.providers.place_photos import extract_first_photo

logger = logging.getLogger(__name__)

SEARCH_TEXT_URL = "https://places.googleapis.com/v1/places:searchText"
PLACE_DETAILS_URL = "https://places.googleapis.com/v1/places/{place_id}"

# Pro SKU fields used for matching + Local/Global scoring + representative photo.
# Avoid '*' masks.
SEARCH_FIELD_MASK = ",".join(
    [
        "places.id",
        "places.displayName",
        "places.formattedAddress",
        "places.location",
        "places.rating",
        "places.userRatingCount",
        "places.photos",
    ]
)
# Same core data for Details (New); no reviews.
DETAILS_FIELD_MASK = ",".join(
    [
        "id",
        "displayName",
        "formattedAddress",
        "location",
        "rating",
        "userRatingCount",
    ]
)
DETAILS_FIELD_MASK_WITH_PHOTOS = f"{DETAILS_FIELD_MASK},photos"

REQUEST_TIMEOUT_S = 10.0
LOCATION_BIAS_RADIUS_M = 500.0
MAX_SEARCH_RESULTS = 5


class LiveGooglePlacesProvider(GooglePlacesProvider):
    def __init__(
        self,
        api_key: str | None = None,
        *,
        transport: httpx.AsyncBaseTransport | None = None,
        counter: ApiCallCounter | None = None,
    ) -> None:
        self._api_key = (
            api_key if api_key is not None else settings.google_places_api_key
        )
        if not self._api_key:
            raise ProviderConfigError(
                "PROVIDER_MODE=live requires GOOGLE_PLACES_API_KEY to be set"
            )
        self._transport = transport
        self._counter = counter
        self._search_cache: dict[
            tuple[str, float, float, str], list[GooglePlaceData]
        ] = {}
        self._details_cache: dict[str, GooglePlaceData | None] = {}
        # Reused across concurrent match calls within one search request.
        self._client: httpx.AsyncClient | None = None

    async def search_places(
        self,
        name: str,
        latitude: float,
        longitude: float,
        address: str | None = None,
    ) -> list[GooglePlaceData]:
        cache_key = (
            name.strip(),
            round(latitude, 5),
            round(longitude, 5),
            (address or "").strip(),
        )
        if cache_key in self._search_cache:
            return list(self._search_cache[cache_key])

        text_query = f"{name} {address}".strip() if address else name.strip()
        body: dict[str, Any] = {
            "textQuery": text_query,
            "languageCode": "ko",
            "regionCode": "KR",
            "includedType": "restaurant",
            "pageSize": MAX_SEARCH_RESULTS,
            "locationBias": {
                "circle": {
                    "center": {"latitude": latitude, "longitude": longitude},
                    "radius": LOCATION_BIAS_RADIUS_M,
                }
            },
        }

        data = await self._request_json(
            "POST",
            SEARCH_TEXT_URL,
            headers={
                "Content-Type": "application/json",
                "X-Goog-Api-Key": self._api_key,
                "X-Goog-FieldMask": SEARCH_FIELD_MASK,
            },
            json_body=body,
            counter_attr="google_search_text",
        )

        places_raw = data.get("places") or []
        places: list[GooglePlaceData] = []
        for raw in places_raw:
            place = _normalize_place(raw, fallback_name=name)
            if place is not None:
                places.append(place)
                self._details_cache.setdefault(place.google_place_id, place)

        self._search_cache[cache_key] = places
        return list(places)

    async def get_place_details(self, google_place_id: str) -> GooglePlaceData | None:
        cached = self._details_cache.get(google_place_id)
        if cached is not None and _has_scoring_fields(cached):
            return cached

        need_photos = cached is None or not cached.photo_name
        field_mask = (
            DETAILS_FIELD_MASK_WITH_PHOTOS if need_photos else DETAILS_FIELD_MASK
        )

        place_id = google_place_id.removeprefix("places/")
        url = PLACE_DETAILS_URL.format(place_id=place_id)
        data = await self._request_json(
            "GET",
            url,
            headers={
                "Content-Type": "application/json",
                "X-Goog-Api-Key": self._api_key,
                "X-Goog-FieldMask": field_mask,
            },
            json_body=None,
            counter_attr="google_details",
        )

        if not data:
            self._details_cache[google_place_id] = None
            return None

        place = _normalize_place(data, fallback_name="")
        if place is not None and cached is not None:
            # Preserve photo metadata from Text Search when Details omit photos.
            if not place.photo_name and cached.photo_name:
                place = place.model_copy(
                    update={
                        "photo_name": cached.photo_name,
                        "photo_attributions": list(cached.photo_attributions),
                    }
                )
        self._details_cache[google_place_id] = place
        if place is not None and place.google_place_id != google_place_id:
            self._details_cache[place.google_place_id] = place
        return place

    def _get_client(self) -> httpx.AsyncClient:
        if self._client is None:
            self._client = httpx.AsyncClient(
                timeout=REQUEST_TIMEOUT_S,
                transport=self._transport,
                limits=httpx.Limits(
                    max_connections=16,
                    max_keepalive_connections=8,
                ),
            )
        return self._client

    async def aclose(self) -> None:
        if self._client is not None:
            await self._client.aclose()
            self._client = None

    async def _request_json(
        self,
        method: str,
        url: str,
        *,
        headers: dict[str, str],
        json_body: dict[str, Any] | None,
        counter_attr: str,
    ) -> dict[str, Any]:
        if self._counter is not None:
            setattr(
                self._counter,
                counter_attr,
                getattr(self._counter, counter_attr) + 1,
            )

        # Never log headers/body — they may include the API key.
        client = self._get_client()
        try:
            resp = await client.request(method, url, headers=headers, json=json_body)
        except httpx.TimeoutException as exc:
            raise ProviderAPIError(
                "Google Places API timed out. Please try again shortly.",
                provider="google",
                status_code=504,
                retryable=True,
            ) from exc
        except httpx.HTTPError as exc:
            logger.warning("Google Places transport error: %s", type(exc).__name__)
            raise ProviderAPIError(
                "Google Places API is temporarily unreachable.",
                provider="google",
                status_code=502,
                retryable=True,
            ) from exc

        if resp.status_code in {401, 403}:
            raise ProviderAPIError(
                "Google Places API authentication failed. Check GOOGLE_PLACES_API_KEY "
                "and Places API (New) enablement.",
                provider="google",
                status_code=502,
            )
        if resp.status_code == 429:
            raise ProviderAPIError(
                "Google Places API quota or rate limit exceeded. Please try again later.",
                provider="google",
                status_code=429,
                retryable=True,
            )
        if resp.status_code == 404:
            return {}
        if resp.status_code >= 400:
            logger.warning("Google Places HTTP %s", resp.status_code)
            # Prefer status-based messages; never forward raw error payloads.
            err_status = _extract_error_status(resp)
            if err_status == "RESOURCE_EXHAUSTED":
                raise ProviderAPIError(
                    "Google Places API quota or rate limit exceeded. Please try again later.",
                    provider="google",
                    status_code=429,
                    retryable=True,
                )
            raise ProviderAPIError(
                "Google Places API returned an error. Check GOOGLE_PLACES_API_KEY "
                "and Places API (New) enablement.",
                provider="google",
                status_code=502,
                retryable=resp.status_code >= 500,
            )

        if not resp.content:
            return {}

        try:
            data = resp.json()
        except ValueError as exc:
            raise ProviderAPIError(
                "Google Places API returned a malformed response.",
                provider="google",
                status_code=502,
            ) from exc

        if not isinstance(data, dict):
            raise ProviderAPIError(
                "Google Places API returned a malformed response.",
                provider="google",
                status_code=502,
            )
        return data


def _extract_error_status(resp: httpx.Response) -> str | None:
    try:
        payload = resp.json()
    except ValueError:
        return None
    if not isinstance(payload, dict):
        return None
    error = payload.get("error")
    if isinstance(error, dict):
        status = error.get("status")
        return str(status) if status else None
    return None


def _has_scoring_fields(place: GooglePlaceData) -> bool:
    return place.rating is not None and place.user_rating_count is not None


def _normalize_place(raw: Any, *, fallback_name: str) -> GooglePlaceData | None:
    """Normalize Places API (New) Place object → GooglePlaceData."""
    if not isinstance(raw, dict):
        return None

    place_id = raw.get("id")
    if not place_id:
        # Resource name form: "places/ChIJ..."
        resource = raw.get("name")
        if isinstance(resource, str) and resource.startswith("places/"):
            place_id = resource.removeprefix("places/")
    if not place_id:
        return None

    display = raw.get("displayName")
    if isinstance(display, dict):
        name = display.get("text") or fallback_name
    elif isinstance(display, str):
        name = display
    else:
        name = fallback_name or ""

    loc = raw.get("location") or {}
    photo_name, photo_attributions = extract_first_photo(raw.get("photos"))
    return GooglePlaceData(
        google_place_id=str(place_id).removeprefix("places/"),
        name=str(name),
        address=raw.get("formattedAddress"),
        latitude=_as_float(loc.get("latitude")),
        longitude=_as_float(loc.get("longitude")),
        rating=_as_float(raw.get("rating")),
        user_rating_count=_as_int(raw.get("userRatingCount")),
        review_metadata=[],
        photo_name=photo_name,
        photo_attributions=photo_attributions,
    )


def _as_float(value: Any) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _as_int(value: Any) -> int | None:
    if value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None
