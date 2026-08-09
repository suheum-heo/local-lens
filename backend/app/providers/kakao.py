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
  - Umbrella cuisine terms (e.g. 양식) expand to related Kakao keywords so places
    tagged as 패밀리레스토랑 / 파스타 still appear when the food intent matches.
  - Specific dish keywords (e.g. 햄버거) drop off-topic Kakao siblings whose
    name/category lack dish relevance tokens.
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
from app.providers.cuisine_queries import (
    expand_food_queries,
    kakao_category_group,
    place_matches_food_keyword,
)
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
        # Grid fan-out is driven by the user's term (맛집), not expanded synonyms.
        origins = _search_origins(
            area.latitude, area.longitude, radius, query=query
        )
        cell_radius = _cell_radius_m(radius, origin_count=len(origins))
        queries = expand_food_queries(query)
        # Cafe intent → CE7; everything else stays FD6 (음식점).
        category_group = kakao_category_group(query)
        jobs = [(q, lat, lon) for q in queries for lat, lon in origins]

        async with httpx.AsyncClient(
            timeout=REQUEST_TIMEOUT_S,
            transport=self._transport,
        ) as client:
            batches = await asyncio.gather(
                *[
                    self._search_at_origin(
                        client,
                        headers=headers,
                        query=q,
                        latitude=lat,
                        longitude=lon,
                        radius_m=cell_radius,
                        category_group_code=category_group,
                    )
                    for q, lat, lon in jobs
                ]
            )

        collected: dict[str, KakaoPlaceData] = {}
        for (q, _lat, _lon), places in zip(jobs, batches, strict=True):
            for place in places:
                if not place_matches_food_keyword(
                    q, name=place.name, category=place.category
                ):
                    continue
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
        category_group_code: str = "FD6",
    ) -> list[KakaoPlaceData]:
        collected: dict[str, KakaoPlaceData] = {}

        def _ingest(documents: list[Any]) -> None:
            for doc in documents:
                place = _normalize_document(doc)
                if place is None:
                    continue
                collected.setdefault(place.kakao_place_id, place)

        async def _fetch_page(page: int) -> dict[str, Any]:
            params = {
                "query": query,
                "x": str(longitude),
                "y": str(latitude),
                "radius": str(radius_m),
                "category_group_code": category_group_code,
                "size": PAGE_SIZE,
                "page": page,
                "sort": "distance",
            }
            return await self._get_json(client, headers=headers, params=params)

        # Page 1 first — if Kakao says is_end, skip the rest (same docs, less RTT).
        first = await _fetch_page(1)
        docs = first.get("documents") or []
        if not docs:
            return []
        _ingest(docs)
        meta = first.get("meta") or {}
        if meta.get("is_end", True) or self._max_pages <= 1:
            return list(collected.values())

        # Use pageable_count when present so we don't over-fetch empty pages.
        pageable = meta.get("pageable_count")
        if isinstance(pageable, int) and pageable > 0:
            last_needed = min(
                self._max_pages,
                max(1, math.ceil(pageable / PAGE_SIZE)),
            )
        else:
            last_needed = self._max_pages
        if last_needed <= 1:
            return list(collected.values())

        # Remaining pages in parallel (same result set as serial fetch).
        extra_pages = list(range(2, last_needed + 1))
        extras = await asyncio.gather(
            *[_fetch_page(page) for page in extra_pages],
            return_exceptions=True,
        )
        for data in extras:
            if isinstance(data, Exception):
                raise data
            _ingest(data.get("documents") or [])

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
