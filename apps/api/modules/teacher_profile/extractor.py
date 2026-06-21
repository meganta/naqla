"""
Teacher Style Profile Extractor.
Analyzes the teacher's knowledgebase and extracts a comprehensive
educational fingerprint of HOW the teacher teaches.

Design:
- Samples chunks per source type for cost efficiency
- GPT-4o at temperature=0 for determinism
- Each major dimension extracted in a focused prompt
- Evidence-based: never invents characteristics
- Returns Unknown when confidence is low
"""
import json
import logging
import random

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from modules.ingestion.models import KnowledgeChunk, KnowledgeSource

logger = logging.getLogger(__name__)

# Sampling config — balance coverage vs cost
SAMPLES_PER_SOURCE_TYPE = 30
MAX_CHUNK_CHARS = 400       # truncate long chunks for prompt efficiency
MAX_SAMPLES_TOTAL = 150     # hard cap on total chunks sent to LLM


def _truncate(text: str, max_chars: int = MAX_CHUNK_CHARS) -> str:
    return text[:max_chars] + "..." if len(text) > max_chars else text


async def _sample_chunks(
    db: AsyncSession,
    tenant_id: str,
) -> tuple[list[dict], dict[str, int]]:
    """
    Sample chunks from the knowledgebase, balanced across source types.
    Returns (sampled_chunks, source_type_counts).
    """
    # Get all chunks with source info
    result = await db.execute(
        select(
            KnowledgeChunk.id,
            KnowledgeChunk.content_text,
            KnowledgeChunk.source_id,
            KnowledgeChunk.source_type_tag,
            KnowledgeSource.title,
            KnowledgeSource.source_type,
        )
        .join(KnowledgeSource, KnowledgeSource.id == KnowledgeChunk.source_id)
        .where(
            KnowledgeChunk.tenant_id == tenant_id,
            KnowledgeChunk.chunk_index > 0,   # skip intro chunks
            func.length(KnowledgeChunk.content_text) > 50,
        )
        .order_by(func.random())
        .limit(500)  # fetch 500, then sample
    )
    rows = result.fetchall()

    # Group by source type
    by_type: dict[str, list] = {}
    type_counts: dict[str, int] = {}
    for row in rows:
        stype = row.source_type or row.source_type_tag or "unknown"
        by_type.setdefault(stype, []).append(row)
        type_counts[stype] = type_counts.get(stype, 0) + 1

    # Sample per type
    sampled = []
    for stype, chunks in by_type.items():
        take = min(SAMPLES_PER_SOURCE_TYPE, len(chunks))
        sampled.extend(random.sample(chunks, take))

    # Shuffle and cap total
    random.shuffle(sampled)
    sampled = sampled[:MAX_SAMPLES_TOTAL]

    # Format for prompt
    formatted = [
        {
            "source_title": row.title or "مصدر غير معروف",
            "source_type": row.source_type or row.source_type_tag or "unknown",
            "text": _truncate(row.content_text or ""),
        }
        for row in sampled
    ]

    return formatted, type_counts


