"""Tests for the Copilot pipeline — normalizer, classifier, expander, reranker, confidence."""
from modules.copilot.pipeline.classifier import classify_question
from modules.copilot.pipeline.confidence import compute_confidence
from modules.copilot.pipeline.expander import expand_query
from modules.copilot.pipeline.normalizer import normalize_arabic_query
from modules.copilot.pipeline.reranker import RankedChunk, rerank_chunks

# ---------- Normalizer ----------

def test_normalize_diacritics():
    r = normalize_arabic_query("الكِتَابُ الجَمِيلُ")
    assert "ِ" not in r.normalized_query
    assert "الكتاب" in r.normalized_query


def test_normalize_alef_variants():
    r = normalize_arabic_query("إبراهيم أحمد آدم")
    assert "إ" not in r.normalized_query
    assert "أ" not in r.normalized_query
    assert "آ" not in r.normalized_query


def test_normalize_colloquial_iezay():
    r = normalize_arabic_query("إزاي أفهم الجناس؟")
    assert "كيف" in r.normalized_query


def test_normalize_preserves_original():
    original = "يعني ايه الجناس؟"
    r = normalize_arabic_query(original)
    assert r.original_query == original
    assert r.original_query != r.normalized_query


def test_normalize_whitespace():
    r = normalize_arabic_query("  كلمة   أخرى  ")
    assert "  " not in r.normalized_query


# ---------- Classifier ----------

def test_classify_definition():
    assert classify_question("ما تعريف الجناس؟") == "definition"
    assert classify_question("ما معنى الاستعارة؟") == "definition"


def test_classify_explanation():
    assert classify_question("اشرح الجناس بمثال") == "explanation"
    assert classify_question("وضح الفرق") == "explanation"


def test_classify_comparison():
    assert classify_question("قارن بين الجناس والطباق") == "comparison"
    assert classify_question("الفرق بين التشبيه والاستعارة") == "comparison"


def test_classify_exam_question():
    assert classify_question("اعمل سؤال امتحان عن البلاغة") == "exam_question"


def test_classify_lesson_planning():
    assert classify_question("اعمل خطة درس للجناس") == "lesson_planning"


def test_classify_summarization():
    assert classify_question("لخص درس البلاغة") == "summarization"


def test_classify_exercise_solving():
    assert classify_question("حل هذا التمرين") == "exercise_solving"


def test_classify_unknown_fallback():
    assert classify_question("هذه جملة عادية بدون سؤال واضح") == "unknown"


# ---------- Expander ----------

def test_expand_definition_query():
    expanded = expand_query("ما معنى الجناس", "definition")
    assert len(expanded) >= 2
    assert "ما معنى الجناس" == expanded[0]  # original always first


def test_expand_with_known_term():
    expanded = expand_query("الجناس في النص", "explanation")
    joined = " ".join(expanded)
    assert "البلاغة" in joined or "الجناس" in joined


def test_expand_max_limit():
    expanded = expand_query("ما تعريف الاستعارة", "definition", max_expansions=3)
    assert len(expanded) <= 3


def test_expand_no_duplicates():
    expanded = expand_query("تعريف الجناس", "definition")
    assert len(expanded) == len(set(expanded))


# ---------- Reranker ----------

def _make_chunk(chunk_id: str, source_id: str, text: str, page: int | None = None):
    """Create a minimal mock KnowledgeChunk-like object."""
    from unittest.mock import MagicMock
    chunk = MagicMock()
    chunk.id = chunk_id
    chunk.source_id = source_id
    chunk.content_text = text
    chunk.source_type_tag = "youtube"
    chunk.page_number = page
    chunk.start_ms = None
    chunk.end_ms = None
    return chunk


def test_reranker_returns_sorted_by_score():
    chunks = [
        _make_chunk("c1", "s1", "تعريف الجناس هو تشابه اللفظين واختلاف المعنى"),
        _make_chunk("c2", "s2", "نص عشوائي غير ذي صلة بالسؤال أبداً"),
    ]
    distances = {"c1": 0.30, "c2": 0.65}
    ranked = rerank_chunks(chunks, distances, "ما تعريف الجناس", "definition")
    assert len(ranked) >= 1
    assert ranked[0].chunk.id == "c1"  # more relevant chunk first


def test_reranker_per_source_cap():
    chunks = [_make_chunk(f"c{i}", "same_source", f"محتوى {i}") for i in range(5)]
    distances = {f"c{i}": 0.3 + i * 0.05 for i in range(5)}
    ranked = rerank_chunks(chunks, distances, "سؤال", "unknown", max_per_source=2)
    assert len(ranked) <= 2


def test_reranker_empty_input():
    assert rerank_chunks([], {}, "سؤال", "unknown") == []


def test_reranker_source_type_priority():
    """YouTube chunk should appear before PDF chunk even with lower similarity."""
    youtube_chunk = _make_chunk("yt1", "s_yt", "محتوى يوتيوب عن الجملة الاسمية")
    youtube_chunk.source_type_tag = "youtube"
    pdf_chunk = _make_chunk("pdf1", "s_pdf", "محتوى PDF عن الجملة الاسمية مفصل جداً")
    pdf_chunk.source_type_tag = "pdf"

    # Equal similarity — YouTube should win due to source priority boost
    distances = {"yt1": 0.60, "pdf1": 0.60}
    ranked = rerank_chunks(
        [youtube_chunk, pdf_chunk], distances, "الجملة الاسمية", "definition"
    )
    assert len(ranked) == 2
    # Both should be present
    ids = [rc.chunk.id for rc in ranked]
    assert "yt1" in ids
    assert "pdf1" in ids
    # YouTube should rank first due to source priority boost (0.18 vs 0.03)
    assert ranked[0].chunk.id == "yt1"


# ---------- Confidence ----------

def _make_ranked(score: float) -> RankedChunk:
    from unittest.mock import MagicMock
    chunk = MagicMock()
    chunk.id = "x"
    chunk.source_id = "s"
    return RankedChunk(
        chunk=chunk,
        vector_distance=1.0 - score,
        rerank_score=score,
        relevance_reason="test",
    )


def test_confidence_high_with_strong_chunks():
    chunks = [_make_ranked(0.85), _make_ranked(0.80), _make_ranked(0.75)]
    result = compute_confidence(chunks, "definition", "teacher_kb_only", 1)
    assert result.level == "high"
    assert result.is_sufficient is True


def test_confidence_insufficient_no_chunks():
    result = compute_confidence([], "definition", "teacher_kb_only", 1)
    assert result.level == "insufficient"
    assert result.is_sufficient is False
    assert result.missing_knowledge_suggestion is not None


def test_confidence_comparison_needs_two():
    chunks = [_make_ranked(0.80)]
    result = compute_confidence(chunks, "comparison", "teacher_kb_only", 2)
    assert result.is_sufficient is False


def test_confidence_medium_single_strong():
    chunks = [_make_ranked(0.50)]
    result = compute_confidence(chunks, "explanation", "teacher_kb_only", 1)
    assert result.level == "medium"
    assert result.is_sufficient is True


def test_confidence_sufficient_with_real_distances():
    """Simulate real Arabic retrieval distances (0.62-0.67 → scores 0.33-0.38 + boosts)."""
    chunks = [_make_ranked(0.38), _make_ranked(0.35), _make_ranked(0.32)]
    result = compute_confidence(chunks, "definition", "teacher_kb_only", 1)
    assert result.is_sufficient is True
