from pathlib import Path

from src.models.paper import PaperItem
from src.pipeline.normalize import restore_openalex_abstract
from src.sources.base import RawItem, SourceQuery
from src.sources.openalex import OpenAlexClient


def test_restore_openalex_abstract() -> None:
    inverted = {
        "world": [1],
        "Hello": [0],
        "again": [3],
        "world.": [2],
    }
    assert restore_openalex_abstract(inverted) == "Hello world world. again"


def test_paper_item_json_serialization() -> None:
    item = PaperItem(
        canonical_id="doi:10.1000/example",
        source="test",
        source_id="x",
        doi="10.1000/example",
        title="Example Paper",
        authors=["Ada Lovelace"],
        fetched_at="2026-05-04T00:00:00+00:00",
    )
    payload = item.model_dump_json()
    assert '"canonical_id":"doi:10.1000/example"' in payload
    assert '"authors":["Ada Lovelace"]' in payload


def test_openalex_normalize_minimal_record(tmp_path: Path) -> None:
    client = OpenAlexClient({}, tmp_path)
    raw = RawItem(
        source="openalex",
        source_id="https://openalex.org/W123",
        query=SourceQuery(lane="test_lane", query="robot learning"),
        raw_path=str(tmp_path / "raw.json"),
        fetched_at="2026-05-04T00:00:00+00:00",
        data={
            "id": "https://openalex.org/W123",
            "doi": "https://doi.org/10.1000/XYZ",
            "title": "Robot Learning",
            "abstract_inverted_index": {"Hello": [0], "world": [1]},
            "authorships": [{"author": {"display_name": "Ada Lovelace"}}],
            "publication_year": 2026,
            "publication_date": "2026-05-01",
            "primary_location": {
                "landing_page_url": "https://example.org/paper",
                "pdf_url": "https://example.org/paper.pdf",
                "source": {"display_name": "Example Journal"},
            },
            "open_access": {"is_oa": True, "oa_url": "https://example.org/oa"},
            "cited_by_count": 7,
            "type": "article",
            "concepts": [{"display_name": "Artificial intelligence"}],
            "keywords": [{"display_name": "robot learning"}],
        },
    )
    item = client.normalize(raw)
    assert item.canonical_id == "doi:10.1000/xyz"
    assert item.openalex_id == "W123"
    assert item.abstract == "Hello world"
    assert item.authors == ["Ada Lovelace"]
    assert item.venue == "Example Journal"
