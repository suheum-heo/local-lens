"""Google Place Photos (New) helpers + secure photo-name validation.

Media is fetched only through the LocalLens backend proxy so
GOOGLE_PLACES_API_KEY never reaches the browser.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from urllib.parse import quote

import httpx

from app.config import settings
from app.providers.errors import ApiCallCounter, ProviderAPIError, ProviderConfigError

logger = logging.getLogger(__name__)

# places/{placeId}/photos/{photoRef} — no schemes, path tricks, or query strings.
PHOTO_NAME_RE = re.compile(
    r"^places/[A-Za-z0-9_-]{1,256}/photos/[A-Za-z0-9_-]{1,512}$"
)

PHOTO_MEDIA_URL = "https://places.googleapis.com/v1/{photo_name}/media"
PHOTO_MAX_WIDTH_PX = 800
PHOTO_TIMEOUT_S = 10.0
PHOTO_PROXY_PATH = "/api/restaurants/photo"

# Tiny branded SVG used in mock mode (no external image hosts).
_MOCK_PHOTO_SVG = b"""<?xml version="1.0" encoding="UTF-8"?>
<svg xmlns="http://www.w3.org/2000/svg" width="640" height="640" viewBox="0 0 640 640">
  <defs>
    <linearGradient id="g" x1="0" y1="0" x2="1" y2="1">
      <stop offset="0%" stop-color="#22C55E"/>
      <stop offset="100%" stop-color="#6366F1"/>
    </linearGradient>
  </defs>
  <rect width="640" height="640" fill="url(#g)"/>
  <g fill="none" stroke="rgba(255,255,255,0.88)" stroke-width="28" stroke-linecap="round">
    <path d="M220 250c0-40 30-70 70-70s70 30 70 70v180"/>
    <path d="M290 250v180"/>
    <path d="M420 200v230"/>
    <path d="M390 230h60"/>
  </g>
</svg>
"""


@dataclass(frozen=True)
class PhotoMedia:
    content: bytes
    content_type: str


def is_valid_photo_name(photo_name: str) -> bool:
    if not photo_name or len(photo_name) > 800:
        return False
    if ".." in photo_name or "://" in photo_name or "?" in photo_name or "#" in photo_name:
        return False
    if "\\" in photo_name or " " in photo_name:
        return False
    return PHOTO_NAME_RE.fullmatch(photo_name) is not None


def is_mock_photo_name(photo_name: str) -> bool:
    """Mock fixtures use photo refs prefixed with mock_ (never hit Google)."""
    if not is_valid_photo_name(photo_name):
        return False
    ref = photo_name.rsplit("/photos/", 1)[-1]
    return ref.startswith("mock_")


def build_photo_proxy_url(photo_name: str) -> str:
    """Relative LocalLens proxy URL (no API key)."""
    return f"{PHOTO_PROXY_PATH}?photo_name={quote(photo_name, safe='')}"


def extract_first_photo(
    photos_raw: object,
) -> tuple[str | None, list[str]]:
    """Parse Places API photos[] → (photo_name, attribution display names)."""
    if not isinstance(photos_raw, list) or not photos_raw:
        return None, []
    first = photos_raw[0]
    if not isinstance(first, dict):
        return None, []
    name = first.get("name")
    if not isinstance(name, str) or not is_valid_photo_name(name):
        return None, []

    attributions: list[str] = []
    raw_attrs = first.get("authorAttributions") or []
    if isinstance(raw_attrs, list):
        for item in raw_attrs:
            if isinstance(item, dict):
                display = item.get("displayName")
                if isinstance(display, str) and display.strip():
                    attributions.append(display.strip())
            elif isinstance(item, str) and item.strip():
                attributions.append(item.strip())
    return name, attributions


async def fetch_place_photo_media(
    photo_name: str,
    *,
    api_key: str | None = None,
    transport: httpx.AsyncBaseTransport | None = None,
    counter: ApiCallCounter | None = None,
    max_width_px: int = PHOTO_MAX_WIDTH_PX,
) -> PhotoMedia:
    """Fetch image bytes from Place Photos (New). Never returns the API key."""
    if not is_valid_photo_name(photo_name):
        raise ProviderAPIError(
            "Invalid photo resource name.",
            provider="google",
            status_code=400,
        )

    if settings.use_mock_providers or is_mock_photo_name(photo_name):
        if counter is not None:
            counter.google_place_photo += 1
        return PhotoMedia(content=_MOCK_PHOTO_SVG, content_type="image/svg+xml")

    key = api_key if api_key is not None else settings.google_places_api_key
    if not key:
        raise ProviderConfigError(
            "PROVIDER_MODE=live requires GOOGLE_PLACES_API_KEY to be set"
        )

    if counter is not None:
        counter.google_place_photo += 1

    url = PHOTO_MEDIA_URL.format(photo_name=photo_name)
    # key is a query param for media; never log the URL.
    try:
        async with httpx.AsyncClient(
            timeout=PHOTO_TIMEOUT_S,
            transport=transport,
            follow_redirects=True,
        ) as client:
            resp = await client.get(
                url,
                params={"maxWidthPx": max_width_px, "key": key},
            )
    except httpx.TimeoutException as exc:
        raise ProviderAPIError(
            "Google Place Photo request timed out.",
            provider="google",
            status_code=504,
            retryable=True,
        ) from exc
    except httpx.HTTPError as exc:
        logger.warning("Google Place Photo transport error: %s", type(exc).__name__)
        raise ProviderAPIError(
            "Google Place Photo service is temporarily unreachable.",
            provider="google",
            status_code=502,
            retryable=True,
        ) from exc

    if resp.status_code in {401, 403}:
        raise ProviderAPIError(
            "Google Place Photo authentication failed.",
            provider="google",
            status_code=502,
        )
    if resp.status_code == 429:
        raise ProviderAPIError(
            "Google Place Photo quota or rate limit exceeded.",
            provider="google",
            status_code=429,
            retryable=True,
        )
    if resp.status_code == 404:
        raise ProviderAPIError(
            "Photo not found.",
            provider="google",
            status_code=404,
        )
    if resp.status_code >= 400:
        logger.warning("Google Place Photo HTTP %s", resp.status_code)
        raise ProviderAPIError(
            "Google Place Photo request failed.",
            provider="google",
            status_code=502,
            retryable=resp.status_code >= 500,
        )

    content_type = resp.headers.get("content-type", "application/octet-stream")
    # Prefer image/*; reject accidental JSON/HTML error bodies.
    if "json" in content_type or "text/html" in content_type:
        raise ProviderAPIError(
            "Google Place Photo returned a non-image response.",
            provider="google",
            status_code=502,
        )
    if not resp.content:
        raise ProviderAPIError(
            "Google Place Photo returned an empty body.",
            provider="google",
            status_code=502,
        )

    # Strip charset etc. for Response media_type when possible.
    media_type = content_type.split(";")[0].strip() or "image/jpeg"
    return PhotoMedia(content=resp.content, content_type=media_type)
