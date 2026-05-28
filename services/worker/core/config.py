from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    environment: str = "dev"
    database_url: str = "postgresql+asyncpg://naqla:placeholder@localhost/naqla_dev"
    gcp_project_id: str = "naqla-mvp"
    gcp_region: str = "europe-west1"
    gcs_bucket_name: str = "naqla-uploads-dev"
    ai_provider: str = "gemini"
    ai_model: str = "gemini-1.5-flash"
    gemini_api_key: str = ""
    api_service_url: str = "http://localhost:8000"


settings = Settings()
