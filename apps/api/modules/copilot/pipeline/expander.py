"""
Arabic educational query expander.
Generates expanded search queries to improve retrieval recall.
Rule-based + keyword extraction for MVP.
"""
import re

from modules.copilot.pipeline.config import QuestionType

_STOP_WORDS = {
    'ما', 'ماذا', 'لماذا', 'كيف', 'متى', 'أين', 'اين', 'من', 'هل',
    'في', 'على', 'عن', 'مع', 'إلى', 'الى', 'هو', 'هي', 'هم', 'هن',
    'أن', 'ان', 'إن', 'لا', 'لم', 'لن', 'قد', 'كان', 'كانت',
    'يكون', 'تكون', 'هذا', 'هذه', 'ذلك', 'تلك', 'ال',
}

# Educational synonym/related-term expansions
_EDUCATIONAL_EXPANSIONS: dict[str, list[str]] = {
    'جناس': ['الجناس في البلاغة', 'المحسنات البديعية', 'تشابه اللفظين'],
    'طباق': ['الطباق في البلاغة', 'المحسنات البديعية', 'التضاد'],
    'استعارة': ['الاستعارة في البلاغة', 'الصور البيانية', 'المجاز'],
    'تشبيه': ['التشبيه في البلاغة', 'الصور البيانية', 'أركان التشبيه'],
    'كناية': ['الكناية في البلاغة', 'الصور البيانية'],
    'مجاز': ['المجاز في البلاغة', 'الاستعارة والكناية'],
    'بلاغة': ['علم البيان', 'المحسنات البديعية', 'الصور البلاغية'],
    'نحو': ['قواعد اللغة العربية', 'الإعراب'],
    'إعراب': ['قواعد النحو', 'الإعراب في اللغة العربية'],
    'فكرة': ['الفكرة الرئيسية', 'موضوع النص', 'محور النص'],
    'موضوع': ['موضوع النص', 'الفكرة الرئيسية', 'مضمون النص'],
}

# Question type → expansion strategy
_TYPE_PREFIXES: dict[QuestionType, list[str]] = {
    'definition': ['تعريف', 'المقصود بـ', 'معنى'],
    'explanation': ['شرح', 'توضيح', 'تفسير'],
    'comparison': ['مقارنة', 'الفرق بين', 'أوجه الشبه والاختلاف'],
    'exercise_solving': ['حل', 'طريقة الحل', 'خطوات الحل'],
    'summarization': ['ملخص', 'أهم النقاط', 'خلاصة'],
    'exam_question': ['سؤال امتحاني', 'نموذج سؤال'],
    'lesson_planning': ['خطة درس', 'شرح الدرس'],
    'source_specific': [],
    'unknown': [],
}


def _extract_keywords(query: str) -> list[str]:
    """Extract meaningful keywords from a normalized Arabic query."""
    tokens = re.split(r'\s+', query.strip())
    keywords = []
    for token in tokens:
        # Remove Arabic definite article
        clean = re.sub(r'^ال', '', token)
        if len(clean) >= 3 and clean not in _STOP_WORDS and token not in _STOP_WORDS:
            keywords.append(clean)
    return list(dict.fromkeys(keywords))  # deduplicate preserving order


def expand_query(
    query: str,
    question_type: QuestionType,
    max_expansions: int = 5,
) -> list[str]:
    """
    Generate expanded queries for retrieval.
    Always includes the original query first.
    """
    expanded: list[str] = [query]
    seen = {query}

    def _add(q: str) -> None:
        q = q.strip()
        if q and q not in seen and len(expanded) < max_expansions:
            expanded.append(q)
            seen.add(q)

    keywords = _extract_keywords(query)

    # 1. Type-based prefix expansions
    prefixes = _TYPE_PREFIXES.get(question_type, [])
    for prefix in prefixes:
        for kw in keywords[:2]:  # use top 2 keywords
            _add(f"{prefix} {kw}")

    # 2. Domain synonym expansions
    for kw in keywords:
        if kw in _EDUCATIONAL_EXPANSIONS:
            for expansion in _EDUCATIONAL_EXPANSIONS[kw]:
                _add(expansion)

    # 3. Keyword-only query (bare topic without question words)
    if keywords:
        bare = ' '.join(keywords[:3])
        _add(bare)

    return expanded[:max_expansions]
