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


# Source type priority order — higher index = higher priority boost
SOURCE_TYPE_PRIORITY: dict[str, float] = {
    "youtube":         0.18,
    "youtube_channel": 0.18,
    "video":           0.14,
    "audio":           0.10,
    "pptx":            0.06,
    "pdf":             0.03,
    "docx":            0.02,
    "text":            0.01,
    "manual":          0.01,
}

# Guaranteed minimum slots per source category
SOURCE_TYPE_ORDER = ["youtube", "youtube_channel", "video", "audio", "pptx", "pdf", "docx"]


def rerank_chunks(
    chunks: list[KnowledgeChunk],
    distances: dict[str, float],
    query: str,
    question_type: QuestionType,
    max_chunks: int = 8,
    max_per_source: int = 3,
) -> list[RankedChunk]:
    """
    Rerank chunks using a weighted scoring formula with source type priority.
    Priority order: YouTube > Video > Audio > PPTX > PDF > Word/Text
    Guarantees at least 1 slot per available source type before score-filling.
    """
    if not chunks:
        return []

    stop_words = {'ما', 'ماذا', 'كيف', 'لماذا', 'متى', 'أين', 'من', 'هل', 'في', 'على', 'عن'}
    keywords = [
        w for w in re.split(r'\s+', query.strip())
        if len(w) >= 3 and w not in stop_words
    ]

    scored: list[tuple[float, RankedChunk]] = []

    for chunk in chunks:
        distance = distances.get(chunk.id, 1.0)
        similarity = max(0.0, 1.0 - distance)

        # Keyword match boost
        kw_hits = _count_keyword_hits(chunk.content_text or "", keywords)
        kw_boost = min(0.15, kw_hits * 0.04)

        # Metadata boost
        meta_boost = 0.05 if _has_metadata(chunk) else 0.0

        # Source type priority boost
        src_type = (chunk.source_type_tag or "").lower()
        type_priority_boost = SOURCE_TYPE_PRIORITY.get(src_type, 0.0)

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

        final_score = similarity + kw_boost + meta_boost + type_priority_boost + type_boost

        reasons = []
        if similarity >= 0.4:
            reasons.append(f"تشابه عالٍ ({similarity:.2f})")
        if kw_hits > 0:
            reasons.append(f"{kw_hits} كلمة مفتاحية")
        if _has_metadata(chunk):
            reasons.append("يحتوي بيانات وصفية")
        if type_priority_boost > 0:
            reasons.append(f"أولوية المصدر ({src_type})")
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

    # Phase 1: Guarantee 1 slot per source type (in priority order)
    result: list[RankedChunk] = []
    used_ids: set[str] = set()
    source_count: dict[str, int] = {}

    for src_type in SOURCE_TYPE_ORDER:
        for score, rc in scored:
            if rc.chunk.id in used_ids:
                continue
            chunk_type = (rc.chunk.source_type_tag or "").lower()
            if chunk_type == src_type:
                result.append(rc)
                used_ids.add(rc.chunk.id)
                source_count[rc.chunk.source_id] = source_count.get(rc.chunk.source_id, 0) + 1
                break  # one guaranteed slot per type

    # Phase 2: Fill remaining slots by score, respecting per-source cap
    for _, rc in scored:
        if len(result) >= max_chunks:
            break
        if rc.chunk.id in used_ids:
            continue
        sid = rc.chunk.source_id
        if source_count.get(sid, 0) < max_per_source:
            result.append(rc)
            used_ids.add(rc.chunk.id)
            source_count[sid] = source_count.get(sid, 0) + 1

    # Re-sort final result by score so display order is logical
    result.sort(key=lambda rc: rc.rerank_score, reverse=True)
    return result
