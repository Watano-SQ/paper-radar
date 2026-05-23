from datetime import date
from pathlib import Path

from src.ranking.balance import select_balanced_candidates
from src.ranking.config import merge_scoring_config
from src.ranking.rejects import write_reject_log
from src.ranking.scoring import score_candidate, score_candidates


TODAY = date(2026, 5, 19)

TOPICS = {
    "neuro_cognitive": {
        "keywords": ["neural coding", "predictive coding", "brain computer interface"],
    },
    "core_embodied_ai": {
        "keywords": ["robot learning", "embodied AI"],
    },
}


def test_strong_metadata_scores_higher_than_weak_metadata() -> None:
    config = merge_scoring_config({})
    strong = score_candidate(
        {
            "canonical_id": "doi:10.1000/strong",
            "source": "pubmed",
            "doi": "10.1000/strong",
            "title": "Neural coding review",
            "abstract": "A useful abstract about neural coding.",
            "url": "https://example.org/strong",
            "published_date": "2026-05-18",
            "source_query": "neuro_cognitive:keyword:neural coding",
        },
        config,
        TOPICS,
        today=TODAY,
    )
    weak = score_candidate(
        {
            "canonical_id": "titlehash:weak",
            "source": "biorxiv",
            "title": "Weak note",
            "published_date": "2026-04-01",
            "source_query": "neuro_cognitive:keyword:neural coding",
        },
        config,
        TOPICS,
        today=TODAY,
    )

    assert strong.score.total > weak.score.total
    assert strong.score.level in {"S_candidate", "A_candidate"}
    assert weak.score.level == "reject"


def test_title_lane_keyword_scores_higher_than_weak_abstract_match() -> None:
    config = merge_scoring_config({})
    title_match = score_candidate(
        _base_candidate(title="Neural coding in hippocampal memory", abstract="General methods."),
        config,
        TOPICS,
        today=TODAY,
    )
    abstract_match = score_candidate(
        _base_candidate(title="Hippocampal memory", abstract="A paragraph mentions neural coding once."),
        config,
        TOPICS,
        today=TODAY,
    )

    assert title_match.score.total > abstract_match.score.total
    assert "matched lane keyword in title" in title_match.score.reasons
    assert "matched lane keyword in abstract" in abstract_match.score.reasons


def test_missing_abstract_penalty_does_not_always_hard_reject() -> None:
    config = merge_scoring_config({})
    scored = score_candidate(
        _base_candidate(title="Neural coding in hippocampal memory", abstract=None),
        config,
        TOPICS,
        today=TODAY,
    )

    assert "missing abstract" in scored.score.penalties
    assert scored.score.level != "reject"


def test_review_signal_bonus_and_benchmark_penalty() -> None:
    config = merge_scoring_config({})
    review = score_candidate(
        _base_candidate(title="A survey of neural coding systems"),
        config,
        TOPICS,
        today=TODAY,
    )
    benchmark = score_candidate(
        _base_candidate(title="Neural coding benchmark with marginal improvement"),
        config,
        TOPICS,
        today=TODAY,
    )

    assert "review/survey signal" in review.score.reasons
    assert "benchmark-only / narrow technical update signal" in benchmark.score.penalties
    assert review.score.total > benchmark.score.total


def test_duplicate_canonical_id_keeps_best_and_records_reject() -> None:
    config = merge_scoring_config({})
    scored = score_candidates(
        [
            _base_candidate(canonical_id="doi:10.1000/dup", title="Neural coding survey", abstract="Good abstract."),
            _base_candidate(canonical_id="doi:10.1000/dup", title="Neural coding", abstract=None),
        ],
        config,
        TOPICS,
        today=TODAY,
    )

    selection = select_balanced_candidates(scored, config)

    selected = [item for items in selection.selected_by_lane.values() for item in items]
    assert len(selected) == 1
    assert selected[0].candidate["title"] == "Neural coding survey"
    assert len(selection.rejected) == 1
    assert selection.rejected[0].reason == "Duplicate canonical ID"


def test_lane_balance_enforces_max_per_lane() -> None:
    config = merge_scoring_config(
        {
            "scoring": {
                "lane_balance": {
                    "max_per_lane": 2,
                    "min_per_active_lane": 1,
                    "global_max": 10,
                }
            }
        }
    )
    scored = score_candidates(
        [
            _base_candidate(canonical_id=f"doi:10.1000/{index}", title=f"Neural coding survey {index}")
            for index in range(5)
        ],
        config,
        TOPICS,
        today=TODAY,
    )

    selection = select_balanced_candidates(scored, config)

    assert len(selection.selected_by_lane["neuro_cognitive"]) == 2
    assert len(selection.downranked) == 3
    assert {decision.reason for decision in selection.downranked} == {"Lane balance limit"}


