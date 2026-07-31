"""Live Kakao Local REST API provider (requires KAKAO_REST_API_KEY).

Endpoint:
  GET https://dapi.kakao.com/v2/local/search/keyword.json

Notes:
  - Keyword search returns place metadata (id, name, address, coords, category, URL).
  - It does NOT return star ratings or review counts — live mode may fill those via
    ``KakaoPlaceEnricher`` (unofficial place-detail), not this provider.
  - Neighborhood searches use the catalog centroid + radius; Kakao does not expose
    official administrative-boundary filtering in this API.
"""

from __future__ import annotations

import logging
from typing import Any

import httpx

from app.config import settings
from app.domain.locations import SearchArea
from app.domain.models import KakaoPlaceData
from app.providers.base import KakaoLocalProvider
from app.providers.errors import ApiCallCounter, ProviderAPIError, ProviderConfigError

logger = logging.getLogger(__name__)

KAKAO_KEYWORD_URL = "https://dapi.kakao.com/v2/local/search/keyword.json"

# Kakao allows size ≤ 15 and page ≤ 45; we cap pages to control latency/quota.
PAGE_SIZE = 15
MAX_PAGES_PER_AREA = 3  # ≤ 45 candidates per SearchArea
REQUEST_TIMEOUT_S = 15.0


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
        collected: dict[str, KakaoPlaceData] = {}

        async with httpx.AsyncClient(
            timeout=REQUEST_TIMEOUT_S,
            transport=self._transport,
        ) as client:
            for page in range(1, self._max_pages + 1):
                params = {
                    "query": query,
                    "x": str(area.longitude),
                    "y": str(area.latitude),
                    "radius": str(radius),
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
