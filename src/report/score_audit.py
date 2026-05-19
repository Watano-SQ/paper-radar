from __future__ import annotations

import argparse
from collections import Counter, defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from src.app.config import RuntimeConfig, load_runtime_config
from src.app.runtime import score_audit_path
from src.ranking.balance import BalancedSelection, CandidateDecision, select_balanced_candidates
from src.ranking.config import scoring_section
from src.ranking.scoring import CANDIDATE_LEVELS, ScoredCandidate, score_candidates
from src.report.weekly_candidates import candidate_score, dedupe_candidates, group_candidates, load_candidates, select_export_file
from src.utils.dates import iso_week_label


@dataclass(frozen=True)
class LaneStats:
    selected: int
    rejected: int
    downranked: int
    avg_score: float
    max_score: float
    input_count: int


@dataclass(frozen=True)
class SourceStats:
    count: int
    avg_score: float


@dataclass(frozen=True)
class ComponentStats:
    count: int
    total: float


@dataclass(frozen=True)
class ScoreAudit:
    week_label: str
    export_file: Path
    selection: BalancedSelection
    scored_candidates: list[ScoredCandidate]
    level_counts: dict[str, int]
    lane_stats: dict[str, LaneStats]
    source_stats: dict[str, SourceStats]
    component_stats: dict[str, ComponentStats]
    penalty_stats: dict[str, int]
    near_threshold: list[tuple[ScoredCandidate, str]]
    calibration_notes: list[str]
    scoring_config_path: Path
    lane_balance: dict[str, Any]


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Generate a Paper Radar score calibration audit report.")
    parser.add_argument("--config-dir", type=Path, default=None)
    parser.add_argument("--export-file", type=Path, default=None)
    parser.add_argument("--output-dir", type=Path, default=None)
    parser.add_argument("--per-lane", type=int, default=None)
    parser.add_argument("--compare-no-scoring", action="store_true")
    args = parser.parse_args(argv)

    runtime = load_runtime_config(config_dir=args.config_dir)
    output_path = generate_score_audit_report(
        runtime=runtime,
        export_file=args.export_file,
        output_dir=args.output_dir,
        per_lane=args.per_lane,
        compare_no_scoring=args.compare_no_scoring,
    )
    print(output_path)


def generate_score_audit_report(
    *,
    runtime: RuntimeConfig | None = None,
    export_file: Path | None = None,
    exports_dir: Path | None = None,
    output_dir: Path | None = None,
    week_label: str | None = None,
    per_lane: int | None = None,
    compare_no_scoring: bool = False,
) -> Path:
    runtime = runtime or load_runtime_config()
    exports_dir = exports_dir or runtime.paths.exports_dir
    output_dir = output_dir or runtime.paths.reports_dir
    export_template = runtime.app.get("files", {}).get("export_filename_template", "candidates_{week}.jsonl")
    selected_export = export_file or select_export_file(exports_dir, week_label or iso_week_label(), filename_template=export_template)
    if selected_export is None:
        raise FileNotFoundError(f"No candidate export found in {exports_dir}")
    audit_week = week_label or _week_from_export(selected_export, export_template) or iso_week_label()
    candidates = load_candidates(selected_export)
    audit = build_score_audit(candidates, runtime, export_file=selected_export, week_label=audit_week, per_lane=per_lane)

    output_dir.mkdir(parents=True, exist_ok=True)
    path = (
        score_audit_path(runtime, week_label=audit_week)
        if output_dir == runtime.paths.reports_dir
        else output_dir / runtime.app.get("files", {}).get("score_audit_filename_template", "score_audit_{week}.md").format(week=audit_week)
    )
    path.write_text(render_score_audit(audit, compare_no_scoring=compare_no_scoring), encoding="utf-8")
    return path


