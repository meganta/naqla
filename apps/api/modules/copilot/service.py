from packages.ai_provider.base import AIMessage, AIProvider, SourceScope
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from modules.ingestion.models import KnowledgeChunk

ARABIC_SUBJECT_SCOPE = (
    "أنت مساعد تعليمي متخصص في اللغة العربية للمرحلة الثانوية المصرية. "
    "تساعد المعلمين فقط في مواضيع اللغة العربية: النحو، الصرف، الأدب، البلاغة، "
    "والمناهج الدراسية المصرية المعتمدة. "
    "لا تخرج عن نطاق تخصصك في أي حال."
)


async def retrieve_context(
    db: AsyncSession,
    tenant_id: str,
    query: str,
    scope: SourceScope,
    limit: int = 5,
) -> list[KnowledgeChunk]:
    if scope == SourceScope.OFFICIAL_CURRICULUM:
        return []
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
    from packages.ai_provider.base import AIResponse

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
