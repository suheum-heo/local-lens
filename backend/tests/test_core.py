"""Basic unit tests for scoring, matching, and deduplication."""

from __future__ import annotations

import pytest

from app.domain.enums import DataAvailability, MatchConfidenceLevel
from app.domain.models import GooglePlaceData, KakaoPlaceData, PlaceMatchResult
from app.matching.place_matcher import score_match
from app.normalization.restaurant import normalize_and_dedupe
from app.scoring.engine import SimpleScoringEngine


def _kakao(**kwargs) -> KakaoPlaceData:
    base = dict(
        kakao_place_id="k1",
        name="테스트 식당",
        address="서울 마포구",
        road_address="서울 마포구 양화로 1",
        latitude=37.55,
        longitude=126.91,
        category="음식점",
        place_url="https://place.map.kakao.com/k1",
        rating=4.5,
        review_count=100,
    )
    base.update(kwargs)
    return KakaoPlaceData(**base)


def _google(**kwargs) -> GooglePlaceData:
    base = dict(
        google_place_id="g1",
        name="Test Restaurant",
        address="1 Yanghwa-ro",
        latitude=37.5501,
        longitude=126.9101,
        rating=4.6,
        user_rating_count=200,
    )
    base.update(kwargs)
    return GooglePlaceData(**base)


def test_dedupe_by_kakao_id():
    place = _kakao()
    results = normalize_and_dedupe(
        [
            ("area-a", [place]),
            ("area-b", [place, _kakao(kakao_place_id="k2", name="다른집")]),
        ]
    )
    assert len(results) == 2
    merged = next(r for r in results if r.kakao.kakao_place_id == "k1")
    assert set(merged.source_area_ids) == {"area-a", "area-b"}


def test_score_match_nearby_similar_name():
    k = _kakao(name="합정 삼겹살집")
    g = _google(name="합정 삼겹살집", latitude=37.55, longitude=126.91)
    assert score_match(k, g) >= 0.8


def test_score_match_far_away_is_low():
    k = _kakao(name="합정 삼겹살집")
    g = _google(name="Random Place", latitude=37.51, longitude=127.04)
    assert score_match(k, g) < 0.55


def test_global_insufficient_reviews_not_zero():
    engine = SimpleScoringEngine()
    match = PlaceMatchResult(
        confidence=0.9,
        confidence_level=MatchConfidenceLevel.HIGH,
        matched=True,
        google=_google(user_rating_count=2, rating=5.0),
    )
    scores, _ = engine.score(_kakao(), match)
    assert scores.global_.availability == DataAvailability.INSUFFICIENT_DATA
    assert scores.global_.score is None
    assert scores.consensus.score is None
    assert "충분하지" in (scores.global_.explanation or "")


def test_unmatched_google_not_zero():
    engine = SimpleScoringEngine()
    match = PlaceMatchResult(
        confidence=0.0,
        confidence_level=MatchConfidenceLevel.NONE,
        matched=False,
        google=None,
    )
    scores, _ = engine.score(_kakao(), match)
    assert scores.global_.availability == DataAvailability.UNMATCHED
    assert scores.global_.score is None


def test_consensus_when_both_available():
    engine = SimpleScoringEngine()
    match = PlaceMatchResult(
        confidence=0.9,
        confidence_level=MatchConfidenceLevel.HIGH,
        matched=True,
        google=_google(rating=4.6, user_rating_count=731),
    )
    scores, label = engine.score(_kakao(rating=4.5, review_count=842), match)
    assert scores.local.score is not None
    assert scores.global_.score is not None
    assert scores.consensus.score is not None
    assert scores.consensus.availability == DataAvailability.AVAILABLE


@pytest.mark.asyncio
async def test_search_orchestrator_mock():
    from app.domain.contracts import SearchRequest
    from app.domain.enums import City, LocationMode
    from app.domain.locations import StationLocation
    from app.providers.mock_google import MockGooglePlacesProvider
    from app.providers.mock_kakao import MockKakaoLocalProvider
    from app.services.search_orchestrator import SearchOrchestrator

    orch = SearchOrchestrator(
        kakao=MockKakaoLocalProvider(),
        google=MockGooglePlacesProvider(),
    )
    resp = await orch.search(
        SearchRequest(
            city=City.SEOUL,
            mode=LocationMode.STATION,
            locations=[
                StationLocation(
                    station_id="st_hapjeong",
                    station_name="합정역",
                    city=City.SEOUL,
                    latitude=37.5496,
                    longitude=126.9139,
                )
            ],
            query="삼겹살",
        )
    )
    assert resp.meta.result_count >= 1
    # Ensure missing data stays missing
    for r in resp.results:
        if r.scores.global_.availability != DataAvailability.AVAILABLE:
            assert r.scores.global_.score is None
        assert r.rating_coverage.value in {
            "both",
            "kakao_only",
            "google_only",
            "none",
        }
