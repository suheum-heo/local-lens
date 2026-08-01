"""Live location lookup for bus stops (OSM Overpass) and dongs (Kakao address)."""

from __future__ import annotations

import logging
import re
from typing import Any

import httpx

from app.config import settings
from app.domain.contracts import LocationCatalogItem
from app.domain.enums import City, LocationMode

logger = logging.getLogger(__name__)

OVERPASS_URL = "https://overpass-api.de/api/interpreter"
KAKAO_ADDRESS_URL = "https://dapi.kakao.com/v2/local/search/address.json"

CITY_CENTERS: dict[City, tuple[float, float]] = {
    City.SEOUL: (126.9780, 37.5665),
    City.BUSAN: (129.0756, 35.1796),
    City.DAEGU: (128.6014, 35.8714),
    City.INCHEON: (126.7052, 37.4563),
    City.GWANGJU: (126.8526, 35.1595),
    City.DAEJEON: (127.3845, 36.3504),
    City.ULSAN: (129.3114, 35.5384),
    City.JEONJU: (127.1480, 35.8242),
    City.OTHER: (127.5, 36.5),
}

# Seoul mode also covers capital-region suburbs for bus search radius.
CITY_SEARCH_RADIUS_M: dict[City, int] = {
    City.SEOUL: 45000,
    City.BUSAN: 25000,
    City.DAEGU: 20000,
    City.INCHEON: 25000,
    City.GWANGJU: 20000,
    City.DAEJEON: 20000,
    City.ULSAN: 20000,
    City.JEONJU: 15000,
    City.OTHER: 30000,
}


async def search_bus_stops(
    city: City,
    query: str,
    *,
    transport: httpx.AsyncBaseTransport | None = None,
    limit: int = 40,
) -> list[LocationCatalogItem]:
    """Search OSM bus stops near the city by Hangul/Latin name substring."""
    q = query.strip()
    if len(q) < 2:
        return []

    lon, lat = CITY_CENTERS.get(city, CITY_CENTERS[City.OTHER])
    radius = CITY_SEARCH_RADIUS_M.get(city, 30000)
    # Escape Overpass regex metacharacters in user input.
    pattern = re.escape(q)
    ql = f"""
    [out:json][timeout:20];
    (
      node["highway"="bus_stop"]["name"~"{pattern}"](around:{radius},{lat},{lon});
      node["public_transport"="platform"]["bus"="yes"]["name"~"{pattern}"](around:{radius},{lat},{lon});
    );
    out body {max(1, min(limit, 60))};
    """
    try:
        async with httpx.AsyncClient(timeout=25.0, transport=transport) as client:
            resp = await client.post(
                OVERPASS_URL,
                data={"data": ql},
                headers={"User-Agent": "LocalLens/0.1 (bus-stop search)"},
            )
            resp.raise_for_status()
            data = resp.json()
    except Exception as exc:  # noqa: BLE001 — soft-fail catalog lookup
        logger.warning("Overpass bus-stop search failed: %s", type(exc).__name__)
        return []

    elements = data.get("elements") or []
    items: list[LocationCatalogItem] = []
    seen: set[str] = set()
    for el in elements:
        tags = el.get("tags") or {}
        name = str(tags.get("name") or "").strip()
        lat_v = el.get("lat")
        lon_v = el.get("lon")
        osm_id = el.get("id")
        if not name or lat_v is None or lon_v is None or osm_id is None:
            continue
        key = f"{name}|{round(float(lat_v), 5)}|{round(float(lon_v), 5)}"
        if key in seen:
            continue
        seen.add(key)
        items.append(
            LocationCatalogItem(
                id=f"bus_osm_{osm_id}",
                name=name,
                name_en=None,
                city=city,
                latitude=float(lat_v),
                longitude=float(lon_v),
                mode=LocationMode.BUS_STOP,
                default_radius_m=1000,
            )
        )
        if len(items) >= limit:
            break
    return items


