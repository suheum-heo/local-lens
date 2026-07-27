"""API request / response contracts."""

from __future__ import annotations

from pydantic import BaseModel, Field

from app.domain.enums import City, LocationMode, RestaurantLabel
from app.domain.locations import LocationInput
from app.domain.models import Restaurant


class SearchRequest(BaseModel):
    city: City
    mode: LocationMode
    locations: list[LocationInput] = Field(min_length=1)
    query: str = Field(min_length=1, description="Restaurant category or keyword")
    language: str = "ko"


class SearchMeta(BaseModel):
    provider_mode: str
    area_count: int
    candidate_count: int
    result_count: int
    query: str
    city: City
    mode: LocationMode
    api_calls: dict[str, int] | None = None


class SearchResponse(BaseModel):
    results: list[Restaurant]
    meta: SearchMeta
    notices: list[str] = Field(default_factory=list)


class LocationCatalogItem(BaseModel):
    """Catalog entry for UI location pickers."""

    id: str
    name: str
    name_en: str | None = None
    city: City
    latitude: float
    longitude: float
    mode: LocationMode
    default_radius_m: int = 1000


class LabelInfo(BaseModel):
    label: RestaurantLabel
    display_ko: str
    display_en: str