def test_near_duplicate_title_keeps_one_and_downranks_the_other() -> None:
    config = merge_scoring_config({})
    scored = score_candidates(
        [
            _base_candidate(canonical_id="doi:10.1000/one", title="Neural coding study"),
            _base_candidate(canonical_id="doi:10.1000/two", title="Neural coding: study"),
        ],
        config,
        TOPICS,
        today=TODAY,
    )

    selection = select_balanced_candidates(scored, config)

    selected = [item for items in selection.selected_by_lane.values() for item in items]
    assert len(selected) == 1
    assert len(selection.downranked) == 1
    assert selection.downranked[0].reason == "Near-duplicate title"


def test_arxiv_mirror_is_preferred_when_duplicate_scores_are_close() -> None:
    config = merge_scoring_config({})
    title = "Neural coding mirror study"
    scored = score_candidates(
        [
            _base_candidate(
                canonical_id="doi:10.1000/mirror",
                source="openalex",
                title=title,
                venue="arXiv (Cornell University)",
            ),
            _base_candidate(
                canonical_id="arxiv:2605.00001",
                source="arxiv",
                arxiv_id="2605.00001",
                title=title,
                doi=None,
                venue="arXiv",
            ),
        ],
        config,
        TOPICS,
        today=TODAY,
    )

    selection = select_balanced_candidates(scored, config)

    selected = [item for items in selection.selected_by_lane.values() for item in items]
    assert len(selected) == 1
    assert selected[0].candidate["source"] == "arxiv"
    assert selection.downranked[0].reason == "Near-duplicate title"


def test_repository_like_candidate_gets_penalty() -> None:
    config = merge_scoring_config({})
    ordinary = score_candidate(
        _base_candidate(canonical_id="doi:10.1000/ordinary", title="Neural coding systems check", venue="Journal"),
        config,
        TOPICS,
        today=TODAY,
    )
    repository_like = score_candidate(
        _base_candidate(
            canonical_id="doi:10.5281/zenodo.123",
            source="openalex",
            title="Neural coding repository check",
            venue="Zenodo (CERN European Organization for Nuclear Research)",
            url="https://doi.org/10.5281/zenodo.123",
        ),
        config,
        TOPICS,
        today=TODAY,
    )

    assert "repository-like venue/source signal" in repository_like.score.penalties
    assert repository_like.score.components["content.repository_like_penalty"] == -4
    assert ordinary.score.total > repository_like.score.total


def test_reject_log_is_grouped_by_reason(tmp_path: Path) -> None:
    config = merge_scoring_config(
        {
            "scoring": {
                "lane_balance": {
                    "max_per_lane": 1,
                    "min_per_active_lane": 1,
                    "global_max": 10,
                }
            }
        }
    )
    scored = score_candidates(
        [
            {"canonical_id": "titlehash:missing", "source": "openalex", "source_query": "neuro_cognitive:keyword:x"},
            _base_candidate(canonical_id="doi:10.1000/strong", title="Neural coding survey"),
            _base_candidate(canonical_id="doi:10.1000/strong-alt", title="Neural coding: survey"),
            _base_candidate(canonical_id="doi:10.1000/bench", title="Neural coding benchmark leaderboard"),
        ],
        config,
        TOPICS,
        today=TODAY,
    )
    selection = select_balanced_candidates(scored, config)

    path = write_reject_log(tmp_path / "rejected_candidates_2026-W21.md", selection, week_label="2026-W21", max_per_reason=30)

    content = path.read_text(encoding="utf-8")
    assert "# Rejected / Downranked Candidates: 2026-W21" in content
    assert "## Missing metadata" in content
    assert "## Lane balance limit" in content
    assert "## Near-duplicate title" in content


def _base_candidate(
    *,
    canonical_id: str = "doi:10.1000/example",
    title: str = "Neural coding example",
    abstract: str | None = "This abstract discusses neural coding.",
    source: str = "pubmed",
    arxiv_id: str | None = None,
    doi: str | None = None,
    venue: str | None = None,
    url: str = "https://example.org/paper",
) -> dict:
    resolved_doi = doi if doi is not None else canonical_id.removeprefix("doi:") if canonical_id.startswith("doi:") else None
    return {
        "canonical_id": canonical_id,
        "source": source,
        "doi": resolved_doi,
        "arxiv_id": arxiv_id,
        "title": title,
        "abstract": abstract,
        "url": url,
        "venue": venue,
        "published_date": "2026-05-18",
        "source_query": "neuro_cognitive:keyword:neural coding",
    }
