from functools import lru_cache
from zoneinfo import ZoneInfo

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=(".env", "../../.env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_name: str = "PLTS Monitor Rumah"
    app_env: str = "local"
    app_timezone: str = "Asia/Jakarta"
    database_url: str = "postgresql+asyncpg://plts:plts@localhost:5432/plts"
    cors_origins: str = "http://localhost:3000,http://127.0.0.1:3000"

    device_slug: str = "prime-rumah-01"
    device_name: str = "PLTS Rumah"
    device_api_key: str | None = None
    tariff_idr_per_kwh: float = 1550.0

    online_after_seconds: int = Field(default=30, ge=10)
    degraded_after_seconds: int = Field(default=120, ge=30)
    max_integration_gap_seconds: int = Field(default=60, ge=10)
    future_tolerance_seconds: int = Field(default=300, ge=0)
    old_sample_after_hours: int = Field(default=24, ge=1)
    auto_bootstrap_device: bool = True

    @property
    def cors_origin_list(self) -> list[str]:
        return [item.strip() for item in self.cors_origins.split(",") if item.strip()]

    @property
    def timezone(self) -> ZoneInfo:
        return ZoneInfo(self.app_timezone)


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
