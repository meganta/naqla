import logging

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from core.config import settings
from modules.copilot.context_builder import build_tenant_context
from modules.copilot.pipeline.classifier import classify_question
from modules.copilot.pipeline.confidence import (
    INSUFFICIENT_MESSAGES,
    compute_confidence,
)
from modules.copilot.pipeline.config import DEFAULT_CONFIG, PipelineConfig
from modules.copilot.pipeline.expander import expand_query
from modules.copilot.pipeline.normalizer import normalize_arabic_query
from modules.copilot.pipeline.reranker import RankedChunk, rerank_chunks
from modules.copilot.pipeline.validator import validate_answer
from modules.copilot.prompt_builder import build_system_prompt, build_user_prompt
from modules.ingestion.models import KnowledgeChunk, KnowledgeSource
from providers.ai_provider.base import AIMessage, AIProvider, SourceScope

logger = logging.getLogger(__name__)


async def embed_query(query: str) -> list[float] | None:
    """Generate embedding for a query using OpenAI."""
    if not settings.openai_api_key:
        logger.error("embed_query: openai_api_key is not set")
        return None
    try:
        import openai
        client = openai.OpenAI(api_key=settings.openai_api_key)
        response = client.embeddings.create(
            model=DEFAULT_CONFIG.retrieval.embedding_model,
            input=[query],
        )
        logger.info("embed_query: success, vector length=%d", len(response.data[0].embedding))
        return response.data[0].embedding
    except Exception as e:
        logger.error("embed_query: failed with error: %s", e)
        return None


async def _vector_search(
    db: AsyncSession,
    tenant_id: str,
    query: str,
    threshold: float,
    candidate_limit: int,
) -> tuple[list[str], dict[str, float]]:
    """
    Run vector similarity search.
    Returns (ordered_ids, {id: distance}).
    """
    query_embedding = await embed_query(query)
    if query_embedding is None:
        return [], {}

    embedding_str = "[" + ",".join(str(x) for x in query_embedding) + "]"

    STOP_WORDS = {
        "ماهي", "ماهو", "ما هي", "ما هو", "هي", "هو", "في", "من", "على",
        "عن", "مع", "إلى", "الى", "كيف", "لماذا", "متى", "اين", "أين",
        "ما", "ماذا", "هل", "كان", "كانت",
    }
    keywords = [
        w.strip() for w in query.split()
        if len(w.strip()) > 3 and w.strip() not in STOP_WORDS
    ]

    if len(keywords) >= 2:
        title_filter = " OR ".join(
            f"ks.title ILIKE :kw{i}" for i in range(min(3, len(keywords)))
        )
    elif keywords:
        title_filter = "ks.title ILIKE :kw0"
    else:
        title_filter = "FALSE"

    kw_params = {f"kw{i}": f"%{kw}%" for i, kw in enumerate(keywords[:3])}

    try:
        result = await db.execute(
            text(f"""
                SELECT kc.id,
                    (kc.embedding <=> CAST(:embedding AS vector)) AS distance,
                    CASE WHEN ({title_filter}) THEN 0.10 ELSE 0 END AS title_boost
                FROM knowledge_chunks kc
                JOIN knowledge_sources ks ON ks.id = kc.source_id
                WHERE kc.tenant_id = :tenant_id
                AND kc.embedding IS NOT NULL
                AND kc.chunk_index > 0
                ORDER BY (kc.embedding <=> CAST(:embedding AS vector))
                    - (CASE WHEN ({title_filter}) THEN 0.10 ELSE 0 END)
                LIMIT :limit
            """),
            {
                "tenant_id": tenant_id,
                "embedding": embedding_str,
                "limit": candidate_limit,
                **kw_params,
            },
        )
        rows = result.fetchall()
        filtered = [(row[0], row[1]) for row in rows if row[1] <= threshold]
        distances = {row[0]: row[1] for row in rows}
        logger.info(
            "vector_search: query=%r candidates=%d filtered=%d threshold=%.2f",
            query[:60], len(rows), len(filtered), threshold,
        )
        return [r[0] for r in filtered], distances
    except Exception as e:
        logger.error("vector_search failed: %s", e)
        return [], {}


