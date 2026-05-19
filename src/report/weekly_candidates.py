from __future__ import annotations

import argparse
import json
import os
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

from src.app.config import RuntimeConfig, load_runtime_config
from src.app.runtime import format_runtime_filename
from src.utils.dates import iso_week_label, to_iso_date


DEFAULT_PER_LANE = 20
DEFAULT_EXPORT_FILENAME_TEMPLATE = "candidates_{week}.jsonl"
DEFAULT_WEEKLY_REPORT_FILENAME_TEMPLATE = "weekly_candidates_{week}.md"


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Generate a weekly Markdown candidate pool report.")
    parser.add_argument("--config-dir", type=Path, default=None)
    parser.add_argument("--export-file", type=Path, default=None)
    parser.add_argument("--output-dir", type=Path, default=None)
    parser.add_argument(
        "--per-lane",
        type=int,
        default=int(os.getenv("PAPER_RADAR_REPORT_PER_LANE", DEFAULT_PER_LANE)),
    )
    args = parser.parse_args(argv)
    runtime = load_runtime_config(config_dir=args.config_dir)
    path = generate_weekly_candidate_report(
        export_file=args.export_file,
        output_dir=args.output_dir,
        per_lane=args.per_lane,
        runtime=runtime,
    )
    print(path)


def generate_weekly_candidate_report(
    *,
    export_file: Path | None = None,
    exports_dir: Path | None = None,
    output_dir: Path | None = None,
    week_label: str | None = None,
    per_lane: int = DEFAULT_PER_LANE,
    runtime: RuntimeConfig | None = None,
    export_filename_template: str | None = None,
    weekly_report_filename_template: str | None = None,
) -> Path:
    if runtime is None and (
        exports_dir is None
        or output_dir is None
        or export_filename_template is None
        or weekly_report_filename_template is None
    ):
        runtime = load_runtime_config()
    if runtime is not None:
        exports_dir = exports_dir or runtime.paths.exports_dir
        output_dir = output_dir or runtime.paths.reports_dir
        files_config = runtime.app.get("files", {})
        export_filename_template = export_filename_template or files_config.get(
            "export_filename_template",
            DEFAULT_EXPORT_FILENAME_TEMPLATE,
        )
        weekly_report_filename_template = weekly_report_filename_template or files_config.get(
            "weekly_report_filename_template",
            DEFAULT_WEEKLY_REPORT_FILENAME_TEMPLATE,
        )
    exports_dir = exports_dir or Path("data") / "exports"
    output_dir = output_dir or Path("data") / "reports"
    export_filename_template = export_filename_template or DEFAULT_EXPORT_FILENAME_TEMPLATE
    weekly_report_filename_template = weekly_report_filename_template or DEFAULT_WEEKLY_REPORT_FILENAME_TEMPLATE

    selected_export = export_file or select_export_file(
        exports_dir,
        week_label or iso_week_label(),
        filename_template=export_filename_template,
    )
    if selected_export is None:
        raise FileNotFoundError(f"No candidate export found in {exports_dir}")
    report_week = week_label or _week_from_export(selected_export, export_filename_template) or iso_week_label()
    candidates = load_candidates(selected_export)
    deduped = dedupe_candidates(candidates)
    groups = group_candidates(deduped)

    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / format_runtime_filename(weekly_report_filename_template, week_label=report_week)
    output_path.write_text(
        render_report(
            groups=groups,
            all_candidates=deduped,
            export_file=selected_export,
            week_label=report_week,
            per_lane=per_lane,
        ),
        encoding="utf-8",
    )
    return output_path


def select_export_file(
    exports_dir: Path,
    current_week: str,
    *,
    filename_template: str = DEFAULT_EXPORT_FILENAME_TEMPLATE,
) -> Path | None:
    current = exports_dir / format_runtime_filename(filename_template, week_label=current_week)
    if current.exists():
        return current
    if not exports_dir.exists():
        return None
    candidates = sorted(
        exports_dir.glob(_template_glob(filename_template)),
        key=lambda path: path.stat().st_mtime,
        reverse=True,
    )
    return candidates[0] if candidates else None


def load_candidates(path: Path) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if not line:
                continue
            try:
                item = json.loads(line)
            except json.JSONDecodeError:
                continue
            if isinstance(item, dict):
                items.append(item)
    return items


def dedupe_candidates(candidates: list[dict[str, Any]]) -> list[dict[str, Any]]:
    best_by_id: dict[str, dict[str, Any]] = {}
    no_id: list[dict[str, Any]] = []
    for candidate in candidates:
        canonical_id = str(candidate.get("canonical_id") or "").strip()
        if not canonical_id:
            no_id.append(candidate)
            continue
        existing = best_by_id.get(canonical_id)
        if existing is None or candidate_score(candidate) > candidate_score(existing):
            best_by_id[canonical_id] = candidate
    return [*best_by_id.values(), *no_id]


