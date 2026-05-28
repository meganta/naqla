from sqlalchemy.ext.asyncio import AsyncSession

from core.config import settings
from providers.ai_provider.base import AIProvider
from providers.ai_provider.factory import build_provider


async def get_ai_provider(tenant_id: str, db: AsyncSession) -> AIProvider:
    provider = settings.ai_provider
    model = settings.ai_model

    if provider == "openai":
        api_key = settings.openai_api_key
    elif provider == "gemini":
        api_key = settings.gemini_api_key
    elif provider == "anthropic":
        api_key = settings.anthropic_api_key
    else:
        api_key = settings.openai_api_key

    return build_provider(provider, model, api_key)
