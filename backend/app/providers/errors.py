"""Provider configuration and upstream API errors (safe for HTTP mapping)."""

from __future__ import annotations


class ProviderConfigError(Exception):
    """Live mode is enabled but required credentials/config are missing."""

    def __init__(self, message: str) -> None:
        super().__init__(message)
        self.message = message


class ProviderAPIError(Exception):
    """Upstream Kakao/Google API failure with a safe, user-facing message."""

    def __init__(
        self,
        message: str,
        *,
        provider: str,
        status_code: int = 502,
        retryable: bool = False,
    ) -> None:
        super().__init__(message)
        self.message = message
        self.provider = provider
        self.status_code = status_code
        self.retryable = retryable


class ApiCallCounter:
    """Request-scoped tally of external HTTP calls (no secrets)."""

    def __init__(self) -> None:
        self.kakao_keyword = 0
        self.kakao_place_detail = 0
        self.google_search_text = 0
        self.google_details = 0
        self.google_place_photo = 0

    def as_dict(self) -> dict[str, int]:
        return {
            "kakao_keyword": self.kakao_keyword,
            "kakao_place_detail": self.kakao_place_detail,
            "google_search_text": self.google_search_text,
            "google_details": self.google_details,
            "google_place_photo": self.google_place_photo,
            "total": (
                self.kakao_keyword
                + self.kakao_place_detail
                + self.google_search_text
                + self.google_details
                + self.google_place_photo
            ),
        }
