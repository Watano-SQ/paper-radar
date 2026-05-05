from __future__ import annotations

from collections.abc import Iterable
from pathlib import Path

from src.models.paper import PaperItem


def export_jsonl(items: Iterable[PaperItem], output_path: Path) -> int:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    count = 0
    with output_path.open("w", encoding="utf-8") as handle:
        for item in items:
            handle.write(item.model_dump_json(exclude_none=False))
            handle.write("\n")
            count += 1
    return count
