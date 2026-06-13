"""
Arabic question detector — two-stage approach:
1. Fast rule-based detection for simple cases (single question, no passage)
2. GPT-4o context-aware extraction when passage + questions are mixed

The AI stage understands:
- Reading passages vs questions that follow them
- Inline rhetorical questions inside a passage (not student questions)
- Exam question formats: numbered, after passage, explicit instruction words
- Multiple questions in one image
"""
import logging
import re

logger = logging.getLogger(__name__)

_QUESTION_MARK = re.compile(r'[؟?]')
_INSTRUCTION_STARTERS = re.compile(
    r'^(?:اشرح|وضح|علل|استخرج|حدد|قارن|اكتب|اذكر|عدد|لخص|حلل|استنتج|بيّن|ما|ماذا|لماذا|كيف|متى|أين|من|هل)\s',
    re.MULTILINE | re.UNICODE,
)

# GPT-4o system prompt for question extraction
_EXTRACTION_SYSTEM_PROMPT = (
    "أنت مساعد تعليمي متخصص في تحليل أسئلة الامتحانات العربية.\n\n"
    "مهمتك: تحديد السؤال أو الأسئلة الحقيقية التي يجب على الطالب "
    "الإجابة عنها من النص.\n\n"
    "قواعد مهمة:\n"
    "1. النص قد يحتوي على فقرة قراءة طويلة يليها سؤال — "
    "الفقرة هي السياق وليست سؤالاً\n"
    "2. علامة الاستفهام (؟) داخل الفقرة القرائية ليست سؤالاً للطالب\n"
    "3. الأسئلة الحقيقية تأتي بعد النص أو تبدأ بكلمات مثل: "
    "اشرح / وضح / علل / استخرج / حدد / قارن / ما / ماذا / لماذا / كيف\n"
    "4. أعد السؤال فقط — لا تُعيد الفقرة القرائية\n"
    "5. إذا لم يكن هناك فقرة قراءة وكان النص سؤالاً مباشراً، أعده كما هو\n\n"
    "أعد ردك بالتنسيق التالي فقط:\n"
    "QUESTIONS:\n"
    "- السؤال الأول\n"
    "- السؤال الثاني (إن وجد)\n\n"
    "إذا لم تجد أسئلة واضحة، أعد:\n"
    "NO_QUESTIONS"
)

_EXTRACTION_USER_PROMPT = (
    "النص المستخرج من الصورة:\n\n{text}\n\n"
    "حدد السؤال أو الأسئلة الحقيقية التي يجب على الطالب الإجابة عنها."
)


def _is_simple_text(text: str) -> bool:
    """
    Check if text is simple enough for rule-based detection.
    Simple = short text with no long reading passage.
    """
    text = text.strip()
    # Long text → likely contains a passage, use AI
    if len(text) > 300:
        return False
    lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
    # Single short question
    if len(lines) == 1 and _QUESTION_MARK.search(text):
        return True
    # Few short lines — likely just questions, no passage
    if all(len(ln) < 150 for ln in lines) and len(lines) <= 3:
        return True
    return False


def _rule_based_detect(text: str) -> list[str]:
    """Fast rule-based detection for simple cases."""
    text = text.strip()
    if not text:
        return []

    # Split on Arabic question mark
    by_qmark = _QUESTION_MARK.split(text)
    marks = _QUESTION_MARK.findall(text)

    if len(marks) >= 1:
        questions = []
        for i, part in enumerate(by_qmark):
            part = part.strip()
            if not part:
                continue
            mark = marks[i] if i < len(marks) else ''
            questions.append(part + mark)
        return [q for q in questions if q.strip()]

    # No question mark — check for instruction starters
    lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
    detected = [ln for ln in lines if _INSTRUCTION_STARTERS.match(ln)]
    return detected if detected else [text]


async def detect_questions_with_ai(
    text: str,
    api_key: str,
) -> list[str]:
    """
    Use GPT-4o to understand the full context and extract only the real questions.
    """
    try:
        import openai
        client = openai.AsyncOpenAI(api_key=api_key)
        response = await client.chat.completions.create(
            model="gpt-4o",
            max_tokens=500,
            temperature=0.0,
            messages=[
                {"role": "system", "content": _EXTRACTION_SYSTEM_PROMPT},
                {"role": "user", "content": _EXTRACTION_USER_PROMPT.format(text=text)},
            ],
        )
        result = (response.choices[0].message.content or "").strip()
        logger.info("AI question extraction result: %s", result[:200])

        if result == "NO_QUESTIONS" or "NO_QUESTIONS" in result:
            return []

        if "QUESTIONS:" in result:
            lines = result.split("QUESTIONS:")[1].strip().splitlines()
            questions = []
            for line in lines:
                line = line.strip().lstrip("- ").strip()
                if line:
                    questions.append(line)
            return questions

        # Fallback: return as single question
        return [result]

    except Exception as e:
        logger.error("AI question detection failed: %s", e)
        return []


async def detect_questions(text: str, api_key: str | None = None) -> list[str]:
    """
    Main entry point.
    Uses rule-based for simple text, AI for complex passages.
    """
    text = text.strip()
    if not text:
        return []

    # Simple text → fast rule-based
    if _is_simple_text(text):
        logger.info("question_detector: using rule-based detection")
        return _rule_based_detect(text)

    # Complex text with passage → AI extraction
    if api_key:
        logger.info("question_detector: using AI context-aware detection")
        questions = await detect_questions_with_ai(text, api_key)
        if questions:
            return questions
        # AI found nothing — fallback to rule-based
        logger.warning("question_detector: AI found no questions, falling back to rule-based")

    return _rule_based_detect(text)
