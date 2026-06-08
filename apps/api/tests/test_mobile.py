"""Tests for mobile module: OCR normalization, question detection, evidence mapping."""
import pytest

from modules.mobile.ocr_service import normalize_arabic
from modules.mobile.question_detector import detect_questions


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


# ---------- Question detection ----------

def test_detect_question_by_arabic_mark():
    text = "ما الفكرة الرئيسية في النص؟"
    questions = detect_questions(text)
    assert len(questions) == 1
    assert "ما الفكرة" in questions[0]


def test_detect_multiple_questions():
    text = "ما معنى الكلمة؟ لماذا فعل ذلك؟"
    questions = detect_questions(text)
    assert len(questions) == 2


def test_detect_hel_starter():
    text = "هل المؤلف يرفض الرأي الآخر"
    questions = detect_questions(text)
    assert len(questions) == 1


def test_no_question_returns_full_text():
    text = "هذا نص عادي بدون سؤال واضح"
    questions = detect_questions(text)
    assert len(questions) == 1
    assert questions[0] == text


def test_empty_text_returns_empty():
    assert detect_questions("") == []
    assert detect_questions("   ") == []


def test_detect_sharh_starter():
    text = "اشرح أهمية الصدق في حياة الإنسان"
    questions = detect_questions(text)
    assert len(questions) >= 1
