"""
Confidence scorer and evidence sufficiency checker.
Determines if retrieved evidence is sufficient to answer a question
and computes a confidence level for the final answer.
"""
from dataclasses import dataclass

from modules.copilot.pipeline.config import ConfidenceLevel, QuestionType
from modules.copilot.pipeline.reranker import RankedChunk

# Insufficient answer messages per scope
INSUFFICIENT_MESSAGES: dict[str, str] = {
    "teacher_kb_only":              "⚠️ لم أجد إجابة كافية من معرفة المعلم المتاحة.",
    "curriculum_only":              "⚠️ لم أجد إجابة كافية من المنهج الرسمي المتاح.",
    "teacher_kb_plus_curriculum":   "⚠️ لم أجد إجابة كافية من قاعدة المعرفة أو المنهج الرسمي.",
    "all_sources":                  "⚠️ لم أجد إجابة كافية في المصادر المتاحة.",
}


@dataclass
class ConfidenceResult:
    level: ConfidenceLevel
    score: float          # 0.0 → 1.0
    reason: str
    is_sufficient: bool
    missing_knowledge_suggestion: str | None = None


def compute_confidence(
    ranked_chunks: list[RankedChunk],
    question_type: QuestionType,
    scope: str,
    min_required: int = 1,
) -> ConfidenceResult:
    """
    Compute confidence based on:
    - Number of ranked chunks
    - Their rerank scores
    - Question type minimum requirements
    """
    if not ranked_chunks:
        return ConfidenceResult(
            level="insufficient",
            score=0.0,
            reason="لا توجد أدلة من قاعدة المعرفة",
            is_sufficient=False,
            missing_knowledge_suggestion=_suggest_missing(question_type),
        )

    # Note: rerank_score = 1 - vector_distance + boosts
    # Distances of 0.60-0.70 → base scores of 0.30-0.40, boosted to 0.35-0.55
    # Thresholds calibrated for Arabic educational content
    strong_chunks = [rc for rc in ranked_chunks if rc.rerank_score >= 0.45]
    medium_chunks = [rc for rc in ranked_chunks if 0.28 <= rc.rerank_score < 0.45]
    total = len(ranked_chunks)

    # Comparison needs evidence for both sides
    if question_type == 'comparison' and total < 2:
        return ConfidenceResult(
            level="low",
            score=0.25,
            reason="المقارنة تحتاج أدلة لكلا الجانبين — وُجد جانب واحد فقط",
            is_sufficient=False,
            missing_knowledge_suggestion="أضف مصادر تغطي الجانب الثاني من المقارنة",
        )

    # Check minimum evidence
    if total < min_required:
        return ConfidenceResult(
            level="insufficient",
            score=0.1 * total,
            reason=f"عدد الأدلة ({total}) أقل من الحد الأدنى المطلوب ({min_required})",
            is_sufficient=False,
            missing_knowledge_suggestion=_suggest_missing(question_type),
        )

    # Score calculation
    if len(strong_chunks) >= 2:
        avg_score = sum(rc.rerank_score for rc in strong_chunks[:3]) / min(3, len(strong_chunks))
        level: ConfidenceLevel = "high"
        reason = f"{len(strong_chunks)} دليل قوي مباشر"
    elif len(strong_chunks) == 1:
        avg_score = strong_chunks[0].rerank_score * 0.85
        level = "medium"
        reason = "دليل قوي واحد مع أدلة داعمة"
    elif medium_chunks:
        n = min(3, len(medium_chunks))
        avg_score = sum(rc.rerank_score for rc in medium_chunks[:n]) / n * 0.7
        level = "medium" if len(medium_chunks) >= 2 else "low"
        reason = f"{len(medium_chunks)} دليل متوسط الجودة"
    else:
        avg_score = 0.2
        level = "low"
        reason = "أدلة ضعيفة الصلة بالسؤال"

    return ConfidenceResult(
        level=level,
        score=round(min(0.99, avg_score), 3),
        reason=reason,
        is_sufficient=level in ("high", "medium"),
    )


def _suggest_missing(question_type: QuestionType) -> str:
    suggestions = {
        "definition": "أضف مصادر تحتوي تعريف المفهوم المطلوب",
        "explanation": "أضف مقاطع فيديو أو ملفات تشرح هذا الموضوع",
        "comparison": "أضف مصادر تغطي كلا الجانبين المراد مقارنتهما",
        "exercise_solving": "أضف أمثلة محلولة من الكتاب أو الفيديوهات",
        "summarization": "أضف المصدر الكامل للدرس المراد تلخيصه",
        "exam_question": "أضف نماذج امتحانية أو دروس تغطي الموضوع",
        "lesson_planning": "أضف مصادر شاملة للدرس المراد التخطيط له",
        "source_specific": "تأكد من أن المصدر المطلوب تم رفعه ومعالجته",
        "unknown": "أضف مصادر ذات صلة بموضوع السؤال",
    }
    return suggestions.get(question_type, "أضف مصادر ذات صلة بموضوع السؤال")
