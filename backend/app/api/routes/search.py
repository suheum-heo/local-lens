"""Search and location catalog API routes."""

from __future__ import annotations

import logging

from fastapi import APIRouter, HTTPException, Query

from app.domain.contracts import LocationCatalogItem, SearchRequest, SearchResponse
from app.domain.enums import City, LocationMode
from app.providers.errors import ProviderAPIError, ProviderConfigError
from app.providers.location_catalog import catalog_for_city
from app.providers.location_search import search_bus_stops, search_neighborhoods
from app.services.search_orchestrator import create_search_orchestrator

logger = logging.getLogger(__name__)

router = APIRouter()

_MODE_TO_TYPE = {
    LocationMode.STATION: "station",
    LocationMode.BUS_STOP: "bus_stop",
    LocationMode.NEIGHBORHOOD: "neighborhood",
}


@router.post("/search", response_model=SearchResponse)
async def search_restaurants(body: SearchRequest) -> SearchResponse:
    if not body.locations:
        raise HTTPException(status_code=400, detail="At least one location is required")

    expected = _MODE_TO_TYPE[body.mode]
    for loc in body.locations:
        if loc.type != expected:
            raise HTTPException(
                status_code=400,
                detail=(
                    f"Location type '{loc.type}' does not match mode "
                    f"'{body.mode.value}'"
                ),
            )
        # Station/bus modes allow cross-city picks; neighborhood stays city-scoped
        # unless the selected dong's city differs after live lookup.
        if (
            body.mode == LocationMode.NEIGHBORHOOD
            and loc.city != body.city
            and loc.city.value not in {"other"}
        ):
            # Allow mismatch after live address remap; only warn via pass-through.
            pass

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
        description="City filter / bias for live bus & neighborhood lookup.",
    ),
    nationwide: bool = Query(
        False,
        description="When true with mode=station, return the full national catalog.",
    ),
    q: str | None = Query(
        None,
        description="Name query. Required for useful bus_stop results; "
        "enables live dong search for neighborhood mode.",
    ),
) -> list[LocationCatalogItem]:
    query = (q or "").strip()

    if mode == LocationMode.STATION:
        if nationwide or city is None:
            return catalog_for_city(None, mode, nationwide=True)
        return catalog_for_city(city, mode, nationwide=False)

    if city is None:
        raise HTTPException(
            status_code=400,
            detail="city is required for bus_stop and neighborhood modes.",
        )

    if mode == LocationMode.BUS_STOP:
        if len(query) >= 2:
            live = await search_bus_stops(city, query)
            if live:
                return live
        # Fallback seeds (filtered by query when present).
        seeds = catalog_for_city(city, mode)
        if query:
            ql = query.lower()
            seeds = [
                s
                for s in seeds
                if ql in s.name.lower()
                or (s.name_en and ql in s.name_en.lower())
            ]
        return seeds

    # neighborhood
    if len(query) >= 1:
        live = await search_neighborhoods(city, query)
        if live:
            return live
    seeds = catalog_for_city(city, mode)
    if query:
        ql = query.lower()
        seeds = [
            s
            for s in seeds
            if ql in s.name.lower() or (s.name_en and ql in s.name_en.lower())
        ]
    return seeds
