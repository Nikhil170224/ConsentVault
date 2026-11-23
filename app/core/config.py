from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    database_url: str = "postgresql+psycopg://consentvault:consentvault@localhost:5432/consentvault"
    secret_key: str = "dev-secret-key-at-least-32-characters-long!!"
    algorithm: str = "HS256"
    access_token_expire_minutes: int = 30
    refresh_token_expire_days: int = 7
    dsr_sla_days: int = 30
    cors_origins: str = "http://localhost:3000"
    environment: str = "development"
    log_level: str = "INFO"
    rate_limit_auth_per_minute: int = 20
    rate_limit_consent_per_minute: int = 120

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
