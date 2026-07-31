"""Lightweight Hangul → Revised Romanization helpers for place-name matching."""

from __future__ import annotations

import re
import unicodedata

# Choseong / Jungseong / Jongseong tables (Unicode Hangul Syllables).
_CHO = [
    "g",
    "kk",
    "n",
    "d",
    "tt",
    "r",
    "m",
    "b",
    "pp",
    "s",
    "ss",
    "",
    "j",
    "jj",
    "ch",
    "k",
    "t",
    "p",
    "h",
]
_JUNG = [
    "a",
    "ae",
    "ya",
    "yae",
    "eo",
    "e",
    "yeo",
    "ye",
    "o",
    "wa",
    "wae",
    "oe",
    "yo",
    "u",
    "wo",
    "we",
    "wi",
    "yu",
    "eu",
    "ui",
    "i",
]
_JONG = [
    "",
    "k",
    "k",
    "k",
    "n",
    "n",
    "n",
    "t",
    "l",
    "l",
    "l",
    "l",
    "l",
    "l",
    "l",
    "l",
    "m",
    "p",
    "p",
    "t",
    "t",
    "ng",
    "t",
    "t",
    "k",
    "t",
    "p",
    "t",
]


def romanize_hangul(text: str) -> str:
    """Romanize Hangul syllables; leave Latin digits as-is; drop other symbols."""
    out: list[str] = []
    for ch in unicodedata.normalize("NFC", text):
        code = ord(ch)
        if 0xAC00 <= code <= 0xD7A3:
            s = code - 0xAC00
            cho = s // 588
            jung = (s % 588) // 28
            jong = s % 28
            out.append(_CHO[cho] + _JUNG[jung] + _JONG[jong])
        elif ch.isascii() and (ch.isalnum() or ch.isspace()):
            out.append(ch.lower())
        elif ch in {"-", "_", "'"}:
            out.append(" ")
        # else drop punctuation / CJK extras
    compact = re.sub(r"\s+", " ", "".join(out)).strip()
    return compact


def romanize_compact(text: str) -> str:
    """Alphanumeric-only romanization for substring / token compares."""
    return re.sub(r"[^a-z0-9]", "", romanize_hangul(text))
