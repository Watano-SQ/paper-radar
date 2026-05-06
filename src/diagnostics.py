from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Any


ROOT = Path.cwd() if (Path.cwd() / "config" / "sources.yaml").exists() else Path(__file__).resolve().parents[1]


def collect_diagnostics(
    db_path: Path | None = None,
    exports_dir: Path | None = None,
) -> dict[str, Any]:
    db_path = db_path or ROOT / "data" / "papers.sqlite"
    exports_dir = exports_dir or ROOT / "data" / "exports"
    latest_export = _latest_export(exports_dir)
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


def main() -> None:
    print(format_diagnostics(collect_diagnostics()))


def _scalar(conn: sqlite3.Connection, query: str) -> int:
    row = conn.execute(query).fetchone()
    return int(row[0])


def _latest_export(exports_dir: Path) -> Path | None:
    if not exports_dir.exists():
        return None
    candidates = sorted(exports_dir.glob("candidates_*.jsonl"), key=lambda path: path.stat().st_mtime, reverse=True)
    return candidates[0] if candidates else None


if __name__ == "__main__":
    main()
