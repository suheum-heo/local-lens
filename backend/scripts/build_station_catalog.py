#!/usr/bin/env python3
"""Harvest nationwide subway / urban-rail stations via Kakao Local SW8.

Writes backend/app/data/stations.json (static catalog for GET /api/locations).

The previous sparse 20km grid missed dense-area stations (e.g. 노량진역) because
Kakao returns at most ~45 pageable hits per origin. This script uses a dense
grid with smaller radii, then fills remaining gaps via keyword lookup against
an OSM subway-station name list.

Usage (from backend/, with KAKAO_REST_API_KEY in .env):
  source .venv/bin/activate
  python scripts/build_station_catalog.py
"""

from __future__ import annotations

import json
import math
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
KEYWORD_URL = "https://dapi.kakao.com/v2/local/search/keyword.json"
OVERPASS_URL = "https://overpass-api.de/api/interpreter"

# Bounding boxes: (min_lon, min_lat, max_lon, max_lat, step_m, radius_m, label)
# Smaller radius + denser steps beat Kakao's ~45-result ceiling in dense metros.
REGIONS: list[tuple[float, float, float, float, int, int, str]] = [
    # Capital region (Seoul / Gyeonggi / Incheon) — north to 소요산/동두천
    (126.45, 37.25, 127.35, 38.05, 4500, 7000, "capital"),
    # Busan / southeast
    (128.85, 35.05, 129.30, 35.35, 5000, 8000, "busan"),
    # Daegu
    (128.45, 35.78, 128.75, 35.95, 5000, 8000, "daegu"),
    # Gwangju
    (126.75, 35.08, 127.00, 35.25, 5000, 8000, "gwangju"),
    # Daejeon
    (127.28, 36.25, 127.50, 36.45, 5000, 8000, "daejeon"),
    # Ulsan
    (129.20, 35.45, 129.45, 35.65, 6000, 9000, "ulsan"),
    # Changwon / Gimhae corridor
    (128.55, 35.15, 128.95, 35.30, 6000, 9000, "changwon"),
    # Pohang
    (129.30, 35.95, 129.45, 36.10, 7000, 10000, "pohang"),
]


def _grid_centers(
    min_lon: float,
    min_lat: float,
    max_lon: float,
    max_lat: float,
    step_m: int,
) -> list[tuple[float, float]]:
    mid_lat = (min_lat + max_lat) / 2.0
    dlat = step_m / 111_320.0
    dlon = step_m / (111_320.0 * max(math.cos(math.radians(mid_lat)), 0.2))
    centers: list[tuple[float, float]] = []
    lat = min_lat
    while lat <= max_lat + 1e-9:
        lon = min_lon
        while lon <= max_lon + 1e-9:
            centers.append((lon, lat))
            lon += dlon
        lat += dlat
    return centers


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
    if "경주" in address:
        return "gyeongju"
    if "김해" in address or "부산김해" in place_name:
        return "busan"
    # Capital-region satellites → searchable under Seoul metro UX bucket
    if address.startswith(("경기", "세종")):
        return "seoul"
    return "other"


_LINE_SUFFIX = re.compile(
    r"\s+(?:"
    r"GTX-?[A-Z]|"
    r"김포골드라인|"
    r"공항철도|"
    r"자기부상철도|"
    r"광역전철|"
    r".+경전철|"
    r"에버라인|"
    r".*호선|"
    r".+선|"
    r".+라인"
    r")$"
)


def display_name(place_name: str) -> str:
    """Strip line suffixes: '강남역 신분당선' → '강남역'."""
    name = place_name.strip()
    cleaned = _LINE_SUFFIX.sub("", name).strip()
    # Kakao sometimes returns '역명 노선명' without a line keyword we know —
    # keep only the first token group ending with 역.
    if " " in cleaned:
        first, rest = cleaned.split(" ", 1)
        if first.endswith("역") and rest:
            cleaned = first
    return cleaned or name


def ensure_station_suffix(name: str) -> str:
    n = name.strip()
    if not n:
        return n
    if n.endswith("역"):
        return n
    return f"{n}역"


