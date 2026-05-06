from __future__ import annotations

import os
from pathlib import Path
from typing import Any
from urllib.parse import quote

import requests

from src.models.paper import PaperItem
from src.pipeline.normalize import compact_list, finalize_paper_item
from src.pipeline.rate_limit import RateLimiter
from src.sources.base import JsonSourceClient, RawItem, SourceQuery, fetched_now
from src.utils.http import build_user_agent, request_json
from src.utils.ids import normalize_arxiv_id, normalize_doi
from src.utils.text import clean_text


class SemanticScholarClient(JsonSourceClient):
    name = "semantic_scholar"
    base_url = "https://api.semanticscholar.org/graph/v1/paper"
    fields = ",".join(
        [
            "paperId",
            "title",
            "abstract",
            "year",
            "venue",
            "authors",
            "citationCount",
            "influentialCitationCount",
            "fieldsOfStudy",
            "s2FieldsOfStudy",
            "externalIds",
            "url",
            "openAccessPdf",
        ]
    )

    def __init__(self, config: dict[str, Any], raw_dir: Path, session: requests.Session | None = None):
        super().__init__(config, raw_dir, session)
        self.api_key = os.getenv(config.get("api_key_env", "S2_API_KEY"), "")
        configured_delay = float(config.get("delay_seconds", 1))
        self.rate_limiter = RateLimiter(configured_delay if self.api_key else max(configured_delay, 3.0))

    def fetch_by_doi(self, doi: str) -> RawItem | None:
        normalized_doi = normalize_doi(doi)
        if not normalized_doi:
            return None
        return self._fetch_identifier(f"DOI:{normalized_doi}", "doi", normalized_doi)

    def fetch_by_arxiv_id(self, arxiv_id: str) -> RawItem | None:
        normalized_arxiv_id = normalize_arxiv_id(arxiv_id)
        if not normalized_arxiv_id:
            return None
        return self._fetch_identifier(f"ARXIV:{normalized_arxiv_id}", "arxiv", normalized_arxiv_id)

    def enrich_item(self, item: PaperItem) -> PaperItem | None:
        raw: RawItem | None = None
        if item.doi:
            raw = self.fetch_by_doi(item.doi)
        elif item.arxiv_id:
            raw = self.fetch_by_arxiv_id(item.arxiv_id)
        if raw is None:
            return None
        return self.normalize(raw, base_item=item)

    def fetch(self, query: SourceQuery) -> list[RawItem]:
        if query.query_type == "doi":
            raw = self.fetch_by_doi(query.query)
        elif query.query_type == "arxiv":
            raw = self.fetch_by_arxiv_id(query.query)
        else:
            raw = None
        return [raw] if raw else []

    def normalize(self, raw: RawItem, base_item: PaperItem | None = None) -> PaperItem:
        data = raw.data
        external_ids = data.get("externalIds") or {}
        doi = normalize_doi(external_ids.get("DOI")) or (base_item.doi if base_item else None)
        arxiv_id = normalize_arxiv_id(external_ids.get("ArXiv")) or (base_item.arxiv_id if base_item else None)
        fields = compact_list(
            [
                *(data.get("fieldsOfStudy") or []),
                *[
                    field.get("category")
                    for field in data.get("s2FieldsOfStudy") or []
                    if field.get("category")
                ],
                *(base_item.fields if base_item else []),
            ]
        )
        open_access_pdf = data.get("openAccessPdf") or {}
        authors = [
            author.get("name")
            for author in data.get("authors") or []
            if author.get("name")
        ] or (base_item.authors if base_item else [])
        item = PaperItem(
            canonical_id=base_item.canonical_id if base_item else "pending",
            source=self.name,
            source_id=data.get("paperId"),
            doi=doi,
            arxiv_id=arxiv_id,
            pmid=external_ids.get("PubMed") or (base_item.pmid if base_item else None),
            openalex_id=base_item.openalex_id if base_item else None,
            semantic_scholar_id=data.get("paperId") or (base_item.semantic_scholar_id if base_item else None),
            title=clean_text(data.get("title")) or (base_item.title if base_item else "Untitled"),
            abstract=clean_text(data.get("abstract")) or (base_item.abstract if base_item else None),
            authors=authors,
            year=data.get("year") or (base_item.year if base_item else None),
            published_date=base_item.published_date if base_item else None,
            updated_date=None,
            venue=data.get("venue") or (base_item.venue if base_item else None),
            work_type=base_item.work_type if base_item else None,
            fields=fields,
            keywords=base_item.keywords if base_item else [],
            url=data.get("url") or (base_item.url if base_item else None),
            pdf_url=open_access_pdf.get("url") or (base_item.pdf_url if base_item else None),
            oa_url=open_access_pdf.get("url") or (base_item.oa_url if base_item else None),
            citation_count=data.get("citationCount") if data.get("citationCount") is not None else (base_item.citation_count if base_item else None),
            influential_citation_count=data.get("influentialCitationCount")
            if data.get("influentialCitationCount") is not None
            else (base_item.influential_citation_count if base_item else None),
            is_open_access=base_item.is_open_access if base_item else None,
            license=base_item.license if base_item else None,
            source_query=raw.query.label,
            fetched_at=raw.fetched_at,
            raw_path=raw.raw_path,
        )
        finalized = finalize_paper_item(item)
        if base_item:
            return finalized.model_copy(update={"canonical_id": base_item.canonical_id})
        return finalized

    def _fetch_identifier(self, identifier: str, query_type: str, query_value: str) -> RawItem:
        self.rate_limiter.wait()
        query = SourceQuery(lane="enrichment", query=query_value, query_type=query_type, limit=1)
        headers = {"User-Agent": build_user_agent()}
        if self.api_key:
            headers["x-api-key"] = self.api_key
        response = request_json(
            self.session,
            "GET",
            f"{self.base_url}/{quote(identifier, safe='')}",
            params={"fields": self.fields},
            headers=headers,
        )
        raw_path = self.save_raw(response, self.name, query, page=1)
        return RawItem(
            source=self.name,
            source_id=response.get("paperId"),
            query=query,
            data=response,
            raw_path=raw_path,
            fetched_at=fetched_now(),
        )
