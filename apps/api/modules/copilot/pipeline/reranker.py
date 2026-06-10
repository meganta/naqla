"""
Rule-based reranker for retrieved knowledge chunks.
Scores chunks by direct relevance signals and returns a ranked, deduplicated list.
"""
import re
from dataclasses import dataclass

from modules.copilot.pipeline.config import QuestionType
from modules.ingestion.models import KnowledgeChunk


@dataclass
class RankedChunk:
    chunk: KnowledgeChunk
    vector_distance: float
    rerank_score: float
    relevance_reason: str
    source_category: str = "teacher_kb"  # teacher_kb | curriculum | general


def _count_keyword_hits(text: str, keywords: list[str]) -> int:
    """Count how many keywords appear in the chunk text."""
    text_lower = text.lower()
    return sum(1 for kw in keywords if kw.lower() in text_lower)


def _has_metadata(chunk: KnowledgeChunk) -> bool:
    """Check if chunk has useful timestamp or page metadata."""
    return (
        chunk.start_ms is not None or
        chunk.page_number is not None
    )


def rerank_chunks(
    chunks: list[KnowledgeChunk],
    distances: dict[str, float],
    query: str,
    question_type: QuestionType,
    max_chunks: int = 8,
    max_per_source: int = 3,
) -> list[RankedChunk]:
    """
    Rerank chunks using a weighted scoring formula:
    - Vector similarity (primary)
    - Keyword match in chunk text (boost)
    - Metadata presence (small boost)
    - Question-type relevance (boost)
    - Per-source diversity cap
    """
    if not chunks:
        return []

    # Extract meaningful keywords from query
    stop_words = {'ما', 'ماذا', 'كيف', 'لماذا', 'متى', 'أين', 'من', 'هل', 'في', 'على', 'عن'}
    keywords = [
        w for w in re.split(r'\s+', query.strip())
        if len(w) >= 3 and w not in stop_words
    ]

    scored: list[tuple[float, RankedChunk]] = []

    for chunk in chunks:
        distance = distances.get(chunk.id, 1.0)
        # Convert distance to similarity (0→1, higher=better)
        similarity = max(0.0, 1.0 - distance)

        # Keyword match boost
        kw_hits = _count_keyword_hits(chunk.content_text or "", keywords)
        kw_boost = min(0.15, kw_hits * 0.04)

        # Metadata boost (has timestamp or page = more trustworthy)
        meta_boost = 0.05 if _has_metadata(chunk) else 0.0

        # Question-type specific boost
        type_boost = 0.0
        ct = chunk.content_text or ''
        if question_type == 'definition' and re.search(r'(?:يعني|هو|تعريف|يُعرَّف)', ct):
            type_boost = 0.08
        elif question_type == 'comparison' and re.search(
            r'(?:بينما|في حين|على خلاف|يشبه|يختلف)', ct
        ):
            type_boost = 0.08
        elif question_type == 'exercise_solving' and re.search(
            r'(?:الحل|خطوات|نحسب|نجد)', ct
        ):
            type_boost = 0.06

        final_score = similarity + kw_boost + meta_boost + type_boost

        # Build relevance reason
        reasons = []
        if similarity >= 0.4:
            reasons.append(f"تشابه عالٍ ({similarity:.2f})")
        if kw_hits > 0:
            reasons.append(f"{kw_hits} كلمة مفتاحية")
        if _has_metadata(chunk):
            reasons.append("يحتوي بيانات وصفية")
        if type_boost > 0:
            reasons.append(f"ملائم لنوع السؤال ({question_type})")
        reason = " — ".join(reasons) if reasons else "تشابه متجه"

        ranked = RankedChunk(
            chunk=chunk,
            vector_distance=distance,
            rerank_score=final_score,
            relevance_reason=reason,
        )
        scored.append((final_score, ranked))

    # Sort by score descending
    scored.sort(key=lambda x: x[0], reverse=True)

    # Apply per-source diversity cap
    source_count: dict[str, int] = {}
    result: list[RankedChunk] = []
    for _, rc in scored:
        sid = rc.chunk.source_id
        if source_count.get(sid, 0) < max_per_source:
            result.append(rc)
            source_count[sid] = source_count.get(sid, 0) + 1
        if len(result) >= max_chunks:
            break

    return result