def _build_extraction_prompt(chunks: list[dict], dimension: str) -> str:
    """Build a focused extraction prompt for a specific profile dimension."""
    chunks_text = "\n\n".join(
        f"[{c['source_type'].upper()} — {c['source_title']}]\n{c['text']}"
        for c in chunks
    )

    dimension_instructions = {
        "tone_and_language": """
Extract from the knowledge chunks:
1. TONE: Primary tone (Formal/Friendly/Strict/Motivational/Humorous/Calm/Energetic/Inspirational)
   and secondary tones if present.
2. LANGUAGE_STYLE: Classical Arabic / Egyptian Arabic / Mixed / Simple / Academic / Technical.
   Also note: sentence length preference, vocabulary complexity, use of dialect/slang/English terms.
3. COMMON_PHRASES: List the top recurring phrases/expressions the teacher uses
   (with frequency estimate).

Return JSON only. No explanation.
{
  "tone": {
    "primary": "...",
    "secondary": ["..."],
    "confidence": 0-100,
    "evidence_count": N,
    "representative_examples": ["...","..."],
    "supporting_sources": [{"source": "...", "type": "..."}]
  },
  "language_style": {
    "dialect": "...",
    "sentence_length": "short|medium|long",
    "vocabulary_complexity": "simple|mixed|academic|technical",
    "uses_english_terms": true/false,
    "uses_dialect_slang": true/false,
    "confidence": 0-100,
    "evidence_count": N,
    "representative_examples": ["...","..."]
  },
  "common_phrases": [
    {"phrase": "...", "frequency": "high|medium|low", "context": "..."}
  ]
}""",

        "explanation_and_methodology": """
Extract from the knowledge chunks:
1. EXPLANATION_STYLE: How does the teacher explain? Rank these:
   step-by-step / storytelling / real-life examples / analogies / definitions-first /
   examples-first / comparison / question-then-explanation / summary-first / theoretical / practical
2. TEACHING_METHODOLOGY: How does the teacher structure lessons?
   - What does the teacher START with? (definition/rule/question/problem/story/misconception)
   - What comes NEXT? (example/exercise/exam-question/discussion/summary)
   - Patterns: spiral/incremental/micro-learning/scaffolding/exam-coaching
3. DIFFICULTY_HANDLING: Does the teacher simplify aggressively / gradually increase /
   use prerequisites / repeat concepts / provide multiple examples?

Return JSON only.
{
  "explanation_style": {
    "ranked_styles": ["...", "..."],
    "primary_style": "...",
    "confidence": 0-100,
    "evidence_count": N,
    "representative_examples": ["...","..."]
  },
  "teaching_methodology": {
    "typically_starts_with": "...",
    "typically_continues_with": ["..."],
    "detected_patterns": ["..."],
    "lesson_flow": "...",
    "confidence": 0-100,
    "evidence_count": N,
    "representative_examples": ["...","..."]
  },
  "difficulty_handling": {
    "approach": "...",
    "uses_prerequisites": true/false,
    "repeats_concepts": true/false,
    "provides_multiple_examples": true/false,
    "confidence": 0-100,
    "evidence_count": N
  }
}""",

        "student_interaction_and_exam": """
Extract from the knowledge chunks:
1. STUDENT_INTERACTION: How does the teacher interact with students?
   encourage / challenge / Socratic questions / motivate / warn / praise /
   correct-gently / correct-directly / guide-discovery / provide-reassurance
2. EXAM_ORIENTATION: Does the teacher focus on exam patterns?
   Rank: marks / exam-patterns / common-mistakes / expected-questions /
   model-answers / exam-traps / scoring-techniques / revision / memory-tricks
3. EVIDENCE_BEHAVIOR: Does the teacher quote textbook / mention page numbers /
   reference previous lessons / explain WHY / justify answers / refer to videos?

Return JSON only.
{
  "student_interaction": {
    "primary_style": "...",
    "detected_behaviors": ["..."],
    "confidence": 0-100,
    "evidence_count": N,
    "representative_examples": ["...","..."]
  },
  "exam_orientation": {
    "is_exam_focused": true/false,
    "ranked_focus_areas": ["..."],
    "confidence": 0-100,
    "evidence_count": N,
    "representative_examples": ["...","..."]
  },
  "evidence_behavior": {
    "cites_sources": true/false,
    "explains_why": true/false,
    "references_previous_lessons": true/false,
    "detected_behaviors": ["..."],
    "confidence": 0-100,
    "evidence_count": N
  }
}""",

        "teaching_habits": """
Extract from the knowledge chunks additional teaching insights:
1. TYPICAL_ANSWER_STRUCTURE: How does the teacher typically structure a complete answer?
2. PREFERRED_DETAIL_LEVEL: brief / moderate / detailed / very-detailed
3. USES_REPETITION: Does the teacher repeat key points frequently?
4. USES_SUMMARY: Does the teacher frequently summarize?
5. ANTICIPATES_MISTAKES: Does the teacher proactively mention common student errors?
6. ENCOURAGES_MEMORIZATION_VS_UNDERSTANDING: Which does the teacher emphasize more?
7. ENCOURAGES_CRITICAL_THINKING: true/false with evidence
8. TRANSITION_STYLE: How does the teacher move between concepts?
9. INTRODUCTION_STYLE: How does the teacher introduce new concepts?
10. CONCLUSION_STYLE: How does the teacher conclude explanations?

Return JSON only.
{
  "teaching_habits": {
    "typical_answer_structure": "...",
    "preferred_detail_level": "...",
    "uses_repetition": true/false,
    "uses_frequent_summaries": true/false,
    "anticipates_student_mistakes": true/false,
    "emphasis": "memorization|understanding|balanced",
    "encourages_critical_thinking": true/false,
    "transition_style": "...",
    "introduction_style": "...",
    "conclusion_style": "...",
    "confidence": 0-100,
    "evidence_count": N,
    "representative_examples": ["...","..."]
  }
}""",
    }

    instruction = dimension_instructions.get(dimension, "")

    return f"""You are analyzing a teacher's knowledge base to extract their teaching style profile.
Analyze ONLY what is explicitly present in the provided chunks.
Do NOT invent characteristics. Return "Unknown" when confidence is below 40.
Use temperature=0 thinking — be deterministic and evidence-based.

KNOWLEDGE CHUNKS ({len(chunks)} samples):
{chunks_text}

TASK:
{instruction}"""


