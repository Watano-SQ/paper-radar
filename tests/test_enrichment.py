from pathlib import Path

import requests

from src.models.paper import PaperItem
from src.sources.base import RawItem, SourceQuery
from src.sources.crossref import CrossrefClient
from src.sources.semantic_scholar import SemanticScholarClient


def test_crossref_normalize_response(tmp_path: Path) -> None:
    base = PaperItem(
        canonical_id="doi:10.1000/example",
        source="openalex",
        source_id="W1",
        doi="10.1000/example",
        title="Old Title",
        authors=["Ada Lovelace"],
        fetched_at="2026-05-04T00:00:00+00:00",
    )
    raw = RawItem(
        source="crossref",
        source_id="10.1000/example",
        query=SourceQuery(lane="enrichment", query="10.1000/example", query_type="doi"),
        raw_path=str(tmp_path / "crossref.json"),
        fetched_at="2026-05-04T01:00:00+00:00",
        data={
            "DOI": "10.1000/EXAMPLE",
            "title": ["Crossref Title"],
            "abstract": "<jats:p>Clean abstract.</jats:p>",
            "author": [{"given": "Ada", "family": "Lovelace"}],
            "issued": {"date-parts": [[2026, 5, 1]]},
            "container-title": ["Journal of Examples"],
            "publisher": "Example Publisher",
            "type": "journal-article",
            "license": [{"URL": "https://creativecommons.org/licenses/by/4.0/"}],
            "URL": "https://doi.org/10.1000/example",
        },
    )
    item = CrossrefClient({}, tmp_path).normalize(raw, base_item=base)
    assert item.canonical_id == "doi:10.1000/example"
    assert item.doi == "10.1000/example"
    assert item.title == "Crossref Title"
    assert item.abstract == "Clean abstract."
    assert item.authors == ["Ada Lovelace"]
    assert item.published_date == "2026-05-01"
    assert item.venue == "Journal of Examples"
    assert item.license == "https://creativecommons.org/licenses/by/4.0/"


def test_crossref_404_returns_none(tmp_path: Path) -> None:
    session = _FakeSession(status_code=404, payload={"status": "failed"})
    client = CrossrefClient({"delay_seconds": 0}, tmp_path, session=session)
    assert client.fetch_by_doi("10.1000/missing") is None
    assert len(session.requests) == 1


def test_semantic_scholar_normalize_doi_response(tmp_path: Path) -> None:
    base = PaperItem(
        canonical_id="doi:10.1000/example",
        source="openalex",
        source_id="W1",
        doi="10.1000/example",
        title="Old Title",
        authors=["Ada Lovelace"],
        fetched_at="2026-05-04T00:00:00+00:00",
    )
    raw = RawItem(
        source="semantic_scholar",
        source_id="S2-1",
        query=SourceQuery(lane="enrichment", query="10.1000/example", query_type="doi"),
        raw_path=str(tmp_path / "s2.json"),
        fetched_at="2026-05-04T01:00:00+00:00",
        data={
            "paperId": "S2-1",
            "title": "Semantic Scholar Title",
            "abstract": "S2 abstract",
            "year": 2026,
            "venue": "S2 Venue",
            "authors": [{"name": "Ada Lovelace"}],
            "citationCount": 42,
            "influentialCitationCount": 7,
            "fieldsOfStudy": ["Computer Science"],
            "s2FieldsOfStudy": [{"category": "Artificial Intelligence"}],
            "externalIds": {"DOI": "10.1000/EXAMPLE"},
            "url": "https://semanticscholar.org/paper/S2-1",
            "openAccessPdf": {"url": "https://example.org/paper.pdf"},
        },
    )
    item = SemanticScholarClient({}, tmp_path).normalize(raw, base_item=base)
    assert item.canonical_id == "doi:10.1000/example"
    assert item.semantic_scholar_id == "S2-1"
    assert item.citation_count == 42
    assert item.influential_citation_count == 7
    assert "Computer Science" in item.fields
    assert "Artificial Intelligence" in item.fields
    assert item.pdf_url == "https://example.org/paper.pdf"


def test_semantic_scholar_requires_api_key_by_default(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.delenv("S2_API_KEY", raising=False)
    session = _ExplodingSession()
    client = SemanticScholarClient({"delay_seconds": 0, "require_api_key": True}, tmp_path, session=session)
    base = PaperItem(
        canonical_id="arxiv:2501.12345",
        source="arxiv",
        source_id="2501.12345",
        arxiv_id="2501.12345",
        title="Arxiv Paper",
        authors=["Ada Lovelace"],
        fetched_at="2026-05-04T00:00:00+00:00",
    )
    assert client.is_available is False
    assert client.unavailable_reason is not None
    assert client.enrich_item(base) is None


def test_semantic_scholar_normalize_arxiv_response_preserves_base_id(tmp_path: Path) -> None:
    base = PaperItem(
        canonical_id="arxiv:2501.12345",
        source="arxiv",
        source_id="2501.12345",
        arxiv_id="2501.12345",
        title="Arxiv Paper",
        authors=["Ada Lovelace"],
        fetched_at="2026-05-04T00:00:00+00:00",
    )
    raw = RawItem(
        source="semantic_scholar",
        source_id="S2-2",
        query=SourceQuery(lane="enrichment", query="2501.12345", query_type="arxiv"),
        raw_path=str(tmp_path / "s2_arxiv.json"),
        fetched_at="2026-05-04T01:00:00+00:00",
        data={
            "paperId": "S2-2",
            "title": "Arxiv Paper",
            "year": 2025,
            "authors": [{"name": "Ada Lovelace"}],
            "citationCount": 3,
            "influentialCitationCount": 1,
            "externalIds": {"ArXiv": "2501.12345v2"},
            "url": "https://semanticscholar.org/paper/S2-2",
        },
    )
    item = SemanticScholarClient({}, tmp_path).normalize(raw, base_item=base)
    assert item.canonical_id == "arxiv:2501.12345"
    assert item.arxiv_id == "2501.12345"
    assert item.semantic_scholar_id == "S2-2"


class _FakeSession:
    def __init__(self, status_code: int, payload: dict):
        self.status_code = status_code
        self.payload = payload
        self.requests: list[dict] = []

    def request(self, method, url, params=None, headers=None, timeout=None):
        self.requests.append(
            {
                "method": method,
                "url": url,
                "params": params,
                "headers": headers,
                "timeout": timeout,
            }
        )
        response = requests.Response()
        response.status_code = self.status_code
        response.url = url
        response._content = b"{}"
        response.headers["content-type"] = "application/json"
        response.json = lambda: self.payload
        return response


class _ExplodingSession:
    def request(self, *args, **kwargs):
        raise AssertionError("Semantic Scholar should not issue requests without an API key")
