from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

ENV_FILE = Path(__file__).resolve().parents[2] / ".env"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=ENV_FILE, extra="ignore")

    app_env: str = "dev"
    database_url: str = "postgresql+asyncpg://assist:assist@localhost:5433/assist"
    jwt_secret: str = "dev-secret-change-me-32-bytes-minimum"
    jwt_ttl_hours: int = 12
    field_encryption_key: str = "MDEyMzQ1Njc4OWFiY2RlZjAxMjM0NTY3ODlhYmNkZWY="
    cors_origins: str = "http://localhost:5173"
    max_bot_token: str = ""
    max_bot_username: str = "t562_hakaton_max_bot"
    # у platform-api2 сертификат Минцифры, которого нет в доверенных ни в Windows, ни в образе
    max_api_base: str = "https://platform-api.max.ru"
    init_data_max_age_seconds: int = 86400

    cleanup_enabled: bool = True
    cleanup_interval_minutes: int = 60
    retention_inbox_hours: int = 24
    retention_invites_days: int = 7
    retention_callbacks_days: int = 7
    retention_drafts_days: int = 30
    retention_submitted_days: int = 90
    db_size_warning_mb: int = 1024

    expiry_enabled: bool = True
    expiry_interval_seconds: int = 60
    assist_waiting_timeout_minutes: int = 30
    assist_idle_timeout_minutes: int = 60
    help_callback_ttl_days: int = 7

    livekit_url: str = "ws://localhost:7880"
    livekit_api_url: str = "http://localhost:7880"
    livekit_api_key: str = "devkey"
    livekit_api_secret: str = "dev-livekit-secret-change-me-32-bytes"
    voice_token_ttl_seconds: int = 120
    recordings_dir: str = str(Path(__file__).resolve().parents[3] / "recordings")

    @property
    def is_dev(self) -> bool:
        return self.app_env == "dev"

    @property
    def cors_origin_list(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]


settings = Settings()
