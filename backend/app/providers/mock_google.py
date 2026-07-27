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

    async def find_place(
        self,
        name: str,
        latitude: float,
        longitude: float,
        address: str | None = None,
    ) -> GooglePlaceData | None:
        # Prefer exact mock linkage via proximity + name overlap
        best: GooglePlaceData | None = None
        best_score = -1.0

        for place in ALL_GOOGLE:
            if place.latitude is None or place.longitude is None:
                continue
            dist = _haversine_m(latitude, longitude, place.latitude, place.longitude)
            if dist > 2000:
                continue
            name_score = _name_similarity(name, place.name)
            # Closer + more similar name wins
            score = name_score * 0.7 + max(0.0, 1.0 - dist / 2000) * 0.3
            if score > best_score:
                best_score = score
                best = place

        # Also expose intentional "missing" cases: if the Kakao id maps to None
        # and the best nearby place is far/name-mismatched, return None.
        if best is None or best_score < 0.25:
            return None
        return best

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
    # Keep Hangul syllables and alphanumerics as separate tokens when spaced;
    # also emit character bigrams for Hangul-heavy strings without spaces.
    normalized = s.lower().replace(",", " ").replace("-", " ")
    parts = {p for p in normalized.split() if p}
    compact = "".join(ch for ch in normalized if ch.isalnum() or "\uac00" <= ch <= "\ud7a3")
    if len(compact) >= 2:
        parts |= {compact[i : i + 2] for i in range(len(compact) - 1)}
    return parts
