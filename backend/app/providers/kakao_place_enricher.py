"""Unofficial Kakao Map place-detail enrichment for ratings.

Official Kakao Local keyword search does not return star ratings. This module
fetches public Kakao Map review-tab JSON to populate rating / review_count
when present.

Risk: this endpoint is not an official Kakao developer API. It may break or
violate Kakao ToS if used at scale. Soft-fail per place; never invent zeros.
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass
from typing import Any

import httpx

from app.domain.models import KakaoPlaceData
from app.providers.errors import ApiCallCounter

logger = logging.getLogger(__name__)

# Lighter than panel3 (~40KB / ~150–300ms vs ~76KB / ~500ms+) while still
# exposing score_set.average_score + review_count.
REVIEW_TAB_URL = (
    "https://place-api.map.kakao.com/places/tab/reviews/kakaomap/{place_id}"
)
APP_VERSION = "6.6.0"
REQUEST_TIMEOUT_S = 4.0
DEFAULT_CONCURRENCY = 16
DEFAULT_MAX_PLACES = 80


@dataclass(frozen=True)
class EnrichmentStats:
    """Outcome of one request-scoped enrichment pass."""

    attempted: int = 0
    enriched: int = 0
    failed: int = 0
    skipped: int = 0


class KakaoPlaceEnricher:
    """Enrich KakaoPlaceData.rating / review_count via place-api review tab."""

    def __init__(
        self,
        *,
        transport: httpx.AsyncBaseTransport | None = None,
        counter: ApiCallCounter | None = None,
        concurrency: int = DEFAULT_CONCURRENCY,
        max_places: int = DEFAULT_MAX_PLACES,
        timeout_s: float = REQUEST_TIMEOUT_S,
    ) -> None:
        self._transport = transport
        self._counter = counter
        self._concurrency = max(1, concurrency)
        self._max_places = max(0, max_places)
        self._timeout_s = timeout_s
        self._cache: dict[str, tuple[float | None, int | None]] = {}

    async def enrich_places(self, places: list[KakaoPlaceData]) -> EnrichmentStats:
        """Mutate places in place with parsed ratings when available.

        Places that already have a rating are skipped. Soft-fails leave fields
        missing. At most ``max_places`` unique ids are requested.
        """
        if not places or self._max_places == 0:
            return EnrichmentStats()

        to_enrich: list[KakaoPlaceData] = []
        skipped = 0
        seen: set[str] = set()
        for place in places:
            if place.rating is not None:
                skipped += 1
                continue
            pid = place.kakao_place_id
            if not pid or pid in seen:
                continue
            seen.add(pid)
            if len(to_enrich) >= self._max_places:
                skipped += 1
                continue
            to_enrich.append(place)

        if not to_enrich:
            return EnrichmentStats(skipped=skipped)

        sem = asyncio.Semaphore(self._concurrency)
        enriched = 0
        failed = 0

        async with httpx.AsyncClient(
            timeout=self._timeout_s,
            transport=self._transport,
            headers=_request_headers(),
            limits=httpx.Limits(
                max_connections=self._concurrency,
                max_keepalive_connections=self._concurrency,
            ),
        ) as client:

            async def _one(place: KakaoPlaceData) -> None:
                nonlocal enriched, failed
                async with sem:
                    rating, count = await self._fetch_rating(
                        client, place.kakao_place_id
                    )
                if rating is not None:
                    place.rating = rating
                    if count is not None:
                        place.review_count = count
                    enriched += 1
                else:
                    failed += 1

            await asyncio.gather(*[_one(p) for p in to_enrich])

        return EnrichmentStats(
            attempted=len(to_enrich),
            enriched=enriched,
            failed=failed,
            skipped=skipped,
        )

    async def _fetch_rating(
        self,
        client: httpx.AsyncClient,
        place_id: str,
    ) -> tuple[float | None, int | None]:
        if place_id in self._cache:
            return self._cache[place_id]

        if self._counter is not None:
            self._counter.kakao_place_detail += 1

        url = REVIEW_TAB_URL.format(place_id=place_id)
        try:
            resp = await client.get(url)
        except httpx.TimeoutException:
            logger.debug("Kakao place-detail timeout for %s", place_id)
            result: tuple[float | None, int | None] = (None, None)
            self._cache[place_id] = result
            return result
        except httpx.HTTPError as exc:
            logger.debug(
                "Kakao place-detail transport error for %s: %s",
                place_id,
                type(exc).__name__,
            )
            result = (None, None)
            self._cache[place_id] = result
            return result

        if resp.status_code != 200:
            result = (None, None)
            self._cache[place_id] = result
            return result

        try:
            data = resp.json()
        except ValueError:
            result = (None, None)
            self._cache[place_id] = result
            return result

        parsed = parse_place_detail_scores(data)
        self._cache[place_id] = parsed
        return parsed


def parse_place_detail_scores(data: Any) -> tuple[float | None, int | None]:
    """Extract average_score / review_count from review-tab or panel3 JSON.

    Returns (None, None) when fields are missing or non-numeric — never 0
    invented from absence.
    """
    if not isinstance(data, dict):
        return (None, None)

    score_set = data.get("score_set")
    if not isinstance(score_set, dict):
        review = data.get("kakaomap_review")
        if isinstance(review, dict):
            score_set = review.get("score_set")
    if not isinstance(score_set, dict):
        return (None, None)

    rating: float | None = None
    count: int | None = None

    raw_score = score_set.get("average_score")
    if raw_score is not None:
        try:
            rating = float(raw_score)
        except (TypeError, ValueError):
            rating = None

    raw_count = score_set.get("review_count")
    if raw_count is not None:
        try:
            count = int(raw_count)
        except (TypeError, ValueError):
            count = None

    if rating is None:
        return (None, None)
    return (rating, count)


# Back-compat alias for older tests/imports.
parse_panel3_scores = parse_place_detail_scores


def _request_headers() -> dict[str, str]:
    return {
        "Accept": "application/json, text/plain, */*",
        "User-Agent": (
            "Mozilla/5.0 (compatible; LocalLens/0.1; +https://github.com/local-lens)"
        ),
        "Referer": "https://place.map.kakao.com/",
        "Origin": "https://place.map.kakao.com",
        "appVersion": APP_VERSION,
        "pf": "PC",
    }
