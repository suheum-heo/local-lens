"""Normalize and deduplicate Kakao restaurant candidates across search areas."""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field
from uuid import uuid4

from app.domain.models import KakaoPlaceData


@dataclass
class NormalizedCandidate:
    restaurant_id: str
    kakao: KakaoPlaceData
    source_area_ids: list[str] = field(default_factory=list)


def normalize_and_dedupe(
    area_results: list[tuple[str, list[KakaoPlaceData]]],
) -> list[NormalizedCandidate]:
    """
    Merge candidates from multiple SearchAreas.

    Dedup key: Kakao place id (stable across overlapping radius searches).
    Secondary soft-dedupe is not applied in MVP — Kakao IDs are authoritative.
    """
    by_kakao_id: dict[str, NormalizedCandidate] = {}
    area_map: dict[str, set[str]] = defaultdict(set)

    for area_id, places in area_results:
        for place in places:
            area_map[place.kakao_place_id].add(area_id)
            if place.kakao_place_id not in by_kakao_id:
                by_kakao_id[place.kakao_place_id] = NormalizedCandidate(
                    restaurant_id=str(uuid4()),
                    kakao=place,
                    source_area_ids=[],
                )

    results: list[NormalizedCandidate] = []
    for kid, candidate in by_kakao_id.items():
        candidate.source_area_ids = sorted(area_map[kid])
        results.append(candidate)
    return results
