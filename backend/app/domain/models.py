"""Restaurant and platform data domain models."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field

from app.domain.enums import DataAvailability, MatchConfidenceLevel, RestaurantLabel


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
    # Kakao Local API does not expose star ratings in the standard place search;
    # keep optional for future enrichment / mock realism.
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
    source_area_ids: list[str] = Field(default_factory=list)


# Rebuild for forward refs if needed
ScoreBundle.model_rebuild()
