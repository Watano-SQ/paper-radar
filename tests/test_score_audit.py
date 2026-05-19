import json
from pathlib import Path
from textwrap import dedent

from src.app.config import load_runtime_config
from src.report.score_audit import build_score_audit, generate_score_audit_report, render_score_audit


def test_score_audit_creates_markdown_file_from_jsonl_fixture(tmp_path: Path) -> None:
    runtime = _runtime(tmp_path)
    export_file = _write_export(runtime.paths.exports_dir)

    output_path = generate_score_audit_report(runtime=runtime, export_file=export_file)

    content = output_path.read_text(encoding="utf-8")
    assert output_path == runtime.paths.reports_dir / "score_audit_2026-W21.md"
    assert "# Score Audit: 2026-W21" in content
    assert "This file audits candidate scoring behavior. It is not a reading list." in content
    assert "## Summary" in content


def test_score_audit_report_includes_core_diagnostics(tmp_path: Path) -> None:
    runtime = _runtime(tmp_path)
    export_file = _write_export(runtime.paths.exports_dir)

    audit = build_score_audit(
        _load_export(export_file),
        runtime,
        export_file=export_file,
        week_label="2026-W21",
        per_lane=2,
    )
    content = render_score_audit(audit)

    assert "## Candidate Levels" in content
    assert "| S_candidate |" in content
    assert "## Selected By Lane" in content
    assert "| neuro_cognitive |" in content
    assert "## Selected By Source" in content
    assert "| pubmed |" in content
    assert "## Top Score Components" in content
    assert "metadata.has_abstract" in content
    assert "## Top Penalties" in content
    assert "missing abstract" in content


def test_score_audit_identifies_near_threshold_candidates(tmp_path: Path) -> None:
    runtime = _runtime(tmp_path)
    candidates = [
        {
            "canonical_id": "doi:10.1000/near",
            "source": "pubmed",
            "doi": "10.1000/near",
            "title": "Plain candidate",
            "abstract": "No lane keyword here.",
            "published_date": "2020-01-01",
            "source_query": "neuro_cognitive:keyword:neural coding",
        }
    ]

    audit = build_score_audit(candidates, runtime, week_label="2026-W21")

    assert audit.near_threshold
    assert audit.near_threshold[0][1] in {"a_candidate_min", "b_candidate_min"}


def test_score_audit_emits_lane_dominance_note(tmp_path: Path) -> None:
    runtime = _runtime(tmp_path)
    candidates = [
        _candidate(f"doi:10.1000/neuro{index}", "neuro_cognitive", title=f"Neural coding survey {index}")
        for index in range(3)
    ]
    candidates.append(_candidate("doi:10.1000/robot", "core_embodied_ai", title="Robot learning benchmark", abstract=None))

    audit = build_score_audit(candidates, runtime, week_label="2026-W21", per_lane=5)

    assert any("dominates selected candidates" in note for note in audit.calibration_notes)


def test_score_audit_runtime_temp_reports_dir_is_respected(tmp_path: Path) -> None:
    runtime = _runtime(
        tmp_path,
        app_yaml="""
        app:
          exports_dir: runtime-exports
          reports_dir: runtime-reports
        files:
          score_audit_filename_template: "audit_{week}.md"
        """,
    )
    export_file = _write_export(runtime.paths.exports_dir)

    output_path = generate_score_audit_report(runtime=runtime, export_file=export_file)

    assert output_path == runtime.paths.reports_dir / "audit_2026-W21.md"
    assert output_path.exists()


def _runtime(tmp_path: Path, app_yaml: str = ""):
    config_dir = tmp_path / "config"
    config_dir.mkdir()
    (config_dir / "app.yaml").write_text(dedent(app_yaml).strip() + "\n", encoding="utf-8")
    (config_dir / "sources.yaml").write_text("sources: {}\n", encoding="utf-8")
    (config_dir / "topics.yaml").write_text(
        dedent(
            """
            lanes:
              neuro_cognitive:
                keywords:
                  - neural coding
                  - predictive coding
              core_embodied_ai:
                keywords:
                  - robot learning
                  - embodied AI
            """
        ),
        encoding="utf-8",
    )
    (config_dir / "scoring.yaml").write_text(
        dedent(
            """
            scoring:
              lane_balance:
                max_per_lane: 2
                min_per_active_lane: 1
                global_max: 10
            """
        ),
        encoding="utf-8",
    )
    return load_runtime_config(project_root=tmp_path, config_dir=config_dir, environ={})


def _write_export(exports_dir: Path) -> Path:
    exports_dir.mkdir(parents=True, exist_ok=True)
    export_file = exports_dir / "candidates_2026-W21.jsonl"
    rows = [
        _candidate("doi:10.1000/strong", "neuro_cognitive", title="Neural coding survey", source="pubmed"),
        _candidate("doi:10.1000/robot", "core_embodied_ai", title="Robot learning survey", source="arxiv"),
        _candidate("titlehash:weak", "neuro_cognitive", title="Weak note", abstract=None, source="biorxiv"),
        _candidate("doi:10.1000/bench", "neuro_cognitive", title="Neural coding benchmark leaderboard", source="openalex"),
    ]
    export_file.write_text("\n".join(json.dumps(row) for row in rows), encoding="utf-8")
    return export_file


def _load_export(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def _candidate(
    canonical_id: str,
    lane: str,
    *,
    title: str,
    abstract: str | None = "This abstract discusses neural coding and robot learning.",
    source: str = "pubmed",
) -> dict:
    doi = canonical_id.removeprefix("doi:") if canonical_id.startswith("doi:") else None
    return {
        "canonical_id": canonical_id,
        "source": source,
        "doi": doi,
        "title": title,
        "abstract": abstract,
        "url": "https://example.org/paper",
        "published_date": "2026-05-18",
        "source_query": f"{lane}:keyword:test",
    }
