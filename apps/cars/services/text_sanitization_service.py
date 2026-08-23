import re
from functools import lru_cache
from pathlib import Path

MAX_DESCRIPTION_LENGTH = 2000

_TAG_RE = re.compile(r'<[^>\n]{0,500}>')
_CONTROL_RE = re.compile(r'[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]')
_URL_RE = re.compile(r'(?:https?://|www\.)\S{0,300}', re.IGNORECASE)
_WHITESPACE_RE = re.compile(r'[ \t\u00a0\u200f\u200e]{2,}')
_NEWLINE_RE = re.compile(r'\n{3,}')
_REPEATED_CHAR_RE = re.compile(r'(.)\1{4,}')

PROFANITY_FILE = Path(__file__).resolve().parent / 'profanity_words.txt'


@lru_cache(maxsize=1)
def _load_profanity_words():
    if not PROFANITY_FILE.exists():
        return frozenset()
    words = set()
    for line in PROFANITY_FILE.read_text(encoding='utf-8').splitlines():
        word = line.strip().lower()
        if word and not word.startswith('#'):
            words.add(word)
    return frozenset(words)


def _mask_profanity(text: str) -> str:
    words = _load_profanity_words()
    if not words:
        return text

    pattern = re.compile(
        r'(^|[\s.,!?;:()\[\]"\'])(' + '|'.join(re.escape(w) for w in sorted(words)) + r')(?=[\s.,!?;:()\[\]"\']|$)',
        re.IGNORECASE | re.UNICODE,
    )
    return pattern.sub(lambda m: m.group(1) + '*' * len(m.group(2)), text)


def sanitize_description(text: str) -> dict:
    """Clean a free-text car description (Data Sanitization & NLP requirement).

    Strips HTML/scripts, control characters, URLs, excessive punctuation and
    repeated characters, masks profanity (EN/AR), normalizes whitespace.
    Returns {'text': cleaned, 'was_sanitized': bool}.
    """
    original = text or ''
    cleaned = original

    cleaned = _TAG_RE.sub(' ', cleaned)
    cleaned = _CONTROL_RE.sub('', cleaned)
    cleaned = _URL_RE.sub('[link removed]', cleaned)
    cleaned = _REPEATED_CHAR_RE.sub(r'\1\1\1', cleaned)
    cleaned = _mask_profanity(cleaned)

    lines = [_WHITESPACE_RE.sub(' ', line).strip() for line in cleaned.splitlines()]
    cleaned = '\n'.join(line for line in lines if line)
    cleaned = _NEWLINE_RE.sub('\n\n', cleaned).strip()

    if len(cleaned) > MAX_DESCRIPTION_LENGTH:
        cleaned = cleaned[:MAX_DESCRIPTION_LENGTH].rstrip()

    return {'text': cleaned, 'was_sanitized': cleaned != original}
