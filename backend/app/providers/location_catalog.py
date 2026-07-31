"""Location catalog: nationwide stations (JSON) + neighborhood fixtures."""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path

from app.domain.contracts import LocationCatalogItem
from app.domain.enums import City, LocationMode

_DATA_DIR = Path(__file__).resolve().parent.parent / "data"
_STATIONS_PATH = _DATA_DIR / "stations.json"

# Small neighborhood seeds for cities without a full dong catalog yet.
NEIGHBORHOODS: list[LocationCatalogItem] = [
    LocationCatalogItem(
        id="nb_samsan",
        name="삼산동",
        name_en="Samsan-dong",
        city=City.ULSAN,
        latitude=35.5412,
        longitude=129.3380,
        mode=LocationMode.NEIGHBORHOOD,
    ),
    LocationCatalogItem(
        id="nb_daldong",
        name="달동",
        name_en="Dal-dong",
        city=City.ULSAN,
        latitude=35.5350,
        longitude=129.3220,
        mode=LocationMode.NEIGHBORHOOD,
    ),
    LocationCatalogItem(
        id="nb_hyoja",
        name="효자동",
        name_en="Hyoja-dong",
        city=City.JEONJU,
        latitude=35.8400,
        longitude=127.1200,
        mode=LocationMode.NEIGHBORHOOD,
    ),
    LocationCatalogItem(
        id="nb_seosin",
        name="서신동",
        name_en="Seosin-dong",
        city=City.JEONJU,
        latitude=35.8330,
        longitude=127.1150,
        mode=LocationMode.NEIGHBORHOOD,
    ),
]


@lru_cache
def load_stations() -> tuple[LocationCatalogItem, ...]:
    if not _STATIONS_PATH.exists():
        return tuple()
    raw = json.loads(_STATIONS_PATH.read_text(encoding="utf-8"))
    items: list[LocationCatalogItem] = []
    for row in raw:
        try:
            city = City(row["city"])
        except ValueError:
            city = City.OTHER
        items.append(
            LocationCatalogItem(
                id=str(row["id"]),
                name=str(row["name"]),
                name_en=row.get("name_en"),
                city=city,
                latitude=float(row["latitude"]),
                longitude=float(row["longitude"]),
                mode=LocationMode.STATION,
                default_radius_m=int(row.get("default_radius_m") or 1000),
            )
        )
    return tuple(items)


def catalog_for_city(
    city: City | None,
    mode: LocationMode,
    *,
    nationwide: bool = False,
) -> list[LocationCatalogItem]:
    """Return catalog items.

    For stations, ``nationwide=True`` (or city is None) returns the full subway
    catalog so the UI can search any station. City filter still available for
    narrower lists.
    """
    if mode == LocationMode.STATION:
        stations = list(load_stations())
        if nationwide or city is None:
            return stations
        return [item for item in stations if item.city == city]

    if city is None:
        return list(NEIGHBORHOODS)
    return [item for item in NEIGHBORHOODS if item.city == city]
