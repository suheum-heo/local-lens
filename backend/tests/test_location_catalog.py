"""Nationwide subway station catalog tests."""

from __future__ import annotations

from app.domain.enums import City, LocationMode
from app.providers.location_catalog import catalog_for_city, load_stations


def test_station_catalog_is_nationwide():
    stations = load_stations()
    assert len(stations) >= 500
    cities = {s.city for s in stations}
    assert City.SEOUL in cities
    assert City.BUSAN in cities
    assert City.DAEGU in cities
    assert City.GWANGJU in cities


def test_catalog_nationwide_flag():
    all_stations = catalog_for_city(None, LocationMode.STATION, nationwide=True)
    seoul_only = catalog_for_city(City.SEOUL, LocationMode.STATION, nationwide=False)
    assert len(all_stations) > len(seoul_only)
    assert all(s.city == City.SEOUL for s in seoul_only)


def test_known_stations_present():
    names = {s.name for s in load_stations()}
    for expected in ("합정역", "강남역", "서면역", "상무역", "대전역"):
        assert any(expected in n for n in names), expected
