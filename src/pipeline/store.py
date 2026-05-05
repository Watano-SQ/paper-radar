from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Any

from src.models.paper import PaperItem
from src.utils.dates import utc_now_iso


class PaperStore:
    """Small SQLite storage layer for the V0 crawl loop."""

    def __init__(self, db_path: Path):
        self.db_path = db_path
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(self.db_path)
        self.conn.row_factory = sqlite3.Row
        self.init_db()

    def close(self) -> None:
        self.conn.close()

    def init_db(self) -> None:
        self.conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS papers (
              canonical_id TEXT PRIMARY KEY,
              title TEXT NOT NULL,
              abstract TEXT,
              authors_json TEXT NOT NULL,
              year INTEGER,
              published_date TEXT,
              updated_date TEXT,
              venue TEXT,
              work_type TEXT,
              fields_json TEXT NOT NULL,
              keywords_json TEXT NOT NULL,
              doi TEXT,
              arxiv_id TEXT,
              pmid TEXT,
              openalex_id TEXT,
              semantic_scholar_id TEXT,
              url TEXT,
              pdf_url TEXT,
              oa_url TEXT,
              citation_count INTEGER,
              influential_citation_count INTEGER,
              is_open_access INTEGER,
              license TEXT,
              first_seen_at TEXT NOT NULL,
              last_seen_at TEXT NOT NULL,
              sources_json TEXT NOT NULL,
              raw_refs_json TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS paper_sources (
              id INTEGER PRIMARY KEY AUTOINCREMENT,
              canonical_id TEXT NOT NULL,
              source TEXT NOT NULL,
              source_id TEXT,
              source_query TEXT,
              fetched_at TEXT NOT NULL,
              raw_path TEXT,
              UNIQUE(source, source_id),
              FOREIGN KEY(canonical_id) REFERENCES papers(canonical_id)
            );
            """
        )
        self.conn.commit()

    def upsert_paper(self, item: PaperItem) -> bool:
        existing = self.conn.execute(
            "SELECT * FROM papers WHERE canonical_id = ?",
            (item.canonical_id,),
        ).fetchone()
        is_new = existing is None
        if is_new:
            self._insert_paper(item)
        else:
            self._update_paper(existing, item)
        self._insert_source(item)
        self.conn.commit()
        return is_new

    def fetch_paper_items(self, canonical_ids: set[str] | list[str]) -> list[PaperItem]:
        if not canonical_ids:
            return []
        placeholders = ",".join("?" for _ in canonical_ids)
        rows = self.conn.execute(
            f"SELECT * FROM papers WHERE canonical_id IN ({placeholders})",
            tuple(canonical_ids),
        ).fetchall()
        return [self._row_to_item(row) for row in rows]

    def count_papers(self) -> int:
        row = self.conn.execute("SELECT COUNT(*) AS count FROM papers").fetchone()
        return int(row["count"])

    def _insert_paper(self, item: PaperItem) -> None:
        now = item.fetched_at or utc_now_iso()
        self.conn.execute(
            """
            INSERT INTO papers (
              canonical_id, title, abstract, authors_json, year, published_date,
              updated_date, venue, work_type, fields_json, keywords_json, doi,
              arxiv_id, pmid, openalex_id, semantic_scholar_id, url, pdf_url,
              oa_url, citation_count, influential_citation_count, is_open_access,
              license, first_seen_at, last_seen_at, sources_json, raw_refs_json
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                item.canonical_id,
                item.title,
                item.abstract,
                _dump_json(item.authors),
                item.year,
                item.published_date,
                item.updated_date,
                item.venue,
                item.work_type,
                _dump_json(item.fields),
                _dump_json(item.keywords),
                item.doi,
                item.arxiv_id,
                item.pmid,
                item.openalex_id,
                item.semantic_scholar_id,
                item.url,
                item.pdf_url,
                item.oa_url,
                item.citation_count,
                item.influential_citation_count,
                _bool_to_int(item.is_open_access),
                item.license,
                now,
                now,
                _dump_json([item.source]),
                _dump_json([_raw_ref(item)] if item.raw_path else []),
            ),
        )

    def _update_paper(self, row: sqlite3.Row, item: PaperItem) -> None:
        now = item.fetched_at or utc_now_iso()
        sources = _merge_lists(_load_json(row["sources_json"], []), [item.source])
        raw_refs = _load_json(row["raw_refs_json"], [])
        if item.raw_path:
            raw_refs = _append_unique_raw_ref(raw_refs, _raw_ref(item))
        self.conn.execute(
            """
            UPDATE papers SET
              title = ?,
              abstract = ?,
              authors_json = ?,
              year = ?,
              published_date = ?,
              updated_date = ?,
              venue = ?,
              work_type = ?,
              fields_json = ?,
              keywords_json = ?,
              doi = ?,
              arxiv_id = ?,
              pmid = ?,
              openalex_id = ?,
              semantic_scholar_id = ?,
              url = ?,
              pdf_url = ?,
              oa_url = ?,
              citation_count = ?,
              influential_citation_count = ?,
              is_open_access = ?,
              license = ?,
              last_seen_at = ?,
              sources_json = ?,
              raw_refs_json = ?
            WHERE canonical_id = ?
            """,
            (
                row["title"] or item.title,
                row["abstract"] or item.abstract,
                _dump_json(_merge_lists(_load_json(row["authors_json"], []), item.authors)),
                row["year"] or item.year,
                row["published_date"] or item.published_date,
                _prefer_newer_text(row["updated_date"], item.updated_date),
                row["venue"] or item.venue,
                row["work_type"] or item.work_type,
                _dump_json(_merge_lists(_load_json(row["fields_json"], []), item.fields)),
                _dump_json(_merge_lists(_load_json(row["keywords_json"], []), item.keywords)),
                row["doi"] or item.doi,
                row["arxiv_id"] or item.arxiv_id,
                row["pmid"] or item.pmid,
                row["openalex_id"] or item.openalex_id,
                row["semantic_scholar_id"] or item.semantic_scholar_id,
                row["url"] or item.url,
                row["pdf_url"] or item.pdf_url,
                row["oa_url"] or item.oa_url,
                _prefer_count(row["citation_count"], item.citation_count),
                _prefer_count(row["influential_citation_count"], item.influential_citation_count),
                row["is_open_access"]
                if row["is_open_access"] is not None
                else _bool_to_int(item.is_open_access),
                row["license"] or item.license,
                now,
                _dump_json(sources),
                _dump_json(raw_refs),
                item.canonical_id,
            ),
        )

    def _insert_source(self, item: PaperItem) -> None:
        if item.source_id is None:
            self.conn.execute(
                """
                INSERT INTO paper_sources (
                  canonical_id, source, source_id, source_query, fetched_at, raw_path
                ) VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    item.canonical_id,
                    item.source,
                    item.source_id,
                    item.source_query,
                    item.fetched_at,
                    item.raw_path,
                ),
            )
            return
        self.conn.execute(
            """
            INSERT OR IGNORE INTO paper_sources (
              canonical_id, source, source_id, source_query, fetched_at, raw_path
            ) VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                item.canonical_id,
                item.source,
                item.source_id,
                item.source_query,
                item.fetched_at,
                item.raw_path,
            ),
        )

    def _row_to_item(self, row: sqlite3.Row) -> PaperItem:
        latest_source = self.conn.execute(
            """
            SELECT source, source_id, source_query, fetched_at, raw_path
            FROM paper_sources
            WHERE canonical_id = ?
            ORDER BY fetched_at DESC, id DESC
            LIMIT 1
            """,
            (row["canonical_id"],),
        ).fetchone()
        return PaperItem(
            canonical_id=row["canonical_id"],
            source=latest_source["source"] if latest_source else "stored",
            source_id=latest_source["source_id"] if latest_source else None,
            doi=row["doi"],
            arxiv_id=row["arxiv_id"],
            pmid=row["pmid"],
            openalex_id=row["openalex_id"],
            semantic_scholar_id=row["semantic_scholar_id"],
            title=row["title"],
            abstract=row["abstract"],
            authors=_load_json(row["authors_json"], []),
            year=row["year"],
            published_date=row["published_date"],
            updated_date=row["updated_date"],
            venue=row["venue"],
            work_type=row["work_type"],
            fields=_load_json(row["fields_json"], []),
            keywords=_load_json(row["keywords_json"], []),
            url=row["url"],
            pdf_url=row["pdf_url"],
            oa_url=row["oa_url"],
            citation_count=row["citation_count"],
            influential_citation_count=row["influential_citation_count"],
            is_open_access=_int_to_bool(row["is_open_access"]),
            license=row["license"],
            source_query=latest_source["source_query"] if latest_source else None,
            fetched_at=latest_source["fetched_at"] if latest_source else utc_now_iso(),
            raw_path=latest_source["raw_path"] if latest_source else None,
        )


