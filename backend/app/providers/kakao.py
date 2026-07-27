"""Live Kakao Local REST API provider (requires KAKAO_REST_API_KEY)."""

from __future__ import annotations

import httpx

from app.config import settings
from app.domain.locations import SearchArea
from app.domain.models import KakaoPlaceData
from app.providers.base import KakaoLocalProvider

KAKAO_KEYWORD_URL = "https://dapi.kakao.com/v2/local/search/keyword.json"


class LiveKakaoLocalProvider(KakaoLocalProvider):
    def __init__(self, api_key: str | None = None) -> None:
        self._api_key = api_key or settings.kakao_rest_api_key
        if not self._api_key:
            raise ValueError("KAKAO_REST_API_KEY is required for live Kakao provider")

    async def search_restaurants(
        self,
        area: SearchArea,
        query: str,
    ) -> list[KakaoPlaceData]:
        headers = {"Authorization": f"KakaoAK {self._api_key}"}
        params = {
            "query": query,
            "x": str(area.longitude),
            "y": str(area.latitude),
            "radius": str(min(area.radius_m, 20000)),
            "category_group_code": "FD6",  # food
            "size": 15,
        }
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.get(KAKAO_KEYWORD_URL, headers=headers, params=params)
            resp.raise_for_status()
            data = resp.json()

        results: list[KakaoPlaceData] = []
        for doc in data.get("documents", []):
            results.append(
                KakaoPlaceData(
                    kakao_place_id=doc["id"],
                    name=doc["place_name"],
                    address=doc.get("address_name"),
                    road_address=doc.get("road_address_name") or None,
                    latitude=float(doc["y"]),
                    longitude=float(doc["x"]),
                    category=doc.get("category_name"),
                    place_url=doc.get("place_url"),
                )
            )
        return results
