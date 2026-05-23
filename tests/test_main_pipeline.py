import logging
from textwrap import dedent
from pathlib import Path

import src.main as main_module
from src.app.config import load_runtime_config
from src.app.runtime import candidate_export_path
from src.main import build_source_preview, main, render_source_preview, run_enrichment, run_pipeline
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
            tmp_path / "raw",
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


def test_source_preview_lists_sources_queries_and_estimates(tmp_path: Path, capsys, monkeypatch) -> None:
    config_dir = _write_config(
        tmp_path,
        sources_yaml="""
        sources:
          openalex:
            enabled: true
            days_back: 14
            per_query_limit: 7
            max_total: 10
            max_queries_per_lane: 1
          arxiv:
            enabled: false
            per_query_limit: 5
            max_total: 20
          crossref:
            enabled: false
            max_total: 200
          openreview:
            enabled: false
        """,
        topics_yaml="""
        lanes:
          embodied:
            keywords:
              - robot learning
              - robotic manipulation
          systems:
            keywords:
              - control theory
        """,
    )
    runtime = load_runtime_config(project_root=tmp_path, config_dir=config_dir, environ={})
    monkeypatch.setitem(main_module.DISCOVERY_CLIENTS, "openalex", _ExplodingClient)

    previews = build_source_preview(runtime)
    rendered = render_source_preview(previews)
    main(["--config-dir", str(config_dir), "--source-preview"])
    cli_output = capsys.readouterr().out

    assert "Network access: disabled" in rendered
    assert "- openalex (discovery):" in rendered
    assert "embodied:keyword:robot learning limit=7" in rendered
    assert "systems:keyword:control theory limit=3" in rendered
    assert "estimated_max_records=10" in rendered
    assert "- arxiv (discovery)" in rendered
    assert "- openreview (config-only)" in rendered
    assert cli_output == rendered


def test_empty_pipeline_skips_export_by_default_and_preserves_existing_file(tmp_path: Path) -> None:
    config_dir = _write_config(tmp_path)
    runtime = load_runtime_config(project_root=tmp_path, config_dir=config_dir, environ={})
    export_path = candidate_export_path(runtime)
    export_path.parent.mkdir(parents=True)
    export_path.write_text("existing candidate export\n", encoding="utf-8")

    result = run_pipeline(runtime)

    assert result.empty_export_skipped is True
    assert result.exported_count == 0
    assert result.collected_count == 0
    assert result.export_path == export_path
    assert export_path.read_text(encoding="utf-8") == "existing candidate export\n"


def test_allow_empty_export_writes_empty_candidate_file(tmp_path: Path) -> None:
    config_dir = _write_config(tmp_path)
    runtime = load_runtime_config(project_root=tmp_path, config_dir=config_dir, environ={})

    result = run_pipeline(runtime, allow_empty_export=True)

    assert result.empty_export_skipped is False
    assert result.exported_count == 0
    assert result.export_path.exists()
    assert result.export_path.read_text(encoding="utf-8") == ""


class _NoneEnrichmentClient:
    def __init__(self, config, raw_dir):
        self.config = config
        self.raw_dir = raw_dir
        self.unavailable_reason = None

    def enrich_item(self, item):
        return None


class _ExplodingClient:
    def __init__(self, config, raw_dir):
        raise AssertionError("source preview must not instantiate source clients")


def _write_config(
    tmp_path: Path,
    *,
    sources_yaml: str = """
    sources:
      openalex:
        enabled: false
      arxiv:
        enabled: false
      pubmed:
        enabled: false
      biorxiv:
        enabled: false
      medrxiv:
        enabled: false
      crossref:
        enabled: false
      semantic_scholar:
        enabled: false
    """,
    topics_yaml: str = "lanes: {}\n",
) -> Path:
    config_dir = tmp_path / "config"
    config_dir.mkdir()
    (config_dir / "app.yaml").write_text("app:\n  exports_dir: exports\n  logs_dir: logs\n", encoding="utf-8")
    (config_dir / "sources.yaml").write_text(dedent(sources_yaml).strip() + "\n", encoding="utf-8")
    (config_dir / "topics.yaml").write_text(dedent(topics_yaml).strip() + "\n", encoding="utf-8")
    return config_dir