def slugify(name: str, place_id: str) -> str:
    base = display_name(name)
    if base.endswith("역"):
        base = base[:-1]
    base = re.sub(r"[^0-9A-Za-z가-힣]+", "_", base).strip("_").lower()
    if not base:
        base = place_id
    return f"st_{base}_{place_id[-6:]}"


def _ingest_doc(by_id: dict[str, dict], doc: dict) -> None:
    pid = str(doc.get("id") or "")
    name = str(doc.get("place_name") or "").strip()
    if not pid or not name:
        return
    # Skip non-station noise that sometimes appears under SW8/keyword.
    # Do not filter on bare '정류장' — 서부정류장역 is a real Daegu subway stop.
    lower = name.lower()
    if any(tok in name for tok in ("출구", "버스정류", "주차장", "화장실")):
        return
    if "역" not in name and "station" not in lower:
        return
    try:
        x = float(doc["x"])
        y = float(doc["y"])
    except (KeyError, TypeError, ValueError):
        return
    address = str(doc.get("address_name") or "")
    display = ensure_station_suffix(display_name(name))
    city = city_from_address(address, name)
    prev = by_id.get(pid)
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


def harvest_category(client: httpx.Client) -> dict[str, dict]:
    by_id: dict[str, dict] = {}
    total_centers = 0
    for min_lon, min_lat, max_lon, max_lat, step_m, radius_m, label in REGIONS:
        centers = _grid_centers(min_lon, min_lat, max_lon, max_lat, step_m)
        total_centers += len(centers)
        print(f"{label}: {len(centers)} centers @ {step_m}m / r={radius_m}m")
        for i, (lon, lat) in enumerate(centers, 1):
            for page in range(1, 4):  # Kakao caps pageable results ~45
                resp = client.get(
                    CATEGORY_URL,
                    params={
                        "category_group_code": "SW8",
                        "x": str(lon),
                        "y": str(lat),
                        "radius": str(radius_m),
                        "size": 15,
                        "page": page,
                        "sort": "distance",
                    },
                )
                if resp.status_code != 200:
                    print(f"  warn {label} #{i} page {page}: HTTP {resp.status_code}")
                    break
                data = resp.json()
                docs = data.get("documents") or []
                if not docs:
                    break
                for doc in docs:
                    _ingest_doc(by_id, doc)
                meta = data.get("meta") or {}
                if meta.get("is_end", True):
                    break
                time.sleep(0.03)
            if i % 25 == 0:
                print(f"  {label} {i}/{len(centers)} unique={len(by_id)}")
            time.sleep(0.03)
    print(f"category pass: {len(by_id)} unique from {total_centers} centers")
    return by_id


def fetch_osm_subway_names() -> list[str]:
    """Return Hangul subway/light-rail station names from OSM (audit source)."""
    query = """
    [out:json][timeout:180];
    area["ISO3166-1"="KR"][admin_level=2]->.kr;
    (
      node["station"="subway"](area.kr);
      node["railway"="station"]["subway"="yes"](area.kr);
      node["railway"="station"]["station"="subway"](area.kr);
      way["station"="subway"](area.kr);
      node["railway"="station"]["name"~"역$"](area.kr);
    );
    out tags center;
    """
    try:
        with httpx.Client(timeout=200.0) as client:
            resp = client.post(OVERPASS_URL, data={"data": query})
            if resp.status_code != 200:
                print(f"OSM overpass HTTP {resp.status_code}; skipping gap fill")
                return []
            data = resp.json()
    except Exception as exc:  # noqa: BLE001
        print(f"OSM overpass failed: {type(exc).__name__}; skipping gap fill")
        return []

    names: set[str] = set()
    for el in data.get("elements") or []:
        tags = el.get("tags") or {}
        name = str(tags.get("name") or tags.get("name:ko") or "").strip()
        if not name:
            continue
        # Prefer urban rail; drop long-distance-only KTX-style if obvious.
        railway = str(tags.get("railway") or "")
        station = str(tags.get("station") or "")
        subway = str(tags.get("subway") or "")
        if station != "subway" and subway != "yes":
            # Keep *역 names that look like metro stops; drop 정류장 etc.
            if not name.endswith("역"):
                continue
            if any(x in name for x in ("버스", "정류장", "화물", "조차")):
                continue
            if railway not in {"station", "halt", ""}:
                continue
        names.add(ensure_station_suffix(display_name(name)))
    print(f"OSM subway-ish names: {len(names)}")
    return sorted(names)


