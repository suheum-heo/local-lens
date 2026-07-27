"""Location selection models.

SearchArea is the common abstraction used by restaurant search so that
downstream logic does not care whether locations came from subway stations
or neighborhoods.
"""

from __future__ import annotations

from typing import Annotated, Literal, Union
from uuid import uuid4

from pydantic import BaseModel, Field, field_validator

from app.domain.enums import City, LocationMode

DEFAULT_SEARCH_RADIUS_M = 1000

# Allowed radii for station-based searches (MVP UI options).
STATION_RADIUS_OPTIONS_M: tuple[int, ...] = (500, 1000, 1500, 2000)


class StationLocation(BaseModel):
    """Subway station search anchor."""

    type: Literal["station"] = "station"
    station_id: str
    station_name: str
    city: City
    latitude: float
    longitude: float
    radius_m: int = DEFAULT_SEARCH_RADIUS_M

    @field_validator("radius_m")
    @classmethod
    def radius_allowed(cls, v: int) -> int:
        if v not in STATION_RADIUS_OPTIONS_M:
            raise ValueError(
                f"radius_m must be one of {list(STATION_RADIUS_OPTIONS_M)}"
            )
        return v


class NeighborhoodLocation(BaseModel):
    """Administrative / local neighborhood search area."""

    type: Literal["neighborhood"] = "neighborhood"
    neighborhood_id: str
    neighborhood_name: str
    city: City
    latitude: float
    longitude: float
    radius_m: int = DEFAULT_SEARCH_RADIUS_M

    @field_validator("radius_m")
    @classmethod
    def radius_positive(cls, v: int) -> int:
        if v <= 0:
            raise ValueError("radius_m must be positive")
        return v


LocationInput = Annotated[
    Union[StationLocation, NeighborhoodLocation],
    Field(discriminator="type"),
]


class SearchArea(BaseModel):
    """Normalized search area used by discovery — origin-agnostic.

    Restaurant search / Kakao queries operate on SearchArea only.
    """

    area_id: str = Field(default_factory=lambda: str(uuid4()))
    label: str
    city: City
    latitude: float
    longitude: float
    radius_m: int = DEFAULT_SEARCH_RADIUS_M
    source_mode: LocationMode
    source_id: str

    @classmethod
    def from_location(cls, loc: StationLocation | NeighborhoodLocation) -> SearchArea:
        if isinstance(loc, StationLocation):
            return cls(
                label=loc.station_name,
                city=loc.city,
                latitude=loc.latitude,
                longitude=loc.longitude,
                radius_m=loc.radius_m,
                source_mode=LocationMode.STATION,
                source_id=loc.station_id,
            )
        return cls(
            label=loc.neighborhood_name,
            city=loc.city,
            latitude=loc.latitude,
            longitude=loc.longitude,
            radius_m=loc.radius_m,
            source_mode=LocationMode.NEIGHBORHOOD,
            source_id=loc.neighborhood_id,
        )


class SearchRequestLocations(BaseModel):
    """Multi-location search payload (stations OR neighborhoods)."""

    mode: LocationMode
    locations: list[LocationInput] = Field(min_length=1)

    def to_search_areas(self) -> list[SearchArea]:
        return [SearchArea.from_location(loc) for loc in self.locations]
