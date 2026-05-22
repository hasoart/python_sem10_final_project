from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    app_name: str = "Object Detection Service"
    debug: bool = False
    cors_allow_origins: list[str] = ["*"]

    database_url: str = "postgresql+psycopg://app:app@localhost:5432/object_detection"
    database_echo: bool = False

    redis_url: str = "redis://localhost:6379/0"

    celery_app_name: str = "object_detection_service"
    celery_timezone: str = "UTC"

    s3_endpoint_url: str = "http://localhost:9000"
    s3_access_key_id: str = Field(default="minioadmin")
    s3_secret_access_key: str = Field(default="minioadmin")
    s3_bucket_name: str = "object-detection"

    yolo_model_path: str = "yolo11n.pt"
    yolo_confidence: float = 0.25

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


@lru_cache
def get_settings() -> Settings:
    """Return cached application settings."""
    return Settings()


settings = get_settings()
