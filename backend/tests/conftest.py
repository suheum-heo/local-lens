"""Shared pytest fixtures."""

from __future__ import annotations

import pytest

from app.providers.google import _DETAILS_TTL, _SEARCH_TTL
from app.providers.kakao_place_enricher import _RATING_TTL


@pytest.fixture(autouse=True)
def _clear_provider_ttl_caches() -> None:
    """Process-level TTLs must not leak across tests."""
    _SEARCH_TTL.clear()
    _DETAILS_TTL.clear()
    _RATING_TTL.clear()
