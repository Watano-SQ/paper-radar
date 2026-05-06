from pathlib import Path

from src.diagnostics import collect_diagnostics, format_diagnostics
from src.models.paper import PaperItem
from src.pipeline.store import PaperStore


def test_diagnostics_reads_sqlite_and_latest_export(tmp_path: Path) -> None:
    db_path = tmp_path / "papers.sqlite"
    exports_dir = tmp_path / "exports"
    exports_dir.mkdir()
    latest_export = exports_dir / "candidates_2026-W19.jsonl"
    latest_export.write_text('{"canonical_id":"doi:10.1000/example"}\n', encoding="utf-8")

    store = PaperStore(db_path)
    try:
        item = PaperItem(
            canonical_id="doi:10.1000/example",
            source="openalex",
            source_id="W1",
            doi="10.1000/example",
            title="Example Paper",
            authors=["Ada Lovelace"],
            fetched_at="2026-05-04T00:00:00+00:00",
        )
        store.upsert_paper(item)
        run_id = store.start_crawl_run(source="openalex", query="test")
        store.finish_crawl_run(run_id, items_found=1, items_new=1)
        store.record_possible_duplicate(
            left_id="doi:10.1000/example",
            right_id="titlehash:example",
            reason="test",
            score=0.99,
        )
    finally:
        store.close()

    diagnostics = collect_diagnostics(db_path=db_path, exports_dir=exports_dir)
    assert diagnostics["papers_count"] == 1
    assert diagnostics["paper_sources_count"] == 1
    assert diagnostics["possible_duplicates_count"] == 1
    assert diagnostics["latest_export"] == str(latest_export)
    assert diagnostics["crawl_runs"] == [{"source": "openalex", "status": "success", "count": 1}]

    formatted = format_diagnostics(diagnostics)
    assert "papers_count: 1" in formatted
    assert "openalex | success | 1" in formatted
