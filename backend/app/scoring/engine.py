"""Scoring engine interface and initial transparent formula."""

from __future__ import annotations

from abc import ABC, abstractmethod

from app.domain.enums import DataAvailability, RestaurantLabel
from app.domain.models import (
    GooglePlaceData,
    KakaoPlaceData,
    PlaceMatchResult,
    PlatformSignal,
    ScoreBundle,
)

# Minimum Google reviews required before Global Score is computed.
MIN_GOOGLE_REVIEWS = 5
# Minimum Kakao reviews (when available) for Local Score.
MIN_KAKAO_REVIEWS = 5


class ScoringEngine(ABC):
    @abstractmethod
    def score(
        self,
        kakao: KakaoPlaceData,
        match: PlaceMatchResult,
    ) -> tuple[ScoreBundle, RestaurantLabel | None]:
        raise NotImplementedError


class SimpleScoringEngine(ScoringEngine):
    """
    Transparent v1 formula (see docs/SCORING.md):

    PlatformScore = 100 * (0.65 * rating_norm + 0.35 * volume_norm)

    where:
      rating_norm = rating / 5.0
      volume_norm = log10(1 + review_count) / log10(1 + VOLUME_CAP)

    Consensus only when both Local and Global are AVAILABLE.
    Consensus = 0.5 * Local + 0.5 * Global (equal weight in v1).
    """

    VOLUME_CAP = 2000

    def score(
        self,
        kakao: KakaoPlaceData,
        match: PlaceMatchResult,
    ) -> tuple[ScoreBundle, RestaurantLabel | None]:
        local = self._local_signal(kakao)
        global_ = self._global_signal(match)

        if (
            local.availability == DataAvailability.AVAILABLE
            and global_.availability == DataAvailability.AVAILABLE
            and local.score is not None
            and global_.score is not None
        ):
            consensus = PlatformSignal(
                availability=DataAvailability.AVAILABLE,
                rating=None,
                review_count=None,
                score=round(0.5 * local.score + 0.5 * global_.score, 1),
                explanation=None,
            )
        else:
            consensus = PlatformSignal(
                availability=DataAvailability.UNAVAILABLE,
                rating=None,
                review_count=None,
                score=None,
                explanation=(
                    "Consensus Score는 Local Score와 Global Score가 모두 "
                    "계산 가능할 때만 제공됩니다."
                ),
            )

        bundle = ScoreBundle(local=local, global_=global_, consensus=consensus)
        label = assign_label(bundle, match)
        return bundle, label

    def _local_signal(self, kakao: KakaoPlaceData) -> PlatformSignal:
        rating = kakao.rating
        count = kakao.review_count

        if rating is None and count is None:
            # Official Local search omits ratings; enrichment may also soft-fail.
            return PlatformSignal(
                availability=DataAvailability.UNAVAILABLE,
                rating=None,
                review_count=None,
                score=None,
                explanation=(
                    "Kakao 평점 보강이 없거나 실패하여 Local Score를 "
                    "계산하지 않았습니다. (없는 값은 0으로 채우지 않습니다.)"
                ),
            )

        if count is not None and count < MIN_KAKAO_REVIEWS:
            return PlatformSignal(
                availability=DataAvailability.INSUFFICIENT_DATA,
                rating=rating,
                review_count=count,
                score=None,
                explanation=(
                    f"Kakao 리뷰 수({count})가 부족하여 Local Score를 "
                    "계산하지 않았습니다."
                ),
            )

        if rating is None:
            return PlatformSignal(
                availability=DataAvailability.INSUFFICIENT_DATA,
                rating=None,
                review_count=count,
                score=None,
                explanation="Kakao 평점이 없어 Local Score를 계산하지 않았습니다.",
            )

        score = self._platform_score(rating, count or 0)
        return PlatformSignal(
            availability=DataAvailability.AVAILABLE,
            rating=rating,
            review_count=count,
            score=score,
            explanation=None,
        )

    def _global_signal(self, match: PlaceMatchResult) -> PlatformSignal:
        if not match.matched or match.google is None:
            if match.confidence_level.value == "low" or (
                match.confidence > 0 and not match.matched
            ):
                return PlatformSignal(
                    availability=DataAvailability.UNMATCHED,
                    rating=None,
                    review_count=None,
                    score=None,
                    explanation=(
                        "Google 장소 매칭 신뢰도가 낮아 Global Score를 "
                        "계산하지 않았습니다."
                        + (f" ({match.reason})" if match.reason else "")
                    ),
                )
            return PlatformSignal(
                availability=DataAvailability.UNMATCHED,
                rating=None,
                review_count=None,
                score=None,
                explanation=(
                    "대응하는 Google 장소를 찾지 못해 Global Score를 "
                    "계산하지 않았습니다."
                ),
            )

        google: GooglePlaceData = match.google
        rating = google.rating
        count = google.user_rating_count

        if rating is None and (count is None or count == 0):
            return PlatformSignal(
                availability=DataAvailability.UNAVAILABLE,
                rating=None,
                review_count=count,
                score=None,
                explanation=(
                    "Google 리뷰 데이터가 없어 Global Score를 계산하지 않았습니다."
                ),
            )

        if count is None or count < MIN_GOOGLE_REVIEWS:
            return PlatformSignal(
                availability=DataAvailability.INSUFFICIENT_DATA,
                rating=rating,
                review_count=count,
                score=None,
                explanation=(
                    "Google 리뷰 데이터가 충분하지 않아 Global Score를 "
                    "계산하지 않았습니다."
                ),
            )

        if rating is None:
            return PlatformSignal(
                availability=DataAvailability.INSUFFICIENT_DATA,
                rating=None,
                review_count=count,
                score=None,
                explanation="Google 평점이 없어 Global Score를 계산하지 않았습니다.",
            )

        score = self._platform_score(rating, count)
        return PlatformSignal(
            availability=DataAvailability.AVAILABLE,
            rating=rating,
            review_count=count,
            score=score,
            explanation=None,
        )

    def _platform_score(self, rating: float, review_count: int) -> float:
        import math

        rating_norm = max(0.0, min(rating / 5.0, 1.0))
        volume_norm = math.log10(1 + review_count) / math.log10(1 + self.VOLUME_CAP)
        volume_norm = max(0.0, min(volume_norm, 1.0))
        return round(100.0 * (0.65 * rating_norm + 0.35 * volume_norm), 1)