def build_score_audit(
    candidates: list[dict[str, Any]],
    runtime: RuntimeConfig,
    *,
    export_file: Path | None = None,
    week_label: str | None = None,
    per_lane: int | None = None,
) -> ScoreAudit:
    scored = score_candidates(candidates, runtime.scoring, runtime.topics)
    selection = select_balanced_candidates(scored, runtime.scoring, max_per_lane=per_lane)
    section = scoring_section(runtime.scoring)
    lane_balance = dict(section.get("lane_balance", {}))
    if per_lane is not None:
        lane_balance["max_per_lane"] = per_lane

    audit = ScoreAudit(
        week_label=week_label or iso_week_label(),
        export_file=export_file or Path("<memory>"),
        selection=selection,
        scored_candidates=scored,
        level_counts=_level_counts(scored),
        lane_stats=_lane_stats(scored, selection),
        source_stats=_source_stats(selection),
        component_stats=_component_stats(scored),
        penalty_stats=_penalty_stats(scored),
        near_threshold=_near_threshold(scored, section.get("thresholds", {})),
        calibration_notes=[],
        scoring_config_path=runtime.paths.scoring_config_path,
        lane_balance=lane_balance,
    )
    return audit.__class__(
        **{
            **audit.__dict__,
            "calibration_notes": _calibration_notes(audit),
        }
    )


def render_score_audit(audit: ScoreAudit, *, compare_no_scoring: bool = False) -> str:
    lines = [
        f"# Score Audit: {audit.week_label}",
        "",
        "This file audits candidate scoring behavior. It is not a reading list.",
        "",
        "## Summary",
        "",
        f"- Total input candidates: {audit.selection.total_input}",
        f"- Selected candidates: {audit.selection.selected_count}",
        f"- Rejected candidates: {len(audit.selection.rejected)}",
        f"- Downranked candidates: {len(audit.selection.downranked)}",
        f"- Export file: {audit.export_file}",
        f"- Scoring config: {audit.scoring_config_path}",
        "- Lane balance:",
        f"  - max_per_lane: {audit.lane_balance.get('max_per_lane')}",
        f"  - min_per_active_lane: {audit.lane_balance.get('min_per_active_lane')}",
        f"  - global_max: {audit.lane_balance.get('global_max')}",
        "",
        "## Candidate Levels",
        "",
        "| Level | Count |",
        "|---|---:|",
    ]
    for level in CANDIDATE_LEVELS:
        lines.append(f"| {level} | {audit.level_counts.get(level, 0)} |")

    lines.extend(["", "## Selected By Lane", "", "| Lane | Selected | Rejected | Downranked | Avg score | Max score |", "|---|---:|---:|---:|---:|---:|"])
    for lane, stats in sorted(audit.lane_stats.items()):
        lines.append(
            f"| {_cell(lane)} | {stats.selected} | {stats.rejected} | {stats.downranked} | {stats.avg_score:.1f} | {stats.max_score:.1f} |"
        )

    lines.extend(["", "## Selected By Source", "", "| Source | Count | Avg score |", "|---|---:|---:|"])
    for source, stats in sorted(audit.source_stats.items()):
        lines.append(f"| {_cell(source)} | {stats.count} | {stats.avg_score:.1f} |")

    lines.extend(["", "## Top Score Components", "", "| Component | Count | Total contribution |", "|---|---:|---:|"])
    for component, stats in _top_items(audit.component_stats, key=lambda item: item[1].total):
        lines.append(f"| {_cell(component)} | {stats.count} | {stats.total:.1f} |")

    lines.extend(["", "## Top Penalties", "", "| Penalty | Count |", "|---|---:|"])
    for penalty, count in audit.penalty_stats.most_common(10) if isinstance(audit.penalty_stats, Counter) else Counter(audit.penalty_stats).most_common(10):
        lines.append(f"| {_cell(penalty)} | {count} |")

    lines.extend(["", "## Near-Threshold Candidates", "", "Candidates within 1.0 point of a threshold.", "", "| Title | Lane | Level | Score | Nearest threshold | Source query |", "|---|---|---|---:|---|---|"])
    for scored, threshold_name in audit.near_threshold[:20]:
        lines.append(
            f"| {_cell(scored.candidate.get('title') or 'Untitled')} | {_cell(scored.lane)} | {scored.score.level} | {scored.score.total:.1f} | {threshold_name} | {_cell(scored.candidate.get('source_query') or 'unknown')} |"
        )

    lines.extend(["", "## Top Selected Candidates", ""])
    for scored in _selected_sorted(audit, reverse=True)[:10]:
        lines.extend(_render_candidate_brief(scored))

    lines.extend(["", "## Bottom Selected Candidates", ""])
    for scored in _selected_sorted(audit, reverse=False)[:10]:
        lines.extend(_render_candidate_brief(scored))

    lines.extend(["", "## Rejected / Downranked Summary", "", "| Reason | Count |", "|---|---:|"])
    reason_counts = Counter(decision.reason for decision in [*audit.selection.rejected, *audit.selection.downranked])
    for reason, count in reason_counts.most_common(10):
        lines.append(f"| {_cell(reason)} | {count} |")

    if compare_no_scoring:
        comparison = _compare_no_scoring(audit)
        lines.extend(
            [
                "",
                "## Comparison With No-Scoring Metadata Ranking",
                "",
                f"- Scored selected: {comparison['scored_selected']}",
                f"- No-scoring selected: {comparison['no_scoring_selected']}",
                f"- Overlap: {comparison['overlap']}",
                f"- Only in scored: {comparison['only_scored']}",
                f"- Only in no-scoring: {comparison['only_no_scoring']}",
            ]
        )

    lines.extend(["", "## Calibration Notes", ""])
    if audit.calibration_notes:
        lines.extend(f"- {note}" for note in audit.calibration_notes)
    else:
        lines.append("- No automatic calibration notes.")
    return "\n".join(lines).rstrip() + "\n"


