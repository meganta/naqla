from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from core.ai import get_ai_provider
from core.database import get_db
from core.security import get_current_user
from modules.copilot.schemas import CopilotRequest, CopilotResponse, SourceUsed
from modules.copilot.service import run_copilot
from providers.ai_provider.base import AIMessage

router = APIRouter(prefix="/copilot", tags=["copilot"])


@router.post("/chat", response_model=CopilotResponse)
async def chat(
    payload: CopilotRequest,
    current_user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    from sqlalchemy import select

    from modules.auth.models import Tenant

    # Load tenant info
    tenant_result = await db.execute(
        select(Tenant).where(Tenant.id == current_user.tenant_id)
    )
    tenant = tenant_result.scalar_one_or_none()
    tenant_name = tenant.name if tenant else current_user.tenant_id
    tenant_slug = tenant.slug if tenant else current_user.tenant_id

    provider = await get_ai_provider(current_user.tenant_id, db)
    messages = [AIMessage(role=m.role, content=m.content) for m in payload.messages]

    response, ctx, insufficient, sources = await run_copilot(
        db=db,
        provider=provider,
        tenant_id=current_user.tenant_id,
        tenant_name=tenant_name,
        tenant_slug=tenant_slug,
        teacher_id=current_user.id,
        teacher_name=current_user.full_name,
        teacher_role=current_user.role,
        messages=messages,
        scope=payload.scope,
        task_type=payload.task_type,
        max_tokens=payload.max_tokens,
        temperature=payload.temperature,
    )

    return CopilotResponse(
        text=response.text,
        tokens_used=response.tokens_used,
        model=response.model,
        provider=response.provider,
        source_scope=response.source_scope or payload.scope.value,
        context_chunks_used=len(ctx.retrieved_chunks),
        insufficient_context=insufficient,
        is_profile_complete=ctx.is_profile_complete,
        missing_profile_fields=ctx.missing_fields,
        sources_used=[SourceUsed(**s) for s in sources],
    )