def group_candidates(candidates: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    groups: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for candidate in candidates:
        groups[_lane_from_source_query(candidate.get("source_query"))].append(candidate)
    return dict(groups)


def render_report(
    *,
    groups: dict[str, list[dict[str, Any]]],
    all_candidates: list[dict[str, Any]],
    export_file: Path,
    week_label: str,
    per_lane: int,
) -> str:
    sources = Counter(str(item.get("source") or "unknown") for item in all_candidates)
    source_queries = Counter(str(item.get("source_query") or "unknown") for item in all_candidates)
    lines = [
        f"# Weekly Candidate Pool: {week_label}",
        "",
        "This file is a candidate pool for later screening. It is not a reading list.",
        "",
        "## Summary",
        "",
        f"- Total candidates: {len(all_candidates)}",
        f"- Sources: {_format_counter(sources)}",
        f"- Lanes / source queries: {len(groups)} lanes, {len(source_queries)} source queries",
        f"- Export file: {export_file}",
        "",
    ]
    for lane in sorted(groups):
        ranked = sorted(groups[lane], key=candidate_score, reverse=True)[:per_lane]
        lines.extend([f"## {lane}", ""])
        for index, item in enumerate(ranked, start=1):
            lines.extend(_render_candidate(index, item))
        if not ranked:
            lines.append("_No candidates._")
            lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def candidate_score(candidate: dict[str, Any]) -> tuple[int, str]:
    score = 0
    if candidate.get("abstract"):
        score += 8
    if candidate.get("doi") or candidate.get("arxiv_id") or candidate.get("pmid"):
        score += 4
    if candidate.get("url") or candidate.get("oa_url"):
        score += 2
    if candidate.get("canonical_id"):
        score += 1
    date_value = to_iso_date(candidate.get("published_date")) or ""
    return score, date_value


def _render_candidate(index: int, item: dict[str, Any]) -> list[str]:
    title = _clean_inline(item.get("title")) or "Untitled"
    lines = [
        f"### {index}. {title}",
        "",
        f"- Source: {_clean_inline(item.get('source')) or 'unknown'}",
        f"- Date: {_clean_inline(item.get('published_date')) or _clean_inline(item.get('year')) or 'unknown'}",
        f"- Authors: {_short_authors(item.get('authors'))}",
        f"- Venue: {_clean_inline(item.get('venue')) or 'unknown'}",
        f"- IDs: {_ids(item)}",
        f"- URL: {_clean_inline(item.get('url') or item.get('oa_url')) or 'missing'}",
        f"- Source query: {_clean_inline(item.get('source_query')) or 'unknown'}",
        f"- Fields / keywords: {_join_values([*_as_list(item.get('fields')), *_as_list(item.get('keywords'))]) or 'missing'}",
        f"- Abstract preview: {_preview(item.get('abstract'))}",
        "",
    ]
    return lines


def _lane_from_source_query(value: Any) -> str:
    if not value:
        return "unassigned"
    text = str(value)
    return text.split(":", 1)[0] or "unassigned"


def _ids(item: dict[str, Any]) -> str:
    values = []
    if item.get("doi"):
        values.append(f"DOI: {item['doi']}")
    if item.get("arxiv_id"):
        values.append(f"arXiv: {item['arxiv_id']}")
    if item.get("pmid"):
        values.append(f"PMID: {item['pmid']}")
    if not values and item.get("canonical_id"):
        values.append(f"Canonical: {item['canonical_id']}")
    return "; ".join(values) if values else "missing"


def _short_authors(value: Any, limit: int = 3) -> str:
    authors = _as_list(value)
    if not authors:
        return "unknown"
    if len(authors) <= limit:
        return ", ".join(authors)
    return f"{', '.join(authors[:limit])}, et al."


def _preview(value: Any, limit: int = 500) -> str:
    text = _clean_inline(value)
    if not text:
        return "missing"
    if len(text) <= limit:
        return text
    return text[: limit - 3].rstrip() + "..."


def _format_counter(counter: Counter[str]) -> str:
    if not counter:
        return "none"
    return ", ".join(f"{key}={value}" for key, value in sorted(counter.items()))


def _join_values(values: list[str]) -> str:
    return ", ".join(dict.fromkeys(value for value in values if value))


def _as_list(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    text = str(value).strip()
    return [text] if text else []


def _clean_inline(value: Any) -> str | None:
    if value is None:
        return None
    text = " ".join(str(value).split())
    return text or None


def _template_glob(template: str) -> str:
    return format_runtime_filename(template, week_label="*")


def _week_from_export(path: Path, filename_template: str = DEFAULT_EXPORT_FILENAME_TEMPLATE) -> str | None:
    name = path.name
    marker = "{week}"
    if marker not in filename_template:
        return None
    prefix, suffix = filename_template.split(marker, 1)
    if name.startswith(prefix) and name.endswith(suffix):
        return name[len(prefix) : len(name) - len(suffix) if suffix else len(name)]
    return None


if __name__ == "__main__":
    main()
