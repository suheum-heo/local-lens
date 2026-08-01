"""Live Kakao Local REST API provider (requires KAKAO_REST_API_KEY).

Endpoint:
  GET https://dapi.kakao.com/v2/local/search/keyword.json

Notes:
  - Keyword search returns place metadata (id, name, address, coords, category, URL).
  - It does NOT return star ratings or review counts — live mode may fill those via
    ``KakaoPlaceEnricher`` (unofficial place-detail), not this provider.
  - Neighborhood searches use the catalog centroid + radius; Kakao does not expose
    official administrative-boundary filtering in this API.
  - Kakao pageable results cap at ~45 per query+origin. Broad food queries therefore
    fan out across a small grid of origins and merge/dedupe within the search radius.
"""

from __future__ import annotations

import asyncio
import logging
import math
from typing import Any

import httpx

from app.config import settings
from app.domain.contracts import DEFAULT_FOOD_QUERY
from app.domain.locations import SearchArea
from app.domain.models import KakaoPlaceData
from app.providers.base import KakaoLocalProvider
from app.providers.errors import ApiCallCounter, ProviderAPIError, ProviderConfigError

logger = logging.getLogger(__name__)

KAKAO_KEYWORD_URL = "https://dapi.kakao.com/v2/local/search/keyword.json"

# Kakao allows size ≤ 15 and page ≤ 45; we cap pages to control latency/quota.
PAGE_SIZE = 15
MAX_PAGES_PER_AREA = 3  # ≤ 45 candidates per origin
REQUEST_TIMEOUT_S = 15.0

# Empty / generic food queries hit Kakao's ~45-result ceiling near dense areas.
# Multi-origin sampling recovers places that sit just outside the nearest pack.
BROAD_FOOD_QUERIES = frozenset(
    {
        DEFAULT_FOOD_QUERY.lower(),
        "restaurant",
        "restaurants",
        "food",
        "맛집추천",
    }
)


class LiveKakaoLocalProvider(KakaoLocalProvider):
    def __init__(
        self,
        api_key: str | None = None,
        *,
        transport: httpx.AsyncBaseTransport | None = None,
        counter: ApiCallCounter | None = None,
        max_pages: int = MAX_PAGES_PER_AREA,
    ) -> None:
        self._api_key = api_key if api_key is not None else settings.kakao_rest_api_key
        if not self._api_key:
            raise ProviderConfigError(
                "PROVIDER_MODE=live requires KAKAO_REST_API_KEY to be set"
            )
        self._transport = transport
        self._counter = counter
        self._max_pages = max(1, min(max_pages, 45))

    async def search_restaurants(
        self,
        area: SearchArea,
        query: str,
    ) -> list[KakaoPlaceData]:
        headers = {"Authorization": f"KakaoAK {self._api_key}"}
        radius = min(max(area.radius_m, 1), 20000)
        origins = _search_origins(
            area.latitude, area.longitude, radius, query=query
        )
        cell_radius = _cell_radius_m(radius, origin_count=len(origins))

        async with httpx.AsyncClient(
            timeout=REQUEST_TIMEOUT_S,
            transport=self._transport,
        ) as client:
            batches = await asyncio.gather(
                *[
                    self._search_at_origin(
                        client,
                        headers=headers,
                        query=query,
                        latitude=lat,
                        longitude=lon,
                        radius_m=cell_radius,
                    )
                    for lat, lon in origins
                ]
            )

        collected: dict[str, KakaoPlaceData] = {}
        for places in batches:
            for place in places:
                if (
                    _haversine_m(
                        area.latitude,
                        area.longitude,
                        place.latitude,
                        place.longitude,
                    )
                    > radius
                ):
                    continue
                collected.setdefault(place.kakao_place_id, place)
        return list(collected.values())

    async def _search_at_origin(
        self,
        client: httpx.AsyncClient,
        *,
        headers: dict[str, str],
        query: str,
        latitude: float,
        longitude: float,
        radius_m: int,
    ) -> list[KakaoPlaceData]:
        collected: dict[str, KakaoPlaceData] = {}
        for page in range(1, self._max_pages + 1):
            params = {
                "query": query,
                "x": str(longitude),
                "y": str(latitude),
                "radius": str(radius_m),
                "category_group_code": "FD6",  # food
                "size": PAGE_SIZE,
                "page": page,
                "sort": "distance",
            }
            data = await self._get_json(client, headers=headers, params=params)
            documents = data.get("documents") or []
            if not documents:
                break

            for doc in documents:
                place = _normalize_document(doc)
                if place is None:
                    continue
                collected.setdefault(place.kakao_place_id, place)

            meta = data.get("meta") or {}
            if meta.get("is_end", True):
                break

        return list(collected.values())

    async def _get_json(
        self,
        client: httpx.AsyncClient,
        *,
        headers: dict[str, str],
        params: dict[str, Any],
    ) -> dict[str, Any]:
        if self._counter is not None:
            self._counter.kakao_keyword += 1
        try:
            resp = await client.get(KAKAO_KEYWORD_URL, headers=headers, params=params)
        except httpx.TimeoutException as exc:
            raise ProviderAPIError(
                "Kakao Local API timed out. Please try again shortly.",
                provider="kakao",
                status_code=504,
                retryable=True,
            ) from exc
        except httpx.HTTPError as exc:
            logger.warning("Kakao Local transport error: %s", type(exc).__name__)
            raise ProviderAPIError(
                "Kakao Local API is temporarily unreachable.",
                provider="kakao",
                status_code=502,
                retryable=True,
            ) from exc

        if resp.status_code == 401:
            raise ProviderAPIError(
                "Kakao Local API authentication failed. Check KAKAO_REST_API_KEY.",
                provider="kakao",
                status_code=502,
            )
        if resp.status_code == 403:
            raise ProviderAPIError(
                "Kakao Local API access was denied for this key.",
                provider="kakao",
                status_code=502,
            )
        if resp.status_code == 429:
            raise ProviderAPIError(
                "Kakao Local API rate limit exceeded. Please try again later.",
                provider="kakao",
                status_code=429,
                retryable=True,
            )
        if resp.status_code >= 400:
            logger.warning("Kakao Local HTTP %s", resp.status_code)
            raise ProviderAPIError(
                "Kakao Local API returned an error.",
                provider="kakao",
                status_code=502,
                retryable=resp.status_code >= 500,
            )

        try:
            data = resp.json()
        except ValueError as exc:
            raise ProviderAPIError(
                "Kakao Local API returned a malformed response.",
                provider="kakao",
                status_code=502,
            ) from exc

        if not isinstance(data, dict):
            raise ProviderAPIError(
                "Kakao Local API returned a malformed response.",
                provider="kakao",
                status_code=502,
            )
        return data