def _level_counts(scored: list[ScoredCandidate]) -> dict[str, int]:
    counts = Counter(item.score.level for item in scored)
    return {level: counts.get(level, 0) for level in CANDIDATE_LEVELS}


def _lane_stats(scored: list[ScoredCandidate], selection: BalancedSelection) -> dict[str, LaneStats]:
    lanes = {item.lane for item in scored}
    rejected_by_lane = Counter(decision.scored.lane for decision in selection.rejected)
    downranked_by_lane = Counter(decision.scored.lane for decision in selection.downranked)
    input_by_lane = Counter(item.lane for item in scored)
    output: dict[str, LaneStats] = {}
    for lane in lanes:
        selected = selection.selected_by_lane.get(lane, [])
        scores = [item.score.total for item in selected]
        output[lane] = LaneStats(
            selected=len(selected),
            rejected=rejected_by_lane.get(lane, 0),
            downranked=downranked_by_lane.get(lane, 0),
            avg_score=round(sum(scores) / len(scores), 2) if scores else 0.0,
            max_score=max(scores) if scores else 0.0,
            input_count=input_by_lane.get(lane, 0),
        )
    return output


def _source_stats(selection: BalancedSelection) -> dict[str, SourceStats]:
    grouped: dict[str, list[float]] = defaultdict(list)
    for scored in _selected(selection):
        grouped[str(scored.candidate.get("source") or "unknown")].append(scored.score.total)
    return {
        source: SourceStats(count=len(scores), avg_score=round(sum(scores) / len(scores), 2))
        for source, scores in grouped.items()
    }


def _component_stats(scored: list[ScoredCandidate]) -> dict[str, ComponentStats]:
    counts: Counter[str] = Counter()
    totals: Counter[str] = Counter()
    for item in scored:
        for component, value in item.score.components.items():
            counts[component] += 1
            totals[component] += value
    return {component: ComponentStats(count=counts[component], total=round(totals[component], 2)) for component in counts}


def _penalty_stats(scored: list[ScoredCandidate]) -> Counter[str]:
    counts: Counter[str] = Counter()
    for item in scored:
        counts.update(item.score.penalties)
    return counts


def _near_threshold(scored: list[ScoredCandidate], thresholds: dict[str, Any]) -> list[tuple[ScoredCandidate, str]]:
    values = {
        "s_candidate_min": float(thresholds.get("s_candidate_min", 18)),
        "a_candidate_min": float(thresholds.get("a_candidate_min", 13)),
        "b_candidate_min": float(thresholds.get("b_candidate_min", 8)),
        "c_candidate_min": float(thresholds.get("c_candidate_min", 4)),
    }
    near: list[tuple[ScoredCandidate, str]] = []
    for item in scored:
        closest_name, closest_value = min(values.items(), key=lambda pair: abs(item.score.total - pair[1]))
        if abs(item.score.total - closest_value) <= 1.0:
            near.append((item, closest_name))
    return sorted(near, key=lambda pair: abs(pair[0].score.total - values[pair[1]]))


