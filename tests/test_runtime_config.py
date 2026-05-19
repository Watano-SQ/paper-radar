import json
from textwrap import dedent
from pathlib import Path

from src.app.config import load_runtime_config
from src.diagnostics import collect_diagnostics
from src.main import run_pipeline
from src.models.paper import PaperItem
from src.pipeline.store import PaperStore
from src.report.weekly_candidates import generate_weekly_candidate_report


def test_default_app_config_resolves_local_paths() -> None:
    project_root = Path(__file__).resolve().parents[1]

    runtime = load_runtime_config(
        project_root=project_root,
        config_dir=project_root / "config",
        environ={},
    )

    assert runtime.paths.project_root == project_root
    assert runtime.paths.config_dir == project_root / "config"
    assert runtime.paths.app_config_path == project_root / "config" / "app.yaml"
    assert runtime.paths.scoring_config_path == project_root / "config" / "scoring.yaml"
    assert runtime.paths.sources_config_path == project_root / "config" / "sources.yaml"
    assert runtime.paths.topics_config_path == project_root / "config" / "topics.yaml"
    assert runtime.paths.data_dir == project_root / "data"
    assert runtime.paths.raw_dir == project_root / "data" / "raw"
    assert runtime.paths.exports_dir == project_root / "data" / "exports"
    assert runtime.paths.reports_dir == project_root / "data" / "reports"
    assert runtime.paths.logs_dir == project_root / "logs"
    assert runtime.paths.database_path == project_root / "data" / "papers.sqlite"
    assert runtime.scoring["scoring"]["enabled"] is True


def test_relative_app_paths_resolve_under_project_root(tmp_path: Path) -> None:
    config_dir = _write_config(
        tmp_path,
        """
        app:
          data_dir: runtime-data
          raw_dir: runtime-data/raw-custom
          exports_dir: runtime-data/exports-custom
          reports_dir: runtime-data/reports-custom
          logs_dir: runtime-logs
          database_path: runtime-data/db/custom.sqlite
        """,
    )

    runtime = load_runtime_config(project_root=tmp_path, config_dir=config_dir, environ={})

    assert runtime.paths.data_dir == tmp_path / "runtime-data"
    assert runtime.paths.raw_dir == tmp_path / "runtime-data" / "raw-custom"
    assert runtime.paths.exports_dir == tmp_path / "runtime-data" / "exports-custom"
    assert runtime.paths.reports_dir == tmp_path / "runtime-data" / "reports-custom"
    assert runtime.paths.logs_dir == tmp_path / "runtime-logs"
    assert runtime.paths.database_path == tmp_path / "runtime-data" / "db" / "custom.sqlite"


def test_absolute_app_paths_stay_absolute(tmp_path: Path) -> None:
    data_dir = tmp_path / "abs-data"
    raw_dir = tmp_path / "abs-raw"
    exports_dir = tmp_path / "abs-exports"
    reports_dir = tmp_path / "abs-reports"
    logs_dir = tmp_path / "abs-logs"
    database_path = tmp_path / "abs-db" / "papers.sqlite"
    config_dir = _write_config(
        tmp_path,
        f"""
        app:
          data_dir: {data_dir}
          raw_dir: {raw_dir}
          exports_dir: {exports_dir}
          reports_dir: {reports_dir}
          logs_dir: {logs_dir}
          database_path: {database_path}
        """,
    )

    runtime = load_runtime_config(project_root=tmp_path, config_dir=config_dir, environ={})

    assert runtime.paths.data_dir == data_dir
    assert runtime.paths.raw_dir == raw_dir
    assert runtime.paths.exports_dir == exports_dir
    assert runtime.paths.reports_dir == reports_dir
    assert runtime.paths.logs_dir == logs_dir
    assert runtime.paths.database_path == database_path


