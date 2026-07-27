"""Search and location catalog API routes."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query

from app.domain.contracts import LocationCatalogItem, SearchRequest, SearchResponse
from app.domain.enums import City, LocationMode
from app.providers.mock_data import catalog_for_city
from app.services.search_orchestrator import SearchOrchestrator

router = APIRouter()
_orchestrator = SearchOrchestrator()


@router.post("/search", response_model=SearchResponse)
async def search_restaurants(body: SearchRequest) -> SearchResponse:
    if not body.locations:
        raise HTTPException(status_code=400, detail="At least one location is required")

    # Validate location types match mode
    for loc in body.locations:
        expected = "station" if body.mode == LocationMode.STATION else "neighborhood"
        if loc.type != expected:
            raise HTTPException(
                status_code=400,
                detail=f"Location type '{loc.type}' does not match mode '{body.mode.value}'",
            )
        if loc.city != body.city:
            raise HTTPException(
                status_code=400,
                detail=f"Location city '{loc.city.value}' does not match request city '{body.city.value}'",
            )

    return await _orchestrator.search(body)


@router.get("/locations", response_model=list[LocationCatalogItem])
async def list_locations(
    city: City = Query(...),
    mode: LocationMode = Query(...),
) -> list[LocationCatalogItem]:
    return catalog_for_city(city, mode)
