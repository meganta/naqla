from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import List


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # Environment
    environment: str = "dev"

    # Database
    database_url: str

    # JWT
    jwt_secret: str
    jwt_algorithm: str = "HS256"
    jwt_access_token_expire_minutes: int = 15
    jwt_refresh_token_expire_days: int = 7

    # GCP
    gcp_project_id: str = "naqla-mvp"
    gcp_region: str = "europe-west1"
    gcs_bucket_name: str = "naqla-uploads-dev"
    cloud_tasks_queue: str = "naqla-ingestion-dev"
    cloud_tasks_location: str = "europe-west1"

    # AI Provider
    ai_provider: str = "gemini"
    ai_model: str = "gemini-1.5-flash"
    gemini_api_key: str = ""

    # Services
    worker_service_url: str = "http://localhost:8001"

    # CORS
    cors_origins: List[str] = ["http://localhost:3000"]

    @property
    def is_production(self) -> bool:
        return self.environment == "prod"


settings = Settings()
