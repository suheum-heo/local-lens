"""Tests for station / bus_stop / neighborhood location modes."""

from __future__ import annotations

import httpx
import pytest

from app.domain.enums import City, LocationMode
from app.domain.locations import BusStopLocation, SearchArea, StreetLocation
from app.providers.location_catalog import catalog_for_city, load_streets
from app.providers.location_search import search_bus_stops, search_neighborhoods


def test_bus_stop_location_to_search_area():
    area = SearchArea.from_location(
        BusStopLocation(
            bus_stop_id="bus_1",
            bus_stop_name="합정역",
            city=City.SEOUL,
            latitude=37.5494,
            longitude=126.9137,
            radius_m=1000,
        )
    )
    assert area.source_mode == LocationMode.BUS_STOP
    assert area.label == "합정역"
    assert area.radius_m == 1000


def test_bus_stop_seed_catalog():
    seeds = catalog_for_city(City.SEOUL, LocationMode.BUS_STOP)
    assert len(seeds) >= 1
    assert all(s.mode == LocationMode.BUS_STOP for s in seeds)


def test_neighborhood_seed_catalog_has_multiple_cities():
    all_nb = catalog_for_city(None, LocationMode.NEIGHBORHOOD)
    cities = {n.city for n in all_nb}
    assert City.SEOUL in cities
    assert City.JEONJU in cities


def test_street_location_to_search_area():
    area = SearchArea.from_location(
        StreetLocation(
            street_id="st_garosu",
            street_name="가로수길",
            city=City.SEOUL,
            latitude=37.5209,
            longitude=127.0228,
            radius_m=1000,
        )
    )
    assert area.source_mode == LocationMode.STREET
    assert area.label == "가로수길"


def test_street_catalog_includes_famous_areas():
    streets = load_streets()
    names = {s.name for s in streets}
    assert "가로수길" in names
    assert "해방촌" in names
    assert "황리단길" in names
    assert any(s.city == City.GYEONGJU for s in streets)
    seoul = catalog_for_city(City.SEOUL, LocationMode.STREET)
    assert all(s.mode == LocationMode.STREET for s in seoul)
    assert any(s.name == "가로수길" for s in seoul)


@pytest.mark.asyncio
async def test_search_bus_stops_parses_overpass():
    payload = {
        "elements": [
            {
                "type": "node",
                "id": 111,
                "lat": 37.5494,
                "lon": 126.9137,
                "tags": {"name": "합정역", "highway": "bus_stop"},
            },
            {
                "type": "node",
                "id": 112,
                "lat": 37.5495,
                "lon": 126.9138,
                "tags": {"name": "합정역7번출구", "highway": "bus_stop"},
            },
        ]
    }

    def handler(request: httpx.Request) -> httpx.Response:
        assert "overpass" in str(request.url)
        return httpx.Response(200, json=payload)

    items = await search_bus_stops(
        City.SEOUL,
        "합정",
        transport=httpx.MockTransport(handler),
    )
    assert len(items) == 2
    assert items[0].mode == LocationMode.BUS_STOP
    assert "합정" in items[0].name


@pytest.mark.asyncio
async def test_search_neighborhoods_parses_kakao_address(monkeypatch):
    from app.providers import location_search as mod

    monkeypatch.setattr(mod.settings, "kakao_rest_api_key", "test-key")

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path.endswith("/v2/local/search/address.json")
        return httpx.Response(
            200,
            json={
                "documents": [
                    {
                        "address_name": "서울 마포구 합정동",
                        "address_type": "REGION",
                        "x": "126.9117",
                        "y": "37.5516",
                        "address": {
                            "region_1depth_name": "서울",
                            "region_2depth_name": "마포구",
                            "region_3depth_name": "합정동",
                            "region_3depth_h_name": "합정동",
                        },
                    }
                ]
            },
        )

    items = await search_neighborhoods(
        City.SEOUL,
        "합정동",
        transport=httpx.MockTransport(handler),
    )
    assert len(items) == 1
    assert items[0].name == "합정동"
    assert items[0].mode == LocationMode.NEIGHBORHOOD
