from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    environment: str = Field(default="development", description="Environment mode (development, staging, production)")
    log_level: str = Field(default="INFO", description="Logging verbosity level")
    api_host: str = Field(default="0.0.0.0", description="API listen host")
    api_port: int = Field(default=8000, description="API listen port")
    api_secret_key: str = Field(
        default="development_only_secret_key_change_in_production_32_bytes", description="Secret key for signing tokens"
    )

    # PostgreSQL Configuration
    postgres_user: str = Field(default="openrobo")
    postgres_password: str = Field(default="openrobo_dev_password")
    postgres_db: str = Field(default="openrobo_db")
    postgres_host: str = Field(default="localhost")
    postgres_port: int = Field(default=5432)
    database_url: str = Field(
        default="postgresql+asyncpg://openrobo:openrobo_dev_password@localhost:5432/openrobo_db",
        description="Async SQLAlchemy Database URL",
    )

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")


settings = Settings()