def _is_broad_food_query(query: str) -> bool:
    return query.strip().lower() in BROAD_FOOD_QUERIES


def _cell_radius_m(area_radius_m: int, *, origin_count: int) -> int:
    """Smaller cells per origin so each request surfaces a different nearest pack."""
    if origin_count <= 1:
        return area_radius_m
    # ~600m cells shift Kakao's distance-sorted top-45 enough to cover gaps.
    return min(area_radius_m, max(500, int(area_radius_m * 0.6)))


def _search_origins(
    latitude: float,
    longitude: float,
    radius_m: int,
    *,
    query: str,
) -> list[tuple[float, float]]:
    """Return search centroids. Broad queries use a tight cardinal grid.

    Kakao returns at most ~45 pageable hits per origin. A single center therefore
    misses in-radius places that are not among the nearest pack (e.g. dense
    station areas). ~200–280 m steps reliably expose those neighbors.
    """
    if not _is_broad_food_query(query) or radius_m < 500:
        return [(latitude, longitude)]

    step_m = min(max(int(radius_m * 0.25), 180), 280)
    dlat = step_m / 111_320.0
    cos_lat = max(math.cos(math.radians(latitude)), 0.2)
    dlon = step_m / (111_320.0 * cos_lat)

    origins: list[tuple[float, float]] = [(latitude, longitude)]
    rings = 2 if radius_m >= 1200 else 1
    for ring in range(1, rings + 1):
        s = float(ring)
        origins.extend(
            [
                (latitude + s * dlat, longitude),
                (latitude - s * dlat, longitude),
                (latitude, longitude + s * dlon),
                (latitude, longitude - s * dlon),
            ]
        )
    return origins


def _haversine_m(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    r = 6_371_000.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp = math.radians(lat2 - lat1)
    dl = math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * r * math.asin(min(1.0, math.sqrt(a)))


def _normalize_document(doc: Any) -> KakaoPlaceData | None:
    """Map a Kakao keyword-search document to KakaoPlaceData.

    Ratings/review counts are intentionally omitted — the official keyword API
    does not provide them.
    """
    if not isinstance(doc, dict):
        return None
    place_id = doc.get("id")
    name = doc.get("place_name")
    x = doc.get("x")
    y = doc.get("y")
    if not place_id or not name or x is None or y is None:
        return None
    try:
        longitude = float(x)
        latitude = float(y)
    except (TypeError, ValueError):
        return None

    road = doc.get("road_address_name") or None
    if isinstance(road, str) and not road.strip():
        road = None

    return KakaoPlaceData(
        kakao_place_id=str(place_id),
        name=str(name),
        address=doc.get("address_name") or None,
        road_address=road,
        latitude=latitude,
        longitude=longitude,
        category=doc.get("category_name") or None,
        place_url=doc.get("place_url") or None,
        # Explicitly leave rating/review_count unset (missing-data semantics).
        rating=None,
        review_count=None,
    )
