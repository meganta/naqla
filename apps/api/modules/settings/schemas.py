from pydantic import BaseModel


class TenantSettingsResponse(BaseModel):
    youtube_channel_url: str | None = None
    youtube_channel_id: str | None = None

    model_config = {"from_attributes": True}


class TenantSettingsUpdate(BaseModel):
    youtube_channel_url: str | None = None
