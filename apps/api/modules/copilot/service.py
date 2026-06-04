import logging

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from core.config import settings
from modules.copilot.context_builder import build_tenant_context
from modules.copilot.prompt_builder import build_system_prompt, build_user_prompt
from modules.ingestion.models import KnowledgeChunk, KnowledgeSource
from providers.ai_provider.base import AIMessage, AIProvider, SourceScope


async def embed_query(query: str) -> list[float] | None:
    """Generate embedding for a query using OpenAI."""
    if not settings.openai_api_key:
        return None
    try:
        import openai
        client = openai.OpenAI(api_key=settings.openai_api_key)
        response = client.embeddings.create(
            model="text-embedding-3-small",
            input=[query],
        )
        return response.data[0].embedding
    except Exception:
        return None


SIMILARITY_THRESHOLD = 0.75  # cosine distance — lower = more similar
CANDIDATE_LIMIT = 20        # fetch this many, then filter
MAX_CHUNKS_RETURNED = 8     # return at most this many after filtering

logger = logging.getLogger(__name__)


async def retrieve_chunks(
    db: AsyncSession,
    tenant_id: str,
    query: str,
    scope: SourceScope,
    limit: int = MAX_CHUNKS_RETURNED,
) -> list[KnowledgeChunk]:
    if scope == SourceScope.OFFICIAL_CURRICULUM:
        return []

    # Try vector similarity search with threshold filtering
    query_embedding = await embed_query(query)
    if query_embedding is not None:
        try:
            embedding_str = "[" + ",".join(str(x) for x in query_embedding) + "]"
            result = await db.execute(
                text("""
                    SELECT id, (embedding <=> CAST(:embedding AS vector)) AS distance
                    FROM knowledge_chunks
                    WHERE tenant_id = :tenant_id
                    AND embedding IS NOT NULL
                    AND chunk_index > 0
                    ORDER BY distance
                    LIMIT :limit
                """),
                {
                    "tenant_id": tenant_id,
                    "embedding": embedding_str,
                    "limit": CANDIDATE_LIMIT,
                }
            )
            rows = result.fetchall()
            filtered = [(row[0], row[1]) for row in rows if row[1] <= SIMILARITY_THRESHOLD]
            logger.info(
                "retrieve_chunks: query=%r candidates=%d filtered=%d threshold=%s",
                query[:80], len(rows), len(filtered), SIMILARITY_THRESHOLD,
            )
            for chunk_id, dist in filtered[:MAX_CHUNKS_RETURNED]:
                logger.info("  chunk=%s distance=%.4f", chunk_id, dist)
            ids = [row[0] for row in filtered[:MAX_CHUNKS_RETURNED]]
            if ids:
                chunks_result = await db.execute(
                    select(KnowledgeChunk).where(KnowledgeChunk.id.in_(ids))
                )
                chunks = list(chunks_result.scalars().all())
                id_order = {id_: i for i, id_ in enumerate(ids)}
                chunks.sort(key=lambda c: id_order.get(c.id, 999))
                return chunks
            logger.warning("retrieve_chunks: no chunks passed threshold for query=%r", query[:80])
        except Exception as e:
            logger.error("retrieve_chunks vector search failed: %s", e)

    # No embedding available — return empty rather than irrelevant recency results
    logger.warning("retrieve_chunks: no embedding, returning empty for tenant=%s", tenant_id)
    return []


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
):
    from modules.settings.service import get_tenant_settings

    query = messages[-1].content if messages else ""

    # Load tenant settings
    tenant_settings = await get_tenant_settings(db, tenant_id)

    # Retrieve relevant chunks
    chunks = await retrieve_chunks(db, tenant_id, query, scope)

    # Get source titles for chunks
    source_ids = list({c.source_id for c in chunks})
    source_titles = await get_source_titles(db, source_ids)

    # Build context package
    ctx = build_tenant_context(
        tenant_id=tenant_id,
        tenant_name=tenant_name,
        tenant_slug=tenant_slug,
        teacher_id=teacher_id,
        teacher_name=teacher_name,
        teacher_role=teacher_role,
        settings=tenant_settings,
        source_scope=scope,
        task_type=task_type,
        chunks=chunks,
        source_titles=source_titles,
    )

    # Build prompts
    system_prompt = build_system_prompt(ctx)
    last_message = messages[-1]
    enriched_messages = messages[:-1] + [
        AIMessage(
            role=last_message.role,
            content=build_user_prompt(last_message.content, task_type),
        )
    ]

    # Call AI provider
    response = await provider.complete(
        messages=enriched_messages,
        system_prompt=system_prompt,
        max_tokens=max_tokens,
        temperature=temperature,
    )
    response.source_scope = scope.value

    # Check insufficient context
    insufficient = (
        scope == SourceScope.TEACHER_KB
        and len(chunks) == 0
    )

    # Build sources used summary
    sources_summary: dict[str, dict] = {}
    for chunk in chunks:
        sid = chunk.source_id
        if sid not in sources_summary:
            sources_summary[sid] = {
                "source_id": sid,
                "source_title": source_titles.get(sid, "مصدر غير معروف"),
                "source_type": chunk.source_type_tag or "unknown",
                "chunk_count": 0,
            }
        sources_summary[sid]["chunk_count"] += 1

    return response, ctx, insufficient, list(sources_summary.values())
