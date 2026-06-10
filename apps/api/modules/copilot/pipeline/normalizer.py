"""
Arabic query normalizer.
Handles diacritics, alef variants, yeh/alif maqsura, spacing, and
simple colloquial-to-formal rewrites for Egyptian Arabic educational queries.
"""
import re
import unicodedata
from dataclasses import dataclass

# Colloquial → formal rewrite patterns (Egyptian Arabic educational)
_COLLOQUIAL_PATTERNS: list[tuple[re.Pattern, str]] = [
    # "يعني ايه" → "ما معنى"
    (re.compile(r'يعني\s+ايه\s+', re.UNICODE), 'ما معنى '),
    (re.compile(r'يعني\s+إيه\s+', re.UNICODE), 'ما معنى '),
    # "ايه ده" / "إيه ده" → "ما هذا"
    (re.compile(r'ايه\s+ده', re.UNICODE), 'ما هذا'),
    (re.compile(r'إيه\s+ده', re.UNICODE), 'ما هذا'),
    # "ايه هو" → "ما هو"
    (re.compile(r'(?:ا|إ)يه\s+هو', re.UNICODE), 'ما هو'),
    # "عايز افهم" → "أريد أن أفهم"
    (re.compile(r'عايز\s+افهم', re.UNICODE), 'أريد أن أفهم'),
    (re.compile(r'عايزة\s+افهم', re.UNICODE), 'أريد أن أفهم'),
    # "ازاي" / "إزاي" → "كيف"
    (re.compile(r'(?:ا|إ)زاي', re.UNICODE), 'كيف'),
    # "ليه" → "لماذا"
    (re.compile(r'\bليه\b', re.UNICODE), 'لماذا'),
    # "فين" → "أين"
    (re.compile(r'\bفين\b', re.UNICODE), 'أين'),
    # "امتى" → "متى"
    (re.compile(r'\bامتى\b', re.UNICODE), 'متى'),
    # "مين" → "من"
    (re.compile(r'\bمين\b', re.UNICODE), 'من'),
    # "انهي" → "أي"
    (re.compile(r'\bانهي\b', re.UNICODE), 'أي'),
    # Remove filler "يعني" at sentence start/middle
    (re.compile(r'\bيعني\b', re.UNICODE), ''),
]

_DIACRITICS = re.compile(r'[\u064B-\u065F\u0670]')
_ALEF_VARIANTS = re.compile(r'[إأآ]')
_ALIF_MAQSURA = re.compile(r'ى(?=\s|$)')  # only at word end
_WHITESPACE = re.compile(r'\s+')


@dataclass
class NormalizedQuery:
    original_query: str
    normalized_query: str

    def __str__(self) -> str:
        return self.normalized_query


def normalize_arabic_query(query: str) -> NormalizedQuery:
    """
    Normalize an Arabic educational query.
    Returns both original and normalized forms.
    """
    original = query.strip()
    text = original

    # Apply colloquial rewrites first
    for pattern, replacement in _COLLOQUIAL_PATTERNS:
        text = pattern.sub(replacement, text)

    # Remove diacritics
    text = _DIACRITICS.sub('', text)

    # Normalize alef variants
    text = _ALEF_VARIANTS.sub('ا', text)

    # Normalize alif maqsura at word end → yeh
    text = _ALIF_MAQSURA.sub('ي', text)

    # Clean up whitespace
    text = _WHITESPACE.sub(' ', text).strip()

    # Unicode NFC normalization
    text = unicodedata.normalize('NFC', text)

    return NormalizedQuery(original_query=original, normalized_query=text)
