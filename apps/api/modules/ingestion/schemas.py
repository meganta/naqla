from datetime import datetime

from pydantic import BaseModel


class CreateSourceRequest(BaseModel):
    title: str
    source_type: str
    original_url: str | None = None
    raw_text: str | None = None


class SourceResponse(BaseModel):
    id: str
    title: str
    source_type: str
    status: str
    file_path: str | None
    original_url: str | None
    extra_meta: str | None
    error_message: str | None = None
    is_resumable: bool = False
    created_at: datetime

    model_config = {"from_attributes": True}


class UploadURLResponse(BaseModel):
    source_id: str
    upload_url: str
    file_path: str


class JobResponse(BaseModel):
    id: str
    source_id: str
    status: str
    error_message: str | None
    chunks_created: int | None
    started_at: datetime | None
    completed_at: datetime | None
    created_at: datetime

    model_config = {"from_attributes": True}
