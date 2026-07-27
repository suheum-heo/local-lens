"""Search orchestration: locations → Kakao → dedupe → match → score."""

from __future__ import annotations

from app.config import settings
from app.domain.contracts import SearchMeta, SearchRequest, SearchResponse
from app.domain.locations import SearchArea
from app.domain.models import Restaurant
from app.matching.place_matcher import DefaultPlaceMatcher, PlaceMatcher
from app.normalization.restaurant import normalize_and_dedupe
from app.providers.base import GooglePlacesProvider, KakaoLocalProvider
from app.providers.factory import get_google_provider, get_kakao_provider
from app.scoring.engine import ScoringEngine, SimpleScoringEngine


class SearchOrchestrator:
    def __init__(
        self,
        kakao: KakaoLocalProvider | None = None,
        google: GooglePlacesProvider | None = None,
        matcher: PlaceMatcher | None = None,
        scoring: ScoringEngine | None = None,
    ) -> None:
        self._kakao = kakao or get_kakao_provider()
        self._google = google or get_google_provider()
        self._matcher = matcher or DefaultPlaceMatcher(self._google)
        self._scoring = scoring or SimpleScoringEngine()

    async def search(self, request: SearchRequest) -> SearchResponse:
        areas = [
            SearchArea.from_location(loc) for loc in request.locations
        ]

        area_results: list[tuple[str, list]] = []
        for area in areas:
            places = await self._kakao.search_restaurants(area, request.query)
            area_results.append((area.area_id, places))

        candidates = normalize_and_dedupe(area_results)
        restaurants: list[Restaurant] = []

        for candidate in candidates:
            match = await self._matcher.match(candidate.kakao)
            scores, label = self._scoring.score(candidate.kakao, match)
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
                    source_area_ids=candidate.source_area_ids,
                )
            )

        restaurants.sort(key=_rank_key, reverse=True)

        notices = _build_notices(restaurants)

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
            ),
            notices=notices,
        )


def _rank_key(r: Restaurant) -> tuple[float, float, float]:
    """Prefer consensus, then local, then global; missing scores sort last."""
    c = r.scores.consensus.score if r.scores.consensus.score is not None else -1.0
    loc = r.scores.local.score if r.scores.local.score is not None else -1.0
    glob = r.scores.global_.score if r.scores.global_.score is not None else -1.0
    return (c, loc, glob)


def _build_notices(restaurants: list[Restaurant]) -> list[str]:
    notices: list[str] = []
    insufficient = sum(
        1
        for r in restaurants
        if r.scores.global_.availability.value == "insufficient_data"
    )
    unmatched = sum(
        1 for r in restaurants if r.scores.global_.availability.value == "unmatched"
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
    return notices