def _calibration_notes(audit: ScoreAudit) -> list[str]:
    notes: list[str] = []
    selected_total = max(audit.selection.selected_count, 1)
    for lane, stats in sorted(audit.lane_stats.items()):
        if stats.selected / selected_total > 0.5 and audit.selection.selected_count > 1:
            notes.append(f"Lane `{lane}` dominates selected candidates.")
        if stats.input_count > 0 and stats.selected == 0:
            notes.append(f"Lane `{lane}` has input candidates but no selected candidates.")

    missing_abstract_count = audit.penalty_stats.get("missing abstract", 0)
    if audit.selection.total_input and missing_abstract_count / audit.selection.total_input > 0.3:
        notes.append("Missing abstracts are common; check source quality or penalty strength.")
    review_count = sum(1 for item in audit.scored_candidates if "review/survey signal" in item.score.reasons)
    if review_count < 2:
        notes.append("Review/survey signal is rare this week.")
    selected = _selected(audit.selection)
    c_selected = sum(1 for item in selected if item.score.level == "C_candidate")
    if selected and c_selected / len(selected) > 0.3:
        notes.append("Lane balance may be pulling in weak candidates.")
    if len(audit.selection.downranked) > audit.selection.selected_count:
        notes.append("Lane/global limits are restrictive this week.")
    if audit.penalty_stats.get("benchmark-only / narrow technical update signal", 0) >= 2:
        notes.append("Benchmark penalty appears often this week.")
    return notes


def _selected(selection: BalancedSelection) -> list[ScoredCandidate]:
    return [item for lane_items in selection.selected_by_lane.values() for item in lane_items]


def _selected_sorted(audit: ScoreAudit, *, reverse: bool) -> list[ScoredCandidate]:
    return sorted(_selected(audit.selection), key=lambda item: (item.score.total, str(item.candidate.get("title") or "")), reverse=reverse)


def _render_candidate_brief(scored: ScoredCandidate) -> list[str]:
    return [
        f"### {_clean(scored.candidate.get('title')) or 'Untitled'}",
        "",
        f"- Lane: {scored.lane}",
        f"- Source: {_clean(scored.candidate.get('source')) or 'unknown'}",
        f"- Score: {scored.score.total:.1f}",
        f"- Level: {scored.score.level}",
        f"- Reasons: {', '.join(scored.score.reasons) if scored.score.reasons else 'none'}",
        f"- Penalties: {', '.join(scored.score.penalties) if scored.score.penalties else 'none'}",
        "",
    ]


def _compare_no_scoring(audit: ScoreAudit) -> dict[str, int]:
    candidates = [item.candidate for item in audit.scored_candidates]
    grouped = group_candidates(dedupe_candidates(candidates))
    max_per_lane = int(audit.lane_balance.get("max_per_lane") or 20)
    no_scoring_selected: list[dict[str, Any]] = []
    for lane in sorted(grouped):
        no_scoring_selected.extend(sorted(grouped[lane], key=candidate_score, reverse=True)[:max_per_lane])
    scored_ids = {_candidate_key(item.candidate) for item in _selected(audit.selection)}
    no_scoring_ids = {_candidate_key(item) for item in no_scoring_selected}
    overlap = scored_ids & no_scoring_ids
    return {
        "scored_selected": len(scored_ids),
        "no_scoring_selected": len(no_scoring_ids),
        "overlap": len(overlap),
        "only_scored": len(scored_ids - no_scoring_ids),
        "only_no_scoring": len(no_scoring_ids - scored_ids),
    }


def _candidate_key(candidate: dict[str, Any]) -> str:
    return str(candidate.get("canonical_id") or candidate.get("title") or "")


def _top_items(data: dict[str, ComponentStats], *, key: Any) -> list[tuple[str, ComponentStats]]:
    return sorted(data.items(), key=key, reverse=True)[:10]


def _week_from_export(path: Path, filename_template: str) -> str | None:
    marker = "{week}"
    if marker not in filename_template:
        return None
    prefix, suffix = filename_template.split(marker, 1)
    name = path.name
    if name.startswith(prefix) and name.endswith(suffix):
        return name[len(prefix) : len(name) - len(suffix) if suffix else len(name)]
    return None


def _cell(value: Any) -> str:
    return _clean(value).replace("|", "\\|")


def _clean(value: Any) -> str:
    if value is None:
        return ""
    return " ".join(str(value).split())


if __name__ == "__main__":
    main()
