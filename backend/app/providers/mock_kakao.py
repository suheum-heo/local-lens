"""Mock Kakao Local provider with sample restaurants."""

from __future__ import annotations

import math

from app.domain.locations import SearchArea
from app.domain.models import KakaoPlaceData
from app.providers.base import KakaoLocalProvider
from app.providers.cuisine_queries import expand_food_queries
from app.providers.mock_data import ALL_KAKAO


def _haversine_m(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    r = 6371000.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlmb = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dlmb / 2) ** 2
    return 2 * r * math.asin(math.sqrt(a))


def _matches_query(place: KakaoPlaceData, query: str) -> bool:
    terms = expand_food_queries(query)
    haystack = " ".join(
        filter(
            None,
            [place.name, place.category or "", place.address or "", place.road_address or ""],
        )
    ).lower()
    for term in terms:
        q = term.strip().lower()
        if not q:
            return True
        if q in haystack:
            return True
        # Broad fallback for short / generic food queries in mock UX
        if q in ("맛집", "restaurant", "restaurants", "food") or len(q) <= 2:
            return True
    return False


class MockKakaoLocalProvider(KakaoLocalProvider):
    async def search_restaurants(
        self,
        area: SearchArea,
        query: str,
    ) -> list[KakaoPlaceData]:
        results: list[KakaoPlaceData] = []
        for place in ALL_KAKAO:
            dist = _haversine_m(
                area.latitude, area.longitude, place.latitude, place.longitude
            )
            if dist <= area.radius_m and _matches_query(place, query):
                results.append(place)
        return results