async def extract_profile(
    db: AsyncSession,
    tenant_id: str,
    api_key: str,
) -> dict:
    """
    Main extraction function.
    Returns a complete Teacher Style Profile as a dict.
    """
    import openai

    client = openai.AsyncOpenAI(api_key=api_key)

    logger.info("extract_profile: sampling chunks for tenant=%s", tenant_id)
    chunks, type_counts = await _sample_chunks(db, tenant_id)
    total_chunks = len(chunks)
    total_sources = sum(type_counts.values())

    logger.info(
        "extract_profile: %d chunks sampled, source types: %s",
        total_chunks, type_counts,
    )

    dimensions = [
        "tone_and_language",
        "explanation_and_methodology",
        "student_interaction_and_exam",
        "teaching_habits",
    ]

    profile_parts: dict = {}

    for dim in dimensions:
        logger.info("extract_profile: extracting dimension=%s", dim)
        prompt = _build_extraction_prompt(chunks, dim)
        try:
            response = await client.chat.completions.create(
                model="gpt-4o",
                max_tokens=2000,
                temperature=0.0,
                messages=[
                    {
                        "role": "system",
                        "content": (
                            "You are an expert educational analyst. "
                            "Return ONLY valid JSON. No markdown, no explanation."
                        ),
                    },
                    {"role": "user", "content": prompt},
                ],
            )
            raw = (response.choices[0].message.content or "").strip()
            # Strip markdown fences if present
            if raw.startswith("```"):
                raw = raw.split("```")[1]
                if raw.startswith("json"):
                    raw = raw[4:]
                raw = raw.strip()
            parsed = json.loads(raw)
            profile_parts.update(parsed)
            logger.info("extract_profile: dimension=%s extracted successfully", dim)
        except Exception as e:
            logger.error("extract_profile: dimension=%s failed: %s", dim, e)
            profile_parts[dim] = {"error": str(e), "confidence": 0}

    # Build final profile
    profile = {
        "version": 1,
        "tenant_id": tenant_id,
        "metadata": {
            "chunks_analyzed": total_chunks,
            "sources_analyzed": total_sources,
            "source_type_distribution": type_counts,
            "extraction_model": "gpt-4o",
            "temperature": 0.0,
        },
        **profile_parts,
    }

    return profile
