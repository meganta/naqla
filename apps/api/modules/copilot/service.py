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

    # Try hybrid search: vector similarity + title keyword boost
    query_embedding = await embed_query(query)
    if query_embedding is not None:
        try:
            embedding_str = "[" + ",".join(str(x) for x in query_embedding) + "]"
            # Extract keywords from query (words > 3 chars)
            keywords = [w.strip() for w in query.split() if len(w.strip()) > 3]
            title_filter = " OR ".join(
                f"ks.title ILIKE :kw{i}" for i in range(len(keywords))
            ) if keywords else "FALSE"
            kw_params = {f"kw{i}": f"%{kw}%" for i, kw in enumerate(keywords)}
            result = await db.execute(
                text(f"""
                    SELECT kc.id,
                        (kc.embedding <=> CAST(:embedding AS vector)) AS distance,
                        CASE WHEN ({title_filter}) THEN 0.15 ELSE 0 END AS title_boost
                    FROM knowledge_chunks kc
                    JOIN knowledge_sources ks ON ks.id = kc.source_id
                    WHERE kc.tenant_id = :tenant_id
                    AND kc.embedding IS NOT NULL
                    AND kc.chunk_index > 0
                    ORDER BY (kc.embedding <=> CAST(:embedding AS vector))
                        - (CASE WHEN ({title_filter}) THEN 0.15 ELSE 0 END)
                    LIMIT :limit
                """),
                {
                    "tenant_id": tenant_id,
                    "embedding": embedding_str,
                    "limit": CANDIDATE_LIMIT,
                    **kw_params,
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
            # Deduplicate: max 2 chunks per source, preserve similarity order
            deduped = []
            for chunk_id, dist in filtered:
                # We need source_id — fetch minimally after dedup
                deduped.append((chunk_id, dist))
                if len(deduped) >= MAX_CHUNKS_RETURNED * 3:
                    break

            ids = [row[0] for row in deduped[:MAX_CHUNKS_RETURNED * 3]]
            if ids:
                chunks_result = await db.execute(
                    select(KnowledgeChunk).where(KnowledgeChunk.id.in_(ids))
                )
                all_chunks = list(chunks_result.scalars().all())
                id_order = {id_: i for i, id_ in enumerate(ids)}
                all_chunks.sort(key=lambda c: id_order.get(c.id, 999))

                # Apply per-source deduplication (max 2 per source)
                source_count: dict[str, int] = {}
                final_chunks = []
                for c in all_chunks:
                    count = source_count.get(c.source_id, 0)
                    if count < 2:
                        final_chunks.append(c)
                        source_count[c.source_id] = count + 1
                    if len(final_chunks) >= MAX_CHUNKS_RETURNED:
                        break

                logger.info(
                    "retrieve_chunks: returning %d chunks from %d sources",
                    len(final_chunks), len(source_count),
                )
                return final_chunks
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
