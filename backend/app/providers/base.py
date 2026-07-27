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
    async def search_places(
        self,
        name: str,
        latitude: float,
        longitude: float,
        address: str | None = None,
    ) -> list[GooglePlaceData]:
        """Return zero or more Google place candidates near the given query.

        Callers (the matcher) must score candidates — do not assume index 0
        is the correct match.
        """
        raise NotImplementedError

    @abstractmethod
    async def get_place_details(self, google_place_id: str) -> GooglePlaceData | None:
        """Optional enrichment when search did not return scoring fields."""
        raise NotImplementedError
