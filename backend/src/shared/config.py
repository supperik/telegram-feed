from functools import lru_cache
from typing import Literal

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=None, extra="ignore", case_sensitive=False)

    # Postgres
    postgres_user: str
    postgres_password: str
    postgres_db: str
    postgres_host: str
    postgres_port: int = 5432

    # Redis
    redis_host: str
    redis_port: int = 6379

    # MinIO
    minio_endpoint: str
    minio_access_key: str
    minio_secret_key: str
    minio_bucket: str = "media"
    minio_secure: bool = False

    # Media ingest caps — short videos are downloaded fully; larger ones
    # keep just the thumb (see specs/2026-05-19-private-channel-ux-...md).
    video_max_download_bytes: int = 20 * 1024 * 1024
    video_max_download_seconds: int = 60

    # Telegram
    tg_api_id: int = 0
    tg_api_hash: str = ""
    tg_phone: str = ""
    tg_session_name: str = "userbot_main"
    tg_bot_token: str = ""

    # Telegram proxy. Supported types: "mtproxy" (host/port/secret tuple)
    # and "socks5" (host/port, no auth — talks to the naive sidecar by default,
    # or the xray/VLESS sidecar as fallback). Leave empty for direct connection.
    tg_proxy_type: Literal["", "mtproxy", "socks5"] = ""
    tg_proxy_host: str = ""
    tg_proxy_port: int = 0
    tg_proxy_secret: str = ""

    @field_validator("tg_api_id", mode="before")
    @classmethod
    def _empty_string_to_zero(cls, v: object) -> object:
        # `.env.example` ships `TG_API_ID=` (empty); treat empty string as the default 0.
        if isinstance(v, str) and v.strip() == "":
            return 0
        return v

    # API / JWT
    api_jwt_secret: str = Field(min_length=16)
    api_jwt_algorithm: str = "HS256"
    api_jwt_access_ttl_seconds: int = 3600
    api_jwt_refresh_ttl_seconds: int = 7 * 24 * 3600
    api_cors_origins: str = "https://web.telegram.org"

    # Misc
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR"] = "INFO"
    log_format: Literal["json", "console"] = "json"
    env: Literal["local", "test", "staging", "prod"] = "local"

    # Approval poller (request-to-join channels)
    approval_timeout_days: int = 7
    approval_poll_interval_s: float = 1800.0

    # Sliding-window rate limits (design §6.5).
    rate_limit_auth_per_window: int = 5
    rate_limit_auth_window_seconds: int = 60
    rate_limit_sources_per_window: int = 30
    rate_limit_sources_window_seconds: int = 3600

    # History backfill — lazy older-post fetch.
    # See specs/2026-05-20-history-backfill-design.md.
    history_backfill_enabled: bool = True
    history_backfill_interval_s: int = 300
    history_backfill_unread_threshold: int = 20
    history_backfill_batch_size: int = 100
    history_backfill_lock_ttl_s: int = 300
    history_backfill_channels_per_tick: int = 20

    @property
    def postgres_dsn(self) -> str:
        return (
            f"postgresql+asyncpg://{self.postgres_user}:{self.postgres_password}"
            f"@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"
        )

    @property
    def redis_dsn(self) -> str:
        return f"redis://{self.redis_host}:{self.redis_port}/0"


@lru_cache
def get_settings() -> Settings:
    return Settings()  # type: ignore[call-arg]
