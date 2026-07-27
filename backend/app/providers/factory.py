"""Provider factory — switches mock vs live via PROVIDER_MODE.

Live mode fails loudly when credentials are missing (no silent mock fallback).
"""

from __future__ import annotations

from app.config import settings
from app.providers.base import GooglePlacesProvider, KakaoLocalProvider
from app.providers.errors import ApiCallCounter, ProviderConfigError
from app.providers.mock_google import MockGooglePlacesProvider
from app.providers.mock_kakao import MockKakaoLocalProvider


def get_kakao_provider(
    *,
    counter: ApiCallCounter | None = None,
) -> KakaoLocalProvider:
    if settings.use_mock_providers:
        return MockKakaoLocalProvider()
    if not settings.kakao_rest_api_key:
        raise ProviderConfigError(
            "PROVIDER_MODE=live requires KAKAO_REST_API_KEY to be set"
        )
    from app.providers.kakao import LiveKakaoLocalProvider

    return LiveKakaoLocalProvider(counter=counter)


def get_google_provider(
    *,
    counter: ApiCallCounter | None = None,
) -> GooglePlacesProvider:
    if settings.use_mock_providers:
        return MockGooglePlacesProvider()
    if not settings.google_places_api_key:
        raise ProviderConfigError(
            "PROVIDER_MODE=live requires GOOGLE_PLACES_API_KEY to be set"
        )
    from app.providers.google import LiveGooglePlacesProvider

    return LiveGooglePlacesProvider(counter=counter)


def build_live_providers() -> tuple[
    KakaoLocalProvider, GooglePlacesProvider, ApiCallCounter
]:
    """Construct a fresh provider pair with a shared request-scoped call counter."""
    counter = ApiCallCounter()
    return get_kakao_provider(counter=counter), get_google_provider(counter=counter), counter
