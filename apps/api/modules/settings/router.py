from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from core.database import get_db
from core.security import get_current_user
from modules.settings.schemas import TenantSettingsResponse, TenantSettingsUpdate
from modules.settings.service import get_tenant_settings, update_tenant_settings

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
    settings = await update_tenant_settings(
        db, current_user.tenant_id, payload.youtube_channel_url
    )
    return settings
