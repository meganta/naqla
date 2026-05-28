from fastapi import APIRouter, Depends
from packages.ai_provider.base import AIMessage
from sqlalchemy.ext.asyncio import AsyncSession

from core.ai import get_ai_provider
from core.database import get_db
from core.security import get_current_user
from modules.copilot.schemas import CopilotRequest, CopilotResponse
from modules.copilot.service import run_copilot

router = APIRouter(prefix="/copilot", tags=["copilot"])


@router.post("/chat", response_model=CopilotResponse)
async def chat(
    payload: CopilotRequest,
    current_user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    provider = await get_ai_provider(current_user.tenant_id, db)
    messages = [AIMessage(role=m.role, content=m.content) for m in payload.messages]
    response, chunks_used = await run_copilot(
        db=db,
        provider=provider,
        tenant_id=current_user.tenant_id,
        messages=messages,
        scope=payload.scope,
        max_tokens=payload.max_tokens,
        temperature=payload.temperature,
    )
    return CopilotResponse(
        text=response.text,
        tokens_used=response.tokens_used,
        model=response.model,
        provider=response.provider,
        source_scope=response.source_scope or payload.scope.value,
        context_chunks_used=chunks_used,
    )
