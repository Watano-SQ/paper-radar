from __future__ import annotations

from pathlib import Path

from src.app.config import RuntimeConfig
from src.utils.dates import iso_week_label


def format_runtime_filename(template: str, *, week_label: str | None = None) -> str:
    return template.format(week=week_label or iso_week_label())


def candidate_export_path(runtime: RuntimeConfig, *, week_label: str | None = None) -> Path:
    template = runtime.app.get("files", {}).get("export_filename_template", "candidates_{week}.jsonl")
    return runtime.paths.exports_dir / format_runtime_filename(template, week_label=week_label)


def weekly_report_path(runtime: RuntimeConfig, *, week_label: str | None = None) -> Path:
    template = runtime.app.get("files", {}).get(
        "weekly_report_filename_template",
        "weekly_candidates_{week}.md",
    )
    return runtime.paths.reports_dir / format_runtime_filename(template, week_label=week_label)


def reject_log_path(runtime: RuntimeConfig, *, week_label: str | None = None) -> Path:
    template = runtime.app.get("files", {}).get(
        "reject_log_filename_template",
        "rejected_candidates_{week}.md",
    )
    return runtime.paths.reports_dir / format_runtime_filename(template, week_label=week_label)


def score_audit_path(runtime: RuntimeConfig, *, week_label: str | None = None) -> Path:
    template = runtime.app.get("files", {}).get(
        "score_audit_filename_template",
        "score_audit_{week}.md",
    )
    return runtime.paths.reports_dir / format_runtime_filename(template, week_label=week_label)
