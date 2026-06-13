"""Tests for mobile module: OCR normalization, question detection, evidence mapping."""
from modules.mobile.ocr_service import normalize_arabic
from modules.mobile.question_detector import _is_simple_text, _rule_based_detect

# ---------- OCR normalization ----------


def test_normalize_strips_diacritics():
    assert normalize_arabic("الكِتَابُ") == "الكتاب"


def test_normalize_alef_variants():
    result = normalize_arabic("إبراهيم أحمد آدم")
    assert "إ" not in result
    assert "أ" not in result
    assert "آ" not in result


def test_normalize_whitespace():
    assert normalize_arabic("  كلمة   أخرى  ") == "كلمه اخرى"


# ---------- Question detection (rule-based, synchronous) ----------


def test_detect_question_by_arabic_mark():
    text = "ما الفكرة الرئيسية في النص؟"
    questions = _rule_based_detect(text)
    assert len(questions) == 1
    assert "ما الفكرة" in questions[0]


def test_detect_multiple_questions():
    text = "ما معنى الكلمة؟ لماذا فعل ذلك؟"
    questions = _rule_based_detect(text)
    assert len(questions) == 2


def test_detect_hel_starter():
    text = "هل المؤلف يرفض الرأي الآخر"
    questions = _rule_based_detect(text)
    assert len(questions) == 1


def test_no_question_returns_full_text():
    text = "هذا نص عادي بدون سؤال واضح"
    questions = _rule_based_detect(text)
    assert len(questions) == 1
    assert questions[0] == text


def test_empty_text_returns_empty():
    assert _rule_based_detect("") == []
    assert _rule_based_detect("   ") == []


def test_detect_sharh_starter():
    text = "اشرح أهمية الصدق في حياة الإنسان"
    questions = _rule_based_detect(text)
    assert len(questions) >= 1


def test_simple_text_is_simple():
    assert _is_simple_text("ما الفكرة الرئيسية؟") is True


def test_long_passage_not_simple():
    long_text = "\n".join(["هذا نص طويل جداً يحتوي على فقرة قراءة مطولة تتضمن الكثير من الكلمات والجمل الطويلة جداً"] * 5)
    assert _is_simple_text(long_text) is False
