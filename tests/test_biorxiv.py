from pathlib import Path

import requests

from src.sources.base import RawItem, SourceQuery
from src.sources.biorxiv import BiorxivClient, MedrxivClient, record_matches_query


def test_biorxiv_fetch_filters_locally_and_normalizes(tmp_path: Path) -> None:
    session = _FakeSession(
        [
            _json_response(
                {
                    "collection": [
                        {
                            "doi": "10.1101/2026.05.01.123456",
                            "title": "Robot Learning Through Tactile Exploration",
                            "abstract": "A preprint about robot learning and embodied control.",
                            "authors": "Ada Lovelace; Norbert Wiener",
                            "date": "2026-05-01",
                            "version": "1",
                            "category": "neuroscience",
                            "license": "cc_by",
                        },
                        {
                            "doi": "10.1101/2026.05.01.999999",
                            "title": "Marine Biology Notes",
                            "abstract": "A distant topic.",
                            "authors": "Grace Hopper",
                            "date": "2026-05-01",
                            "version": "1",
                            "category": "biology",
                        },
                    ]
                }
            )
        ]
    )
    client = BiorxivClient(
        {"delay_seconds": 0, "days_back": 14, "per_query_limit": 10, "max_total": 10},
        tmp_path,
        session=session,
    )
    query = SourceQuery(lane="core_embodied_ai", query="robot learning", days_back=14, limit=10)

    raw_items = client.fetch(query)
    item = client.normalize(raw_items[0])

    assert len(raw_items) == 1
    assert item.source == "biorxiv"
    assert item.source_id == "10.1101/2026.05.01.123456"
    assert item.doi == "10.1101/2026.05.01.123456"
    assert item.venue == "bioRxiv"
    assert item.work_type == "preprint"
    assert item.authors == ["Ada Lovelace", "Norbert Wiener"]
    assert item.published_date == "2026-05-01"
    assert item.fields == ["neuroscience"]
    assert item.pdf_url is None
    assert item.oa_url == "https://www.biorxiv.org/content/10.1101/2026.05.01.123456v1"
    assert list(tmp_path.rglob("*.json"))


def test_medrxiv_normalizes_sample_record(tmp_path: Path) -> None:
    raw = RawItem(
        source="medrxiv",
        source_id="10.1101/2026.05.03.222222",
        query=SourceQuery(lane="neuro_cognitive", query="brain computer interface"),
        raw_path=str(tmp_path / "medrxiv.json"),
        fetched_at="2026-05-04T00:00:00+00:00",
        data={
            "doi": "10.1101/2026.05.03.222222",
            "title": "Brain Computer Interfaces in Clinical Control",
            "abstract": "A medRxiv preprint.",
            "authors": "Jane Doe; Max Planck",
            "date": "2026-05-03",
            "version": "2",
            "category": "neurology",
            "license": "cc_by_nc_nd",
        },
    )

    item = MedrxivClient({"delay_seconds": 0}, tmp_path).normalize(raw)

    assert item.source == "medrxiv"
    assert item.venue == "medRxiv"
    assert item.work_type == "preprint"
    assert item.canonical_id == "doi:10.1101/2026.05.03.222222"
    assert item.url == "https://www.medrxiv.org/content/10.1101/2026.05.03.222222v2"
    assert item.fields == ["neurology"]


def test_preprint_keyword_matching_uses_title_abstract_and_category() -> None:
    record = {
        "title": "Predictive Coding for Control",
        "abstract": "No exact phrase here, but both brain and interface appear.",
        "category": "neuroscience",
    }

    assert record_matches_query(record, "predictive coding") is True
    assert record_matches_query(record, "brain interface") is True
    assert record_matches_query(record, "neuroscience") is True
    assert record_matches_query(record, "institutional economics") is False


class _FakeSession:
    def __init__(self, responses: list[requests.Response]):
        self.responses = responses

    def request(self, method, url, params=None, headers=None, timeout=None):
        return self.responses.pop(0)


def _json_response(payload: dict) -> requests.Response:
    response = requests.Response()
    response.status_code = 200
    response.url = "https://example.test/json"
    response._content = b"{}"
    response.headers["content-type"] = "application/json"
    response.json = lambda: payload
    return response
