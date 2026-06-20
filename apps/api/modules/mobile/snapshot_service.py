"""
Snapshot service.
Orchestrates: OCR → question detection → chunk retrieval → answer generation → evidence mapping.
"""
import logging

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core.config import settings
from modules.copilot.pipeline.reranker import rerank_chunks
from modules.copilot.service import retrieve_chunks
from modules.ingestion.models import KnowledgeSource
from modules.mobile.evidence_builder import chunk_to_evidence
from modules.mobile.ocr_service import OCRResult, get_ocr_provider
from modules.mobile.question_detector import detect_questions
from modules.mobile.schemas import (
    DetectedQuestion,
    SnapshotQuestionRequest,
    SnapshotQuestionResponse,
)
from modules.settings.service import get_tenant_settings
from providers.ai_provider.base import AIMessage, AIProvider, SourceScope

logger = logging.getLogger(__name__)

NO_ANSWER_TEXT = "⚠️ لم أجد إجابة كافية في قاعدة معرفة المعلم لهذا السؤال."

def _build_snapshot_system_prompt(
    subject: str | None = None,
    grade_level: str | None = None,
) -> str:
    """Build a subject-aware expert persona system prompt."""
    if subject and grade_level:
        persona = (
            f"You are a highly experienced {subject} teacher specializing in "
            f"{grade_level} curriculum with deep mastery of the subject, "
            f"its rules, concepts, and exam question patterns."
        )
    elif subject:
        persona = (
            f"You are a highly experienced {subject} teacher with deep mastery "
            f"of the subject rules, concepts, and how questions are structured."
        )
    else:
        persona = (
            "You are a brilliant, highly experienced curriculum expert and teacher "
            "with deep mastery of academic subjects, their rules, concepts, "
            "and how exam questions are structured."
        )

    return (
        f"{persona}\n\n"
        "A student sent you a photo of an exam question or textbook page.\n"
        "You will receive:\n"
        "1. The full text from the image (may include a reading passage + question)\n"
        "2. Retrieved knowledge chunks from the teacher's knowledge base\n\n"
        "How to think and answer:\n"
        "- Read and deeply understand the full passage as an expert would\n"
        "- Identify the key theme, concepts, and academic elements in the passage\n"
        "- Understand exactly what the question asks in context of this passage\n"
        "- Use your expert knowledge AND retrieved chunks to form the answer\n"
        "- If passage + chunks lack sufficient info, respond ONLY with:\n"
        "  ⚠️ لم أجد إجابة كافية في قاعدة معرفة المعلم لهذا السؤال.\n"
        "- Answer clearly at the right academic level\n"
        "- Structure: direct answer first, explanation second, example if needed\n"
    )


async def _get_sources_by_ids(
    db: AsyncSession, source_ids: list[str]
) -> dict[str, KnowledgeSource]:
    if not source_ids:
        return {}
    result = await db.execute(
        select(KnowledgeSource).where(KnowledgeSource.id.in_(source_ids))
    )
    return {s.id: s for s in result.scalars().all()}


async def _answer_question(
    provider: AIProvider,
    question: str,
    full_ocr_text: str,
    chunks,
    sources: dict[str, KnowledgeSource],
    system_prompt: str = "",
) -> tuple[str, float]:
    """Generate answer using full OCR passage context + KB chunks."""
    context_parts = []

    # Full OCR text as reading passage context
    if full_ocr_text and len(full_ocr_text) > len(question) + 20:
        context_parts.append(
            f"[نص الصورة الكامل - اقرأه كاملاً قبل الإجابة]\n{full_ocr_text}"
        )

    # KB chunks
    for i, chunk in enumerate(chunks, 1):
        source = sources.get(chunk.source_id)
        title = source.title if source else "مصدر غير معروف"
        context_parts.append(f"[مصدر {i}: {title}]\n{chunk.content_text}")

    if not context_parts:
        return NO_ANSWER_TEXT, 0.0

    context = "\n\n".join(context_parts)
    user_message = (
        f"{context}\n\n"
        f"السؤال المطلوب الإجابة عنه فقط:\n{question}"
    )

    try:
        response = await provider.complete(
            messages=[AIMessage(role="user", content=user_message)],
            system_prompt=system_prompt or _build_snapshot_system_prompt(),
            max_tokens=800,
            temperature=0.3,
        )
        answer = response.text.strip()
        if answer.startswith("⚠️"):
            confidence = 0.0
        else:
            confidence = min(0.95, 0.6 + len(chunks) * 0.05)
        return answer, confidence
    except Exception as e:
        logger.error("snapshot _answer_question failed: %s", e)
        return NO_ANSWER_TEXT, 0.0