def fill_gaps_by_keyword(
    client: httpx.Client,
    by_id: dict[str, dict],
    osm_names: list[str],
) -> None:
    have = {re.sub(r"\s+", "", s["name"]) for s in by_id.values()}
    missing = [n for n in osm_names if re.sub(r"\s+", "", n) not in have]
    print(f"keyword gap fill: {len(missing)} OSM names not in catalog")
    added = 0
    for i, name in enumerate(missing, 1):
        resp = client.get(
            KEYWORD_URL,
            params={
                "query": name,
                "category_group_code": "SW8",
                "size": 5,
                "page": 1,
            },
        )
        if resp.status_code != 200:
            print(f"  warn keyword {name}: HTTP {resp.status_code}")
            time.sleep(0.1)
            continue
        docs = (resp.json().get("documents") or [])
        # Prefer exact / near-exact display name match.
        target = re.sub(r"\s+", "", name)
        chosen = None
        for doc in docs:
            disp = re.sub(r"\s+", "", ensure_station_suffix(display_name(str(doc.get("place_name") or ""))))
            if disp == target or disp.startswith(target) or target.startswith(disp):
                chosen = doc
                break
        if chosen is None and docs:
            # Fall back to first SW8 hit only if names share the bare stem.
            stem = target.replace("역", "")
            for doc in docs:
                disp = ensure_station_suffix(display_name(str(doc.get("place_name") or "")))
                if stem and stem in disp.replace(" ", ""):
                    chosen = doc
                    break
        if chosen is not None:
            before = len(by_id)
            _ingest_doc(by_id, chosen)
            if len(by_id) > before:
                added += 1
        if i % 50 == 0:
            print(f"  keyword {i}/{len(missing)} added={added} unique={len(by_id)}")
        time.sleep(0.05)
    print(f"keyword gap fill done: +{added} (unique now {len(by_id)})")


def collapse(by_id: dict[str, dict]) -> list[dict]:
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
        if len(item["name"]) < len(existing["name"]):
            idx = collapsed.index(existing)
            collapsed[idx] = item
            seen_keys[key] = item
    return collapsed


def to_public(collapsed: list[dict]) -> list[dict]:
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


def harvest() -> list[dict]:
    key = settings.kakao_rest_api_key
    if not key:
        raise SystemExit("KAKAO_REST_API_KEY is required")

    headers = {"Authorization": f"KakaoAK {key}"}
    with httpx.Client(timeout=30.0, headers=headers) as client:
        by_id = harvest_category(client)
        osm_names = fetch_osm_subway_names()
        if osm_names:
            fill_gaps_by_keyword(client, by_id, osm_names)
        # Hard guarantee for known gaps even if OSM / grid harvest misses them.
        force = [
            "노량진역",
            "지행역",
            "동두천중앙역",
            "보산역",
            "동두천역",
            "소요산역",
            "서부정류장역",
            "걸포북변역",
            "구래역",
            "사우역",
            "영종역",
            "운서역",
            "청라국제도시역",
            "공항화물청사역",
            "인천공항1터미널역",
            "인천공항2터미널역",
            "동탄역",
        ]
        have = {re.sub(r"\s+", "", s["name"]) for s in by_id.values()}
        missing_force = [n for n in force if re.sub(r"\s+", "", n) not in have]
        if missing_force:
            print(f"forcing keyword lookup for {len(missing_force)} must-have stations")
            fill_gaps_by_keyword(client, by_id, missing_force)

    return to_public(collapse(by_id))


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
    must = [
        "노량진역",
        "합정역",
        "강남역",
        "서면역",
        "동대구역",
        "대전역",
        "종합운동장역",
        "소요산역",
        "서부정류장역",
        "걸포북변역",
        "인천공항1터미널역",
    ]
    names = {s["name"] for s in stations}
    for m in must:
        print(f"  {'OK' if m in names else 'MISSING'}: {m}")


if __name__ == "__main__":
    main()
