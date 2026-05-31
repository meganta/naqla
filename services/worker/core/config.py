from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    environment: str = "dev"
    database_url: str = "postgresql+asyncpg://naqla:placeholder@localhost/naqla_dev"
    gcp_project_id: str = "naqla-mvp"
    gcp_region: str = "europe-west1"
    gcs_bucket_name: str = "naqla-uploads-dev"
    ai_provider: str = "openai"
    ai_model: str = "gpt-4o-mini"
    gemini_api_key: str = ""
    openai_api_key: str = ""
    api_service_url: str = "http://localhost:8000"
    youtube_api_key: str = ""
    youtube_channel_max_videos: int = 25
    google_client_id: str = ""
    google_client_secret: str = ""
    supadata_api_key: str = ""


settings = Settings()
