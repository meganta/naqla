from packages.ai_provider.base import AIProvider
from packages.ai_provider.factory import build_provider
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core.config import settings


async def get_ai_provider(tenant_id: str, db: AsyncSession) -> AIProvider:
    from modules.auth.models import Tenant

    result = await db.execute(select(Tenant).where(Tenant.id == tenant_id))
    result.scalar_one_or_none()

    provider = settings.ai_provider
    model = settings.ai_model
    api_key = settings.gemini_api_key

    return build_provider(provider, model, api_key)