def test_environment_path_overrides(tmp_path: Path) -> None:
    config_dir = _write_config(tmp_path, "")
    env = {
        "PAPER_RADAR_DATA_DIR": str(tmp_path / "env-data"),
        "PAPER_RADAR_REPORTS_DIR": str(tmp_path / "env-reports"),
        "PAPER_RADAR_EXPORTS_DIR": str(tmp_path / "env-exports"),
        "PAPER_RADAR_LOGS_DIR": str(tmp_path / "env-logs"),
        "PAPER_RADAR_DATABASE_PATH": str(tmp_path / "env-db" / "papers.sqlite"),
    }

    runtime = load_runtime_config(project_root=tmp_path, config_dir=config_dir, environ=env)

    assert runtime.paths.data_dir == tmp_path / "env-data"
    assert runtime.paths.raw_dir == tmp_path / "env-data" / "raw"
    assert runtime.paths.reports_dir == tmp_path / "env-reports"
    assert runtime.paths.exports_dir == tmp_path / "env-exports"
    assert runtime.paths.logs_dir == tmp_path / "env-logs"
    assert runtime.paths.database_path == tmp_path / "env-db" / "papers.sqlite"


def test_run_pipeline_uses_configured_temp_runtime_paths(tmp_path: Path) -> None:
    config_dir = _write_config(
        tmp_path,
        """
        app:
          data_dir: runtime-data
          exports_dir: runtime-exports
          logs_dir: runtime-logs
          database_path: runtime-db/papers.sqlite
        """,
    )
    runtime = load_runtime_config(project_root=tmp_path, config_dir=config_dir, environ={})

    output_path = run_pipeline(runtime)

    assert output_path.parent == tmp_path / "runtime-exports"
    assert output_path.exists()
    assert runtime.paths.database_path.exists()
    assert runtime.paths.logs_dir.exists()
    assert not (tmp_path / "data").exists()
    assert not (tmp_path / "logs").exists()


def test_weekly_report_uses_configured_reports_directory(tmp_path: Path) -> None:
    config_dir = _write_config(
        tmp_path,
        """
        app:
          exports_dir: runtime-exports
          reports_dir: runtime-reports
        files:
          weekly_report_filename_template: "radar_{week}.md"
          reject_log_filename_template: "rejects_{week}.md"
        """,
    )
    runtime = load_runtime_config(project_root=tmp_path, config_dir=config_dir, environ={})
    runtime.paths.exports_dir.mkdir(parents=True)
    export_file = runtime.paths.exports_dir / "candidates_2026-W21.jsonl"
    export_file.write_text(
        json.dumps({"canonical_id": "doi:10.1000/example", "title": "Example", "source_query": "lane:keyword:x"}),
        encoding="utf-8",
    )

    output_path = generate_weekly_candidate_report(runtime=runtime, week_label="2026-W21", write_reject_log=True)

    assert output_path == runtime.paths.reports_dir / "radar_2026-W21.md"
    assert output_path.exists()
    assert (runtime.paths.reports_dir / "rejects_2026-W21.md").exists()


def test_diagnostics_reads_configured_runtime_paths(tmp_path: Path) -> None:
    config_dir = _write_config(
        tmp_path,
        """
        app:
          exports_dir: runtime-exports
          database_path: runtime-db/papers.sqlite
        files:
          export_filename_template: "pool_{week}.jsonl"
        """,
    )
    runtime = load_runtime_config(project_root=tmp_path, config_dir=config_dir, environ={})
    runtime.paths.exports_dir.mkdir(parents=True)
    latest_export = runtime.paths.exports_dir / "pool_2026-W21.jsonl"
    latest_export.write_text('{"canonical_id":"doi:10.1000/example"}\n', encoding="utf-8")
    store = PaperStore(runtime.paths.database_path)
    try:
        store.upsert_paper(
            PaperItem(
                canonical_id="doi:10.1000/example",
                source="openalex",
                source_id="W1",
                doi="10.1000/example",
                title="Example Paper",
                authors=["Ada Lovelace"],
                fetched_at="2026-05-04T00:00:00+00:00",
            )
        )
    finally:
        store.close()

    diagnostics = collect_diagnostics(runtime=runtime)

    assert diagnostics["db_path"] == str(runtime.paths.database_path)
    assert diagnostics["papers_count"] == 1
    assert diagnostics["latest_export"] == str(latest_export)


def _write_config(tmp_path: Path, app_yaml: str) -> Path:
    config_dir = tmp_path / "config"
    config_dir.mkdir()
    (config_dir / "app.yaml").write_text(dedent(app_yaml).strip() + "\n", encoding="utf-8")
    (config_dir / "sources.yaml").write_text(
        dedent(
            """
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
        """
        ),
        encoding="utf-8",
    )
    (config_dir / "topics.yaml").write_text("lanes: {}\n", encoding="utf-8")
    return config_dir
