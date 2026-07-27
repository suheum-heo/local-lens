"""Live Google Places API provider (requires GOOGLE_PLACES_API_KEY).

Endpoints (Places API — Find Place / Place Details):
  GET https://maps.googleapis.com/maps/api/place/findplacefromtext/json
  GET https://maps.googleapis.com/maps/api/place/details/json

Cost control:
  - Request-scoped in-memory caches for find_place and get_place_details
  - Find Place requests only fields needed for matching + scoring
  - Place Details is optional; callers should skip it when Find Place already
    returned rating + user_ratings_total
"""

from __future__ import annotations

import logging
from typing import Any

import httpx

from app.config import settings
from app.domain.models import GooglePlaceData
from app.providers.base import GooglePlacesProvider
from app.providers.errors import ApiCallCounter, ProviderAPIError, ProviderConfigError

logger = logging.getLogger(__name__)

FIND_PLACE_URL = "https://maps.googleapis.com/maps/api/place/findplacefromtext/json"
DETAILS_URL = "https://maps.googleapis.com/maps/api/place/details/json"

FIND_PLACE_FIELDS = (
    "place_id,name,formatted_address,geometry,rating,user_ratings_total"
)
# Details only when Find Place lacks scoring fields; reviews are optional metadata.
DETAILS_FIELDS = (
    "place_id,name,formatted_address,geometry,rating,user_ratings_total,reviews"
)

REQUEST_TIMEOUT_S = 15.0
# Bias Find Place to the Kakao coordinates so distant namesakes are less likely.
FIND_LOCATION_BIAS_RADIUS_M = 500


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
        # Request-scoped caches (provider is constructed per search).
        self._find_cache: dict[tuple[str, float, float, str], GooglePlaceData | None] = {}
        self._details_cache: dict[str, GooglePlaceData | None] = {}

    async def find_place(
        self,
        name: str,
        latitude: float,
        longitude: float,
        address: str | None = None,
    ) -> GooglePlaceData | None:
        cache_key = (
            name.strip(),
            round(latitude, 5),
            round(longitude, 5),
            (address or "").strip(),
        )
        if cache_key in self._find_cache:
            return self._find_cache[cache_key]

        input_text = f"{name} {address}".strip() if address else name
        params = {
            "input": input_text,
            "inputtype": "textquery",
            "fields": FIND_PLACE_FIELDS,
            "locationbias": (
                f"circle:{FIND_LOCATION_BIAS_RADIUS_M}@{latitude},{longitude}"
            ),
            "key": self._api_key,
            "language": "ko",
        }

        data = await self._get_json(
            FIND_PLACE_URL,
            params=params,
            counter_attr="google_find_place",
        )
        status = data.get("status")
        if status == "ZERO_RESULTS":
            self._find_cache[cache_key] = None
            return None
        if status != "OK":
            self._raise_google_status(status, data.get("error_message"))

        candidates = data.get("candidates") or []
        if not candidates:
            self._find_cache[cache_key] = None
            return None

        place = _normalize_candidate(candidates[0], fallback_name=name)
        self._find_cache[cache_key] = place
        if place is not None:
            # Seed details cache so a later details call can reuse if identical.
            self._details_cache.setdefault(place.google_place_id, place)
        return place

    async def get_place_details(self, google_place_id: str) -> GooglePlaceData | None:
        if google_place_id in self._details_cache:
            cached = self._details_cache[google_place_id]
            # If cache only has Find Place payload without reviews but has scores,
            # still return it — callers decide whether details are required.
            if cached is not None and _has_scoring_fields(cached):
                return cached

        params = {
            "place_id": google_place_id,
            "fields": DETAILS_FIELDS,
            "key": self._api_key,
            "language": "ko",
            "reviews_no_translations": "true",
        }
        data = await self._get_json(
            DETAILS_URL,
            params=params,
            counter_attr="google_details",
        )
        status = data.get("status")
        if status == "NOT_FOUND" or status == "ZERO_RESULTS":
            self._details_cache[google_place_id] = None
            return None
        if status != "OK":
            self._raise_google_status(status, data.get("error_message"))

        result = data.get("result")
        if not result:
            self._details_cache[google_place_id] = None
            return None

        place = _normalize_details(result)
        self._details_cache[google_place_id] = place
        return place

    async def _get_json(
        self,
        url: str,
        *,
        params: dict[str, Any],
        counter_attr: str,
    ) -> dict[str, Any]:
        if self._counter is not None:
            setattr(self._counter, counter_attr, getattr(self._counter, counter_attr) + 1)

        # Never log params — they contain the API key.
        async with httpx.AsyncClient(
            timeout=REQUEST_TIMEOUT_S,
            transport=self._transport,
        ) as client:
            try:
                resp = await client.get(url, params=params)
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

        if resp.status_code >= 400:
            logger.warning("Google Places HTTP %s", resp.status_code)
            raise ProviderAPIError(
                "Google Places API returned an error.",
                provider="google",
                status_code=502,
                retryable=resp.status_code >= 500,
            )

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

    def _raise_google_status(self, status: str | None, error_message: Any) -> None:
        # Do not surface Google's raw error_message to clients — may leak config hints.
        logger.warning("Google Places status=%s", status)
        if status in {"OVER_QUERY_LIMIT", "RESOURCE_EXHAUSTED"}:
            raise ProviderAPIError(
                "Google Places API quota or rate limit exceeded. Please try again later.",
                provider="google",
                status_code=429,
                retryable=True,
            )
        if status in {"REQUEST_DENIED", "INVALID_REQUEST"}:
            raise ProviderAPIError(
                "Google Places API rejected the request. Check GOOGLE_PLACES_API_KEY "
                "and Places API enablement.",
                provider="google",
                status_code=502,
            )
        if status == "UNKNOWN_ERROR":
            raise ProviderAPIError(
                "Google Places API reported a temporary error.",
                provider="google",
                status_code=502,
                retryable=True,
            )
        raise ProviderAPIError(
            "Google Places API returned an unexpected status.",
            provider="google",
            status_code=502,
        )


def _has_scoring_fields(place: GooglePlaceData) -> bool:
    return place.rating is not None and place.user_rating_count is not None


def _normalize_candidate(c: Any, *, fallback_name: str) -> GooglePlaceData | None:
    if not isinstance(c, dict):
        return None
    place_id = c.get("place_id")
    if not place_id:
        return None
    loc = (c.get("geometry") or {}).get("location") or {}
    return GooglePlaceData(
        google_place_id=str(place_id),
        name=c.get("name") or fallback_name,
        address=c.get("formatted_address"),
        latitude=_as_float(loc.get("lat")),
        longitude=_as_float(loc.get("lng")),
        rating=_as_float(c.get("rating")),
        user_rating_count=_as_int(c.get("user_ratings_total")),
        review_metadata=[],
    )


def _normalize_details(result: dict[str, Any]) -> GooglePlaceData:
    loc = (result.get("geometry") or {}).get("location") or {}
    reviews = result.get("reviews") or []
    review_metadata: list[dict[str, Any]] = []
    for r in reviews:
        if not isinstance(r, dict):
            continue
        review_metadata.append(
            {
                "language": r.get("language"),
                "rating": r.get("rating"),
                "text": r.get("text"),
            }
        )
    return GooglePlaceData(
        google_place_id=str(result["place_id"]),
        name=result.get("name") or "",
        address=result.get("formatted_address"),
        latitude=_as_float(loc.get("lat")),
        longitude=_as_float(loc.get("lng")),
        rating=_as_float(result.get("rating")),
        user_rating_count=_as_int(result.get("user_ratings_total")),
        review_metadata=review_metadata,
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
