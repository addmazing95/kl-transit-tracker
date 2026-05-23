from __future__ import annotations

from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=(".env", "../.env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_host: str = "127.0.0.1"
    app_port: int = 8000
    log_level: str = "INFO"

    database_url: str = "sqlite:///./data/transit.db"

    poll_interval_seconds: int = 20
    news_scrape_interval_minutes: int = 15
    timezone: str = "Asia/Kuala_Lumpur"

    ktmb_gtfs_rt_url: str = "https://api.data.gov.my/gtfs-realtime/vehicle-position/ktmb"
    ktmb_gtfs_static_url: str = "https://api.data.gov.my/gtfs-static/ktmb"
    prasarana_rail_static_url: str = (
        "https://api.data.gov.my/gtfs-static/prasarana?category=rapid-rail-kl"
    )
    prasarana_mrtfeeder_rt_url: str = (
        "https://api.data.gov.my/gtfs-realtime/vehicle-position/prasarana"
        "?category=rapid-bus-mrtfeeder"
    )

    rapid_rail_live: bool = False

    gtfs_cache_dir: Path = Field(default=Path("data/gtfs_cache"))

    @property
    def data_dir(self) -> Path:
        return Path("data")


settings = Settings()
