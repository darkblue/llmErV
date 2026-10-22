"""Explicit radio-digit decoding profile; candidates never replace ASR facts."""

import re
from .base import ASRError

READINGS = {
    "0": "洞",
    "1": "幺",
    "2": "两",
    "3": "三",
    "4": "四",
    "5": "五",
    "6": "六",
    "7": "拐",
    "8": "八",
    "9": "九",
}
# Acoustic lexicons may omit 幺. Same-pronunciation lexical bridges are only
# allowed inside the operator-selected, constrained digit decoder.
ALIASES = {
    "0": ("洞", "栋"),
    "1": ("幺", "腰", "邀"),
    "2": ("两",),
    "3": ("三",),
    "4": ("四",),
    "5": ("五",),
    "6": ("六",),
    "7": ("拐",),
    "8": ("八",),
    "9": ("九",),
}
SOURCE = {
    "standard": "MH/T 4014-2003",
    "clause": "3.4.1.1 表1",
    "pdf_page": 12,
    "url": "https://www.caac.gov.cn/XXGK/XXGK/BZGF/HYBZ/201511/P020170804579259214829.pdf",
    "currency": "current_validity_not_verified",
}


def profile():
    return {
        "id": "caac_radio_digits",
        "readings": READINGS,
        "source": SOURCE,
        "mechanism": "constrained_grammar_not_hotword_boosting",
        "requires_audio_review": True,
        "scope": "digit_only_short_utterances",
        "acoustic_aliases": ALIASES,
    }


def vocabulary(model):
    supported = {
        digit: [word for word in words if model.vosk_model_find_word(word) >= 0]
        for digit, words in ALIASES.items()
    }
    if any(not supported[digit] for digit in READINGS):
        raise ASRError("RADIO_DIGIT_VOCABULARY_UNSUPPORTED")
    return [word for words in supported.values() for word in words] + ["[unk]"]


def candidate(text, constrained=False):
    """Only a whole digit utterance. No broad homophone replacement in prose."""
    compact = re.sub(r"\s+", "", text)
    mapping = {word: digit for digit, word in READINGS.items()}
    if constrained:
        mapping.update(
            {word: digit for digit, words in ALIASES.items() for word in words}
        )
    if not 1 <= len(compact) <= 32 or any(char not in mapping for char in compact):
        return None
    # Normal language: one 两 or 九 is ambiguous and not a number sequence.
    if not constrained and (
        len(compact) < 2 or not any(c in compact for c in "幺拐洞")
    ):
        return None
    digits = "".join(mapping[char] for char in compact)
    return {
        "digits": digits,
        "readings": "".join(READINGS[d] for d in digits),
        "recognized_text": text,
        "verification": "unverified",
        "requires_audio_review": True,
        "mechanism": "constrained_grammar"
        if constrained
        else "literal_reading_mapping",
        "source": SOURCE,
    }
