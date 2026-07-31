"""Tests for rating coverage classification."""

from __future__ import annotations

from app.domain.enums import MatchConfidenceLevel, RatingCoverage
from app.domain.models import GooglePlaceData, KakaoPlaceData, PlaceMatchResult
from app.domain.rating_coverage import classify_rating_coverage


def _kakao(rating: float | None = None) -> KakaoPlaceData:
    return KakaoPlaceData(
        kakao_place_id="k1",
        name="테스트",
        address="서울",
        road_address="서울",
        latitude=37.55,
        longitude=126.91,
        category="음식점",
        place_url="https://place.map.kakao.com/k1",
        rating=rating,
        review_count=10 if rating is not None else None,
    )


def _match(
    *,
    matched: bool,
    rating: float | None = None,
) -> PlaceMatchResult:
    google = None
    if matched:
        google = GooglePlaceData(
            google_place_id="g1",
            name="테스트",
            address="서울",
            latitude=37.55,
            longitude=126.91,
            rating=rating,
            user_rating_count=20 if rating is not None else None,
        )
    return PlaceMatchResult(
        confidence=0.9 if matched else 0.0,
        confidence_level=(
            MatchConfidenceLevel.HIGH if matched else MatchConfidenceLevel.NONE
        ),
        matched=matched,
        google=google,
    )


def test_coverage_both():
    assert (
        classify_rating_coverage(_kakao(4.5), _match(matched=True, rating=4.2))
        == RatingCoverage.BOTH
    )


def test_coverage_kakao_only():
    assert (
        classify_rating_coverage(_kakao(4.5), _match(matched=False))
        == RatingCoverage.KAKAO_ONLY
    )


def test_coverage_google_only():
    assert (
        classify_rating_coverage(_kakao(None), _match(matched=True, rating=4.6))
        == RatingCoverage.GOOGLE_ONLY
    )


def test_coverage_none_when_live_kakao_has_no_rating():
    assert (
        classify_rating_coverage(_kakao(None), _match(matched=False))
        == RatingCoverage.NONE
    )
