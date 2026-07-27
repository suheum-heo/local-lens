"""Provider factory — switches mock vs live via PROVIDER_MODE."""

from __future__ import annotations

from app.config import settings
from app.providers.base import GooglePlacesProvider, KakaoLocalProvider
from app.providers.mock_google import MockGooglePlacesProvider
from app.providers.mock_kakao import MockKakaoLocalProvider


def get_kakao_provider() -> KakaoLocalProvider:
    if settings.use_mock_providers:
        return MockKakaoLocalProvider()
    from app.providers.kakao import LiveKakaoLocalProvider

    return LiveKakaoLocalProvider()


def get_google_provider() -> GooglePlacesProvider:
    if settings.use_mock_providers:
        return MockGooglePlacesProvider()
    from app.providers.google import LiveGooglePlacesProvider

    return LiveGooglePlacesProvider()
