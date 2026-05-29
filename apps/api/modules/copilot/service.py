from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from core.config import settings
from modules.ingestion.models import KnowledgeChunk
from providers.ai_provider.base import AIMessage, AIProvider, SourceScope

ARABIC_SUBJECT_SCOPE = (
    "أنت مساعد تعليمي متخصص في اللغة العربية للمرحلة الثانوية المصرية. "
    "تساعد المعلمين فقط في مواضيع اللغة العربية: النحو، الصرف، الأدب، البلاغة، "
    "والمناهج الدراسية المصرية المعتمدة. "
    "لا تخرج عن نطاق تخصصك في أي حال."
)


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


async def retrieve_context(
    db: AsyncSession,
    tenant_id: str,
    query: str,
    scope: SourceScope,
    limit: int = 5,
) -> list[KnowledgeChunk]:
    if scope == SourceScope.OFFICIAL_CURRICULUM:
        return []

    # Try vector similarity search first
    query_embedding = await embed_query(query)
    if query_embedding is not None:
        try:
            embedding_str = "[" + ",".join(str(x) for x in query_embedding) + "]"
            result = await db.execute(
                text("""
                    SELECT id FROM knowledge_chunks
                    WHERE tenant_id = :tenant_id
                    AND embedding IS NOT NULL
                    ORDER BY embedding <=> CAST(:embedding AS vector)
                    LIMIT :limit
                """),
                {
                    "tenant_id": tenant_id,
                    "embedding": embedding_str,
                    "limit": limit,
                }
            )
            ids = [row[0] for row in result.fetchall()]
            if ids:
                chunks_result = await db.execute(
                    select(KnowledgeChunk).where(KnowledgeChunk.id.in_(ids))
                )
                chunks = list(chunks_result.scalars().all())
                # Sort by original order
                id_order = {id_: i for i, id_ in enumerate(ids)}
                chunks.sort(key=lambda c: id_order.get(c.id, 999))
                return chunks
        except Exception:
            pass

    # Fallback to recency if no embeddings available
    stmt = (
        select(KnowledgeChunk)
        .where(KnowledgeChunk.tenant_id == tenant_id)
        .order_by(KnowledgeChunk.created_at.desc())
        .limit(limit)
    )
    result = await db.execute(stmt)
    return list(result.scalars().all())


def build_system_prompt(scope: SourceScope, context_chunks: list[KnowledgeChunk]) -> str:
    prompt = ARABIC_SUBJECT_SCOPE
    if context_chunks:
        context_text = chr(10).join(
            f"[مقطع {i + 1}]: {chunk.content_text}"
            for i, chunk in enumerate(context_chunks)
        )
        header = "استند إلى المعلومات التالية من قاعدة معرفة المعلم عند الإجابة:"
        prompt += f"{header}{chr(10)}{chr(10)}{context_text}"
    if scope == SourceScope.TEACHER_KB:
        prompt += "أجب فقط بناءً على المعلومات المقدمة من المعلم."
    elif scope == SourceScope.TEACHER_AND_CURRICULUM:
        prompt += "يمكنك الاستعانة بمعلومات المعلم والمنهج الرسمي معًا."
    elif scope == SourceScope.ALL:
        prompt += "يمكنك الاستعانة بجميع المصادر ضمن تخصص اللغة العربية."
    return prompt


async def run_copilot(
    db: AsyncSession,
    provider: AIProvider,
    tenant_id: str,
    messages: list[AIMessage],
    scope: SourceScope,
    max_tokens: int = 1000,
    temperature: float = 0.7,
):
    from providers.ai_provider.base import AIResponse

    query = messages[-1].content if messages else ''
    context_chunks = await retrieve_context(db, tenant_id, query, scope)
    system_prompt = build_system_prompt(scope, context_chunks)
    response: AIResponse = await provider.complete(
        messages=messages,
        system_prompt=system_prompt,
        max_tokens=max_tokens,
        temperature=temperature,
    )
    response.source_scope = scope.value
    return response, len(context_chunks)
