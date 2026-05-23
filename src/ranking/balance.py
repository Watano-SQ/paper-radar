from __future__ import annotations

from dataclasses import dataclass
from difflib import SequenceMatcher
from typing import Any

from src.ranking.config import scoring_section
from src.ranking.scoring import ScoredCandidate, is_repository_like_candidate, normalize_title_for_dedupe
from src.utils.dates import to_iso_date


@dataclass(frozen=True)
class CandidateDecision:
    scored: ScoredCandidate
    reason: str


@dataclass(frozen=True)
class BalancedSelection:
    selected_by_lane: dict[str, list[ScoredCandidate]]
    rejected: list[CandidateDecision]
    downranked: list[CandidateDecision]
    total_input: int

    @property
    def selected_count(self) -> int:
        return sum(len(items) for items in self.selected_by_lane.values())


def select_balanced_candidates(
    scored_candidates: list[ScoredCandidate],
    scoring_config: dict[str, Any],
    *,
    max_per_lane: int | None = None,
) -> BalancedSelection:
    config = scoring_section(scoring_config)
    lane_balance = config.get("lane_balance", {})
    reject_config = config.get("reject", {})
    effective_max_per_lane = int(lane_balance.get("max_per_lane", 20) if max_per_lane is None else max_per_lane)
    min_per_active_lane = int(lane_balance.get("min_per_active_lane", 3))
    global_max = int(lane_balance.get("global_max", 120))

    rejected: list[CandidateDecision] = []
    downranked: list[CandidateDecision] = []
    eligible: list[ScoredCandidate] = []
    for scored in scored_candidates:
        if scored.score.level == "reject":
            rejected.append(CandidateDecision(scored, _reject_reason(scored)))
        else:
            eligible.append(scored)

    if reject_config.get("hard_reject_duplicate_canonical_id", True):
        eligible, duplicate_rejects = _dedupe_by_canonical_id(eligible)
        rejected.extend(duplicate_rejects)

    eligible, duplicate_downranks = _suppress_near_duplicate_titles(eligible, config)
    downranked.extend(duplicate_downranks)

    by_lane: dict[str, list[ScoredCandidate]] = {}
    for scored in eligible:
        by_lane.setdefault(scored.lane, []).append(scored)
    for lane in by_lane:
        by_lane[lane] = sorted(by_lane[lane], key=_sort_key, reverse=True)

    selected_by_lane: dict[str, list[ScoredCandidate]] = {lane: [] for lane in by_lane}
    selected_keys: set[int] = set()

    for lane in sorted(by_lane):
        guaranteed = min(min_per_active_lane, effective_max_per_lane, len(by_lane[lane]))
        for scored in by_lane[lane][:guaranteed]:
            if _total_selected(selected_by_lane) >= global_max:
                break
            selected_by_lane[lane].append(scored)
            selected_keys.add(id(scored))

    remaining = sorted(
        [scored for scored in eligible if id(scored) not in selected_keys],
        key=_sort_key,
        reverse=True,
    )
    for scored in remaining:
        if _total_selected(selected_by_lane) >= global_max:
            downranked.append(CandidateDecision(scored, "Global candidate limit"))
            continue
        lane_selected = selected_by_lane.setdefault(scored.lane, [])
        if len(lane_selected) >= effective_max_per_lane:
            downranked.append(CandidateDecision(scored, "Lane balance limit"))
            continue
        lane_selected.append(scored)
        selected_keys.add(id(scored))

    for lane in list(selected_by_lane):
        selected_by_lane[lane] = sorted(selected_by_lane[lane], key=_sort_key, reverse=True)
        if not selected_by_lane[lane]:
            del selected_by_lane[lane]

    return BalancedSelection(
        selected_by_lane=selected_by_lane,
        rejected=rejected,
        downranked=downranked,
        total_input=len(scored_candidates),
    )


def _dedupe_by_canonical_id(
    candidates: list[ScoredCandidate],
) -> tuple[list[ScoredCandidate], list[CandidateDecision]]:
    grouped: dict[str, list[ScoredCandidate]] = {}
    no_id: list[ScoredCandidate] = []
    for scored in candidates:
        canonical_id = str(scored.candidate.get("canonical_id") or "").strip()
        if not canonical_id:
            no_id.append(scored)
            continue
        grouped.setdefault(canonical_id, []).append(scored)

    kept: list[ScoredCandidate] = [*no_id]
    rejected: list[CandidateDecision] = []
    for group in grouped.values():
        ranked = sorted(group, key=_sort_key, reverse=True)
        kept.append(ranked[0])
        for duplicate in ranked[1:]:
            rejected.append(CandidateDecision(duplicate, "Duplicate canonical ID"))
    return kept, rejected


def _suppress_near_duplicate_titles(
    candidates: list[ScoredCandidate],
    config: dict[str, Any],
) -> tuple[list[ScoredCandidate], list[CandidateDecision]]:
    groups: list[list[ScoredCandidate]] = []
    no_title: list[ScoredCandidate] = []
    for scored in candidates:
        normalized_title = normalize_title_for_dedupe(scored.candidate.get("title"))
        if not normalized_title:
            no_title.append(scored)
            continue
        for group in groups:
            group_title = normalize_title_for_dedupe(group[0].candidate.get("title"))
            if _near_duplicate_title(normalized_title, group_title):
                group.append(scored)
                break
        else:
            groups.append([scored])

    kept: list[ScoredCandidate] = [*no_title]
    downranked: list[CandidateDecision] = []
    for group in groups:
        if len(group) == 1:
            kept.append(group[0])
            continue
        keep = _best_title_duplicate(group, config)
        kept.append(keep)
        for duplicate in group:
            if duplicate is not keep:
                downranked.append(CandidateDecision(duplicate, "Near-duplicate title"))
    return kept, downranked


def _near_duplicate_title(left: str, right: str) -> bool:
    if not left or not right:
        return False
    if left == right:
        return True
    return SequenceMatcher(a=left, b=right).ratio() >= 0.96


def _best_title_duplicate(group: list[ScoredCandidate], config: dict[str, Any]) -> ScoredCandidate:
    highest_score = max(item.score.total for item in group)
    close_candidates = [item for item in group if highest_score - item.score.total <= 1.0]
    return max(close_candidates, key=lambda item: (_source_preference(item, config), *_sort_key(item)))


def _source_preference(scored: ScoredCandidate, config: dict[str, Any]) -> int:
    source = str(scored.candidate.get("source") or "").casefold()
    signals = config.get("signals", {})
    if source == "arxiv":
        return 3
    if source == "openalex" and not is_repository_like_candidate(scored.candidate, signals):
        return 2
    if source == "openalex":
        return 1
    return 0


def _reject_reason(scored: ScoredCandidate) -> str:
    penalties = scored.score.penalties
    if any("missing title" in penalty for penalty in penalties):
        return "Missing metadata"
    if any("missing abstract and URL" in penalty for penalty in penalties):
        return "Missing metadata"
    if any("benchmark-only" in penalty for penalty in penalties):
        return "Benchmark-only / narrow technical update"
    if any("too short metadata" in penalty for penalty in penalties):
        return "Missing metadata"
    return "Below candidate threshold"


def _sort_key(scored: ScoredCandidate) -> tuple[float, str, str]:
    date_value = to_iso_date(scored.candidate.get("published_date")) or ""
    title = str(scored.candidate.get("title") or "")
    return scored.score.total, date_value, title


def _total_selected(selected_by_lane: dict[str, list[ScoredCandidate]]) -> int:
    return sum(len(items) for items in selected_by_lane.values())
