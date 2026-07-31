#!/usr/bin/env python3
"""Harvest nationwide subway stations via Kakao Local category SW8.

Writes backend/app/data/stations.json (static catalog for GET /api/locations).

Usage (from backend/, with KAKAO_REST_API_KEY in .env):
  source .venv/bin/activate
  python scripts/build_station_catalog.py
"""

from __future__ import annotations

import json
import re
import sys
import time
from collections import defaultdict
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.config import settings  # noqa: E402

OUT = ROOT / "app" / "data" / "stations.json"
CATEGORY_URL = "https://dapi.kakao.com/v2/local/search/category.json"

# Grid centers covering major metro regions (lon, lat). Radius 20km each.
CENTERS: list[tuple[float, float, str]] = [
    # Seoul / capital region
    (126.9780, 37.5665, "seoul-jung"),
    (126.9240, 37.5560, "seoul-west"),
    (127.0280, 37.4970, "seoul-gangnam"),
    (127.0700, 37.5400, "seoul-east"),
    (126.8900, 37.5200, "seoul-southwest"),
    (127.1200, 37.5000, "seoul-southeast"),
    (126.9800, 37.6500, "seoul-north"),
    (127.0500, 37.6500, "seoul-northeast"),
    (126.8300, 37.4900, "bucheon"),
    (126.7800, 37.5000, "bucheon-west"),
    (126.7200, 37.4500, "siheung"),
    (126.9500, 37.4000, "anyang"),
    (127.0300, 37.3200, "suwon"),
    (127.1100, 37.3500, "yongin"),
    (127.0000, 37.2700, "suwon-south"),
    (127.2000, 37.4500, "seongnam"),
    (127.1500, 37.4400, "bundang"),
    (127.1300, 37.6000, "guri"),
    (127.2000, 37.6000, "namyangju"),
    (126.7600, 37.6000, "gimpo"),
    (126.7800, 37.7000, "goyang"),
    (126.9000, 37.7500, "uisan"),
    (127.0500, 37.7400, "uiijeongbu"),
    (127.0000, 37.8500, "yangju"),
    (126.6200, 37.4500, "incheon"),
    (126.7000, 37.4500, "incheon-east"),
    (126.5300, 37.4800, "incheon-west"),
    (126.6500, 37.3800, "incheon-south"),
    # Busan / southeast
    (129.0756, 35.1796, "busan"),
    (129.0400, 35.1000, "busan-south"),
    (129.1600, 35.1600, "busan-east"),
    (128.9800, 35.2000, "busan-west"),
    (129.0300, 35.2400, "busan-north"),
    (129.0800, 35.2200, "busan-dongnae"),
    # Daegu
    (128.6014, 35.8714, "daegu"),
    (128.5500, 35.8500, "daegu-west"),
    (128.6500, 35.8800, "daegu-east"),
    (128.6000, 35.8200, "daegu-south"),
    # Gwangju
    (126.8526, 35.1595, "gwangju"),
    (126.9000, 35.1500, "gwangju-east"),
    (126.8000, 35.1600, "gwangju-west"),
    # Daejeon
    (127.3845, 36.3504, "daejeon"),
    (127.4300, 36.3500, "daejeon-east"),
    (127.3400, 36.3300, "daejeon-west"),
    # Others with metro / light rail
    (129.3114, 35.5384, "ulsan"),
    (128.5830, 35.2280, "changwon"),
    (129.3650, 36.0190, "pohang"),
]


def city_from_address(address: str, place_name: str = "") -> str:
    text = f"{address} {place_name}"
    if address.startswith("서울") or "서울" in address[:6]:
        return "seoul"
    if address.startswith("부산") or "부산" in address[:6]:
        return "busan"
    if address.startswith("대구") or "대구" in address[:6]:
        return "daegu"
    if address.startswith("인천") or "인천" in address[:6]:
        return "incheon"
    # Includes legacy 광주광역시 and newer 전남광주통합특별시.
    if "광주" in address or "광주" in place_name:
        return "gwangju"
    if address.startswith("대전") or "대전" in address[:6]:
        return "daejeon"
    if address.startswith("울산") or "울산" in address[:6]:
        return "ulsan"
    if "전주" in address:
        return "jeonju"
    if "김해" in address or "부산김해" in place_name:
        return "busan"
    # Capital-region satellites → searchable under Seoul metro UX bucket
    if address.startswith(("경기", "세종")):
        return "seoul"
    return "other"


