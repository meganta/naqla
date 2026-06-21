import json
import logging
from datetime import datetime
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core.config import settings
from modules.teacher_profile.extractor import extract_profile
from modules.teacher_profile.models import TeacherStyleProfile

logger = logging.getLogger(__name__)


async def get_profile(
    db: AsyncSession,
    tenant_id: str,
) -> TeacherStyleProfile | None:
    """Get the latest profile for a tenant."""
    result = await db.execute(
        select(TeacherStyleProfile)
        .where(TeacherStyleProfile.tenant_id == tenant_id)
        .order_by(TeacherStyleProfile.version.desc())
        .limit(1)
    )
    return result.scalar_one_or_none()


async def generate_profile(
    db: AsyncSession,
    tenant_id: str,
) -> TeacherStyleProfile:
    """
    Generate or regenerate the Teacher Style Profile for a tenant.
    Creates a new versioned profile record.
    """
    if not settings.openai_api_key:
        raise ValueError("OPENAI_API_KEY not configured")

    # Get current version
    existing = await get_profile(db, tenant_id)
    next_version = (existing.version + 1) if existing else 1

    # Create pending record
    profile_record = TeacherStyleProfile(
        id=str(uuid4()),
        tenant_id=tenant_id,
        version=next_version,
        profile_json="{}",
        status="processing",
        generated_at=datetime.utcnow(),
        updated_at=datetime.utcnow(),
    )
    db.add(profile_record)
    await db.commit()

    try:
        logger.info(
            "generate_profile: starting extraction tenant=%s version=%d",
            tenant_id, next_version,
        )
        profile_data = await extract_profile(db, tenant_id, settings.openai_api_key)

        profile_record.profile_json = json.dumps(
            profile_data, ensure_ascii=False, indent=2
        )
        profile_record.chunks_analyzed = profile_data.get("metadata", {}).get(
            "chunks_analyzed", 0
        )
        profile_record.sources_analyzed = profile_data.get("metadata", {}).get(
            "sources_analyzed", 0
        )
        profile_record.status = "completed"
        profile_record.updated_at = datetime.utcnow()
        await db.commit()

        logger.info(
            "generate_profile: completed tenant=%s version=%d chunks=%d",
            tenant_id, next_version, profile_record.chunks_analyzed,
        )
        return profile_record

    except Exception as e:
        logger.error("generate_profile: failed tenant=%s: %s", tenant_id, e)
        profile_record.status = "failed"
        profile_record.error_message = str(e)
        profile_record.updated_at = datetime.utcnow()
        await db.commit()
        raise
