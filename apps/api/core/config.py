from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    environment: str = "dev"
    database_url: str = "postgresql+asyncpg://naqla:placeholder@localhost/naqla_dev"
    jwt_secret: str = ""
    jwt_algorithm: str = "HS256"
    jwt_access_token_expire_minutes: int = 10080  # 7 days
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
    youtube_api_key: str = ""
    worker_service_url: str = "http://localhost:8001"
    cors_origins_str: str = "http://localhost:3000"
    cors_origins: list[str] = []

    def model_post_init(self, __context) -> None:
        if not self.cors_origins:
            origins = [o.strip() for o in self.cors_origins_str.split(",")]
            object.__setattr__(self, "cors_origins", origins)

    @property
    def is_production(self) -> bool:
        return self.environment == "prod"


settings = Settings()
