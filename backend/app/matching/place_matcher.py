"""Place matching: Kakao candidate → Google Place with confidence."""

from __future__ import annotations

import math
import re
from abc import ABC, abstractmethod

from app.domain.enums import MatchConfidenceLevel
from app.domain.models import GooglePlaceData, KakaoPlaceData, PlaceMatchResult
from app.providers.base import GooglePlacesProvider

# Matches below this confidence are never silently accepted.
MATCH_ACCEPT_THRESHOLD = 0.55
MATCH_HIGH_THRESHOLD = 0.80
MATCH_MEDIUM_THRESHOLD = 0.55


class PlaceMatcher(ABC):
    @abstractmethod
    async def match(self, kakao: KakaoPlaceData) -> PlaceMatchResult:
        raise NotImplementedError


class DefaultPlaceMatcher(PlaceMatcher):
    """Score name similarity + geographic distance; reject uncertain matches."""

    def __init__(self, google: GooglePlacesProvider) -> None:
        self._google = google

    async def match(self, kakao: KakaoPlaceData) -> PlaceMatchResult:
        candidate = await self._google.find_place(
            name=kakao.name,
            latitude=kakao.latitude,
            longitude=kakao.longitude,
            address=kakao.road_address or kakao.address,
        )
        if candidate is None:
            return PlaceMatchResult(
                confidence=0.0,
                confidence_level=MatchConfidenceLevel.NONE,
                matched=False,
                google=None,
                reason="No Google Places candidate found near this location.",
            )

        confidence = score_match(kakao, candidate)
        level = confidence_level(confidence)
        accepted = confidence >= MATCH_ACCEPT_THRESHOLD

        if not accepted:
            return PlaceMatchResult(
                confidence=confidence,
                confidence_level=level,
                matched=False,
                google=None,
                reason=(
                    f"Possible Google match '{candidate.name}' found but confidence "
                    f"{confidence:.2f} is below the accept threshold "
                    f"({MATCH_ACCEPT_THRESHOLD}). Not matched."
                ),
            )

        # Prefer Find Place payload when it already has scoring fields to avoid
        # a billable Place Details request. Fetch details only when needed.
        google = candidate
        if candidate.rating is None or candidate.user_rating_count is None:
            details = await self._google.get_place_details(candidate.google_place_id)
            if details is not None:
                google = details

        return PlaceMatchResult(
            confidence=confidence,
            confidence_level=level,
            matched=True,
            google=google,
            reason=None,
        )


def confidence_level(confidence: float) -> MatchConfidenceLevel:
    if confidence >= MATCH_HIGH_THRESHOLD:
        return MatchConfidenceLevel.HIGH
    if confidence >= MATCH_MEDIUM_THRESHOLD:
        return MatchConfidenceLevel.MEDIUM
    if confidence > 0:
        return MatchConfidenceLevel.LOW
    return MatchConfidenceLevel.NONE


def score_match(kakao: KakaoPlaceData, google: GooglePlaceData) -> float:
    """
    Weighted confidence in [0, 1]:
      - name similarity (0.55)
      - distance proximity (0.35)
      - address token overlap (0.10)
    """
    name_sim = name_similarity(kakao.name, google.name)

    if google.latitude is not None and google.longitude is not None:
        dist = haversine_m(
            kakao.latitude, kakao.longitude, google.latitude, google.longitude
        )
        # 0m → 1.0, 150m → ~0.5, 500m+ → ~0
        dist_score = max(0.0, 1.0 - dist / 500.0)
    else:
        dist_score = 0.0

    addr_a = kakao.road_address or kakao.address or ""
    addr_b = google.address or ""
    addr_sim = address_similarity(addr_a, addr_b) if addr_a and addr_b else 0.0

    return round(name_sim * 0.55 + dist_score * 0.35 + addr_sim * 0.10, 4)


def haversine_m(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    r = 6371000.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlmb = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dlmb / 2) ** 2
    return 2 * r * math.asin(math.sqrt(a))


def name_similarity(a: str, b: str) -> float:
    ta, tb = _tokens(a), _tokens(b)
    if not ta or not tb:
        return 0.0
    # Also compare transliteration-agnostic compact forms
    ca, cb = _compact(a), _compact(b)
    jaccard = len(ta & tb) / len(ta | tb)
    if ca and cb and (ca in cb or cb in ca):
        jaccard = max(jaccard, 0.75)
    return jaccard


def address_similarity(a: str, b: str) -> float:
    # Digits and key locality tokens
    da, db = set(re.findall(r"\d+", a)), set(re.findall(r"\d+", b))
    digit_score = (len(da & db) / len(da | db)) if da and db else 0.0
    ta, tb = _tokens(a), _tokens(b)
    tok_score = (len(ta & tb) / len(ta | tb)) if ta and tb else 0.0
    return 0.5 * digit_score + 0.5 * tok_score


def _compact(s: str) -> str:
    return "".join(
        ch for ch in s.lower() if ch.isalnum() or "\uac00" <= ch <= "\ud7a3"
    )


def _tokens(s: str) -> set[str]:
    normalized = s.lower().replace(",", " ").replace("-", " ")
    parts = {p for p in re.split(r"\s+", normalized) if p}
    compact = _compact(s)
    if len(compact) >= 2:
        parts |= {compact[i : i + 2] for i in range(len(compact) - 1)}
    return parts
