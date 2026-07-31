"""Mocked HTTP tests for unofficial Kakao place-detail enrichment."""

from __future__ import annotations

import httpx
import pytest

from app.domain.enums import City, LocationMode, RatingCoverage
from app.domain.models import GooglePlaceData, KakaoPlaceData, PlaceMatchResult
from app.domain.enums import MatchConfidenceLevel
from app.matching.place_matcher import PlaceMatcher
from app.providers.base import GooglePlacesProvider, KakaoLocalProvider
from app.providers.errors import ApiCallCounter
from app.providers.kakao_place_enricher import (
    KakaoPlaceEnricher,
    parse_panel3_scores,
)
from app.services.search_orchestrator import SearchOrchestrator
from app.domain.contracts import SearchRequest
from app.domain.locations import StationLocation


def _place(pid: str = "83301316", *, rating: float | None = None) -> KakaoPlaceData:
    return KakaoPlaceData(
        kakao_place_id=pid,
        name="크레이지카츠",
        address="서울 마포구",
        latitude=37.55,
        longitude=126.91,
        place_url=f"https://place.map.kakao.com/{pid}",
        rating=rating,
        review_count=10 if rating is not None else None,
    )


def _review_tab(
    *,
    average_score: float | None = 4.0,
    review_count: int | None = 593,
) -> dict:
    score_set: dict = {}
    if average_score is not None:
        score_set["average_score"] = average_score
    if review_count is not None:
        score_set["review_count"] = review_count
    return {"score_set": score_set}


def _panel3_legacy(
    *,
    average_score: float | None = 4.0,
    review_count: int | None = 593,
) -> dict:
    return {"kakaomap_review": {"score_set": _review_tab(
        average_score=average_score, review_count=review_count
    )["score_set"]}}


def test_parse_review_tab_valid():
    rating, count = parse_panel3_scores(_review_tab())
    assert rating == 4.0
    assert count == 593


def test_parse_panel3_legacy_valid():
    rating, count = parse_panel3_scores(_panel3_legacy())
    assert rating == 4.0
    assert count == 593


def test_parse_panel3_missing_score_set():
    assert parse_panel3_scores({"kakaomap_review": {}}) == (None, None)
    assert parse_panel3_scores({}) == (None, None)
    assert parse_panel3_scores("bad") == (None, None)


def test_parse_panel3_malformed_values():
    assert parse_panel3_scores(
        {"score_set": {"average_score": "x", "review_count": 3}}
    ) == (None, None)


@pytest.mark.asyncio
async def test_enricher_sets_rating_and_count():
    def handler(request: httpx.Request) -> httpx.Response:
        assert "/places/tab/reviews/kakaomap/83301316" in str(request.url)
        assert request.headers.get("appVersion") == "6.6.0"
        assert request.headers.get("pf") == "PC"
        return httpx.Response(200, json=_review_tab())

    counter = ApiCallCounter()
    enricher = KakaoPlaceEnricher(
        transport=httpx.MockTransport(handler),
        counter=counter,
    )
    place = _place()
    stats = await enricher.enrich_places([place])
    assert stats.attempted == 1
    assert stats.enriched == 1
    assert place.rating == 4.0
    assert place.review_count == 593
    assert counter.kakao_place_detail == 1


@pytest.mark.asyncio
async def test_enricher_404_leaves_missing():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(404, json={"code": "NONE"})

    place = _place()
    enricher = KakaoPlaceEnricher(transport=httpx.MockTransport(handler))
    stats = await enricher.enrich_places([place])
    assert stats.failed == 1
    assert place.rating is None
    assert place.review_count is None


@pytest.mark.asyncio
async def test_enricher_timeout_soft_fails():
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.TimeoutException("timeout")

    place = _place()
    counter = ApiCallCounter()
    enricher = KakaoPlaceEnricher(
        transport=httpx.MockTransport(handler),
        counter=counter,
    )
    stats = await enricher.enrich_places([place])
    assert stats.failed == 1
    assert place.rating is None
    assert counter.kakao_place_detail == 1


@pytest.mark.asyncio
async def test_enricher_malformed_json_soft_fails():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, content=b"not-json", headers={"content-type": "text/plain"})

    place = _place()
    enricher = KakaoPlaceEnricher(transport=httpx.MockTransport(handler))
    stats = await enricher.enrich_places([place])
    assert stats.failed == 1
    assert place.rating is None


@pytest.mark.asyncio
async def test_enricher_missing_fields_soft_fails():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"kakaomap_review": {"score_set": {}}})

    place = _place()
    enricher = KakaoPlaceEnricher(transport=httpx.MockTransport(handler))
    stats = await enricher.enrich_places([place])
    assert stats.failed == 1
    assert place.rating is None


