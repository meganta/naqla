"""
Grounding validator.
Rule-based MVP — validates the generated answer against retrieved chunks
to catch obvious grounding violations before returning to client.
"""
import re
from dataclasses import dataclass

from modules.copilot.pipeline.reranker import RankedChunk


@dataclass
class ValidationResult:
    is_valid: bool
    violations: list[str]
    used_general_knowledge: bool
    has_citations: bool


_GENERAL_KNOWLEDGE_MARKER = re.compile(r'\[معلومة عامة\]')
_INSUFFICIENT_MARKER = re.compile(r'⚠️\s*لم\s+أجد')
_CITATION_PATTERNS = [
    re.compile(r'📍'),          # video citation marker
    re.compile(r'▶️'),          # video play marker
    re.compile(r'المصدر\s*:'),  # text source citation
]


def validate_answer(
    answer: str,
    ranked_chunks: list[RankedChunk],
    scope: str,
    general_knowledge_allowed: bool,
) -> ValidationResult:
    """
    Validate the generated answer.
    Returns validation result with any violations found.
    """
    violations: list[str] = []

    used_general_knowledge = bool(_GENERAL_KNOWLEDGE_MARKER.search(answer))
    has_citations = any(p.search(answer) for p in _CITATION_PATTERNS)
    is_insufficient_response = bool(_INSUFFICIENT_MARKER.search(answer))

    # Rule 1: General knowledge used when not allowed
    if used_general_knowledge and not general_knowledge_allowed:
        violations.append(
            "الإجابة تحتوي على معلومات عامة وهي غير مسموح بها في النطاق الحالي"
        )

    # Rule 2: Answer has content but no chunks — only valid for all_sources
    if (
        not ranked_chunks
        and not is_insufficient_response
        and scope not in ("all_sources",)
        and len(answer.strip()) > 50
    ):
        violations.append(
            "الإجابة تحتوي على محتوى دون أدلة من قاعدة المعرفة"
        )

    # Rule 3: Insufficient marker but chunks exist with high confidence
    strong_chunks = [rc for rc in ranked_chunks if rc.rerank_score >= 0.55]
    if is_insufficient_response and len(strong_chunks) >= 2:
        # Regenerate would help here — just flag it
        violations.append(
            "الإجابة تشير إلى عدم وجود أدلة لكن تم العثور على أدلة قوية"
        )

    is_valid = len(violations) == 0

    return ValidationResult(
        is_valid=is_valid,
        violations=violations,
        used_general_knowledge=used_general_knowledge,
        has_citations=has_citations,
    )
