"""Location catalog: nationwide stations (JSON) + neighborhood fixtures."""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path

from app.domain.contracts import LocationCatalogItem
from app.domain.enums import City, LocationMode

_DATA_DIR = Path(__file__).resolve().parent.parent / "data"
_STATIONS_PATH = _DATA_DIR / "stations.json"

# Seed neighborhoods shown before the user types (live Kakao address fills more).
NEIGHBORHOODS: list[LocationCatalogItem] = [
    LocationCatalogItem(
        id="nb_hapjeong",
        name="합정동",
        name_en="Hapjeong-dong",
        city=City.SEOUL,
        latitude=37.5496,
        longitude=126.9139,
        mode=LocationMode.NEIGHBORHOOD,
    ),
    LocationCatalogItem(
        id="nb_seogyo",
        name="서교동",
        name_en="Seogyo-dong",
        city=City.SEOUL,
        latitude=37.5535,
        longitude=126.9210,
        mode=LocationMode.NEIGHBORHOOD,
    ),
    LocationCatalogItem(
        id="nb_yeoksam",
        name="역삼동",
        name_en="Yeoksam-dong",
        city=City.SEOUL,
        latitude=37.5009,
        longitude=127.0374,
        mode=LocationMode.NEIGHBORHOOD,
    ),
    LocationCatalogItem(
        id="nb_suji",
        name="서면",
        name_en="Seomyeon",
        city=City.BUSAN,
        latitude=35.1570,
        longitude=129.0590,
        mode=LocationMode.NEIGHBORHOOD,
    ),
    LocationCatalogItem(
        id="nb_haeundae",
        name="우동",
        name_en="U-dong",
        city=City.BUSAN,
        latitude=35.1631,
        longitude=129.1635,
        mode=LocationMode.NEIGHBORHOOD,
    ),
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
    LocationCatalogItem(
        id="nb_dunsan",
        name="둔산동",
        name_en="Dunsan-dong",
        city=City.DAEJEON,
        latitude=36.3510,
        longitude=127.3780,
        mode=LocationMode.NEIGHBORHOOD,
    ),
    LocationCatalogItem(
        id="nb_sangmu",
        name="치평동",
        name_en="Chipyeong-dong",
        city=City.GWANGJU,
        latitude=35.1520,
        longitude=126.8400,
        mode=LocationMode.NEIGHBORHOOD,
    ),
]

# Small mock bus-stop seeds for offline / empty-query UX.
BUS_STOP_SEEDS: list[LocationCatalogItem] = [
    LocationCatalogItem(
        id="bus_seed_hapjeong",
        name="합정역",
        name_en=None,
        city=City.SEOUL,
        latitude=37.5494,
        longitude=126.9137,
        mode=LocationMode.BUS_STOP,
    ),
    LocationCatalogItem(
        id="bus_seed_hongdae",
        name="홍대입구역",
        name_en=None,
        city=City.SEOUL,
        latitude=37.5570,
        longitude=126.9240,
        mode=LocationMode.BUS_STOP,
    ),
    LocationCatalogItem(
        id="bus_seed_seomyeon",
        name="서면역",
        name_en=None,
        city=City.BUSAN,
        latitude=35.1576,
        longitude=129.0590,
        mode=LocationMode.BUS_STOP,
    ),
    LocationCatalogItem(
        id="bus_seed_jeonju_hanok",
        name="한옥마을",
        name_en=None,
        city=City.JEONJU,
        latitude=35.8150,
        longitude=127.1530,
        mode=LocationMode.BUS_STOP,
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
    """Return static catalog seeds (stations / fixtures)."""
    if mode == LocationMode.STATION:
        stations = list(load_stations())
        if nationwide or city is None:
            return stations
        return [item for item in stations if item.city == city]

    if mode == LocationMode.BUS_STOP:
        seeds = BUS_STOP_SEEDS
        if city is None:
            return list(seeds)
        return [item for item in seeds if item.city == city]

    if city is None:
        return list(NEIGHBORHOODS)
    return [item for item in NEIGHBORHOODS if item.city == city]
