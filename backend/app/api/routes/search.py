"""Search and location catalog API routes."""

from __future__ import annotations

import logging

from fastapi import APIRouter, HTTPException, Query

from app.domain.contracts import LocationCatalogItem, SearchRequest, SearchResponse
from app.domain.enums import City, LocationMode
from app.providers.errors import ProviderAPIError, ProviderConfigError
from app.providers.location_catalog import catalog_for_city
from app.services.search_orchestrator import create_search_orchestrator

logger = logging.getLogger(__name__)

router = APIRouter()


@router.post("/search", response_model=SearchResponse)
async def search_restaurants(body: SearchRequest) -> SearchResponse:
    if not body.locations:
        raise HTTPException(status_code=400, detail="At least one location is required")

    for loc in body.locations:
        expected = "station" if body.mode == LocationMode.STATION else "neighborhood"
        if loc.type != expected:
            raise HTTPException(
                status_code=400,
                detail=(
                    f"Location type '{loc.type}' does not match mode "
                    f"'{body.mode.value}'"
                ),
            )
        # Station mode allows nationwide picks; city on the request is contextual.
        if body.mode != LocationMode.STATION and loc.city != body.city:
            raise HTTPException(
                status_code=400,
                detail=(
                    f"Location city '{loc.city.value}' does not match request city "
                    f"'{body.city.value}'"
                ),
            )

    try:
        orchestrator = create_search_orchestrator()
        return await orchestrator.search(body)
    except ProviderConfigError as exc:
        raise HTTPException(status_code=503, detail=exc.message) from exc
    except ProviderAPIError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.message) from exc
    except Exception as exc:
        logger.exception("Unexpected search failure")
        raise HTTPException(
            status_code=500,
            detail="Search failed due to an unexpected server error.",
        ) from exc


@router.get("/locations", response_model=list[LocationCatalogItem])
async def list_locations(
    mode: LocationMode = Query(...),
    city: City | None = Query(
        None,
        description="Optional city filter. Omit (or use nationwide) for all subway stations.",
    ),
    nationwide: bool = Query(
        False,
        description="When true with mode=station, return the full national catalog.",
    ),
) -> list[LocationCatalogItem]:
    # Station picker defaults to nationwide so any station is searchable.
    if mode == LocationMode.STATION and (nationwide or city is None):
        return catalog_for_city(None, mode, nationwide=True)
    if city is None:
        raise HTTPException(
            status_code=400,
            detail="city is required when mode is neighborhood (or when not nationwide).",
        )
    return catalog_for_city(city, mode, nationwide=False)
