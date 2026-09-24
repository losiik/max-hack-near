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
    max_bot_username: str = "max_assist_bot"
    init_data_max_age_seconds: int = 86400

    @property
    def is_dev(self) -> bool:
        return self.app_env == "dev"

    @property
    def cors_origin_list(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]


settings = Settings()
