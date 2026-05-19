from __future__ import annotations

import argparse
import sqlite3
from pathlib import Path
from typing import Any

from src.app.config import RuntimeConfig, load_runtime_config


def collect_diagnostics(
    db_path: Path | None = None,
    exports_dir: Path | None = None,
    runtime: RuntimeConfig | None = None,
    export_filename_template: str | None = None,
) -> dict[str, Any]:
    if runtime is None and (db_path is None or exports_dir is None):
        runtime = load_runtime_config()
    if runtime is not None:
        db_path = db_path or runtime.paths.database_path
        exports_dir = exports_dir or runtime.paths.exports_dir
        export_filename_template = export_filename_template or runtime.app.get("files", {}).get(
            "export_filename_template"
        )
    if db_path is None or exports_dir is None:
        raise ValueError("db_path and exports_dir are required when runtime is not available")
    latest_export = _latest_export(exports_dir, export_filename_template)
    result: dict[str, Any] = {
        "db_path": str(db_path),
        "papers_count": None,
        "paper_sources_count": None,
        "crawl_runs": [],
        "possible_duplicates_count": None,
        "latest_export": str(latest_export) if latest_export else None,
    }
    if not db_path.exists():
        result["error"] = f"SQLite database not found: {db_path}"
        return result

    conn = sqlite3.connect(db_path)
    try:
        result["papers_count"] = _scalar(conn, "select count(*) from papers")
        result["paper_sources_count"] = _scalar(conn, "select count(*) from paper_sources")
        result["possible_duplicates_count"] = _scalar(conn, "select count(*) from possible_duplicates")
        result["crawl_runs"] = [
            {"source": source, "status": status, "count": count}
            for source, status, count in conn.execute(
                "select source, status, count(*) from crawl_runs group by source, status order by source, status"
            ).fetchall()
        ]
    finally:
        conn.close()
    return result


def format_diagnostics(diagnostics: dict[str, Any]) -> str:
    lines = [
        f"db_path: {diagnostics.get('db_path')}",
        f"papers_count: {diagnostics.get('papers_count')}",
        f"paper_sources_count: {diagnostics.get('paper_sources_count')}",
        "crawl_runs:",
    ]
    for row in diagnostics.get("crawl_runs", []):
        lines.append(f"  {row['source']} | {row['status']} | {row['count']}")
    lines.extend(
        [
            f"possible_duplicates_count: {diagnostics.get('possible_duplicates_count')}",
            f"latest_export: {diagnostics.get('latest_export')}",
        ]
    )
    if diagnostics.get("error"):
        lines.append(f"error: {diagnostics['error']}")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Inspect local Paper Radar runtime state.")
    parser.add_argument("--config-dir", type=Path, default=None)
    args = parser.parse_args(argv)
    runtime = load_runtime_config(config_dir=args.config_dir)
    print(format_diagnostics(collect_diagnostics(runtime=runtime)))


def _scalar(conn: sqlite3.Connection, query: str) -> int:
    row = conn.execute(query).fetchone()
    return int(row[0])


def _latest_export(exports_dir: Path, filename_template: str | None = None) -> Path | None:
    if not exports_dir.exists():
        return None
    pattern = (filename_template or "candidates_{week}.jsonl").format(week="*")
    candidates = sorted(exports_dir.glob(pattern), key=lambda path: path.stat().st_mtime, reverse=True)
    return candidates[0] if candidates else None


if __name__ == "__main__":
    main()
