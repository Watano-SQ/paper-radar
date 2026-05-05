from __future__ import annotations

import hashlib
import re
import unicodedata


_DOI_URL_RE = re.compile(r"^(?:https?://(?:dx\.)?doi\.org/|doi:\s*)", re.IGNORECASE)
_ARXIV_URL_RE = re.compile(r"^https?://arxiv\.org/(?:abs|pdf)/", re.IGNORECASE)
_ARXIV_VERSION_RE = re.compile(r"v\d+$", re.IGNORECASE)
_TITLE_PUNCT_RE = re.compile(r"[^\w\s]", re.UNICODE)
_WHITESPACE_RE = re.compile(r"\s+")


def normalize_doi(value: str | None) -> str | None:
    if not value:
        return None
    doi = value.strip()
    doi = _DOI_URL_RE.sub("", doi)
    doi = doi.strip().rstrip(".,;")
    doi = doi.lower()
    return doi or None


def normalize_arxiv_id(value: str | None) -> str | None:
    if not value:
        return None
    arxiv_id = value.strip()
    arxiv_id = _ARXIV_URL_RE.sub("", arxiv_id)
    arxiv_id = arxiv_id.removesuffix(".pdf")
    if arxiv_id.lower().startswith("arxiv:"):
        arxiv_id = arxiv_id[6:]
    arxiv_id = arxiv_id.split("?")[0].split("#")[0]
    arxiv_id = _ARXIV_VERSION_RE.sub("", arxiv_id)
    return arxiv_id.strip() or None


def normalize_title(value: str | None) -> str:
    if not value:
        return ""
    normalized = unicodedata.normalize("NFKC", value)
    normalized = normalized.casefold()
    normalized = _TITLE_PUNCT_RE.sub(" ", normalized)
    normalized = _WHITESPACE_RE.sub(" ", normalized).strip()
    return normalized


def title_author_year_hash(
    title: str | None,
    first_author: str | None = None,
    year: int | str | None = None,
) -> str:
    title_part = normalize_title(title)
    author_part = normalize_title(first_author)
    year_part = "" if year is None else str(year)
    payload = "|".join([title_part, author_part, year_part])
    return hashlib.sha1(payload.encode("utf-8")).hexdigest()[:16]


def make_canonical_id(
    *,
    doi: str | None = None,
    arxiv_id: str | None = None,
    pmid: str | None = None,
    openalex_id: str | None = None,
    semantic_scholar_id: str | None = None,
    title: str | None = None,
    first_author: str | None = None,
    year: int | str | None = None,
) -> str:
    normalized_doi = normalize_doi(doi)
    if normalized_doi:
        return f"doi:{normalized_doi}"

    normalized_arxiv_id = normalize_arxiv_id(arxiv_id)
    if normalized_arxiv_id:
        return f"arxiv:{normalized_arxiv_id}"

    if pmid:
        return f"pmid:{str(pmid).strip()}"

    if openalex_id:
        return f"openalex:{str(openalex_id).rstrip('/').split('/')[-1]}"

    if semantic_scholar_id:
        return f"s2:{str(semantic_scholar_id).strip()}"

    return f"titlehash:{title_author_year_hash(title, first_author, year)}"
