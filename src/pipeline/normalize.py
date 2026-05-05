from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from src.models.paper import PaperItem
from src.utils.ids import make_canonical_id, normalize_arxiv_id, normalize_doi
from src.utils.text import first_author


def restore_openalex_abstract(
    abstract_inverted_index: Mapping[str, list[int]] | None,
) -> str | None:
    """Restore OpenAlex abstract text from an inverted index."""

    if not abstract_inverted_index:
        return None
    positioned_words: list[tuple[int, str]] = []
    for word, positions in abstract_inverted_index.items():
        for position in positions:
            positioned_words.append((int(position), word))
    if not positioned_words:
        return None
    words = [word for _, word in sorted(positioned_words, key=lambda item: item[0])]
    return " ".join(words)


def finalize_paper_item(item: PaperItem) -> PaperItem:
    """Normalize external IDs and recompute canonical_id consistently."""

    doi = normalize_doi(item.doi)
    arxiv_id = normalize_arxiv_id(item.arxiv_id)
    canonical_id = make_canonical_id(
        doi=doi,
        arxiv_id=arxiv_id,
        pmid=item.pmid,
        openalex_id=item.openalex_id,
        semantic_scholar_id=item.semantic_scholar_id,
        title=item.title,
        first_author=first_author(item.authors),
        year=item.year,
    )
    return item.model_copy(
        update={
            "canonical_id": canonical_id,
            "doi": doi,
            "arxiv_id": arxiv_id,
        }
    )


def compact_list(values: list[Any] | None) -> list[str]:
    if not values:
        return []
    output: list[str] = []
    seen: set[str] = set()
    for value in values:
        text = str(value).strip()
        key = text.casefold()
        if text and key not in seen:
            output.append(text)
            seen.add(key)
    return output
