from __future__ import annotations

import html
import re


_WHITESPACE_RE = re.compile(r"\s+")
_TAG_RE = re.compile(r"<[^>]+>")


def clean_text(value: str | None) -> str | None:
    if value is None:
        return None
    unescaped = html.unescape(value)
    without_tags = _TAG_RE.sub(" ", unescaped)
    cleaned = _WHITESPACE_RE.sub(" ", without_tags).strip()
    return cleaned or None


def first_author(authors: list[str] | None) -> str:
    if not authors:
        return ""
    return clean_text(authors[0]) or ""
