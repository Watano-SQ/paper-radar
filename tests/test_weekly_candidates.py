import json
from pathlib import Path

from src.report.weekly_candidates import generate_weekly_candidate_report


def test_weekly_candidate_report_from_jsonl_fixture(tmp_path: Path) -> None:
    exports_dir = tmp_path / "exports"
    export_file = exports_dir / "candidates_2026-W21.jsonl"
    output_dir = tmp_path / "reports"
    exports_dir.mkdir()
    rows = [
        {
            "canonical_id": "doi:10.1000/strong",
            "source": "pubmed",
            "doi": "10.1000/strong",
            "pmid": "123",
            "title": "Strong Candidate",
            "abstract": "This abstract gives enough metadata for screening.",
            "authors": ["Ada Lovelace", "Norbert Wiener", "Grace Hopper", "Alan Turing"],
            "published_date": "2026-05-02",
            "venue": "Journal of Examples",
            "url": "https://pubmed.ncbi.nlm.nih.gov/123/",
            "fields": ["Neuroscience"],
            "keywords": ["control"],
            "source_query": "neuro_cognitive:keyword:neural coding",
        },
        {
            "canonical_id": "doi:10.1000/weak",
            "source": "openalex",
            "doi": "10.1000/weak",
            "title": "Weak Candidate",
            "authors": [],
            "published_date": "2026-04-01",
            "source_query": "neuro_cognitive:keyword:neural coding",
        },
        {
            "canonical_id": "titlehash:missing",
            "source": "biorxiv",
            "title": "Missing Fields Candidate",
        },
    ]
    export_file.write_text("\n".join(json.dumps(row) for row in rows), encoding="utf-8")

    output_path = generate_weekly_candidate_report(
        export_file=export_file,
        output_dir=output_dir,
        per_lane=1,
    )

    content = output_path.read_text(encoding="utf-8")
    assert output_path == output_dir / "weekly_candidates_2026-W21.md"
    assert output_dir.exists()
    assert "# Weekly Candidate Pool: 2026-W21" in content
    assert "This file is a candidate pool for later screening. It is not a reading list." in content
    assert "## neuro_cognitive" in content
    assert "### 1. Strong Candidate" in content
    assert "Weak Candidate" not in content
    assert "## unassigned" in content
    assert "Missing Fields Candidate" in content
    assert "- Authors: Ada Lovelace, Norbert Wiener, Grace Hopper, et al." in content
    assert "- Abstract preview: missing" in content
