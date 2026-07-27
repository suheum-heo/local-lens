"""Mock Kakao Local provider with sample restaurants."""

from __future__ import annotations

import math

from app.domain.locations import SearchArea
from app.domain.models import KakaoPlaceData
from app.providers.base import KakaoLocalProvider
from app.providers.mock_data import ALL_KAKAO


def _haversine_m(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    r = 6371000.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlmb = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dlmb / 2) ** 2
    return 2 * r * math.asin(math.sqrt(a))


def _matches_query(place: KakaoPlaceData, query: str) -> bool:
    q = query.strip().lower()
    if not q:
        return True
    haystack = " ".join(
        filter(
            None,
            [place.name, place.category or "", place.address or "", place.road_address or ""],
        )
    ).lower()
    # Allow common Korean food keywords to match related categories loosely
    aliases = {
        "삼겹살": ["삼겹", "고기", "육류", "bbq"],
        "국밥": ["국밥"],
        "분식": ["분식"],
        "해물": ["해물", "생선"],
        "이자카야": ["이자카야", "일식"],
        "카페": ["카페"],
        "국수": ["국수", "칼국수"],
        "restaurant": [],
        "맛집": [],
    }
    if q in haystack:
        return True
    for key, extra in aliases.items():
        if key in q or q in key:
            if key in haystack or any(e in haystack for e in extra):
                return True
            if not extra and key in ("맛집", "restaurant"):
                return True
    # Broad fallback: any food query returns all in radius for mock UX
    return len(q) <= 2


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
