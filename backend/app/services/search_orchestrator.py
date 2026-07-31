"""Search orchestration: locations → Kakao → dedupe → match → score."""

from __future__ import annotations

from app.config import settings
from app.domain.contracts import SearchMeta, SearchRequest, SearchResponse
from app.domain.enums import RatingCoverage
from app.domain.locations import SearchArea
from app.domain.models import Restaurant
from app.domain.rating_coverage import classify_rating_coverage
from app.matching.place_matcher import DefaultPlaceMatcher, PlaceMatcher
from app.normalization.restaurant import normalize_and_dedupe
from app.providers.base import GooglePlacesProvider, KakaoLocalProvider
from app.providers.errors import ApiCallCounter
from app.providers.factory import get_google_provider, get_kakao_provider
from app.scoring.engine import ScoringEngine, SimpleScoringEngine


class SearchOrchestrator:
    def __init__(
        self,
        kakao: KakaoLocalProvider | None = None,
        google: GooglePlacesProvider | None = None,
        matcher: PlaceMatcher | None = None,
        scoring: ScoringEngine | None = None,
        counter: ApiCallCounter | None = None,
    ) -> None:
        self._counter = counter
        self._kakao = kakao or get_kakao_provider(counter=counter)
        self._google = google or get_google_provider(counter=counter)
        self._matcher = matcher or DefaultPlaceMatcher(self._google)
        self._scoring = scoring or SimpleScoringEngine()

    async def search(self, request: SearchRequest) -> SearchResponse:
        areas = [SearchArea.from_location(loc) for loc in request.locations]

        area_results: list[tuple[str, list]] = []
        for area in areas:
            places = await self._kakao.search_restaurants(area, request.query)
            area_results.append((area.area_id, places))

        # Dedupe BEFORE Google enrichment so each Kakao place is matched once.
        candidates = normalize_and_dedupe(area_results)
        restaurants: list[Restaurant] = []

        for candidate in candidates:
            match = await self._matcher.match(candidate.kakao)
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
        notices = _build_notices(restaurants, settings.provider_mode)

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


def _build_notices(restaurants: list[Restaurant], provider_mode: str) -> list[str]:
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

    if provider_mode.lower() == "live" and restaurants and kakao_ratings == 0:
        notices.append(
            "Kakao Local API는 별점·후기 수를 반환하지 않습니다. "
            "카카오맵 앱에 후기가 있어도 LocalLens에는 Kakao 평점이 표시되지 않으며, "
            "이는 매칭 오류가 아닙니다."
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