async def retrieve_chunks(
    db: AsyncSession,
    tenant_id: str,
    query: str,
    scope: SourceScope,
    config: PipelineConfig = DEFAULT_CONFIG,
    question_type: str = "unknown",
) -> tuple[list[KnowledgeChunk], dict[str, float]]:
    """
    Retrieve knowledge chunks using hybrid search + scope filtering.
    Returns (chunks, distances_map).
    """
    if scope == SourceScope.OFFICIAL_CURRICULUM:
        return [], {}

    threshold = config.retrieval.threshold_for(question_type)

    # Expand query for better recall
    normalized = normalize_arabic_query(query)
    expanded = expand_query(normalized.normalized_query, question_type)  # type: ignore[arg-type]

    all_ids: list[str] = []
    all_distances: dict[str, float] = {}

    # Search with each expanded query, merge results
    for eq in expanded:
        ids, distances = await _vector_search(
            db, tenant_id, eq, threshold, config.retrieval.candidate_limit
        )
        all_distances.update(distances)
        for id_ in ids:
            if id_ not in all_ids:
                all_ids.append(id_)

    if not all_ids:
        logger.warning("retrieve_chunks: no chunks found for tenant=%s", tenant_id)
        return [], {}

    # Fetch chunk objects
    chunks_result = await db.execute(
        select(KnowledgeChunk).where(KnowledgeChunk.id.in_(all_ids[:config.retrieval.candidate_limit]))
    )
    chunks = list(chunks_result.scalars().all())
    return chunks, all_distances


async def get_source_titles(
    db: AsyncSession, source_ids: list[str]
) -> dict[str, str]:
    if not source_ids:
        return {}
    result = await db.execute(
        select(KnowledgeSource.id, KnowledgeSource.title).where(
            KnowledgeSource.id.in_(source_ids)
        )
    )
    return {row[0]: row[1] for row in result.fetchall()}


