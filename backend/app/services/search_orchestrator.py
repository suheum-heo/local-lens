"""Search orchestration: locations → Kakao → dedupe → enrich∥match → score."""

from __future__ import annotations

import asyncio

from app.config import settings
from app.domain.contracts import SearchMeta, SearchRequest, SearchResponse
from app.domain.enums import RatingCoverage
from app.domain.locations import SearchArea
from app.domain.models import PlaceMatchResult, Restaurant
from app.domain.rating_coverage import classify_rating_coverage
from app.matching.place_matcher import DefaultPlaceMatcher, PlaceMatcher
from app.normalization.restaurant import NormalizedCandidate, normalize_and_dedupe
from app.providers.base import GooglePlacesProvider, KakaoLocalProvider
from app.providers.errors import ApiCallCounter
from app.providers.factory import get_google_provider, get_kakao_provider
from app.providers.kakao_place_enricher import EnrichmentStats, KakaoPlaceEnricher
from app.scoring.engine import ScoringEngine, SimpleScoringEngine

# Google Text Search is the other major latency driver; bound concurrency
# to stay under typical rate limits while overlapping with Kakao enrichment.
GOOGLE_MATCH_CONCURRENCY = 8


class SearchOrchestrator:
    def __init__(
        self,
        kakao: KakaoLocalProvider | None = None,
        google: GooglePlacesProvider | None = None,
        matcher: PlaceMatcher | None = None,
        scoring: ScoringEngine | None = None,
        counter: ApiCallCounter | None = None,
        enricher: KakaoPlaceEnricher | None = None,
        *,
        enable_kakao_enrichment: bool | None = None,
        google_match_concurrency: int = GOOGLE_MATCH_CONCURRENCY,
    ) -> None:
        self._counter = counter
        self._kakao = kakao or get_kakao_provider(counter=counter)
        self._google = google or get_google_provider(counter=counter)
        self._matcher = matcher or DefaultPlaceMatcher(self._google)
        self._scoring = scoring or SimpleScoringEngine()
        if enable_kakao_enrichment is None:
            enable_kakao_enrichment = not settings.use_mock_providers
        self._enable_kakao_enrichment = enable_kakao_enrichment
        self._enricher = enricher
        self._google_match_concurrency = max(1, google_match_concurrency)

    async def search(self, request: SearchRequest) -> SearchResponse:
        areas = [SearchArea.from_location(loc) for loc in request.locations]

        # Parallel keyword search across selected areas.
        area_place_lists = await asyncio.gather(
            *[
                self._kakao.search_restaurants(area, request.query)
                for area in areas
            ]
        )
        area_results = [
            (area.area_id, places)
            for area, places in zip(areas, area_place_lists, strict=True)
        ]

        # Dedupe BEFORE enrichment / Google matching so each Kakao place is
        # processed once.
        candidates = normalize_and_dedupe(area_results)

        # Enrichment and Google matching are independent — overlap them.
        enrichment_task = asyncio.create_task(
            self._enrich_candidates(candidates)
        )
        matches_task = asyncio.create_task(self._match_candidates(candidates))
        enrichment_stats, matches = await asyncio.gather(
            enrichment_task, matches_task
        )

        restaurants: list[Restaurant] = []
        for candidate, match in zip(candidates, matches, strict=True):
            scores, label = self._scoring.score(candidate.kakao, match)
            coverage = classify_rating_coverage(candidate.kakao, match)
            restaurants.append(
                Restaurant(
                    restaurant_id=candidate.restaurant_id,
                    name=candidate.kakao.name,
                    address=candidate.kakao.address,
                    road_address=candidate.kakao.road_address,
                    latitude=candidate.kakao.latitude,
                    longitude=candidate.kakao.longitude,
                    category=candidate.kakao.category,
                    kakao=candidate.kakao,
                    google=match.google if match.matched else None,
                    match=match,
                    scores=scores,
                    label=label,
                    rating_coverage=coverage,
                    source_area_ids=candidate.source_area_ids,
                )
            )

        restaurants.sort(key=_rank_key, reverse=True)
        notices = _build_notices(
            restaurants,
            settings.provider_mode,
            enrichment_stats=enrichment_stats,
            enrichment_enabled=self._enable_kakao_enrichment,
        )

        return SearchResponse(
            results=restaurants,
            meta=SearchMeta(
                provider_mode=settings.provider_mode,
                area_count=len(areas),
                candidate_count=len(candidates),
                result_count=len(restaurants),
                query=request.query,
                city=request.city,
                mode=request.mode,
                api_calls=self._counter.as_dict() if self._counter else None,
            ),
            notices=notices,
        )

    async def _enrich_candidates(
        self, candidates: list[NormalizedCandidate]
    ) -> EnrichmentStats:
        if not self._enable_kakao_enrichment:
            return EnrichmentStats()
        enricher = self._enricher or KakaoPlaceEnricher(counter=self._counter)
        return await enricher.enrich_places([c.kakao for c in candidates])

    async def _match_candidates(
        self, candidates: list[NormalizedCandidate]
    ) -> list[PlaceMatchResult]:
        if not candidates:
            return []
        sem = asyncio.Semaphore(self._google_match_concurrency)

        async def _one(candidate: NormalizedCandidate) -> PlaceMatchResult:
            async with sem:
                return await self._matcher.match(candidate.kakao)

        return list(await asyncio.gather(*[_one(c) for c in candidates]))


