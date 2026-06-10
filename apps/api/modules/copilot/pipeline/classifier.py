"""
Arabic question classifier.
Rule-based for MVP — classifies educational questions into types
that influence retrieval thresholds and answer formatting.
"""
import re

from modules.copilot.pipeline.config import QuestionType

# Ordered patterns: first match wins
_P = re.UNICODE  # shorthand

_PATTERNS: list[tuple[re.Pattern, QuestionType]] = [
    # source_specific — must check before others
    (re.compile(r'(?:من|في|بناءً على)\s+(?:الملف|الفيديو|المصدر|الكتاب|الدرس|الشرح)', _P),
     'source_specific'),
    # comparison
    (re.compile(r'(?:قارن|الفرق بين|أوجه الشبه|مقارنة|الاختلاف بين|يختلف عن|يشبه)', _P),
     'comparison'),
    # exam_question
    (re.compile(r'(?:اعمل سؤال|أنشئ سؤال|اكتب سؤال|سؤال امتحان|أسئلة امتحانية|نموذج امتحان)', _P),
     'exam_question'),
    # lesson_planning
    (re.compile(r'(?:خطة درس|خطة شرح|تحضير درس|منهجية الشرح|كيف أشرح)', _P),
     'lesson_planning'),
    # summarization
    (re.compile(r'(?:لخص|ملخص|اختصر|أهم النقاط|أبرز ما|نقاط الدرس)', _P),
     'summarization'),
    # exercise_solving
    (re.compile(r'(?:حل|اشرح الحل|طريقة الحل|كيف نحل|أحل|تمرين|مسألة)', _P),
     'exercise_solving'),
    # explanation
    (re.compile(r'(?:اشرح|وضح|فسر|بيّن|اذكر أمثلة|مثال على|كيف يعمل|كيف يتم)', _P),
     'explanation'),
    # definition
    (re.compile(r'(?:ما (?:هو|هي|معنى|تعريف|المقصود بـ?|المراد بـ?)|عرّف|يُعرَّف|تعريف)', _P),
     'definition'),
    # question mark starters — broad fallback
    (re.compile(r'^(?:ما|ماذا|لماذا|كيف|متى|أين|من|هل)\s', _P), 'unknown'),
]

_QUESTION_MARK = re.compile(r'[؟?]')


def classify_question(query: str) -> QuestionType:
    """
    Classify an Arabic educational question into a question type.
    Rule-based MVP — extend with LLM classification by replacing this function.
    """
    q = query.strip()

    for pattern, q_type in _PATTERNS:
        if pattern.search(q):
            return q_type

    # Has Arabic question mark → unknown but still a question
    if _QUESTION_MARK.search(q):
        return 'unknown'

    # Default
    return 'unknown'


# TODO: LLM-based classifier for ambiguous cases
# async def classify_question_llm(query: str, provider: AIProvider) -> QuestionType:
#     ...
