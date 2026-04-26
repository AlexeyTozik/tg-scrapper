# ruff: noqa: RUF001

import re
from collections.abc import Mapping

from .app_support import get_optional_int, get_optional_str

ALNUM_RE = re.compile(r"\w", flags=re.UNICODE)
VERSION_RE = re.compile(r"(?i)\bv?\d+(?:[._-]\d+){1,}\b")
MIXED_ALNUM_RE = re.compile(r"(?=.*[A-Za-zА-Яа-я])(?=.*\d)", flags=re.UNICODE)
TECH_TOKEN_WITH_SYMBOL_RE = re.compile(r"(?i)[A-Za-z0-9][A-Za-z0-9+_.-]*[=/:][A-Za-z0-9._/-]+")
LATIN_TOKEN_RE = re.compile(r"^[A-Za-z][A-Za-z0-9+_.-]{2,}$")
STOPLIST_NORMALIZE_RE = re.compile(r"[^0-9A-Za-zА-Яа-я]+", flags=re.UNICODE)

SHORT_CHAT_STOPLIST = {
    "ага",
    "да",
    "нет",
    "угу",
    "ок",
    "окей",
    "ок спс",
    "спасибо",
    "спс",
    "ясно",
    "понял",
    "понятно",
    "принял",
    "норм",
    "окей спасибо",
    "thanks",
    "thx",
    "ok",
    "okay",
    "yes",
    "no",
}


def extract_message_text(row: Mapping[str, object]) -> str | None:
    for key in ("text", "raw_text"):
        value = get_optional_str(row, key)
        if value is not None:
            cleaned = value.strip()
            if cleaned:
                return cleaned
    return None


def normalize_short_chat_text(text: str) -> str:
    lowered = text.casefold().replace("ё", "е")
    cleaned = STOPLIST_NORMALIZE_RE.sub(" ", lowered)
    return " ".join(cleaned.split())


def is_short_chat_noise(text: str) -> bool:
    return normalize_short_chat_text(text) in SHORT_CHAT_STOPLIST


def has_technical_signal(text: str) -> bool:
    stripped = text.strip()

    if VERSION_RE.search(stripped):
        return True

    if MIXED_ALNUM_RE.search(stripped):
        return True

    if TECH_TOKEN_WITH_SYMBOL_RE.search(stripped):
        return True

    return " " not in stripped and LATIN_TOKEN_RE.fullmatch(stripped) is not None


def should_keep_message(row: Mapping[str, object], *, min_chars: int) -> bool:
    if get_optional_str(row, "action_type") is not None:
        return False

    text = extract_message_text(row)
    if text is None:
        return False

    if not ALNUM_RE.search(text):
        return False

    if is_short_chat_noise(text):
        return False

    if len(text) >= min_chars:
        return True

    if get_optional_int(row, "reply_to_msg_id") is not None:
        return True

    return has_technical_signal(text)


def get_filtered_message_text(row: Mapping[str, object], *, min_chars: int) -> str | None:
    text = extract_message_text(row)
    if text is None:
        return None

    if not should_keep_message(row, min_chars=min_chars):
        return None

    return text
