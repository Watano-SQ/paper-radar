from pathlib import Path

from src.models.paper import PaperItem
from src.pipeline.store import PaperStore


def test_sqlite_upsert_does_not_duplicate(tmp_path: Path) -> None:
    store = PaperStore(tmp_path / "papers.sqlite")
    try:
        first = PaperItem(
            canonical_id="doi:10.1000/example",
            source="openalex",
            source_id="W1",
            doi="10.1000/example",
            title="Example Paper",
            authors=["Ada Lovelace"],
            fetched_at="2026-05-04T00:00:00+00:00",
            raw_path="raw/openalex.json",
        )
        second = PaperItem(
            canonical_id="doi:10.1000/example",
            source="arxiv",
            source_id="2501.12345",
            doi="10.1000/example",
            arxiv_id="2501.12345",
            title="Example Paper",
            authors=["Ada Lovelace"],
            fetched_at="2026-05-04T01:00:00+00:00",
            raw_path="raw/arxiv.xml",
        )
        assert store.upsert_paper(first) is True
        assert store.upsert_paper(second) is False
        assert store.count_papers() == 1
        item = store.fetch_paper_items({"doi:10.1000/example"})[0]
        assert item.arxiv_id == "2501.12345"
    finally:
        store.close()


def test_crawl_runs_insert_finish_fail(tmp_path: Path) -> None:
    store = PaperStore(tmp_path / "papers.sqlite")
    try:
        success_id = store.start_crawl_run(source="openalex", query="lane:keyword:test")
        store.finish_crawl_run(success_id, items_found=3, items_new=2)
        success = store.get_crawl_run(success_id)
        assert success is not None
        assert success["status"] == "success"
        assert success["items_found"] == 3
        assert success["items_new"] == 2
        assert success["finished_at"] is not None

        failed_id = store.start_crawl_run(source="arxiv", query="lane:keyword:test")
        store.fail_crawl_run(failed_id, error="boom")
        failed = store.get_crawl_run(failed_id)
        assert failed is not None
        assert failed["status"] == "failed"
        assert failed["error"] == "boom"
    finally:
        store.close()


def test_enrichment_upsert_merges_fields(tmp_path: Path) -> None:
    store = PaperStore(tmp_path / "papers.sqlite")
    try:
        original = PaperItem(
            canonical_id="doi:10.1000/example",
            source="openalex",
            source_id="W1",
            doi="10.1000/example",
            title="Example Paper",
            authors=["Ada Lovelace"],
            fetched_at="2026-05-04T00:00:00+00:00",
        )
        crossref = PaperItem(
            canonical_id="doi:10.1000/example",
            source="crossref",
            source_id="10.1000/example",
            doi="10.1000/example",
            title="Example Paper",
            authors=["Ada Lovelace"],
            venue="Journal of Examples",
            license="https://creativecommons.org/licenses/by/4.0/",
            fetched_at="2026-05-04T01:00:00+00:00",
        )
        semantic_scholar = PaperItem(
            canonical_id="doi:10.1000/example",
            source="semantic_scholar",
            source_id="S2-1",
            doi="10.1000/example",
            semantic_scholar_id="S2-1",
            title="Example Paper",
            authors=["Ada Lovelace"],
            citation_count=11,
            influential_citation_count=2,
            fields=["Computer Science"],
            fetched_at="2026-05-04T02:00:00+00:00",
        )
        store.upsert_paper(original)
        store.upsert_paper(crossref)
        store.upsert_paper(semantic_scholar)
        item = store.fetch_paper_items({"doi:10.1000/example"})[0]
        assert item.venue == "Journal of Examples"
        assert item.license == "https://creativecommons.org/licenses/by/4.0/"
        assert item.semantic_scholar_id == "S2-1"
        assert item.citation_count == 11
        assert item.influential_citation_count == 2
        assert "Computer Science" in item.fields
    finally:
        store.close()
