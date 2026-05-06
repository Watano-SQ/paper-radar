import logging
from pathlib import Path

from src.main import run_enrichment
from src.models.paper import PaperItem
from src.pipeline.store import PaperStore


def test_enrichment_none_marks_crawl_run_skipped(tmp_path: Path) -> None:
    store = PaperStore(tmp_path / "papers.sqlite")
    try:
        item = PaperItem(
            canonical_id="doi:10.1000/missing",
            source="openalex",
            source_id="W1",
            doi="10.1000/missing",
            title="Missing DOI",
            authors=["Ada Lovelace"],
            fetched_at="2026-05-04T00:00:00+00:00",
        )
        store.upsert_paper(item)
        updated_ids = run_enrichment(
            "crossref",
            _NoneEnrichmentClient,
            {"enabled": True, "max_total": 1},
            store,
            {item.canonical_id},
            logging.getLogger("test"),
        )
        assert updated_ids == set()
        row = store.conn.execute(
            "select source, status, items_found, items_new from crawl_runs where source = 'crossref'"
        ).fetchone()
        assert row is not None
        assert row["status"] == "skipped"
        assert row["items_found"] == 0
        assert row["items_new"] == 0
    finally:
        store.close()


class _NoneEnrichmentClient:
    def __init__(self, config, raw_dir):
        self.config = config
        self.raw_dir = raw_dir
        self.unavailable_reason = None

    def enrich_item(self, item):
        return None
