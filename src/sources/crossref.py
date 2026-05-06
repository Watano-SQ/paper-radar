from __future__ import annotations

import os
from pathlib import Path
from typing import Any
from urllib.parse import quote

import requests

from src.models.paper import PaperItem
from src.pipeline.normalize import finalize_paper_item
from src.pipeline.rate_limit import RateLimiter
from src.sources.base import JsonSourceClient, RawItem, SourceQuery, fetched_now
from src.utils.dates import to_iso_date, year_from_date
from src.utils.http import build_user_agent, request_json
from src.utils.ids import normalize_doi
from src.utils.text import clean_text


class CrossrefClient(JsonSourceClient):
    name = "crossref"
    base_url = "https://api.crossref.org/works"

    def __init__(self, config: dict[str, Any], raw_dir: Path, session: requests.Session | None = None):
        super().__init__(config, raw_dir, session)
        self.contact_email = os.getenv(config.get("email_env", "CONTACT_EMAIL"), "")
        self.rate_limiter = RateLimiter(float(config.get("delay_seconds", 1)))

    def fetch_by_doi(self, doi: str) -> RawItem | None:
        normalized_doi = normalize_doi(doi)
        if not normalized_doi:
            return None
        self.rate_limiter.wait()
        query = SourceQuery(lane="enrichment", query=normalized_doi, query_type="doi", limit=1)
        params = {"mailto": self.contact_email} if self.contact_email else None
        response = request_json(
            self.session,
            "GET",
            f"{self.base_url}/{quote(normalized_doi, safe='')}",
            params=params,
            headers={"User-Agent": build_user_agent(self.contact_email)},
        )
        raw_path = self.save_raw(response, self.name, query, page=1)
        message = response.get("message") or {}
        return RawItem(
            source=self.name,
            source_id=normalized_doi,
            query=query,
            data=message,
            raw_path=raw_path,
            fetched_at=fetched_now(),
        )

    def enrich_item(self, item: PaperItem) -> PaperItem | None:
        if not item.doi:
            return None
        raw = self.fetch_by_doi(item.doi)
        if raw is None:
            return None
        return self.normalize(raw, base_item=item)

    def fetch(self, query: SourceQuery) -> list[RawItem]:
        raw = self.fetch_by_doi(query.query)
        return [raw] if raw else []

    def normalize(self, raw: RawItem, base_item: PaperItem | None = None) -> PaperItem:
        data = raw.data
        title = clean_text(_first(data.get("title"))) or (base_item.title if base_item else "Untitled")
        published_date = _published_date(data)
        authors = _authors(data.get("author", [])) or (base_item.authors if base_item else [])
        doi = normalize_doi(data.get("DOI")) or (base_item.doi if base_item else None)
        license_value = _license_value(data.get("license", []))
        venue = clean_text(_first(data.get("container-title"))) or data.get("publisher")
        item = PaperItem(
            canonical_id=base_item.canonical_id if base_item else "pending",
            source=self.name,
            source_id=doi,
            doi=doi,
            arxiv_id=base_item.arxiv_id if base_item else None,
            pmid=base_item.pmid if base_item else None,
            openalex_id=base_item.openalex_id if base_item else None,
            semantic_scholar_id=base_item.semantic_scholar_id if base_item else None,
            title=title,
            abstract=clean_text(data.get("abstract")) or (base_item.abstract if base_item else None),
            authors=authors,
            year=year_from_date(published_date) or data.get("published_year") or (base_item.year if base_item else None),
            published_date=published_date or (base_item.published_date if base_item else None),
            updated_date=to_iso_date((data.get("created") or {}).get("date-time")),
            venue=venue,
            work_type=data.get("type"),
            fields=base_item.fields if base_item else [],
            keywords=base_item.keywords if base_item else [],
            url=data.get("URL") or (base_item.url if base_item else None),
            pdf_url=base_item.pdf_url if base_item else None,
            oa_url=base_item.oa_url if base_item else None,
            citation_count=base_item.citation_count if base_item else None,
            influential_citation_count=base_item.influential_citation_count if base_item else None,
            is_open_access=base_item.is_open_access if base_item else None,
            license=license_value,
            source_query=raw.query.label,
            fetched_at=raw.fetched_at,
            raw_path=raw.raw_path,
        )
        finalized = finalize_paper_item(item)
        if base_item:
            return finalized.model_copy(update={"canonical_id": base_item.canonical_id})
        return finalized


def _first(value: list[Any] | Any) -> Any:
    if isinstance(value, list):
        return value[0] if value else None
    return value


def _published_date(data: dict[str, Any]) -> str | None:
    for key in ("published-print", "published-online", "published", "issued"):
        date_value = to_iso_date(data.get(key))
        if date_value:
            return date_value
    return None


def _authors(values: list[dict[str, Any]]) -> list[str]:
    authors: list[str] = []
    for author in values:
        given = author.get("given")
        family = author.get("family")
        name = author.get("name")
        if given or family:
            authors.append(" ".join(part for part in [given, family] if part))
        elif name:
            authors.append(str(name))
    return authors


def _license_value(values: list[dict[str, Any]]) -> str | None:
    if not values:
        return None
    first = values[0]
    return first.get("URL") or first.get("content-version")
