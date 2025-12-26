"""Konfiguracja aplikacji."""

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Ustawienia aplikacji."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )

    # Database
    database_url: str = "sqlite:///./cennik.db"

    # Application
    app_name: str = "Cennik Stali"
    debug: bool = False
    secret_key: str = "change-this-in-production"

    # Server
    host: str = "0.0.0.0"
    port: int = 8000


@lru_cache
def get_settings() -> Settings:
    """Pobierz ustawienia (z cache)."""
    return Settings()
