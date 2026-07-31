"""Classify restaurants by which platforms expose a numeric rating."""

from __future__ import annotations

from app.domain.enums import RatingCoverage
from app.domain.models import KakaoPlaceData, PlaceMatchResult


def classify_rating_coverage(
    kakao: KakaoPlaceData,
    match: PlaceMatchResult,
) -> RatingCoverage:
    """
    Three primary buckets (plus NONE):

    - both: Kakao rating and Google rating both present
    - kakao_only: Kakao rating only
    - google_only: Google rating only (matched)
    - none: neither side has a numeric rating

    Note: Official Kakao Local keyword search omits ratings; live mode fills
    them only when unofficial place-detail enrichment succeeds.
    """
    has_kakao = kakao.rating is not None
    has_google = (
        match.matched
        and match.google is not None
        and match.google.rating is not None
    )

    if has_kakao and has_google:
        return RatingCoverage.BOTH
    if has_kakao and not has_google:
        return RatingCoverage.KAKAO_ONLY
    if has_google and not has_kakao:
        return RatingCoverage.GOOGLE_ONLY
    return RatingCoverage.NONE