async def _extract_passage_concepts(
    text: str,
    question: str,
    api_key: str,
) -> str:
    """
    Extract key concepts from the passage to enrich KB search query.
    Returns a combined search query: question + passage concepts.
    """
    try:
        import openai
        client = openai.AsyncOpenAI(api_key=api_key)
        response = await client.chat.completions.create(
            model="gpt-4o-mini",
            max_tokens=100,
            temperature=0.0,
            messages=[
                {
                    "role": "system",
                    "content": (
                        "Extract 3-5 key academic concepts or topics from the passage. "
                        "Return ONLY a comma-separated list of concepts in the same "
                        "language as the text. No explanation."
                    ),
                },
                {
                    "role": "user",
                    "content": f"الفقرة:\n{text[:500]}\n\nالسؤال: {question}",
                },
            ],
        )
        concepts = (response.choices[0].message.content or "").strip()
        if concepts:
            return f"{question} {concepts}"
    except Exception as e:
        logger.warning("_extract_passage_concepts failed: %s", e)
    return question


async def process_snapshot(
    db: AsyncSession,
    provider: AIProvider,
    request: SnapshotQuestionRequest,
    request_id: str,
) -> SnapshotQuestionResponse:
    warnings: list[str] = []
    logger.info("snapshot request_id=%s tenant=%s", request_id, request.tenant_id)

    # Load tenant settings for subject-aware persona
    tenant_settings = await get_tenant_settings(db, request.tenant_id)
    snapshot_system_prompt = _build_snapshot_system_prompt(
        subject=getattr(tenant_settings, "subject", None),
        grade_level=getattr(tenant_settings, "grade_level", None),
    )

    # 1. OCR or override
    ocr_text = ""
    if request.ocr_override:
        ocr_text = request.ocr_override
        logger.info("snapshot request_id=%s using ocr_override", request_id)
    elif request.image_url or request.image_ref:
        image_ref = request.image_url or request.image_ref or ""
        ocr_provider = get_ocr_provider()
        ocr_result: OCRResult = await ocr_provider.extract_text(image_ref)
        if not ocr_result.is_usable:
            warnings.append(
                "لم يتمكن النظام من قراءة الصورة بوضوح. "
                "يرجى التقاط صورة أوضح وإعادة المحاولة."
            )
            if ocr_result.error:
                logger.warning(
                    "snapshot request_id=%s OCR error: %s", request_id, ocr_result.error
                )
            return SnapshotQuestionResponse(
                request_id=request_id,
                detected_questions=[],
                warnings=warnings,
            )
        ocr_text = ocr_result.normalized_text
    else:
        warnings.append("لم يتم تقديم صورة أو نص.")
        return SnapshotQuestionResponse(
            request_id=request_id, detected_questions=[], warnings=warnings
        )

    # 2. Detect questions
    questions = await detect_questions(ocr_text, api_key=settings.openai_api_key)
    if not questions:
        warnings.append("لم يتم اكتشاف أسئلة في النص المستخرج.")
        return SnapshotQuestionResponse(
            request_id=request_id, detected_questions=[], warnings=warnings
        )

    logger.info(
        "snapshot request_id=%s detected %d question(s): %s",
        request_id, len(questions), [q[:50] for q in questions]
    )

    # 3. Answer each question
    detected: list[DetectedQuestion] = []
    for i, question_text in enumerate(questions):
        q_id = f"q{i + 1}"

        # Enrich search query with passage concepts if text is long enough
        search_query = question_text
        if (
            settings.openai_api_key
            and len(ocr_text) > len(question_text) + 50
        ):
            search_query = await _extract_passage_concepts(
                ocr_text, question_text, settings.openai_api_key
            )
            logger.info(
                "snapshot request_id=%s enriched query: %s",
                request_id, search_query[:100],
            )

        # Retrieve chunks using enriched query
        chunks, distances = await retrieve_chunks(
            db=db,
            tenant_id=request.tenant_id,
            query=search_query,
            scope=SourceScope.TEACHER_KB,
        )

        # Rerank and filter — keep top 3 with minimum quality score
        ranked = rerank_chunks(
            chunks=chunks,
            distances=distances,
            query=question_text,
            question_type="unknown",
            max_chunks=8,
            max_per_source=2,
        )
        # Filter: minimum rerank score 0.28, max 3 evidence cards
        MIN_EVIDENCE_SCORE = 0.28
        MAX_EVIDENCE_CARDS = 3
        top_ranked = [
            rc for rc in ranked if rc.rerank_score >= MIN_EVIDENCE_SCORE
        ][:MAX_EVIDENCE_CARDS]
        top_chunks = [rc.chunk for rc in top_ranked]

        # Load sources for evidence
        source_ids = list({c.source_id for c in top_chunks})
        sources = await _get_sources_by_ids(db, source_ids)

        # Generate answer using top chunks
        answer, confidence = await _answer_question(
            provider, question_text, ocr_text, top_chunks, sources,
            system_prompt=snapshot_system_prompt,
        )

        # Build evidence cards from top ranked only
        evidence = []
        for chunk in top_chunks:
            source = sources.get(chunk.source_id)
            if not source:
                continue
            ev = chunk_to_evidence(chunk, source)
            if ev:
                evidence.append(ev)

        detected.append(DetectedQuestion(
            question_id=q_id,
            question_text=question_text,
            answer=answer,
            confidence=confidence,
            evidence=evidence,
        ))

    return SnapshotQuestionResponse(
        request_id=request_id,
        detected_questions=detected,
        warnings=warnings,
    )
