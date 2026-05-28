import re


ARABIC_SENTENCE_ENDINGS = re.compile(r"[.؟!،\n]+")
MAX_CHUNK_CHARS = 500
MIN_CHUNK_CHARS = 50


def chunk_arabic_text(text: str, source_type_tag: str = "") -> list[dict]:
    text = text.strip()
    if not text:
        return []

    parts = ARABIC_SENTENCE_ENDINGS.split(text)
    parts = [p.strip() for p in parts if p.strip()]

    chunks = []
    current = ""

    for part in parts:
        if len(current) + len(part) + 1 <= MAX_CHUNK_CHARS:
            current = f"{current} {part}".strip() if current else part
        else:
            if len(current) >= MIN_CHUNK_CHARS:
                chunks.append(current)
            current = part

    if len(current) >= MIN_CHUNK_CHARS:
        chunks.append(current)
    elif chunks:
        chunks[-1] = f"{chunks[-1]} {current}".strip()

    return [
        {
            "content_text": chunk,
            "chunk_index": i,
            "char_count": len(chunk),
            "source_type_tag": source_type_tag,
        }
        for i, chunk in enumerate(chunks)
    ]
