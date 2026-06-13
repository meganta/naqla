"""
Snapshot service.
Orchestrates: OCR → question detection → chunk retrieval → answer generation → evidence mapping.
"""
import logging

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core.config import settings
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
from providers.ai_provider.base import AIMessage, AIProvider, SourceScope

logger = logging.getLogger(__name__)

NO_ANSWER_TEXT = "⚠️ لم أجد إجابة كافية في قاعدة معرفة المعلم لهذا السؤال."

SNAPSHOT_SYSTEM_PROMPT = """\
You are an Arabic-language education assistant for Egyptian high school students.
You MUST answer ONLY using the retrieved knowledge chunks provided below.
Do NOT use any general knowledge outside the provided chunks.
If the chunks do not contain a sufficient answer, respond ONLY with:
⚠️ لم أجد إجابة كافية في قاعدة معرفة المعلم لهذا السؤال.
Do not add any extra text in that case.
Answer in clear formal Arabic suitable for a high school student.
Keep the answer concise and directly address the question.
"""


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
    chunks,
    sources: dict[str, KnowledgeSource],
) -> tuple[str, float]:
    """Generate an answer from chunks. Returns (answer_text, confidence)."""
    if not chunks:
        return NO_ANSWER_TEXT, 0.0

    context_parts = []
    for i, chunk in enumerate(chunks, 1):
        source = sources.get(chunk.source_id)
        title = source.title if source else "مصدر غير معروف"
        context_parts.append(f"[{i}] {title}:\n{chunk.content_text}")

    context = "\n\n".join(context_parts)
    user_message = f"السياق:\n{context}\n\nالسؤال:\n{question}"

    try:
        response = await provider.complete(
            messages=[AIMessage(role="user", content=user_message)],
            system_prompt=SNAPSHOT_SYSTEM_PROMPT,
            max_tokens=800,
            temperature=0.3,
        )
        answer = response.text.strip()
        # Simple confidence heuristic: no-answer response → 0.0, else based on chunk count
        if answer.startswith("⚠️"):
            confidence = 0.0
        else:
            confidence = min(0.95, 0.6 + len(chunks) * 0.05)
        return answer, confidence
    except Exception as e:
        logger.error("snapshot _answer_question failed: %s", e)
        return NO_ANSWER_TEXT, 0.0


async def process_snapshot(
    db: AsyncSession,
    provider: AIProvider,
    request: SnapshotQuestionRequest,
    request_id: str,
) -> SnapshotQuestionResponse:
    warnings: list[str] = []
    logger.info("snapshot request_id=%s tenant=%s", request_id, request.tenant_id)

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
        "snapshot request_id=%s detected %d question(s)", request_id, len(questions)
    )

    # 3. Answer each question
    detected: list[DetectedQuestion] = []
    for i, question_text in enumerate(questions):
        q_id = f"q{i + 1}"

        # Retrieve chunks
        chunks, _ = await retrieve_chunks(
            db=db,
            tenant_id=request.tenant_id,
            query=question_text,
            scope=SourceScope.TEACHER_KB,
        )

        # Load sources for evidence
        source_ids = list({c.source_id for c in chunks})
        sources = await _get_sources_by_ids(db, source_ids)

        # Generate answer
        answer, confidence = await _answer_question(provider, question_text, chunks, sources)

        # Build evidence
        evidence = []
        for chunk in chunks:
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
