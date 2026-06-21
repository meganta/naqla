import json
import logging

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from core.database import get_db
from core.security import get_current_user
from modules.teacher_profile.service import generate_profile, get_profile

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/teacher-profile", tags=["teacher-profile"])


class ProfileStatusResponse(BaseModel):
    tenant_id: str
    version: int
    status: str
    chunks_analyzed: int
    sources_analyzed: int
    generated_at: str
    profile: dict | None = None


class GenerateResponse(BaseModel):
    message: str
    version: int
    status: str


@router.post("/generate", response_model=GenerateResponse)
async def trigger_generate(
    background_tasks: BackgroundTasks,
    current_user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Trigger Teacher Style Profile generation for the current tenant.
    Runs in background — poll GET /teacher-profile for results.
    """
    tenant_id = current_user.tenant_id

    async def _run():
        from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

        from core.config import settings as cfg
        engine = create_async_engine(cfg.database_url, pool_pre_ping=True)
        session_factory = async_sessionmaker(engine, expire_on_commit=False)
        try:
            async with session_factory() as bg_db:
                await generate_profile(bg_db, tenant_id)
        except Exception as e:
            logger.error("background generate_profile failed: %s", e)
        finally:
            await engine.dispose()

    background_tasks.add_task(_run)

    # Get current version for response
    existing = await get_profile(db, tenant_id)
    next_version = (existing.version + 1) if existing else 1

    return GenerateResponse(
        message="Profile generation started. Poll GET /teacher-profile for results.",
        version=next_version,
        status="processing",
    )


@router.get("", response_model=ProfileStatusResponse)
async def get_teacher_profile(
    include_profile: bool = False,
    current_user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Get the latest Teacher Style Profile for the current tenant.
    Use include_profile=true to get full profile JSON.
    """
    tenant_id = current_user.tenant_id
    record = await get_profile(db, tenant_id)

    if not record:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No profile generated yet. POST /teacher-profile/generate to start.",
        )

    profile_data = None
    if include_profile and record.status == "completed":
        try:
            profile_data = json.loads(record.profile_json)
        except Exception:
            profile_data = None

    return ProfileStatusResponse(
        tenant_id=tenant_id,
        version=record.version,
        status=record.status,
        chunks_analyzed=record.chunks_analyzed,
        sources_analyzed=record.sources_analyzed,
        generated_at=record.generated_at.isoformat(),
        profile=profile_data,
    )
