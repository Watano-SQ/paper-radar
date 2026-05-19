from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Any

from src.ranking.config import scoring_section
from src.utils.dates import to_iso_date, utc_now


CANDIDATE_LEVELS = ("S_candidate", "A_candidate", "B_candidate", "C_candidate", "reject")


@dataclass(frozen=True)
class ScoreBreakdown:
    total: float
    level: str
    components: dict[str, float]
    reasons: list[str]
    penalties: list[str]


@dataclass(frozen=True)
class ScoredCandidate:
    candidate: dict[str, Any]
    lane: str
    score: ScoreBreakdown


def score_candidates(
    candidates: list[dict[str, Any]],
    scoring_config: dict[str, Any],
    topics: dict[str, Any],
    *,
    today: date | None = None,
) -> list[ScoredCandidate]:
    return [score_candidate(candidate, scoring_config, topics, today=today) for candidate in candidates]


def score_candidate(
    candidate: dict[str, Any],
    scoring_config: dict[str, Any],
    topics: dict[str, Any],
    *,
    today: date | None = None,
) -> ScoredCandidate:
    config = scoring_section(scoring_config)
    weights = config.get("weights", {})
    thresholds = config.get("thresholds", {})
    reject_config = config.get("reject", {})
    signals = config.get("signals", {})
    current_date = today or utc_now().date()

    components: dict[str, float] = {}
    reasons: list[str] = []
    penalties: list[str] = []

    title = _clean(candidate.get("title"))
    abstract = _clean(candidate.get("abstract"))
    source = _clean(candidate.get("source")).casefold()
    lane = lane_from_source_query(candidate.get("source_query"))

    if _truthy_text(abstract):
        _add_component(components, reasons, "metadata.has_abstract", _weight(weights, "metadata", "has_abstract"), "has abstract")
    else:
        _add_component(
            components,
            penalties,
            "content.missing_abstract_penalty",
            _weight(weights, "content", "missing_abstract_penalty"),
            "missing abstract",
        )

    if candidate.get("doi") or candidate.get("arxiv_id") or candidate.get("pmid"):
        _add_component(
            components,
            reasons,
            "metadata.has_identifier",
            _weight(weights, "metadata", "has_identifier"),
            "has DOI/arXiv/PMID",
        )
    else:
        penalties.append("missing DOI/arXiv/PMID")

    if candidate.get("url") or candidate.get("oa_url"):
        _add_component(components, reasons, "metadata.has_url", _weight(weights, "metadata", "has_url"), "has URL")
    else:
        penalties.append("missing URL")

    if candidate.get("canonical_id"):
        _add_component(
            components,
            reasons,
            "metadata.has_canonical_id",
            _weight(weights, "metadata", "has_canonical_id"),
            "has canonical id",
        )

    _score_freshness(candidate, current_date, weights, components, reasons)

    source_weight = float((weights.get("source_quality") or {}).get(source, 0))
    if source_weight:
        _add_component(components, reasons, f"source_quality.{source}", source_weight, f"source quality: {source}")

    _score_lane_relevance(candidate, topics, lane, weights, components, reasons)
    _score_cross_domain(candidate, topics, weights, components, reasons)
    _score_review_signal(candidate, signals, weights, components, reasons)
    _score_noise(candidate, signals, weights, components, penalties)

    hard_rejects = _hard_reject_reasons(candidate, reject_config)
    penalties.extend(hard_rejects)
    total = round(sum(components.values()), 2)
    level = "reject" if hard_rejects else _candidate_level(total, thresholds)
    return ScoredCandidate(
        candidate=candidate,
        lane=lane,
        score=ScoreBreakdown(
            total=total,
            level=level,
            components={key: round(value, 2) for key, value in components.items()},
            reasons=_unique(reasons),
            penalties=_unique(penalties),
        ),
    )


def lane_from_source_query(value: Any) -> str:
    if not value:
        return "unassigned"
    text = str(value).strip()
    return text.split(":", 1)[0] or "unassigned"


def _score_freshness(
    candidate: dict[str, Any],
    today: date,
    weights: dict[str, Any],
    components: dict[str, float],
    reasons: list[str],
) -> None:
    published = to_iso_date(candidate.get("published_date"))
    if not published and candidate.get("year"):
        published = f"{candidate['year']}-01-01"
    if not published:
        return
    try:
        delta = (today - date.fromisoformat(published)).days
    except ValueError:
        return
    if delta < 0:
        delta = 0
    freshness_weights = weights.get("freshness", {})
    if delta <= 7:
        _add_component(components, reasons, "freshness.within_7_days", float(freshness_weights.get("within_7_days", 0)), "within 7 days")
    elif delta <= 14:
        _add_component(components, reasons, "freshness.within_14_days", float(freshness_weights.get("within_14_days", 0)), "within 14 days")
    elif delta <= 30:
        _add_component(components, reasons, "freshness.within_30_days", float(freshness_weights.get("within_30_days", 0)), "within 30 days")


