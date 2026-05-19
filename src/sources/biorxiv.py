from __future__ import annotations

from pathlib import Path
from typing import Any

import requests

from src.models.paper import PaperItem
from src.pipeline.normalize import compact_list, finalize_paper_item
from src.pipeline.rate_limit import RateLimiter
from src.sources.base import JsonSourceClient, RawItem, SourceQuery, fetched_now
from src.utils.dates import days_ago_iso, to_iso_date, utc_now, year_from_date
from src.utils.http import build_user_agent, request_json
from src.utils.ids import normalize_doi
from src.utils.text import clean_text


class _PreprintServerClient(JsonSourceClient):
    base_url = "https://api.biorxiv.org/details"
    default_server = "biorxiv"
    venue_name = "bioRxiv"

    def __init__(self, config: dict[str, Any], raw_dir: Path, session: requests.Session | None = None):
        super().__init__(config, raw_dir, session)
        self.server = str(config.get("server") or self.default_server)
        self.rate_limiter = RateLimiter(float(config.get("delay_seconds", 1)))

    def fetch(self, query: SourceQuery) -> list[RawItem]:
        limit = int(query.limit or self.config.get("per_query_limit", 50))
        days_back = int(query.days_back or self.config.get("days_back", 14))
        from_date = days_ago_iso(days_back)
        to_date = utc_now().date().isoformat()
        max_scan = max(limit, int(self.config.get("max_total", limit)))
        cursor = 0
        page = 1
        scanned = 0
        items: list[RawItem] = []

        while scanned < max_scan and len(items) < limit:
            self.rate_limiter.wait()
            response = request_json(
                self.session,
                "GET",
                f"{self.base_url}/{self.server}/{from_date}/{to_date}/{cursor}",
                headers={"User-Agent": build_user_agent()},
            )
            raw_path = self.save_raw(response, self.name, query, page=page)
            fetched_at = fetched_now()
            collection = response.get("collection") or []
            if not collection:
                break

            for record in collection:
                if not isinstance(record, dict):
                    continue
                scanned += 1
                if record_matches_query(record, query.query):
                    items.append(
                        RawItem(
                            source=self.name,
                            source_id=normalize_doi(record.get("doi")) or record.get("doi"),
                            query=query,
                            data=record,
                            raw_path=raw_path,
                            fetched_at=fetched_at,
                        )
                    )
                    if len(items) >= limit:
                        break
                if scanned >= max_scan:
                    break

            if len(collection) < 100:
                break
            cursor += len(collection)
            page += 1

        return items

    def normalize(self, raw: RawItem) -> PaperItem:
        data = raw.data
        doi = normalize_doi(data.get("doi"))
        published_date = to_iso_date(data.get("date"))
        url = _landing_url(self.server, doi, data.get("version")) or data.get("url")
        item = PaperItem(
            canonical_id="pending",
            source=self.name,
            source_id=doi or data.get("id"),
            doi=doi,
            arxiv_id=None,
            pmid=None,
            openalex_id=None,
            semantic_scholar_id=None,
            title=clean_text(data.get("title")) or "Untitled",
            abstract=clean_text(data.get("abstract")),
            authors=_split_authors(data.get("authors")),
            year=year_from_date(published_date),
            published_date=published_date,
            updated_date=None,
            venue=self.venue_name,
            work_type="preprint",
            fields=compact_list([data.get("category")]),
            keywords=[],
            url=url,
            pdf_url=_safe_pdf_url(data),
            oa_url=data.get("oa_url") or url,
            citation_count=None,
            influential_citation_count=None,
            is_open_access=True,
            license=clean_text(data.get("license")),
            source_query=raw.query.label,
            fetched_at=raw.fetched_at,
            raw_path=raw.raw_path,
        )
        return finalize_paper_item(item)


class BiorxivClient(_PreprintServerClient):
    name = "biorxiv"
    default_server = "biorxiv"
    venue_name = "bioRxiv"


class MedrxivClient(_PreprintServerClient):
    name = "medrxiv"
    default_server = "medrxiv"
    venue_name = "medRxiv"


def record_matches_query(record: dict[str, Any], query: str) -> bool:
    haystack = " ".join(
        str(value)
        for value in [
            record.get("title"),
            record.get("abstract"),
            record.get("category"),
        ]
        if value
    ).casefold()
    needle = clean_text(query)
    if not needle:
        return True
    needle = needle.casefold()
    if needle in haystack:
        return True
    terms = [term for term in needle.split() if len(term) > 2]
    return bool(terms) and all(term in haystack for term in terms)


def _split_authors(value: Any) -> list[str]:
    if isinstance(value, list):
        return compact_list(value)
    if not value:
        return []
    return compact_list(str(value).replace(" and ", ";").split(";"))


def _landing_url(server: str, doi: str | None, version: Any) -> str | None:
    if not doi:
        return None
    domain = "medrxiv.org" if server == "medrxiv" else "biorxiv.org"
    suffix = f"v{version}" if version else ""
    return f"https://www.{domain}/content/{doi}{suffix}"


def _safe_pdf_url(data: dict[str, Any]) -> str | None:
    value = data.get("pdf_url") or data.get("pdf")
    if not isinstance(value, str):
        return None
    normalized = value.strip()
    if "biorxiv.org" in normalized or "medrxiv.org" in normalized:
        return normalized
    return None
