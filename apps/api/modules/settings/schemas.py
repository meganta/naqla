from pydantic import BaseModel


class TenantSettingsResponse(BaseModel):
    youtube_channel_url: str | None = None
    youtube_channel_id: str | None = None
    # Academic profile
    subject: str | None = None
    grade_level: str | None = None
    curriculum_country: str | None = None
    curriculum_name: str | None = None
    school_name: str | None = None
    academic_year: str | None = None
    teaching_language: str | None = None
    student_level: str | None = None
    # Copilot behavior
    copilot_tone: str | None = None
    copilot_response_language: str | None = None
    # Methodology
    methodology_template: str | None = None
    teaching_style: str | None = None
    explanation_depth: str | None = None

    model_config = {"from_attributes": True}


class TenantSettingsUpdate(BaseModel):
    youtube_channel_url: str | None = None
    # Academic profile
    subject: str | None = None
    grade_level: str | None = None
    curriculum_country: str | None = None
    curriculum_name: str | None = None
    school_name: str | None = None
    academic_year: str | None = None
    teaching_language: str | None = None
    student_level: str | None = None
    # Copilot behavior
    copilot_tone: str | None = None
    copilot_response_language: str | None = None
    # Methodology
    methodology_template: str | None = None
    teaching_style: str | None = None
    explanation_depth: str | None = None
