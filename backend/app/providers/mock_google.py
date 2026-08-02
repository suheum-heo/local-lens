"""Mock Google Places provider."""

from __future__ import annotations

import math

from app.domain.models import GooglePlaceData
from app.providers.base import GooglePlacesProvider
from app.providers.mock_data import ALL_GOOGLE, GOOGLE_BY_KAKAO_ID


def _haversine_m(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    r = 6371000.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlmb = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dlmb / 2) ** 2
    return 2 * r * math.asin(math.sqrt(a))


class MockGooglePlacesProvider(GooglePlacesProvider):
    """Returns pre-seeded Google places near a query coordinate."""

    async def search_places(
        self,
        name: str,
        latitude: float,
        longitude: float,
        address: str | None = None,
        *,
        included_type: str = "restaurant",
    ) -> list[GooglePlaceData]:
        del included_type  # mock catalog is type-agnostic
        ranked: list[tuple[float, GooglePlaceData]] = []

        for place in ALL_GOOGLE:
            if place.latitude is None or place.longitude is None:
                continue
            dist = _haversine_m(latitude, longitude, place.latitude, place.longitude)
            if dist > 2000:
                continue
            name_score = _name_similarity(name, place.name)
            score = name_score * 0.7 + max(0.0, 1.0 - dist / 2000) * 0.3
            if score >= 0.25:
                ranked.append((score, place))

        ranked.sort(key=lambda pair: pair[0], reverse=True)
        # Return up to a few nearby candidates so the matcher can choose.
        return [place for _, place in ranked[:5]]

    async def get_place_details(self, google_place_id: str) -> GooglePlaceData | None:
        for place in ALL_GOOGLE:
            if place.google_place_id == google_place_id:
                return place
        return None

    async def get_linked_for_kakao(self, kakao_place_id: str) -> GooglePlaceData | None:
        """Test helper — not part of the public provider interface."""
        return GOOGLE_BY_KAKAO_ID.get(kakao_place_id)


def _name_similarity(a: str, b: str) -> float:
    """Simple token Jaccard over normalized strings (Korean + Latin)."""
    ta = _tokens(a)
    tb = _tokens(b)
    if not ta or not tb:
        return 0.0
    inter = len(ta & tb)
    union = len(ta | tb)
    return inter / union if union else 0.0


def _tokens(s: str) -> set[str]:
    normalized = s.lower().replace(",", " ").replace("-", " ")
    parts = {p for p in normalized.split() if p}
    compact = "".join(
        ch for ch in normalized if ch.isalnum() or "\uac00" <= ch <= "\ud7a3"
    )
    if len(compact) >= 2:
        parts |= {compact[i : i + 2] for i in range(len(compact) - 1)}
    return parts