def _dump_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True)


def _load_json(value: str | None, default: Any) -> Any:
    if not value:
        return default
    try:
        return json.loads(value)
    except json.JSONDecodeError:
        return default


def _merge_lists(existing: list[str], incoming: list[str]) -> list[str]:
    output: list[str] = []
    seen: set[str] = set()
    for value in [*existing, *incoming]:
        text = str(value).strip()
        key = text.casefold()
        if text and key not in seen:
            output.append(text)
            seen.add(key)
    return output


def _raw_ref(item: PaperItem) -> dict[str, str | None]:
    return {
        "source": item.source,
        "source_id": item.source_id,
        "source_query": item.source_query,
        "fetched_at": item.fetched_at,
        "raw_path": item.raw_path,
    }


def _append_unique_raw_ref(existing: list[dict[str, Any]], incoming: dict[str, Any]) -> list[dict[str, Any]]:
    incoming_key = (incoming.get("source"), incoming.get("source_id"), incoming.get("raw_path"))
    keys = {(item.get("source"), item.get("source_id"), item.get("raw_path")) for item in existing}
    if incoming_key not in keys:
        existing.append(incoming)
    return existing


def _prefer_count(existing: int | None, incoming: int | None) -> int | None:
    if incoming is None:
        return existing
    if existing is None:
        return incoming
    return max(existing, incoming)


def _prefer_newer_text(existing: str | None, incoming: str | None) -> str | None:
    if not incoming:
        return existing
    if not existing:
        return incoming
    return max(existing, incoming)


def _bool_to_int(value: bool | None) -> int | None:
    if value is None:
        return None
    return 1 if value else 0


def _int_to_bool(value: int | None) -> bool | None:
    if value is None:
        return None
    return bool(value)
