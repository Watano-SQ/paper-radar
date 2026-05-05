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
