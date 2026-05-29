from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from core.database import get_db
from core.security import get_current_user
from modules.settings.schemas import TenantSettingsResponse, TenantSettingsUpdate
from modules.settings.service import get_tenant_settings, is_copilot_ready, update_tenant_settings

router = APIRouter(prefix="/settings", tags=["settings"])


@router.get("", response_model=TenantSettingsResponse)
async def get_settings(
    current_user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    settings = await get_tenant_settings(db, current_user.tenant_id)
    return settings


@router.put("", response_model=TenantSettingsResponse)
async def update_settings(
    payload: TenantSettingsUpdate,
    current_user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    settings = await update_tenant_settings(db, current_user.tenant_id, payload)
    return settings


@router.get("/copilot-ready")
async def check_copilot_ready(
    current_user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    settings = await get_tenant_settings(db, current_user.tenant_id)
    ready = is_copilot_ready(settings)
    missing = []
    if not settings.subject:
        missing.append("subject")
    if not settings.grade_level:
        missing.append("grade_level")
    if not settings.curriculum_country:
        missing.append("curriculum_country")
    return {"ready": ready, "missing_fields": missing}
