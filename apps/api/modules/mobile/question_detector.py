"""
Arabic question detector.
Detects questions by:
1. Arabic question mark (؟)
2. Common Arabic question starters
3. Instruction/task starters used in Egyptian high school exams
"""
import re

QUESTION_STARTERS = (
    r'ما\s', r'ماذا', r'لماذا', r'كيف', r'متى', r'أين', r'اين',
    r'من\s', r'هل', r'اشرح', r'وضح', r'علل', r'استخرج', r'حدد',
    r'قارن', r'عرف', r'عدد', r'اذكر', r'بين', r'ما\s+هو', r'ما\s+هي',
)

_STARTER_PATTERN = re.compile(
    r'(?:^|\n|[.،])[\s]*(' + '|'.join(QUESTION_STARTERS) + r')',
    re.UNICODE | re.MULTILINE,
)

_QUESTION_MARK_SPLIT = re.compile(r'[؟?]')


def detect_questions(text: str) -> list[str]:
    """
    Return a list of detected questions from the text.
    If no questions are found, returns the full text as a single item
    so the caller can still attempt a retrieval.
    """
    text = text.strip()
    if not text:
        return []

    # Try splitting on Arabic question mark first
    by_qmark = [s.strip() for s in _QUESTION_MARK_SPLIT.split(text) if s.strip()]
    if len(by_qmark) > 1:
        # Re-attach question mark to each fragment except last if it was split
        questions = []
        parts = _QUESTION_MARK_SPLIT.split(text)
        marks = _QUESTION_MARK_SPLIT.findall(text)
        for i, part in enumerate(parts):
            part = part.strip()
            if not part:
                continue
            mark = marks[i] if i < len(marks) else ''
            questions.append(part + mark)
        return questions

    # Try detecting by question starters
    sentences = re.split(r'[.،\n]', text)
    detected = []
    for sentence in sentences:
        sentence = sentence.strip()
        if not sentence:
            continue
        if _STARTER_PATTERN.search(' ' + sentence):
            detected.append(sentence)

    if detected:
        return detected

    # Fallback: treat whole text as one question context
    return [text]