def assign_label(
    scores: ScoreBundle,
    match: PlaceMatchResult,
) -> RestaurantLabel | None:
    local_ok = scores.local.availability == DataAvailability.AVAILABLE
    global_ok = scores.global_.availability == DataAvailability.AVAILABLE
    consensus_ok = scores.consensus.availability == DataAvailability.AVAILABLE

    if consensus_ok and scores.local.score is not None and scores.global_.score is not None:
        # Consensus pick when both are strong (>= 75) and close
        if (
            scores.local.score >= 75
            and scores.global_.score >= 75
            and abs(scores.local.score - scores.global_.score) <= 15
        ):
            return RestaurantLabel.CONSENSUS_PICK

    if local_ok and scores.local.score is not None and scores.local.score >= 80:
        if not global_ok or (
            scores.global_.score is not None and scores.local.score - scores.global_.score >= 10
        ):
            return RestaurantLabel.LOCAL_FAVORITE

    if global_ok and scores.global_.score is not None and scores.global_.score >= 80:
        if not local_ok or (
            scores.local.score is not None and scores.global_.score - scores.local.score >= 10
        ):
            return RestaurantLabel.GLOBAL_FAVORITE

    # Limited data when Google side is missing/insufficient/unmatched
    # and we still show the restaurant (Kakao candidate exists).
    if scores.global_.availability in {
        DataAvailability.INSUFFICIENT_DATA,
        DataAvailability.UNAVAILABLE,
        DataAvailability.UNMATCHED,
    } and not consensus_ok:
        # Prefer more specific favorite labels first; fall through to limited
        if not local_ok or (scores.local.score is not None and scores.local.score < 80):
            return RestaurantLabel.LIMITED_DATA

    if not match.matched and not local_ok:
        return RestaurantLabel.LIMITED_DATA

    return None
