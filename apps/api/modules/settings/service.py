import re
from datetime import datetime
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from modules.ingestion.models import TenantSettings
from modules.settings.schemas import TenantSettingsUpdate


async def get_tenant_settings(
    db: AsyncSession, tenant_id: str
) -> TenantSettings:
    result = await db.execute(
        select(TenantSettings).where(TenantSettings.tenant_id == tenant_id)
    )
    settings = result.scalar_one_or_none()
    if not settings:
        settings = TenantSettings(
            id=str(uuid4()),
            tenant_id=tenant_id,
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
        )
        db.add(settings)
        await db.flush()
    return settings


async def update_tenant_settings(
    db: AsyncSession,
    tenant_id: str,
    payload: TenantSettingsUpdate,
) -> TenantSettings:
    settings = await get_tenant_settings(db, tenant_id)

    # YouTube channel
    if payload.youtube_channel_url is not None:
        settings.youtube_channel_url = payload.youtube_channel_url
        settings.youtube_channel_id = None
        if payload.youtube_channel_url:
            handle_match = re.search(
                r"youtube\.com/@([\w.-]+)", payload.youtube_channel_url
            )
            id_match = re.search(
                r"youtube\.com/channel/(UC[\w-]+)", payload.youtube_channel_url
            )
            if handle_match:
                settings.youtube_channel_id = f"@{handle_match.group(1)}"
            elif id_match:
                settings.youtube_channel_id = id_match.group(1)
            else:
                settings.youtube_channel_id = payload.youtube_channel_url

    # Academic profile
    if payload.subject is not None:
        settings.subject = payload.subject
    if payload.grade_level is not None:
        settings.grade_level = payload.grade_level
    if payload.curriculum_country is not None:
        settings.curriculum_country = payload.curriculum_country
    if payload.curriculum_name is not None:
        settings.curriculum_name = payload.curriculum_name
    if payload.school_name is not None:
        settings.school_name = payload.school_name
    if payload.academic_year is not None:
        settings.academic_year = payload.academic_year
    if payload.teaching_language is not None:
        settings.teaching_language = payload.teaching_language
    if payload.student_level is not None:
        settings.student_level = payload.student_level

    # Copilot behavior
    if payload.copilot_tone is not None:
        settings.copilot_tone = payload.copilot_tone
    if payload.copilot_response_language is not None:
        settings.copilot_response_language = payload.copilot_response_language

    # Methodology
    if payload.methodology_template is not None:
        settings.methodology_template = payload.methodology_template
    if payload.teaching_style is not None:
        settings.teaching_style = payload.teaching_style
    if payload.explanation_depth is not None:
        settings.explanation_depth = payload.explanation_depth

    settings.updated_at = datetime.utcnow()
    await db.flush()
    return settings


def is_copilot_ready(settings: TenantSettings) -> bool:
    """Check if minimum required settings are configured for Copilot."""
    return bool(settings.subject and settings.grade_level and settings.curriculum_country)
