"""Provider interfaces for Kakao Local and Google Places."""

from __future__ import annotations

from abc import ABC, abstractmethod

from app.domain.locations import SearchArea
from app.domain.models import GooglePlaceData, KakaoPlaceData


class KakaoLocalProvider(ABC):
    """Discover restaurant candidates near a search area."""

    @abstractmethod
    async def search_restaurants(
        self,
        area: SearchArea,
        query: str,
    ) -> list[KakaoPlaceData]:
        raise NotImplementedError


class GooglePlacesProvider(ABC):
    """Look up Google Places entities for matching / enrichment."""

    @abstractmethod
    async def find_place(
        self,
        name: str,
        latitude: float,
        longitude: float,
        address: str | None = None,
    ) -> GooglePlaceData | None:
        """Return a candidate Google place near the given coordinates, or None."""
        raise NotImplementedError

    @abstractmethod
    async def get_place_details(self, google_place_id: str) -> GooglePlaceData | None:
        raise NotImplementedError