def _score_lane_relevance(
    candidate: dict[str, Any],
    topics: dict[str, Any],
    lane: str,
    weights: dict[str, Any],
    components: dict[str, float],
    reasons: list[str],
) -> None:
    lane_keywords = _lane_keywords(topics, lane)
    if not lane_keywords:
        return
    content_weights = weights.get("content", {})
    title = _clean(candidate.get("title"))
    abstract = _clean(candidate.get("abstract"))
    field_text = " ".join([*_as_list(candidate.get("fields")), *_as_list(candidate.get("keywords"))])
    if _matches_any(title, lane_keywords):
        _add_component(
            components,
            reasons,
            "content.title_keyword_match",
            float(content_weights.get("title_keyword_match", 0)),
            "matched lane keyword in title",
        )
    if _matches_any(abstract, lane_keywords):
        _add_component(
            components,
            reasons,
            "content.abstract_keyword_match",
            float(content_weights.get("abstract_keyword_match", 0)),
            "matched lane keyword in abstract",
        )
    if _matches_any(field_text, lane_keywords):
        _add_component(
            components,
            reasons,
            "content.field_keyword_match",
            float(content_weights.get("field_keyword_match", 0)),
            "matched lane keyword in fields/keywords",
        )


def _score_cross_domain(
    candidate: dict[str, Any],
    topics: dict[str, Any],
    weights: dict[str, Any],
    components: dict[str, float],
    reasons: list[str],
) -> None:
    text = " ".join(
        [
            _clean(candidate.get("title")),
            _clean(candidate.get("abstract")),
            " ".join(_as_list(candidate.get("fields"))),
            " ".join(_as_list(candidate.get("keywords"))),
        ]
    )
    matched_lanes = {
        lane
        for lane, lane_config in topics.items()
        if _matches_any(text, [str(keyword) for keyword in lane_config.get("keywords", [])])
    }
    if len(matched_lanes) >= 2:
        _add_component(
            components,
            reasons,
            "content.cross_domain_signal",
            _weight(weights, "content", "cross_domain_signal"),
            "matched keywords from multiple lanes",
        )


def _score_review_signal(
    candidate: dict[str, Any],
    signals: dict[str, Any],
    weights: dict[str, Any],
    components: dict[str, float],
    reasons: list[str],
) -> None:
    text = " ".join([_clean(candidate.get("title")), _clean(candidate.get("work_type"))])
    if _matches_any(text, [str(term) for term in signals.get("review_terms", [])]):
        _add_component(
            components,
            reasons,
            "content.review_or_survey_signal",
            _weight(weights, "content", "review_or_survey_signal"),
            "review/survey signal",
        )


def _score_noise(
    candidate: dict[str, Any],
    signals: dict[str, Any],
    weights: dict[str, Any],
    components: dict[str, float],
    penalties: list[str],
) -> None:
    title = _clean(candidate.get("title"))
    if _matches_any(title, [str(term) for term in signals.get("benchmark_only_terms", [])]):
        _add_component(
            components,
            penalties,
            "content.benchmark_only_penalty",
            _weight(weights, "content", "benchmark_only_penalty"),
            "benchmark-only / narrow technical update signal",
        )
    title_words = [word for word in title.split() if word]
    has_identifier = bool(candidate.get("doi") or candidate.get("arxiv_id") or candidate.get("pmid"))
    has_link = bool(candidate.get("url") or candidate.get("oa_url"))
    if len(title_words) <= 3 and not candidate.get("abstract") and not has_identifier and not has_link:
        _add_component(
            components,
            penalties,
            "content.too_short_metadata_penalty",
            _weight(weights, "content", "too_short_metadata_penalty"),
            "too short metadata",
        )


def _hard_reject_reasons(candidate: dict[str, Any], reject_config: dict[str, Any]) -> list[str]:
    if not reject_config.get("enabled", True):
        return []
    reasons: list[str] = []
    if reject_config.get("hard_reject_missing_title", True) and not _truthy_text(candidate.get("title")):
        reasons.append("hard reject: missing title")
    if reject_config.get("hard_reject_missing_abstract_and_url", False):
        has_abstract = _truthy_text(candidate.get("abstract"))
        has_url = bool(candidate.get("url") or candidate.get("oa_url"))
        if not has_abstract and not has_url:
            reasons.append("hard reject: missing abstract and URL")
    return reasons


def _candidate_level(total: float, thresholds: dict[str, Any]) -> str:
    if total >= float(thresholds.get("s_candidate_min", 18)):
        return "S_candidate"
    if total >= float(thresholds.get("a_candidate_min", 13)):
        return "A_candidate"
    if total >= float(thresholds.get("b_candidate_min", 8)):
        return "B_candidate"
    if total >= float(thresholds.get("c_candidate_min", 4)):
        return "C_candidate"
    return "reject"


def _lane_keywords(topics: dict[str, Any], lane: str) -> list[str]:
    lane_config = topics.get(lane, {})
    return [str(keyword) for keyword in lane_config.get("keywords", [])]


def _weight(weights: dict[str, Any], section: str, key: str) -> float:
    return float((weights.get(section) or {}).get(key, 0))


def _add_component(
    components: dict[str, float],
    labels: list[str],
    key: str,
    value: float,
    label: str,
) -> None:
    if value == 0:
        return
    components[key] = components.get(key, 0) + value
    labels.append(label)


def _matches_any(text: str, terms: list[str]) -> bool:
    folded = f" {_clean(text).casefold()} "
    return any(term and f" {term.casefold()} " in folded for term in terms)


def _truthy_text(value: Any) -> bool:
    return bool(_clean(value))


def _clean(value: Any) -> str:
    if value is None:
        return ""
    return " ".join(str(value).split())


def _as_list(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    text = str(value).strip()
    return [text] if text else []


def _unique(values: list[str]) -> list[str]:
    return list(dict.fromkeys(values))