@pytest.mark.asyncio
async def test_enricher_caches_and_skips_existing_rating():
    calls = {"n": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        calls["n"] += 1
        return httpx.Response(200, json=_review_tab(average_score=3.8, review_count=10))

    enricher = KakaoPlaceEnricher(transport=httpx.MockTransport(handler))
    a = _place("111")
    b = _place("111")  # same id, separate object
    already = _place("222", rating=4.5)
    stats = await enricher.enrich_places([a, b, already])
    # Only one unique id without rating is attempted; cache avoids a second HTTP call
    # if enrich_places were called again — within one pass each place is fetched once.
    assert calls["n"] == 1
    assert a.rating == 3.8
    assert b.rating is None  # second object with same id was not in to_enrich (seen)
    assert already.rating == 4.5
    assert stats.skipped == 1
    assert stats.attempted == 1

    # Second pass uses request-scoped cache (no extra HTTP).
    c = _place("111")
    await enricher.enrich_places([c])
    assert calls["n"] == 1
    assert c.rating == 3.8


@pytest.mark.asyncio
async def test_enricher_respects_max_places_cap():
    calls = {"n": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        calls["n"] += 1
        return httpx.Response(200, json=_review_tab())

    enricher = KakaoPlaceEnricher(
        transport=httpx.MockTransport(handler),
        max_places=2,
    )
    places = [_place(str(i)) for i in range(5)]
    stats = await enricher.enrich_places(places)
    assert stats.attempted == 2
    assert calls["n"] == 2
    assert sum(1 for p in places if p.rating is not None) == 2


@pytest.mark.asyncio
async def test_orchestrator_enrichment_enables_local_and_both_coverage():
    class StubKakao(KakaoLocalProvider):
        async def search_restaurants(self, area, query):
            return [_place("p1")]

    class StubGoogle(GooglePlacesProvider):
        async def search_places(self, name, latitude, longitude, address=None):
            return [
                GooglePlaceData(
                    google_place_id="g1",
                    name=name,
                    address=address,
                    latitude=latitude,
                    longitude=longitude,
                    rating=4.2,
                    user_rating_count=80,
                )
            ]

        async def get_place_details(self, place_id: str):
            return None

    class AlwaysMatch(PlaceMatcher):
        async def match(self, kakao: KakaoPlaceData) -> PlaceMatchResult:
            return PlaceMatchResult(
                confidence=0.9,
                confidence_level=MatchConfidenceLevel.HIGH,
                matched=True,
                google=GooglePlaceData(
                    google_place_id="g1",
                    name=kakao.name,
                    latitude=kakao.latitude,
                    longitude=kakao.longitude,
                    rating=4.2,
                    user_rating_count=80,
                ),
            )

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200, json=_review_tab(average_score=4.5, review_count=120)
        )

    counter = ApiCallCounter()
    enricher = KakaoPlaceEnricher(
        transport=httpx.MockTransport(handler),
        counter=counter,
    )
    orch = SearchOrchestrator(
        kakao=StubKakao(),
        google=StubGoogle(),
        matcher=AlwaysMatch(),
        counter=counter,
        enricher=enricher,
        enable_kakao_enrichment=True,
    )
    resp = await orch.search(
        SearchRequest(
            city=City.SEOUL,
            mode=LocationMode.STATION,
            query="맛집",
            locations=[
                StationLocation(
                    station_id="st_hapjeong",
                    station_name="합정역",
                    city=City.SEOUL,
                    latitude=37.5496,
                    longitude=126.9139,
                    radius_m=1000,
                )
            ],
        )
    )
    assert len(resp.results) == 1
    r = resp.results[0]
    assert r.kakao.rating == 4.5
    assert r.kakao.review_count == 120
    assert r.scores.local.score is not None
    assert r.rating_coverage == RatingCoverage.BOTH
    assert counter.kakao_place_detail == 1
    assert any("평점 보강" in n for n in resp.notices)


@pytest.mark.asyncio
async def test_orchestrator_skips_enrichment_in_mock_mode_flag():
    class StubKakao(KakaoLocalProvider):
        async def search_restaurants(self, area, query):
            return [_place("p1", rating=4.7)]

    class StubGoogle(GooglePlacesProvider):
        async def search_places(self, name, latitude, longitude, address=None):
            return []

        async def get_place_details(self, place_id: str):
            return None

    class NoMatch(PlaceMatcher):
        async def match(self, kakao: KakaoPlaceData) -> PlaceMatchResult:
            return PlaceMatchResult(
                confidence=0.0,
                confidence_level=MatchConfidenceLevel.LOW,
                matched=False,
                reason="no match",
            )

    calls = {"n": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        calls["n"] += 1
        return httpx.Response(200, json=_review_tab())

    enricher = KakaoPlaceEnricher(transport=httpx.MockTransport(handler))
    orch = SearchOrchestrator(
        kakao=StubKakao(),
        google=StubGoogle(),
        matcher=NoMatch(),
        enricher=enricher,
        enable_kakao_enrichment=False,
    )
    resp = await orch.search(
        SearchRequest(
            city=City.SEOUL,
            mode=LocationMode.STATION,
            query="맛집",
            locations=[
                StationLocation(
                    station_id="st_hapjeong",
                    station_name="합정역",
                    city=City.SEOUL,
                    latitude=37.5496,
                    longitude=126.9139,
                    radius_m=1000,
                )
            ],
        )
    )
    assert calls["n"] == 0
    assert resp.results[0].kakao.rating == 4.7
    assert not any("평점 보강" in n for n in resp.notices)
