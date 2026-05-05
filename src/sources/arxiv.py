from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any

import feedparser
import requests

from src.models.paper import PaperItem
from src.pipeline.normalize import finalize_paper_item
from src.pipeline.rate_limit import RateLimiter
from src.sources.base import JsonSourceClient, RawItem, SourceQuery, fetched_now
from src.utils.dates import days_ago_iso, to_iso_date, utc_now, year_from_date
from src.utils.http import build_user_agent, request_text
from src.utils.ids import normalize_arxiv_id, normalize_doi
from src.utils.text import clean_text


class ArxivClient(JsonSourceClient):
    name = "arxiv"
    base_url = "https://export.arxiv.org/api/query"

    def __init__(self, config: dict[str, Any], raw_dir: Path, session: requests.Session | None = None):
        super().__init__(config, raw_dir, session)
        self.rate_limiter = RateLimiter(float(config.get("delay_seconds", 3)))

    def fetch(self, query: SourceQuery) -> list[RawItem]:
        limit = int(query.limit or self.config.get("per_query_limit", 10))
        self.rate_limiter.wait()
        xml_text = request_text(
            self.session,
            "GET",
            self.base_url,
            params={
                "search_query": self._search_query(query),
                "start": 0,
                "max_results": limit,
                "sortBy": "submittedDate",
                "sortOrder": "descending",
            },
            headers={"User-Agent": build_user_agent()},
        )
        raw_path = self.save_raw(xml_text, self.name, query, page=1, suffix="xml")
        parsed = feedparser.parse(xml_text)
        fetched_at = fetched_now()
        return [
            RawItem(
                source=self.name,
                source_id=normalize_arxiv_id(entry.get("id")),
                query=query,
                data=dict(entry),
                raw_path=raw_path,
                fetched_at=fetched_at,
            )
            for entry in parsed.entries
            if self._inside_date_window(entry, query)
        ]

    def normalize(self, raw: RawItem) -> PaperItem:
        entry = raw.data
        arxiv_id = normalize_arxiv_id(entry.get("id"))
        tags = [
            tag.get("term")
            for tag in entry.get("tags", [])
            if isinstance(tag, dict) and tag.get("term")
        ]
        authors = [
            author.get("name")
            for author in entry.get("authors", [])
            if isinstance(author, dict) and author.get("name")
        ]
        published_date = to_iso_date(entry.get("published"))
        pdf_url = _find_pdf_url(entry.get("links", []))
        item = PaperItem(
            canonical_id="pending",
            source=self.name,
            source_id=arxiv_id,
            doi=normalize_doi(entry.get("arxiv_doi")),
            arxiv_id=arxiv_id,
            pmid=None,
            openalex_id=None,
            semantic_scholar_id=None,
            title=clean_text(entry.get("title")) or "Untitled",
            abstract=clean_text(entry.get("summary")),
            authors=authors,
            year=year_from_date(published_date),
            published_date=published_date,
            updated_date=to_iso_date(entry.get("updated")),
            venue="arXiv",
            work_type="preprint",
            fields=tags,
            keywords=[],
            url=entry.get("link") or entry.get("id"),
            pdf_url=pdf_url,
            oa_url=entry.get("link") or entry.get("id"),
            citation_count=None,
            influential_citation_count=None,
            is_open_access=True,
            license=None,
            source_query=raw.query.label,
            fetched_at=raw.fetched_at,
            raw_path=raw.raw_path,
        )
        return finalize_paper_item(item)

    def _search_query(self, query: SourceQuery) -> str:
        if query.query_type == "category":
            base = f"cat:{query.query}"
        else:
            escaped = query.query.replace('"', '\\"')
            base = f'all:"{escaped}"'
        days_back = int(query.days_back or self.config.get("days_back", 14))
        start = days_ago_iso(days_back).replace("-", "")
        end = utc_now().date().isoformat().replace("-", "")
        return f"({base}) AND submittedDate:[{start}0000 TO {end}2359]"

    def _inside_date_window(self, entry: dict[str, Any], query: SourceQuery) -> bool:
        published = to_iso_date(entry.get("published"))
        if not published:
            return True
        days_back = int(query.days_back or self.config.get("days_back", 14))
        start = datetime.fromisoformat(days_ago_iso(days_back)).date()
        return datetime.fromisoformat(published).date() >= start


def _find_pdf_url(links: list[Any]) -> str | None:
    for link in links:
        if not isinstance(link, dict):
            continue
        if link.get("type") == "application/pdf" or link.get("title") == "pdf":
            return link.get("href")
    return None
