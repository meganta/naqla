from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core.ai import get_ai_provider
from core.database import get_db
from core.security import get_current_user
from modules.auth.models import Tenant
from modules.copilot.schemas import (
    ConfidenceInfo,
    CopilotDebugInfo,
    CopilotRequest,
    CopilotResponse,
    SourceUsed,
)
from modules.copilot.service import run_copilot
from modules.ingestion.models import KnowledgeSource
from modules.mobile.evidence_builder import chunk_to_evidence
from providers.ai_provider.base import AIMessage

router = APIRouter(prefix="/copilot", tags=["copilot"])


@router.post("/chat", response_model=CopilotResponse)
async def chat(
    payload: CopilotRequest,
    current_user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    tenant_result = await db.execute(
        select(Tenant).where(Tenant.id == current_user.tenant_id)
    )
    tenant = tenant_result.scalar_one_or_none()
    tenant_name = tenant.name if tenant else current_user.tenant_id
    tenant_slug = tenant.slug if tenant else current_user.tenant_id

    provider = await get_ai_provider(current_user.tenant_id, db)
    messages = [AIMessage(role=m.role, content=m.content) for m in payload.messages]

    response, ctx, insufficient, sources, chunks, debug_info = await run_copilot(
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

    # Build evidence cards
    source_ids = list({c.source_id for c in chunks})
    sources_result = await db.execute(
        select(KnowledgeSource).where(KnowledgeSource.id.in_(source_ids))
    )
    sources_map = {s.id: s for s in sources_result.scalars().all()}
    evidence_items = []
    seen: set[str] = set()
    for chunk in chunks:
        source = sources_map.get(chunk.source_id)
        if not source:
            continue
        ev = chunk_to_evidence(chunk, source)
        if ev and ev.evidence_id not in seen:
            evidence_items.append(ev)
            seen.add(ev.evidence_id)

    # Build confidence info
    confidence_result = debug_info.get("confidence")
    confidence_info: ConfidenceInfo | None = None
    if confidence_result:
        confidence_info = ConfidenceInfo(
            level=confidence_result.level,
            score=confidence_result.score,
            reason=confidence_result.reason,
        )

    # Debug info (only if requested)
    debug_out: CopilotDebugInfo | None = None
    if payload.debug:
        debug_out = CopilotDebugInfo(
            original_query=debug_info.get("original_query", ""),
            normalized_query=debug_info.get("normalized_query", ""),
            question_type=debug_info.get("question_type", "unknown"),
            retrieved_candidates_count=debug_info.get("retrieved_candidates_count", 0),
            selected_chunks_count=debug_info.get("selected_chunks_count", 0),
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
        evidence=[ev.model_dump() for ev in evidence_items],
        question_type=debug_info.get("question_type", "unknown"),
        confidence=confidence_info,
        debug=debug_out,
    )
