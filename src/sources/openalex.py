from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import requests

from src.models.paper import PaperItem
from src.pipeline.normalize import finalize_paper_item, restore_openalex_abstract
from src.sources.base import JsonSourceClient, RawItem, SourceQuery, fetched_now
from src.utils.dates import days_ago_iso, to_iso_date, year_from_date
from src.utils.http import build_user_agent, request_json
from src.utils.ids import normalize_doi
from src.utils.text import clean_text


class OpenAlexClient(JsonSourceClient):
    name = "openalex"
    base_url = "https://api.openalex.org/works"

    def __init__(self, config: dict[str, Any], raw_dir: Path, session: requests.Session | None = None):
        super().__init__(config, raw_dir, session)
        self.contact_email = os.getenv(config.get("email_env", "CONTACT_EMAIL"), "")
        self.api_key = os.getenv(config.get("api_key_env", "OPENALEX_API_KEY"), "")

    def fetch(self, query: SourceQuery) -> list[RawItem]:
        limit = int(query.limit or self.config.get("per_query_limit", 10))
        per_page = min(200, int(self.config.get("per_query_limit", limit)), limit)
        from_date = days_ago_iso(int(query.days_back or self.config.get("days_back", 14)))
        page = 1
        items: list[RawItem] = []
        while len(items) < limit:
            params: dict[str, Any] = {
                "search": query.query,
                "filter": f"from_publication_date:{from_date}",
                "per-page": min(per_page, limit - len(items)),
                "page": page,
            }
            if self.contact_email:
                params["mailto"] = self.contact_email
            if self.api_key:
                params["api_key"] = self.api_key
            response = request_json(
                self.session,
                "GET",
                self.base_url,
                params=params,
                headers={"User-Agent": build_user_agent(self.contact_email)},
            )
            raw_path = self.save_raw(response, self.name, query, page=page)
            fetched_at = fetched_now()
            results = response.get("results", [])
            for result in results:
                items.append(
                    RawItem(
                        source=self.name,
                        source_id=result.get("id"),
                        query=query,
                        data=result,
                        raw_path=raw_path,
                        fetched_at=fetched_at,
                    )
                )
                if len(items) >= limit:
                    break
            if not results or len(results) < per_page:
                break
            page += 1
        return items

    def normalize(self, raw: RawItem) -> PaperItem:
        data = raw.data
        primary_location = data.get("primary_location") or {}
        open_access = data.get("open_access") or {}
        source = primary_location.get("source") or {}
        authors = [
            author_name
            for author_name in (
                ((authorship.get("author") or {}).get("display_name"))
                for authorship in data.get("authorships", [])
            )
            if author_name
        ]
        published_date = to_iso_date(data.get("publication_date"))
        if not published_date and data.get("publication_year"):
            published_date = f"{data['publication_year']}-01-01"
        fields = [
            concept.get("display_name")
            for concept in data.get("concepts", [])
            if concept.get("display_name")
        ]
        keywords = [
            keyword.get("display_name") or keyword.get("keyword")
            for keyword in data.get("keywords", [])
            if keyword.get("display_name") or keyword.get("keyword")
        ]
        item = PaperItem(
            canonical_id="pending",
            source=self.name,
            source_id=data.get("id"),
            doi=normalize_doi(data.get("doi")),
            arxiv_id=None,
            pmid=None,
            openalex_id=_last_path(data.get("id")),
            semantic_scholar_id=None,
            title=clean_text(data.get("title") or data.get("display_name")) or "Untitled",
            abstract=restore_openalex_abstract(data.get("abstract_inverted_index")),
            authors=authors,
            year=data.get("publication_year") or year_from_date(published_date),
            published_date=published_date,
            updated_date=to_iso_date(data.get("updated_date")),
            venue=source.get("display_name"),
            work_type=data.get("type"),
            fields=fields,
            keywords=keywords,
            url=primary_location.get("landing_page_url") or data.get("doi") or data.get("id"),
            pdf_url=primary_location.get("pdf_url"),
            oa_url=open_access.get("oa_url"),
            citation_count=data.get("cited_by_count"),
            influential_citation_count=None,
            is_open_access=open_access.get("is_oa"),
            license=primary_location.get("license"),
            source_query=raw.query.label,
            fetched_at=raw.fetched_at,
            raw_path=raw.raw_path,
        )
        return finalize_paper_item(item)


def _last_path(value: str | None) -> str | None:
    if not value:
        return None
    return value.rstrip("/").split("/")[-1]
