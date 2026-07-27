"""Application configuration loaded from environment variables."""

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    provider_mode: str = "mock"  # "mock" | "live"
    kakao_rest_api_key: str = ""
    google_places_api_key: str = ""
    backend_host: str = "0.0.0.0"
    backend_port: int = 8000
    cors_origins: str = "http://localhost:3000"
    database_url: str = (
        "postgresql+asyncpg://locallens:locallens@localhost:5432/locallens"
    )

    @property
    def cors_origins_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

    @property
    def use_mock_providers(self) -> bool:
        return self.provider_mode.lower() != "live"


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
