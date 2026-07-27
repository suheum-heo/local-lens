"""Tests for search radius options and overlapping multi-area dedupe."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from app.domain.contracts import SearchRequest
from app.domain.enums import City, LocationMode
from app.domain.locations import (
    STATION_RADIUS_OPTIONS_M,
    StationLocation,
)
from app.providers.mock_kakao import MockKakaoLocalProvider
from app.domain.locations import SearchArea
from app.services.search_orchestrator import SearchOrchestrator


def test_station_radius_options():
    assert STATION_RADIUS_OPTIONS_M == (500, 1000, 1500, 2000)
    for radius in STATION_RADIUS_OPTIONS_M:
        loc = StationLocation(
            station_id="st_hapjeong",
            station_name="합정역",
            city=City.SEOUL,
            latitude=37.5496,
            longitude=126.9139,
            radius_m=radius,
        )
        assert loc.radius_m == radius


def test_station_radius_rejects_invalid():
    with pytest.raises(ValidationError):
        StationLocation(
            station_id="st_hapjeong",
            station_name="합정역",
            city=City.SEOUL,
            latitude=37.5496,
            longitude=126.9139,
            radius_m=750,
        )


@pytest.mark.asyncio
async def test_mock_kakao_respects_radius():
    provider = MockKakaoLocalProvider()
    tight = SearchArea(
        label="합정역",
        city=City.SEOUL,
        latitude=37.5496,
        longitude=126.9139,
        radius_m=500,
        source_mode=LocationMode.STATION,
        source_id="st_hapjeong",
    )
    wide = SearchArea(
        label="합정역",
        city=City.SEOUL,
        latitude=37.5496,
        longitude=126.9139,
        radius_m=2000,
        source_mode=LocationMode.STATION,
        source_id="st_hapjeong",
    )
    tight_hits = await provider.search_restaurants(tight, "맛집")
    wide_hits = await provider.search_restaurants(wide, "맛집")
    tight_ids = {p.kakao_place_id for p in tight_hits}
    wide_ids = {p.kakao_place_id for p in wide_hits}

    # Near-station BBQ should appear even in a tight radius.
    assert "kakao_hp_001" in tight_ids
    # Wider radius should find at least as many candidates.
    assert wide_ids >= tight_ids
    assert len(wide_hits) >= len(tight_hits)


@pytest.mark.asyncio
async def test_overlapping_stations_dedupe():
    """Hapjeong + Sangsu overlap should not duplicate shared Kakao places."""
    orch = SearchOrchestrator()
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
                    radius_m=1000,
                ),
                StationLocation(
                    station_id="st_sangsu",
                    station_name="상수역",
                    city=City.SEOUL,
                    latitude=37.5478,
                    longitude=126.9227,
                    radius_m=1000,
                ),
            ],
            query="맛집",
        )
    )
    ids = [r.kakao.kakao_place_id for r in resp.results]
    assert len(ids) == len(set(ids))
    # At least one restaurant should be attributed to both areas when overlapping.
    multi = [r for r in resp.results if len(r.source_area_ids) >= 2]
    assert multi, "expected at least one restaurant covered by both stations"
    assert resp.meta.area_count == 2
    assert resp.meta.candidate_count == resp.meta.result_count
