from __future__ import annotations

from copy import deepcopy
from typing import Any


DEFAULT_SCORING_CONFIG: dict[str, Any] = {
    "scoring": {
        "enabled": True,
        "weights": {
            "metadata": {
                "has_abstract": 6,
                "has_identifier": 4,
                "has_url": 2,
                "has_canonical_id": 1,
            },
            "freshness": {
                "within_7_days": 4,
                "within_14_days": 3,
                "within_30_days": 1,
            },
            "source_quality": {
                "openalex": 1,
                "arxiv": 1,
                "pubmed": 1,
                "biorxiv": 0,
                "medrxiv": 0,
                "crossref": 0,
                "semantic_scholar": 0,
            },
            "content": {
                "title_keyword_match": 3,
                "abstract_keyword_match": 2,
                "field_keyword_match": 2,
                "cross_domain_signal": 2,
                "review_or_survey_signal": 3,
                "benchmark_only_penalty": -2,
                "repository_like_penalty": -4,
                "missing_abstract_penalty": -6,
                "too_short_metadata_penalty": -2,
            },
        },
        "thresholds": {
            "s_candidate_min": 22,
            "a_candidate_min": 13,
            "b_candidate_min": 8,
            "c_candidate_min": 4,
        },
        "lane_balance": {
            "max_per_lane": 20,
            "min_per_active_lane": 3,
            "global_max": 120,
        },
        "reject": {
            "enabled": True,
            "hard_reject_missing_title": True,
            "hard_reject_missing_abstract_and_url": False,
            "hard_reject_duplicate_canonical_id": True,
            "reject_log_max_per_reason": 30,
        },
        "report": {
            "include_score_details": True,
            "include_reject_summary": True,
        },
        "signals": {
            "review_terms": [
                "review",
                "survey",
                "tutorial",
                "perspective",
                "primer",
                "introduction",
                "systematic review",
                "meta-analysis",
            ],
            "benchmark_only_terms": [
                "benchmark",
                "leaderboard",
                "marginal improvement",
                "incremental improvement",
                "sota",
            ],
            "repository_like_terms": [
                "zenodo",
                "figshare",
                "dataverse",
                "osf",
                "open science framework",
                "ieee dataport",
                "repository",
            ],
        },
    }
}


def merge_scoring_config(override: dict[str, Any] | None) -> dict[str, Any]:
    return _deep_merge(DEFAULT_SCORING_CONFIG, override or {})


def scoring_section(config: dict[str, Any]) -> dict[str, Any]:
    return config.get("scoring", {})


def _deep_merge(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
    merged = deepcopy(base)
    for key, value in override.items():
        if isinstance(value, dict) and isinstance(merged.get(key), dict):
            merged[key] = _deep_merge(merged[key], value)
        else:
            merged[key] = value
    return merged
