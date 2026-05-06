from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Protocol

try:
    from rapidfuzz import fuzz
except ImportError:  # pragma: no cover
    fuzz = None

from difflib import SequenceMatcher

from src.utils.ids import normalize_title


class PaperLike(Protocol):
    canonical_id: str
    title: str
    authors: list[str]
    year: int | None


@dataclass(slots=True)
class PossibleDuplicate:
    left_id: str
    right_id: str
    reason: str
    score: float


def detect_possible_duplicates(
    current_items: Iterable[PaperLike],
    candidate_items: Iterable[PaperLike],
    *,
    title_threshold: float = 0.95,
    author_threshold: float = 0.92,
) -> list[PossibleDuplicate]:
    matches: list[PossibleDuplicate] = []
    seen_pairs: set[tuple[str, str]] = set()
    candidates = list(candidate_items)
    for left in current_items:
        for right in candidates:
            if left.canonical_id == right.canonical_id:
                continue
            pair = tuple(sorted([left.canonical_id, right.canonical_id]))
            if pair in seen_pairs:
                continue
            if not _years_close(left.year, right.year):
                continue
            title_score = similarity(normalize_title(left.title), normalize_title(right.title))
            if title_score <= title_threshold:
                continue
            left_author = _first_author(left)
            right_author = _first_author(right)
            author_score = similarity(left_author, right_author)
            authors_match = bool(left_author and left_author == right_author) or author_score >= author_threshold
            if not authors_match:
                continue
            seen_pairs.add(pair)
            matches.append(
                PossibleDuplicate(
                    left_id=pair[0],
                    right_id=pair[1],
                    reason="title_similarity>0.95; first_author_similar; year_delta<=1",
                    score=min(title_score, author_score if author_score > 0 else 1.0),
                )
            )
    return matches


def similarity(left: str, right: str) -> float:
    if not left or not right:
        return 0.0
    if fuzz is not None:
        return fuzz.ratio(left, right) / 100.0
    return SequenceMatcher(None, left, right).ratio()


def _first_author(item: PaperLike) -> str:
    if not item.authors:
        return ""
    return normalize_title(item.authors[0])


def _years_close(left: int | None, right: int | None) -> bool:
    if left is None or right is None:
        return True
    return abs(left - right) <= 1
