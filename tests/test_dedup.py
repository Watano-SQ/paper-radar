from dataclasses import dataclass

from src.pipeline.dedup import detect_possible_duplicates


@dataclass(slots=True)
class PaperStub:
    canonical_id: str
    title: str
    authors: list[str]
    year: int | None


def test_possible_duplicate_detection() -> None:
    left = PaperStub(
        canonical_id="titlehash:left",
        title="A Study of Robot Learning",
        authors=["Ada Lovelace"],
        year=2026,
    )
    right = PaperStub(
        canonical_id="titlehash:right",
        title="A study of robot learning!",
        authors=["Ada Lovelace"],
        year=2025,
    )
    unrelated = PaperStub(
        canonical_id="titlehash:other",
        title="A Different Paper",
        authors=["Grace Hopper"],
        year=2026,
    )
    matches = detect_possible_duplicates([left], [right, unrelated])
    assert len(matches) == 1
    assert matches[0].left_id == "titlehash:left"
    assert matches[0].right_id == "titlehash:right"
    assert matches[0].score > 0.95
