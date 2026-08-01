"""Secure Google Place Photo proxy (API key stays server-side)."""

from __future__ import annotations

import logging

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import Response

from app.providers.errors import ApiCallCounter, ProviderAPIError, ProviderConfigError
from app.providers.place_photos import (
    PHOTO_MAX_WIDTH_PX,
    fetch_place_photo_media,
    is_valid_photo_name,
)

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("/restaurants/photo")
async def get_restaurant_photo(
    photo_name: str = Query(..., min_length=1, max_length=800),
    max_width_px: int = Query(PHOTO_MAX_WIDTH_PX, ge=64, le=1600),
) -> Response:
    """Stream a Place Photo (New) image through LocalLens.

    Rejects arbitrary URLs. Counts `google_place_photo` only when media is fetched.
    """
    if not is_valid_photo_name(photo_name):
        raise HTTPException(status_code=400, detail="Invalid photo_name")

    counter = ApiCallCounter()
    try:
        media = await fetch_place_photo_media(
            photo_name,
            counter=counter,
            max_width_px=max_width_px,
        )
    except ProviderConfigError as exc:
        raise HTTPException(status_code=503, detail=exc.message) from exc
    except ProviderAPIError as exc:
        # Photo failures must not look like restaurant search failures.
        status = exc.status_code if exc.status_code in {400, 404, 429, 502, 504} else 502
        if status == 404:
            raise HTTPException(status_code=404, detail="Photo unavailable") from exc
        raise HTTPException(status_code=status, detail=exc.message) from exc
    except Exception as exc:  # pragma: no cover — defensive
        logger.warning("Unexpected photo proxy error: %s", type(exc).__name__)
        raise HTTPException(status_code=502, detail="Photo unavailable") from exc

    return Response(
        content=media.content,
        media_type=media.content_type,
        headers={
            # Photos are session-bound resources; short private cache is OK.
            "Cache-Control": "private, max-age=3600",
            "X-Content-Type-Options": "nosniff",
        },
    )