_LINE_SUFFIX = re.compile(
    r"\s+(?:\d+호선|.+선|.+경전철|에버라인|자기부상철도)$"
)


def display_name(place_name: str) -> str:
    """Strip line suffixes: '강남역 신분당선' → '강남역'."""
    name = place_name.strip()
    cleaned = _LINE_SUFFIX.sub("", name).strip()
    return cleaned or name


def slugify(name: str, place_id: str) -> str:
    base = display_name(name)
    base = base.replace("역", "")
    base = re.sub(r"[^0-9A-Za-z가-힣]+", "_", base).strip("_").lower()
    if not base:
        base = place_id
    return f"st_{base}_{place_id[-6:]}"


def harvest() -> list[dict]:
    key = settings.kakao_rest_api_key
    if not key:
        raise SystemExit("KAKAO_REST_API_KEY is required")

    by_id: dict[str, dict] = {}
    headers = {"Authorization": f"KakaoAK {key}"}

    with httpx.Client(timeout=20.0, headers=headers) as client:
        for lon, lat, label in CENTERS:
            for page in range(1, 4):  # Kakao caps pageable results ~45
                resp = client.get(
                    CATEGORY_URL,
                    params={
                        "category_group_code": "SW8",
                        "x": str(lon),
                        "y": str(lat),
                        "radius": "20000",
                        "size": 15,
                        "page": page,
                        "sort": "distance",
                    },
                )
                if resp.status_code != 200:
                    print(f"warn {label} page {page}: HTTP {resp.status_code}")
                    break
                data = resp.json()
                docs = data.get("documents") or []
                if not docs:
                    break
                for doc in docs:
                    pid = str(doc.get("id") or "")
                    name = str(doc.get("place_name") or "").strip()
                    if not pid or not name:
                        continue
                    try:
                        x = float(doc["x"])
                        y = float(doc["y"])
                    except (KeyError, TypeError, ValueError):
                        continue
                    address = str(doc.get("address_name") or "")
                    display = display_name(name)
                    city = city_from_address(address, name)
                    prev = by_id.get(pid)
                    # Prefer cleaned station labels over line-suffixed Kakao names.
                    if prev is None or len(display) < len(prev["name"]):
                        by_id[pid] = {
                            "id": slugify(display, pid),
                            "name": display,
                            "name_en": None,
                            "city": city,
                            "latitude": round(y, 6),
                            "longitude": round(x, 6),
                            "mode": "station",
                            "default_radius_m": 1000,
                            "kakao_place_id": pid,
                            "address": address,
                        }
                meta = data.get("meta") or {}
                if meta.get("is_end", True):
                    break
                time.sleep(0.05)
            print(f"{label}: unique so far {len(by_id)}")
            time.sleep(0.05)

    # Dedupe by (normalized name, city) keeping closest-to-centroid... just by id is enough.
    # Collapse transfer duplicates that share nearly same coords + base name.
    items = list(by_id.values())
    items.sort(key=lambda s: (s["city"], s["name"], s["kakao_place_id"]))

    collapsed: list[dict] = []
    seen_keys: dict[tuple[str, str], dict] = {}
    for item in items:
        base = re.sub(r"\s+", "", display_name(item["name"]))
        key = (item["city"], base)
        existing = seen_keys.get(key)
        if existing is None:
            seen_keys[key] = item
            collapsed.append(item)
            continue
        # Prefer shorter cleaned name
        if len(item["name"]) < len(existing["name"]):
            idx = collapsed.index(existing)
            collapsed[idx] = item
            seen_keys[key] = item

    # Strip harvest-only fields from public catalog
    public = []
    for item in collapsed:
        public.append(
            {
                "id": item["id"],
                "name": item["name"],
                "name_en": item["name_en"],
                "city": item["city"],
                "latitude": item["latitude"],
                "longitude": item["longitude"],
                "mode": "station",
                "default_radius_m": 1000,
            }
        )
    public.sort(key=lambda s: (s["city"], s["name"], s["id"]))
    return public


def main() -> None:
    stations = harvest()
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(
        json.dumps(stations, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    by_city: dict[str, int] = defaultdict(int)
    for s in stations:
        by_city[s["city"]] += 1
    print(f"Wrote {len(stations)} stations → {OUT}")
    for city, n in sorted(by_city.items()):
        print(f"  {city}: {n}")


if __name__ == "__main__":
    main()
