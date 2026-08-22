from pathlib import Path
from typing import Optional

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "CreatorOS AI"
    app_env: str = "development"
    debug: bool = True

    database_url: str

    jwt_secret_key: str
    jwt_algorithm: str = "HS256"
    jwt_access_token_expire_minutes: int = 60
    jwt_reset_token_expire_minutes: int = 30

    frontend_origins: str = "http://localhost:3000"

    ollama_base_url: str = "http://localhost:11434"
    ollama_model: str = "qwen3"
    ollama_timeout_seconds: float = 45.0
    ai_fallback_enabled: bool = True

    supabase_url: Optional[str] = None
    supabase_service_role_key: Optional[str] = None
    supabase_storage_bucket: str = "creatoros-media"
    media_local_dir: str = "media"
    max_upload_mb: int = 25

    social_publish_mode: str = "simulate"
    meta_graph_base_url: str = "https://graph.facebook.com/v23.0"

    model_config = SettingsConfigDict(
        env_file=".env",
        extra="ignore",
    )

    @property
    def cors_origins(self) -> list[str]:
        return [origin.strip() for origin in self.frontend_origins.split(",") if origin.strip()]

    @property
    def media_path(self) -> Path:
        return Path(self.media_local_dir)


settings = Settings()