def create_search_orchestrator() -> SearchOrchestrator:
    """Build a request-scoped orchestrator (fresh provider caches + call counter)."""
    counter = ApiCallCounter()
    return SearchOrchestrator(counter=counter)


def _rank_key(r: Restaurant) -> tuple[float, float, float]:
    """Prefer consensus, then local, then global; missing scores sort last."""
    c = r.scores.consensus.score if r.scores.consensus.score is not None else -1.0
    loc = r.scores.local.score if r.scores.local.score is not None else -1.0
    glob = r.scores.global_.score if r.scores.global_.score is not None else -1.0
    return (c, loc, glob)


def _build_notices(
    restaurants: list[Restaurant],
    provider_mode: str,
    *,
    enrichment_stats: EnrichmentStats | None = None,
    enrichment_enabled: bool = False,
) -> list[str]:
    notices: list[str] = []
    insufficient = sum(
        1
        for r in restaurants
        if r.scores.global_.availability.value == "insufficient_data"
    )
    unmatched = sum(
        1 for r in restaurants if r.scores.global_.availability.value == "unmatched"
    )
    kakao_ratings = sum(1 for r in restaurants if r.kakao.rating is not None)
    stats = enrichment_stats or EnrichmentStats()

    if enrichment_enabled and stats.attempted > 0:
        notices.append(
            f"카카오맵 평점 보강 — 성공 {stats.enriched}곳 · "
            f"실패/미제공 {stats.failed}곳"
            + (
                f" · 한도 외 생략 {stats.skipped}곳"
                if stats.skipped
                else ""
            )
            + " (비공식 place-detail; 실패 시 평점은 비워 둡니다)."
        )
    elif (
        provider_mode.lower() == "live"
        and restaurants
        and kakao_ratings == 0
        and enrichment_enabled
    ):
        notices.append(
            "카카오맵 평점 보강이 이번 검색에서 평점을 채우지 못했습니다. "
            "Local Score는 비워 두며, 이는 매칭 오류가 아닙니다."
        )

    if insufficient:
        notices.append(
            f"{insufficient}곳의 식당은 Google 리뷰 데이터가 충분하지 않아 "
            "Global Score를 계산하지 않았습니다."
        )
    if unmatched:
        notices.append(
            f"{unmatched}곳의 식당은 Google 장소와 매칭되지 않았거나 "
            "매칭 신뢰도가 낮아 Global Score를 표시하지 않습니다."
        )

    both = sum(1 for r in restaurants if r.rating_coverage == RatingCoverage.BOTH)
    kakao_only = sum(
        1 for r in restaurants if r.rating_coverage == RatingCoverage.KAKAO_ONLY
    )
    google_only = sum(
        1 for r in restaurants if r.rating_coverage == RatingCoverage.GOOGLE_ONLY
    )
    notices.append(
        f"평점 분류 — 양쪽 {both}곳 · 카카오만 {kakao_only}곳 · 구글만 {google_only}곳"
    )
    return notices
