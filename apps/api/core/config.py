from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    environment: str = "dev"
    database_url: str = "postgresql+asyncpg://naqla:placeholder@localhost/naqla_dev"
    jwt_secret: str = ""
    jwt_algorithm: str = "HS256"
    jwt_access_token_expire_minutes: int = 15
    jwt_refresh_token_expire_days: int = 7
    gcp_project_id: str = "naqla-mvp"
    gcp_region: str = "europe-west1"
    gcs_bucket_name: str = "naqla-uploads-dev"
    cloud_tasks_queue: str = "naqla-ingestion-dev"
    cloud_tasks_location: str = "europe-west1"
    ai_provider: str = "openai"
    ai_model: str = "gpt-4o-mini"
    gemini_api_key: str = ""
    openai_api_key: str = ""
    anthropic_api_key: str = ""
    worker_service_url: str = "http://localhost:8001"
    cors_origins_str: str = "http://localhost:3000"

    @property
    def cors_origins(self) -> list[str]:
        return [o.strip() for o in self.cors_origins_str.split(",")]

    @property
    def is_production(self) -> bool:
        return self.environment == "prod"


settings = Settings()
