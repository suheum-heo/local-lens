"""Live Google Places API provider (requires GOOGLE_PLACES_API_KEY)."""

from __future__ import annotations

import httpx

from app.config import settings
from app.domain.models import GooglePlaceData
from app.providers.base import GooglePlacesProvider

FIND_PLACE_URL = "https://maps.googleapis.com/maps/api/place/findplacefromtext/json"
DETAILS_URL = "https://maps.googleapis.com/maps/api/place/details/json"


class LiveGooglePlacesProvider(GooglePlacesProvider):
    def __init__(self, api_key: str | None = None) -> None:
        self._api_key = api_key or settings.google_places_api_key
        if not self._api_key:
            raise ValueError("GOOGLE_PLACES_API_KEY is required for live Google provider")

    async def find_place(
        self,
        name: str,
        latitude: float,
        longitude: float,
        address: str | None = None,
    ) -> GooglePlaceData | None:
        input_text = f"{name} {address}" if address else name
        params = {
            "input": input_text,
            "inputtype": "textquery",
            "fields": "place_id,name,formatted_address,geometry,rating,user_ratings_total",
            "locationbias": f"circle:500@{latitude},{longitude}",
            "key": self._api_key,
            "language": "ko",
        }
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.get(FIND_PLACE_URL, params=params)
            resp.raise_for_status()
            data = resp.json()

        candidates = data.get("candidates") or []
        if not candidates:
            return None
        c = candidates[0]
        loc = (c.get("geometry") or {}).get("location") or {}
        return GooglePlaceData(
            google_place_id=c["place_id"],
            name=c.get("name", name),
            address=c.get("formatted_address"),
            latitude=loc.get("lat"),
            longitude=loc.get("lng"),
            rating=c.get("rating"),
            user_rating_count=c.get("user_ratings_total"),
            review_metadata=[],
        )

    async def get_place_details(self, google_place_id: str) -> GooglePlaceData | None:
        params = {
            "place_id": google_place_id,
            "fields": "place_id,name,formatted_address,geometry,rating,user_ratings_total,reviews",
            "key": self._api_key,
            "language": "ko",
            "reviews_no_translations": "true",
        }
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.get(DETAILS_URL, params=params)
            resp.raise_for_status()
            data = resp.json()

        result = data.get("result")
        if not result:
            return None
        loc = (result.get("geometry") or {}).get("location") or {}
        reviews = result.get("reviews") or []
        return GooglePlaceData(
            google_place_id=result["place_id"],
            name=result.get("name", ""),
            address=result.get("formatted_address"),
            latitude=loc.get("lat"),
            longitude=loc.get("lng"),
            rating=result.get("rating"),
            user_rating_count=result.get("user_ratings_total"),
            review_metadata=[
                {
                    "language": r.get("language"),
                    "rating": r.get("rating"),
                    "text": r.get("text"),
                }
                for r in reviews
            ],
        )
