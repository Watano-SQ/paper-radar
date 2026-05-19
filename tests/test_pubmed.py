from pathlib import Path

import requests

from src.sources.base import SourceQuery
from src.sources.pubmed import PubMedClient


PUBMED_XML = """<?xml version="1.0" encoding="UTF-8"?>
<PubmedArticleSet>
  <PubmedArticle>
    <MedlineCitation>
      <PMID Version="1">12345678</PMID>
      <Article>
        <Journal>
          <JournalIssue>
            <PubDate>
              <Year>2026</Year>
              <Month>May</Month>
              <Day>02</Day>
            </PubDate>
          </JournalIssue>
          <Title>Journal of Intelligent Systems</Title>
        </Journal>
        <ArticleTitle>Embodied Intelligence in Neural Control</ArticleTitle>
        <ELocationID EIdType="doi" ValidYN="Y">10.1000/PUBMED.XYZ</ELocationID>
        <Abstract>
          <AbstractText>This study tests embodied intelligence in adaptive neural control.</AbstractText>
        </Abstract>
        <AuthorList>
          <Author>
            <ForeName>Ada</ForeName>
            <LastName>Lovelace</LastName>
          </Author>
          <Author>
            <ForeName>Norbert</ForeName>
            <LastName>Wiener</LastName>
          </Author>
        </AuthorList>
        <PublicationTypeList>
          <PublicationType>Journal Article</PublicationType>
        </PublicationTypeList>
      </Article>
      <MeshHeadingList>
        <MeshHeading>
          <DescriptorName>Neural Networks, Computer</DescriptorName>
        </MeshHeading>
      </MeshHeadingList>
      <KeywordList>
        <Keyword>embodied intelligence</Keyword>
      </KeywordList>
    </MedlineCitation>
    <PubmedData>
      <ArticleIdList>
        <ArticleId IdType="pubmed">12345678</ArticleId>
        <ArticleId IdType="doi">10.1000/PUBMED.XYZ</ArticleId>
      </ArticleIdList>
    </PubmedData>
  </PubmedArticle>
</PubmedArticleSet>
"""


def test_pubmed_fetch_and_normalize_sample_response(tmp_path: Path) -> None:
    session = _FakeSession(
        [
            _json_response({"esearchresult": {"idlist": ["12345678"]}}),
            _text_response(PUBMED_XML),
        ]
    )
    client = PubMedClient(
        {"delay_seconds": 0, "days_back": 14, "per_query_limit": 5},
        tmp_path,
        session=session,
    )
    query = SourceQuery(
        lane="neuro_cognitive",
        query="embodied intelligence",
        days_back=14,
        limit=5,
    )

    raw_items = client.fetch(query)
    item = client.normalize(raw_items[0])

    assert len(raw_items) == 1
    assert item.source == "pubmed"
    assert item.source_id == "12345678"
    assert item.pmid == "12345678"
    assert item.doi == "10.1000/pubmed.xyz"
    assert item.canonical_id == "doi:10.1000/pubmed.xyz"
    assert item.title == "Embodied Intelligence in Neural Control"
    assert item.abstract == "This study tests embodied intelligence in adaptive neural control."
    assert item.authors == ["Ada Lovelace", "Norbert Wiener"]
    assert item.published_date == "2026-05-02"
    assert item.year == 2026
    assert item.venue == "Journal of Intelligent Systems"
    assert item.work_type == "Journal Article"
    assert item.url == "https://pubmed.ncbi.nlm.nih.gov/12345678/"
    assert item.fields == ["Neural Networks, Computer"]
    assert item.keywords == ["embodied intelligence"]
    assert item.source_query == "neuro_cognitive:keyword:embodied intelligence"
    assert len(session.requests) == 2
    assert list(tmp_path.rglob("*.json"))
    assert list(tmp_path.rglob("*.xml"))


class _FakeSession:
    def __init__(self, responses: list[requests.Response]):
        self.responses = responses
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
        return self.responses.pop(0)


def _json_response(payload: dict) -> requests.Response:
    response = requests.Response()
    response.status_code = 200
    response.url = "https://example.test/json"
    response._content = b"{}"
    response.headers["content-type"] = "application/json"
    response.json = lambda: payload
    return response


def _text_response(text: str) -> requests.Response:
    response = requests.Response()
    response.status_code = 200
    response.url = "https://example.test/xml"
    response._content = text.encode("utf-8")
    response.encoding = "utf-8"
    response.headers["content-type"] = "application/xml"
    return response
