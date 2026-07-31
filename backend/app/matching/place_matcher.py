"""Place matching: Kakao candidate → Google Place with confidence."""

from __future__ import annotations

import math
import re
from abc import ABC, abstractmethod
from difflib import SequenceMatcher

from app.domain.enums import MatchConfidenceLevel
from app.domain.models import GooglePlaceData, KakaoPlaceData, PlaceMatchResult
from app.matching.romanize import romanize_compact, romanize_hangul
from app.providers.base import GooglePlacesProvider

# Matches below this confidence are never silently accepted.
MATCH_ACCEPT_THRESHOLD = 0.55
MATCH_HIGH_THRESHOLD = 0.80
MATCH_MEDIUM_THRESHOLD = 0.55
# When Hangul vs Latin names diverge but the candidate is essentially the same
# pin, lean on distance + address so English Google displayNames can still match.
CROSS_SCRIPT_GEO_M = 80.0


class PlaceMatcher(ABC):
    @abstractmethod
    async def match(self, kakao: KakaoPlaceData) -> PlaceMatchResult:
        raise NotImplementedError


class DefaultPlaceMatcher(PlaceMatcher):
    """Score name similarity + geographic distance; reject uncertain matches.

    When Google returns multiple Text Search candidates, pick the highest
    confidence match rather than assuming index 0 is correct.
    """

    def __init__(self, google: GooglePlacesProvider) -> None:
        self._google = google

    async def match(self, kakao: KakaoPlaceData) -> PlaceMatchResult:
        candidates = await self._google.search_places(
            name=kakao.name,
            latitude=kakao.latitude,
            longitude=kakao.longitude,
            address=kakao.road_address or kakao.address,
        )
        if not candidates:
            return PlaceMatchResult(
                confidence=0.0,
                confidence_level=MatchConfidenceLevel.NONE,
                matched=False,
                google=None,
                reason="No Google Places candidate found near this location.",
            )

        scored = [(score_match(kakao, c), c) for c in candidates]
        scored.sort(key=lambda pair: pair[0], reverse=True)
        confidence, candidate = scored[0]
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

        # Prefer Text Search payload when it already has scoring fields to avoid
        # a billable Place Details (New) request.
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

    Cross-script pairs (Kakao Hangul vs Google English) also get a geo+address
    reweight so romanization gaps do not force unmatched below 0.55.
    """
    name_sim = name_similarity(kakao.name, google.name)

    dist: float | None = None
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

    base = name_sim * 0.55 + dist_score * 0.35 + addr_sim * 0.10

    if (
        _scripts_diverge(kakao.name, google.name)
        and dist is not None
        and dist <= CROSS_SCRIPT_GEO_M
        and addr_sim >= 0.25
    ):
        # name 0.25 / dist 0.55 / addr 0.20 — still needs a nearby pin + address cue
        geo_fallback = name_sim * 0.25 + dist_score * 0.55 + addr_sim * 0.20
        base = max(base, geo_fallback)

    return round(base, 4)


def haversine_m(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    r = 6371000.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlmb = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dlmb / 2) ** 2
    return 2 * r * math.asin(math.sqrt(a))


def name_similarity(a: str, b: str) -> float:
    raw = _token_similarity(a, b)

    # Romanize Hangul sides so 명동교자 ≈ Myeongdong Kyoja (g/k variants etc.).
    ra, rb = romanize_hangul(a), romanize_hangul(b)
    ca, cb = romanize_compact(a), romanize_compact(b)
    roman = 0.0
    if ra and rb:
        roman = _token_similarity(ra, rb)
    if ca and cb:
        if ca == cb:
            roman = max(roman, 1.0)
        else:
            ratio = SequenceMatcher(None, ca, cb).ratio()
            if ratio >= 0.9:
                roman = max(roman, 0.95)
            elif ratio >= 0.8:
                roman = max(roman, 0.85)
            elif ratio >= 0.72:
                roman = max(roman, 0.7)
            elif ca in cb or cb in ca:
                shorter = min(len(ca), len(cb))
                if shorter >= 4:
                    roman = max(roman, 0.85)

    return max(raw, roman)


def _token_similarity(a: str, b: str) -> float:
    ta, tb = _tokens(a), _tokens(b)
    if not ta or not tb:
        return 0.0
    ca, cb = _compact(a), _compact(b)
    jaccard = len(ta & tb) / len(ta | tb)
    if ca and cb and (ca in cb or cb in ca):
        jaccard = max(jaccard, 0.75)
    return jaccard


def _scripts_diverge(a: str, b: str) -> bool:
    """True when one side is Hangul-heavy and the other is Latin-heavy."""
    def _flags(s: str) -> tuple[bool, bool]:
        has_hangul = any("\uac00" <= ch <= "\ud7a3" for ch in s)
        has_latin = any("a" <= ch.lower() <= "z" for ch in s if ch.isascii())
        return has_hangul, has_latin

    ah, al = _flags(a)
    bh, bl = _flags(b)
    return (ah and not al and bl and not bh) or (bh and not bl and al and not ah)


def address_similarity(a: str, b: str) -> float:
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