async def run_copilot(
    db: AsyncSession,
    provider: AIProvider,
    tenant_id: str,
    tenant_name: str,
    tenant_slug: str,
    teacher_id: str,
    teacher_name: str,
    teacher_role: str,
    messages: list[AIMessage],
    scope: SourceScope,
    task_type: str = "answer_question",
    max_tokens: int = 2000,
    temperature: float = 0.3,
    config: PipelineConfig = DEFAULT_CONFIG,
):
    from modules.settings.service import get_tenant_settings

    raw_query = messages[-1].content if messages else ""

    # --- Stage 1: Normalize + Classify ---
    normalized = normalize_arabic_query(raw_query)
    question_type = classify_question(normalized.normalized_query)
    logger.info(
        "copilot: query=%r type=%s scope=%s",
        normalized.normalized_query[:60], question_type, scope.value,
    )

    # --- Stage 2: Retrieve ---
    tenant_settings = await get_tenant_settings(db, tenant_id)
    chunks, distances = await retrieve_chunks(
        db, tenant_id, normalized.normalized_query, scope, config, question_type
    )

    # --- Stage 3: Rerank ---
    ranked_chunks: list[RankedChunk] = rerank_chunks(
        chunks=chunks,
        distances=distances,
        query=normalized.normalized_query,
        question_type=question_type,  # type: ignore[arg-type]
        max_chunks=config.retrieval.final_chunks,
        max_per_source=config.retrieval.max_chunks_per_source,
    )
    final_chunks = [rc.chunk for rc in ranked_chunks]

    # --- Stage 4: Confidence + sufficiency ---
    scope_str = scope.value
    # Map old scope values to new scope strings
    scope_map = {
        "teacher_kb": "teacher_kb_only",
        "official_curriculum": "curriculum_only",
        "teacher_and_curriculum": "teacher_kb_plus_curriculum",
        "all": "all_sources",
    }
    scope_key = scope_map.get(scope_str, scope_str)
    general_knowledge_allowed = scope_key == "all_sources"

    confidence = compute_confidence(
        ranked_chunks=ranked_chunks,
        question_type=question_type,  # type: ignore[arg-type]
        scope=scope_key,
        min_required=config.min_evidence_for(question_type),
    )

    # If evidence is insufficient and scope restricts general knowledge → short-circuit
    if not confidence.is_sufficient and not general_knowledge_allowed:
        insufficient_msg = INSUFFICIENT_MESSAGES.get(
            scope_key, "⚠️ لم أجد إجابة كافية في المصادر المتاحة."
        )
        if confidence.missing_knowledge_suggestion:
            insufficient_msg += f"\n\n💡 {confidence.missing_knowledge_suggestion}"

        source_ids = list({c.source_id for c in final_chunks})
        source_titles = await get_source_titles(db, source_ids)

        ctx = build_tenant_context(
            tenant_id=tenant_id, tenant_name=tenant_name, tenant_slug=tenant_slug,
            teacher_id=teacher_id, teacher_name=teacher_name, teacher_role=teacher_role,
            settings=tenant_settings, source_scope=scope, task_type=task_type,
            chunks=final_chunks, source_titles=source_titles,
        )

        from providers.ai_provider.base import AIResponse
        mock_response = AIResponse(
            text=insufficient_msg, tokens_used=0, model="none",
            provider="none", source_scope=scope.value,
        )
        return mock_response, ctx, True, [], final_chunks, {
            "original_query": normalized.original_query,
            "normalized_query": normalized.normalized_query,
            "question_type": question_type,
            "confidence": confidence,
            "retrieved_candidates_count": len(chunks),
            "selected_chunks_count": len(final_chunks),
        }

    # --- Stage 5: Build context + generate answer ---
    source_ids = list({c.source_id for c in final_chunks})
    source_titles = await get_source_titles(db, source_ids)

    ctx = build_tenant_context(
        tenant_id=tenant_id, tenant_name=tenant_name, tenant_slug=tenant_slug,
        teacher_id=teacher_id, teacher_name=teacher_name, teacher_role=teacher_role,
        settings=tenant_settings, source_scope=scope, task_type=task_type,
        chunks=final_chunks, source_titles=source_titles,
    )

    system_prompt = build_system_prompt(ctx)
    last_message = messages[-1]
    enriched_messages = messages[:-1] + [
        AIMessage(
            role=last_message.role,
            content=build_user_prompt(last_message.content, task_type),
        )
    ]

    response = await provider.complete(
        messages=enriched_messages,
        system_prompt=system_prompt,
        max_tokens=max_tokens,
        temperature=temperature,
    )
    response.source_scope = scope.value

    # --- Stage 6: Validate grounding ---
    validation = validate_answer(
        answer=response.text,
        ranked_chunks=ranked_chunks,
        scope=scope_key,
        general_knowledge_allowed=general_knowledge_allowed,
    )
    if not validation.is_valid:
        for v in validation.violations:
            logger.warning("copilot grounding violation: %s", v)

    # --- Stage 7: Build sources summary ---
    insufficient = len(final_chunks) == 0
    sources_summary: dict[str, dict] = {}
    for chunk in final_chunks:
        sid = chunk.source_id
        if sid not in sources_summary:
            sources_summary[sid] = {
                "source_id": sid,
                "source_title": source_titles.get(sid, "مصدر غير معروف"),
                "source_type": chunk.source_type_tag or "unknown",
                "chunk_count": 0,
                "page_numbers": [],
            }
        sources_summary[sid]["chunk_count"] += 1
        if chunk.page_number is not None:
            pages = sources_summary[sid]["page_numbers"]
            if chunk.page_number not in pages:
                pages.append(chunk.page_number)

    for s in sources_summary.values():
        s["page_numbers"].sort()

    debug_info = {
        "original_query": normalized.original_query,
        "normalized_query": normalized.normalized_query,
        "question_type": question_type,
        "confidence": confidence,
        "retrieved_candidates_count": len(chunks),
        "selected_chunks_count": len(final_chunks),
    }

    return response, ctx, insufficient, list(sources_summary.values()), final_chunks, debug_info
