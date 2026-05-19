from __future__ import annotations

import os
import re
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any

import requests

from src.models.paper import PaperItem
from src.pipeline.normalize import compact_list, finalize_paper_item
from src.pipeline.rate_limit import RateLimiter
from src.sources.base import JsonSourceClient, RawItem, SourceQuery, fetched_now
from src.utils.dates import days_ago_iso, to_iso_date, utc_now, year_from_date
from src.utils.http import build_user_agent, request_json, request_text
from src.utils.ids import normalize_doi
from src.utils.text import clean_text


class PubMedClient(JsonSourceClient):
    name = "pubmed"
    esearch_url = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi"
    efetch_url = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi"

    def __init__(self, config: dict[str, Any], raw_dir: Path, session: requests.Session | None = None):
        super().__init__(config, raw_dir, session)
        self.contact_email = os.getenv(config.get("email_env", "CONTACT_EMAIL"), "")
        self.api_key = os.getenv(config.get("api_key_env", "NCBI_API_KEY"), "")
        self.rate_limiter = RateLimiter(float(config.get("delay_seconds", 0.4)))

    def fetch(self, query: SourceQuery) -> list[RawItem]:
        limit = int(query.limit or self.config.get("per_query_limit", 20))
        pmids = self._search_pmids(query, limit)
        if not pmids:
            return []

        xml_text = self._fetch_articles(query, pmids)
        raw_path = self.save_raw(xml_text, self.name, query, page=2, suffix="xml")
        fetched_at = fetched_now()
        items: list[RawItem] = []
        for record in parse_pubmed_xml(xml_text):
            pmid = record.get("pmid")
            items.append(
                RawItem(
                    source=self.name,
                    source_id=pmid,
                    query=query,
                    data=record,
                    raw_path=raw_path,
                    fetched_at=fetched_at,
                )
            )
            if len(items) >= limit:
                break
        return items

    def normalize(self, raw: RawItem) -> PaperItem:
        data = raw.data
        pmid = clean_text(data.get("pmid")) or raw.source_id
        published_date = to_iso_date(data.get("published_date"))
        item = PaperItem(
            canonical_id="pending",
            source=self.name,
            source_id=pmid,
            doi=normalize_doi(data.get("doi")),
            arxiv_id=None,
            pmid=pmid,
            openalex_id=None,
            semantic_scholar_id=None,
            title=clean_text(data.get("title")) or "Untitled",
            abstract=clean_text(data.get("abstract")),
            authors=compact_list(data.get("authors") or []),
            year=year_from_date(published_date) or data.get("year"),
            published_date=published_date,
            updated_date=None,
            venue=clean_text(data.get("journal")),
            work_type=clean_text(_first(data.get("publication_types") or [])),
            fields=compact_list(data.get("mesh_terms") or []),
            keywords=compact_list(data.get("keywords") or []),
            url=data.get("url") or (f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/" if pmid else None),
            pdf_url=None,
            oa_url=None,
            citation_count=None,
            influential_citation_count=None,
            is_open_access=None,
            license=None,
            source_query=raw.query.label,
            fetched_at=raw.fetched_at,
            raw_path=raw.raw_path,
        )
        return finalize_paper_item(item)

    def _search_pmids(self, query: SourceQuery, limit: int) -> list[str]:
        days_back = int(query.days_back or self.config.get("days_back", 14))
        params = {
            "db": "pubmed",
            "term": query.query,
            "retmax": limit,
            "retmode": "json",
            "sort": "pub date",
            "datetype": "pdat",
            "mindate": days_ago_iso(days_back),
            "maxdate": utc_now().date().isoformat(),
            "tool": "paper-radar",
        }
        params.update(self._polite_params())
        self.rate_limiter.wait()
        response = request_json(
            self.session,
            "GET",
            self.esearch_url,
            params=params,
            headers={"User-Agent": build_user_agent(self.contact_email)},
        )
        self.save_raw(response, self.name, query, page=1)
        id_list = (response.get("esearchresult") or {}).get("idlist") or []
        return [str(pmid).strip() for pmid in id_list if str(pmid).strip()]

    def _fetch_articles(self, query: SourceQuery, pmids: list[str]) -> str:
        params = {
            "db": "pubmed",
            "id": ",".join(pmids),
            "retmode": "xml",
            "tool": "paper-radar",
        }
        params.update(self._polite_params())
        self.rate_limiter.wait()
        return request_text(
            self.session,
            "GET",
            self.efetch_url,
            params=params,
            headers={"User-Agent": build_user_agent(self.contact_email)},
        )

    def _polite_params(self) -> dict[str, str]:
        params: dict[str, str] = {}
        if self.contact_email:
            params["email"] = self.contact_email
        if self.api_key:
            params["api_key"] = self.api_key
        return params


def parse_pubmed_xml(xml_text: str) -> list[dict[str, Any]]:
    root = ET.fromstring(xml_text)
    records: list[dict[str, Any]] = []
    for article in root.findall(".//PubmedArticle"):
        try:
            records.append(_article_to_record(article))
        except Exception:
            continue
    return records


def _article_to_record(article: ET.Element) -> dict[str, Any]:
    article_node = article.find("./MedlineCitation/Article")
    pmid = _text(article.find("./MedlineCitation/PMID")) or _article_id(article, "pubmed")
    published_date = _published_date(article)
    record = {
        "pmid": pmid,
        "doi": _doi(article),
        "title": _node_text(article_node.find("./ArticleTitle") if article_node is not None else None),
        "abstract": _abstract(article_node.find("./Abstract") if article_node is not None else None),
        "authors": _authors(article_node.find("./AuthorList") if article_node is not None else None),
        "published_date": published_date,
        "year": year_from_date(published_date),
        "journal": _node_text(article_node.find("./Journal/Title") if article_node is not None else None),
        "publication_types": _publication_types(article_node),
        "mesh_terms": _mesh_terms(article),
        "keywords": _keywords(article),
        "url": f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/" if pmid else None,
    }
    return record


def _doi(article: ET.Element) -> str | None:
    article_id_doi = _article_id(article, "doi")
    if article_id_doi:
        return normalize_doi(article_id_doi)
    for node in article.findall(".//ELocationID"):
        if (node.get("EIdType") or "").casefold() == "doi" and (node.get("ValidYN") or "Y") != "N":
            doi = normalize_doi(_node_text(node))
            if doi:
                return doi
    return None


def _article_id(article: ET.Element, id_type: str) -> str | None:
    for node in article.findall(".//ArticleId"):
        if (node.get("IdType") or "").casefold() == id_type.casefold():
            return _node_text(node)
    return None


def _abstract(abstract_node: ET.Element | None) -> str | None:
    if abstract_node is None:
        return None
    parts: list[str] = []
    abstract_texts = abstract_node.findall("./AbstractText")
    for node in abstract_texts:
        text = _node_text(node)
        if not text:
            continue
        label = clean_text(node.get("Label"))
        parts.append(f"{label}: {text}" if label and len(abstract_texts) > 1 else text)
    return clean_text(" ".join(parts))


def _authors(author_list: ET.Element | None) -> list[str]:
    if author_list is None:
        return []
    authors: list[str] = []
    for author in author_list.findall("./Author"):
        collective = _node_text(author.find("./CollectiveName"))
        if collective:
            authors.append(collective)
            continue
        fore_name = _node_text(author.find("./ForeName"))
        last_name = _node_text(author.find("./LastName"))
        initials = _node_text(author.find("./Initials"))
        parts = [fore_name or initials, last_name]
        name = clean_text(" ".join(part for part in parts if part))
        if name:
            authors.append(name)
    return authors


def _published_date(article: ET.Element) -> str | None:
    date_nodes = [
        article.find("./MedlineCitation/Article/Journal/JournalIssue/PubDate"),
        article.find("./MedlineCitation/Article/ArticleDate"),
        article.find("./MedlineCitation/DateCompleted"),
        article.find("./MedlineCitation/DateRevised"),
    ]
    for node in date_nodes:
        parsed = _date_node_to_iso(node)
        if parsed:
            return parsed
    return None


def _date_node_to_iso(node: ET.Element | None) -> str | None:
    if node is None:
        return None
    year = _node_text(node.find("./Year"))
    month = _node_text(node.find("./Month"))
    day = _node_text(node.find("./Day"))
    if year:
        parsed = to_iso_date(" ".join(part for part in [year, month, day] if part))
        return parsed or f"{year[:4]}-01-01"
    medline_date = _node_text(node.find("./MedlineDate"))
    if medline_date:
        parsed = to_iso_date(medline_date)
        if parsed:
            return parsed
        match = re.search(r"\b(\d{4})\b", medline_date)
        if match:
            return f"{match.group(1)}-01-01"
    return None


def _publication_types(article_node: ET.Element | None) -> list[str]:
    if article_node is None:
        return []
    return [
        text
        for text in (_node_text(node) for node in article_node.findall("./PublicationTypeList/PublicationType"))
        if text
    ]


def _mesh_terms(article: ET.Element) -> list[str]:
    return [
        text
        for text in (_node_text(node) for node in article.findall("./MedlineCitation/MeshHeadingList/MeshHeading/DescriptorName"))
        if text
    ]


def _keywords(article: ET.Element) -> list[str]:
    return [
        text
        for text in (_node_text(node) for node in article.findall("./MedlineCitation/KeywordList/Keyword"))
        if text
    ]


def _text(node: ET.Element | None) -> str | None:
    return clean_text(node.text if node is not None else None)


def _node_text(node: ET.Element | None) -> str | None:
    if node is None:
        return None
    return clean_text(" ".join(node.itertext()))


def _first(values: list[Any]) -> Any:
    return values[0] if values else None