async def search_neighborhoods(
    city: City,
    query: str,
    *,
    transport: httpx.AsyncBaseTransport | None = None,
    limit: int = 40,
) -> list[LocationCatalogItem]:
    """Search administrative regions (동/읍/면) via Kakao address API."""
    q = query.strip()
    if len(q) < 1:
        return []

    api_key = settings.kakao_rest_api_key
    if not api_key:
        return []

    # Bias query with city label so "합정동" prefers Seoul when city=seoul.
    city_prefix = {
        City.SEOUL: "서울",
        City.BUSAN: "부산",
        City.DAEGU: "대구",
        City.INCHEON: "인천",
        City.GWANGJU: "광주",
        City.DAEJEON: "대전",
        City.ULSAN: "울산",
        City.JEONJU: "전주",
        City.OTHER: "",
    }.get(city, "")
    search_q = f"{city_prefix} {q}".strip()

    try:
        async with httpx.AsyncClient(timeout=15.0, transport=transport) as client:
            resp = await client.get(
                KAKAO_ADDRESS_URL,
                headers={"Authorization": f"KakaoAK {api_key}"},
                params={"query": search_q, "size": min(limit, 30)},
            )
            if resp.status_code >= 400:
                logger.warning("Kakao address search HTTP %s", resp.status_code)
                return []
            data = resp.json()
    except Exception as exc:  # noqa: BLE001
        logger.warning("Kakao address search failed: %s", type(exc).__name__)
        return []

    items: list[LocationCatalogItem] = []
    seen: set[str] = set()
    for doc in data.get("documents") or []:
        if not isinstance(doc, dict):
            continue
        # Prefer REGION (동/구) over road parcels.
        addr_type = str(doc.get("address_type") or "")
        if addr_type not in {"REGION", "REGION_ADDR", ""}:
            # Still allow REGION_ADDR; skip pure ROAD if we already have enough.
            if addr_type == "ROAD" and len(items) >= 5:
                continue
        try:
            lat = float(doc["y"])
            lon = float(doc["x"])
        except (KeyError, TypeError, ValueError):
            continue
        name = _region_label(doc)
        if not name:
            continue
        mapped_city = _city_from_address_name(str(doc.get("address_name") or ""))
        if city != City.OTHER and mapped_city not in {city, City.OTHER}:
            # Soft filter: keep capital-region hits when searching Seoul.
            if not (city == City.SEOUL and mapped_city == City.OTHER):
                if mapped_city != city:
                    continue
        key = f"{name}|{round(lat, 5)}|{round(lon, 5)}"
        if key in seen:
            continue
        seen.add(key)
        slug = re.sub(r"[^0-9A-Za-z가-힣]+", "_", name).strip("_") or "nb"
        items.append(
            LocationCatalogItem(
                id=f"nb_{slug}_{abs(hash(key)) % 10_000_000}",
                name=name,
                name_en=None,
                city=mapped_city if mapped_city != City.OTHER else city,
                latitude=lat,
                longitude=lon,
                mode=LocationMode.NEIGHBORHOOD,
                default_radius_m=1000,
            )
        )
        if len(items) >= limit:
            break
    return items


def _region_label(doc: dict[str, Any]) -> str:
    address = doc.get("address") if isinstance(doc.get("address"), dict) else {}
    h_name = str(address.get("region_3depth_h_name") or "").strip()
    name = str(address.get("region_3depth_name") or "").strip()
    label = h_name or name or str(doc.get("address_name") or "").strip()
    # Prefer short dong label when full address is lengthy.
    if label and " " in label:
        parts = label.split()
        if parts[-1].endswith(("동", "읍", "면", "가", "리")):
            return parts[-1] if len(parts[-1]) >= 2 else label
    return label


def _city_from_address_name(address: str) -> City:
    if address.startswith("서울") or "서울" in address[:6]:
        return City.SEOUL
    if address.startswith("부산"):
        return City.BUSAN
    if address.startswith("대구"):
        return City.DAEGU
    if address.startswith("인천"):
        return City.INCHEON
    if "광주" in address:
        return City.GWANGJU
    if address.startswith("대전"):
        return City.DAEJEON
    if address.startswith("울산"):
        return City.ULSAN
    if "전주" in address:
        return City.JEONJU
    if address.startswith(("경기", "세종")):
        return City.SEOUL
    return City.OTHER
