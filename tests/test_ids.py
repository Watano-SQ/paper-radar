from src.utils.ids import (
    make_canonical_id,
    normalize_arxiv_id,
    normalize_doi,
    normalize_title,
    title_author_year_hash,
)


def test_normalize_doi() -> None:
    assert normalize_doi("https://doi.org/10.1145/ABC.123.") == "10.1145/abc.123"
    assert normalize_doi("doi: 10.1000/XYZ") == "10.1000/xyz"
    assert normalize_doi(None) is None


def test_normalize_arxiv_id() -> None:
    assert normalize_arxiv_id("arXiv:2501.12345v2") == "2501.12345"
    assert normalize_arxiv_id("https://arxiv.org/abs/1706.03762v7") == "1706.03762"
    assert normalize_arxiv_id("https://arxiv.org/pdf/1706.03762v7.pdf") == "1706.03762"


def test_normalize_title() -> None:
    assert normalize_title("  A Study: Of Embodied-AI! ") == "a study of embodied ai"


def test_make_canonical_id_priority() -> None:
    assert (
        make_canonical_id(
            doi="10.1000/XYZ",
            arxiv_id="2501.12345v2",
            title="Ignored",
        )
        == "doi:10.1000/xyz"
    )
    assert make_canonical_id(arxiv_id="2501.12345v2") == "arxiv:2501.12345"
    assert make_canonical_id(pmid="123") == "pmid:123"
    assert make_canonical_id(openalex_id="https://openalex.org/W123") == "openalex:W123"
    assert make_canonical_id(semantic_scholar_id="abc") == "s2:abc"


def test_title_author_year_hash_is_stable() -> None:
    left = title_author_year_hash("A Study!", "Ada Lovelace", 2024)
    right = title_author_year_hash("a study", "Ada Lovelace", "2024")
    assert left == right
    assert make_canonical_id(title="A Study!", first_author="Ada Lovelace", year=2024) == f"titlehash:{left}"
