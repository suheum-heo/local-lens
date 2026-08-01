"""Restaurant and platform data domain models."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field

from app.domain.enums import (
    DataAvailability,
    MatchConfidenceLevel,
    RatingCoverage,
    RestaurantLabel,
)

class KakaoPlaceData(BaseModel):
    """Normalized Kakao Local place fields."""

    kakao_place_id: str
    name: str
    address: str | None = None
    road_address: str | None = None
    latitude: float
    longitude: float
    category: str | None = None
    place_url: str | None = None
    # Official Local keyword search omits these; live mode may fill them via
    # unofficial Kakao Map place-detail enrichment (or mock fixtures).
    rating: float | None = None
    review_count: int | None = None


class GooglePlaceData(BaseModel):
    """Normalized Google Places fields when a match exists."""

    google_place_id: str
    name: str
    address: str | None = None
    latitude: float | None = None
    longitude: float | None = None
    rating: float | None = None
    user_rating_count: int | None = None
    review_metadata: list[dict[str, Any]] = Field(default_factory=list)
    # Places API (New) photo resource name, e.g. places/ChIJ…/photos/…
    # Never stores API keys or credentialed media URLs.
    photo_name: str | None = None
    photo_attributions: list[str] = Field(default_factory=list)


class PlaceMatchResult(BaseModel):
    """Outcome of Kakao → Google place matching."""

    confidence: float = Field(ge=0.0, le=1.0)
    confidence_level: MatchConfidenceLevel
    matched: bool
    google: GooglePlaceData | None = None
    reason: str | None = None


class PlatformSignal(BaseModel):
    """Scored view of one platform's data with explicit availability."""

    availability: DataAvailability
    rating: float | None = None
    review_count: int | None = None
    score: float | None = None
    explanation: str | None = None


class ScoreBundle(BaseModel):
    local: PlatformSignal
    global_: PlatformSignal = Field(
        validation_alias="global",
        serialization_alias="global",
    )
    consensus: PlatformSignal

    model_config = {
        "populate_by_name": True,
        "ser_json_by_alias": True,
    }


class Restaurant(BaseModel):
    """Internal restaurant entity after normalization + matching + scoring."""

    restaurant_id: str
    name: str
    address: str | None = None
    road_address: str | None = None
    latitude: float
    longitude: float
    category: str | None = None
    kakao: KakaoPlaceData
    google: GooglePlaceData | None = None
    match: PlaceMatchResult
    scores: ScoreBundle
    label: RestaurantLabel | None = None
    rating_coverage: RatingCoverage = RatingCoverage.NONE
    source_area_ids: list[str] = Field(default_factory=list)
    # Representative Google photo (optional). photo_url is a LocalLens proxy path only.
    photo_name: str | None = None
    photo_url: str | None = None
    photo_attributions: list[str] = Field(default_factory=list)


# Rebuild for forward refs if needed
ScoreBundle.model_rebuild()
