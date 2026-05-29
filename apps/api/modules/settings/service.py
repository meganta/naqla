from datetime import datetime
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from modules.ingestion.models import TenantSettings


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
    youtube_channel_url: str | None,
) -> TenantSettings:
    import re
    settings = await get_tenant_settings(db, tenant_id)
    settings.youtube_channel_url = youtube_channel_url
    settings.youtube_channel_id = None
    if youtube_channel_url:
        # Extract channel ID or handle from URL
        handle_match = re.search(r"youtube\.com/@([\w.-]+)", youtube_channel_url)
        id_match = re.search(r"youtube\.com/channel/(UC[\w-]+)", youtube_channel_url)
        if handle_match:
            settings.youtube_channel_id = f"@{handle_match.group(1)}"
        elif id_match:
            settings.youtube_channel_id = id_match.group(1)
        else:
            settings.youtube_channel_id = youtube_channel_url
    settings.updated_at = datetime.utcnow()
    await db.flush()
    return settings
