from __future__ import annotations

from collections import defaultdict
from pathlib import Path
from typing import Any

from src.ranking.balance import BalancedSelection, CandidateDecision


def render_reject_log(
    selection: BalancedSelection,
    *,
    week_label: str,
    max_per_reason: int,
) -> str:
    grouped: dict[str, list[CandidateDecision]] = defaultdict(list)
    for decision in [*selection.rejected, *selection.downranked]:
        grouped[decision.reason].append(decision)

    lines = [
        f"# Rejected / Downranked Candidates: {week_label}",
        "",
        "This file is for debugging candidate filtering. It is not a reading list.",
        "",
        "## Summary",
        "",
        f"- Total input candidates: {selection.total_input}",
        f"- Selected candidates: {selection.selected_count}",
        f"- Rejected candidates: {len(selection.rejected)}",
        f"- Downranked candidates: {len(selection.downranked)}",
        "",
    ]
    for reason in sorted(grouped):
        lines.extend([f"## {reason}", ""])
        for decision in grouped[reason][:max_per_reason]:
            lines.extend(_render_reject_item(decision))
        omitted = len(grouped[reason]) - max_per_reason
        if omitted > 0:
            lines.append(f"_Omitted {omitted} additional candidates for this reason._")
            lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def write_reject_log(path: Path, selection: BalancedSelection, *, week_label: str, max_per_reason: int) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(render_reject_log(selection, week_label=week_label, max_per_reason=max_per_reason), encoding="utf-8")
    return path


def _render_reject_item(decision: CandidateDecision) -> list[str]:
    candidate = decision.scored.candidate
    score = decision.scored.score
    return [
        f"### {_clean(candidate.get('title')) or 'Untitled'}",
        "",
        f"- Source: {_clean(candidate.get('source')) or 'unknown'}",
        f"- Source query: {_clean(candidate.get('source_query')) or 'unknown'}",
        f"- Score: {score.total:g}",
        f"- Candidate level: {score.level}",
        f"- Reason: {decision.reason}",
        "",
    ]


def _clean(value: Any) -> str | None:
    if value is None:
        return None
    text = " ".join(str(value).split())
    return text or None
