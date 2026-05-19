from __future__ import annotations

import logging
from collections.abc import Iterable
from dataclasses import replace
from pathlib import Path
from typing import Any

import yaml

from src.pipeline.export import export_jsonl
from src.pipeline.logging_utils import setup_logging
from src.pipeline.store import PaperStore
from src.pipeline.dedup import detect_possible_duplicates
from src.sources.arxiv import ArxivClient
from src.sources.base import SourceQuery
from src.sources.biorxiv import BiorxivClient, MedrxivClient
from src.sources.crossref import CrossrefClient
from src.sources.openalex import OpenAlexClient
from src.sources.pubmed import PubMedClient
from src.sources.semantic_scholar import SemanticScholarClient
from src.utils.dates import iso_week_label


ROOT = Path.cwd() if (Path.cwd() / "config" / "sources.yaml").exists() else Path(__file__).resolve().parents[1]


def main() -> None:
    logger = setup_logging(ROOT / "logs")
    sources_config = load_yaml(ROOT / "config" / "sources.yaml").get("sources", {})
    topics_config = load_yaml(ROOT / "config" / "topics.yaml").get("lanes", {})
    store = PaperStore(ROOT / "data" / "papers.sqlite")
    collected_ids: set[str] = set()

    try:
        for source_name, client_cls in {
            "openalex": OpenAlexClient,
            "arxiv": ArxivClient,
            "pubmed": PubMedClient,
            "biorxiv": BiorxivClient,
            "medrxiv": MedrxivClient,
        }.items():
            config = sources_config.get(source_name, {})
            if not config.get("enabled", False):
                logger.info("source=%s skipped because it is disabled", source_name)
                continue
            client = client_cls(config, ROOT / "data" / "raw")
            collected_ids.update(run_source(client, config, topics_config, store, logger))

        collected_ids.update(
            run_enrichment(
                "crossref",
                CrossrefClient,
                sources_config.get("crossref", {}),
                store,
                collected_ids,
                logger,
            )
        )
        collected_ids.update(
            run_enrichment(
                "semantic_scholar",
                SemanticScholarClient,
                sources_config.get("semantic_scholar", {}),
                store,
                collected_ids,
                logger,
            )
        )
        detect_and_store_duplicates(store, collected_ids, logger)

        output_path = ROOT / "data" / "exports" / f"candidates_{iso_week_label()}.jsonl"
        exported = export_jsonl(store.fetch_paper_items(collected_ids), output_path)
        logger.info("exported=%s path=%s", exported, output_path)
    finally:
        store.close()


def run_source(
    client: Any,
    config: dict[str, Any],
    lanes: dict[str, Any],
    store: PaperStore,
    logger: logging.Logger,
) -> set[str]:
    max_total = int(config.get("max_total", 50))
    total_seen = 0
    collected_ids: set[str] = set()
    for query in build_queries(client.name, config, lanes):
        if total_seen >= max_total:
            break
        remaining = max_total - total_seen
        query = replace(query, limit=min(int(query.limit or remaining), remaining))
        run_id = store.start_crawl_run(source=client.name, query=query.label)
        try:
            raw_items = client.fetch(query)
        except Exception as exc:  # noqa: BLE001 - source/query isolation is intentional
            logger.exception("source=%s query=%s failed: %s", client.name, query.label, exc)
            store.fail_crawl_run(run_id, error=str(exc))
            continue

        new_count = 0
        normalized_count = 0
        for raw in raw_items:
            try:
                item = client.normalize(raw)
                if store.upsert_paper(item):
                    new_count += 1
                collected_ids.add(item.canonical_id)
                normalized_count += 1
            except Exception as exc:  # noqa: BLE001 - one bad record should not stop a crawl
                logger.exception(
                    "source=%s query=%s item=%s normalize/store failed: %s",
                    client.name,
                    query.label,
                    raw.source_id,
                    exc,
                )
        total_seen += normalized_count
        store.finish_crawl_run(
            run_id,
            items_found=len(raw_items),
            items_new=new_count,
        )
        logger.info(
            "source=%s query=%s fetched=%s stored=%s new=%s",
            client.name,
            query.label,
            len(raw_items),
            normalized_count,
            new_count,
        )
    return collected_ids


def run_enrichment(
    source_name: str,
    client_cls: Any,
    config: dict[str, Any],
    store: PaperStore,
    collected_ids: set[str],
    logger: logging.Logger,
) -> set[str]:
    if not config.get("enabled", False):
        logger.info("source=%s skipped because it is disabled", source_name)
        return set()
    client = client_cls(config, ROOT / "data" / "raw")
    unavailable_reason = getattr(client, "unavailable_reason", None)
    if unavailable_reason:
        logger.warning("source=%s skipped: %s", source_name, unavailable_reason)
        return set()
    max_total = int(config.get("max_total", 200))
    updated_ids: set[str] = set()
    candidates = _enrichment_candidates(source_name, store.fetch_paper_items(collected_ids))
    for item in candidates[:max_total]:
        query_label = _enrichment_query_label(source_name, item)
        run_id = store.start_crawl_run(source=source_name, query=query_label)
        try:
            enriched = client.enrich_item(item)
            if enriched is None:
                store.finish_crawl_run(run_id, items_found=0, items_new=0, status="skipped")
                continue
            is_new = store.upsert_paper(enriched)
            updated_ids.add(enriched.canonical_id)
            store.finish_crawl_run(run_id, items_found=1, items_new=1 if is_new else 0)
            logger.info(
                "source=%s query=%s enriched=%s",
                source_name,
                query_label,
                enriched.canonical_id,
            )
        except Exception as exc:  # noqa: BLE001 - enrichment is per-record and isolated
            logger.exception("source=%s query=%s enrichment failed: %s", source_name, query_label, exc)
            store.fail_crawl_run(run_id, error=str(exc))
    return updated_ids


def detect_and_store_duplicates(
    store: PaperStore,
    collected_ids: set[str],
    logger: logging.Logger,
) -> None:
    current_items = store.fetch_paper_items(collected_ids)
    all_items = store.list_papers_for_duplicate_check()
    matches = detect_possible_duplicates(current_items, all_items)
    inserted = 0
    for match in matches:
        if store.record_possible_duplicate(
            left_id=match.left_id,
            right_id=match.right_id,
            reason=match.reason,
            score=match.score,
        ):
            inserted += 1
    logger.info("possible_duplicates detected=%s new=%s", len(matches), inserted)


def _enrichment_candidates(source_name: str, items: list[Any]) -> list[Any]:
    if source_name == "crossref":
        return [item for item in items if item.doi]
    if source_name == "semantic_scholar":
        return [item for item in items if item.doi or item.arxiv_id]
    return []


def _enrichment_query_label(source_name: str, item: Any) -> str:
    if source_name == "crossref":
        return f"doi:{item.doi}"
    if item.doi:
        return f"doi:{item.doi}"
    return f"arxiv:{item.arxiv_id}"


def build_queries(
    source_name: str,
    config: dict[str, Any],
    lanes: dict[str, Any],
) -> Iterable[SourceQuery]:
    days_back = int(config.get("days_back", 14))
    per_query_limit = int(config.get("per_query_limit", 10))
    max_queries_per_lane = int(config.get("max_queries_per_lane", 1))
    for lane_name, lane_config in lanes.items():
        keywords = lane_config.get("keywords", [])
        for keyword in keywords[:max_queries_per_lane]:
            yield SourceQuery(
                lane=lane_name,
                query=keyword,
                query_type="keyword",
                days_back=days_back,
                limit=per_query_limit,
            )
        if source_name == "arxiv":
            categories = lane_config.get("arxiv_categories", [])
            for category in categories[:max_queries_per_lane]:
                yield SourceQuery(
                    lane=lane_name,
                    query=category,
                    query_type="category",
                    days_back=days_back,
                    limit=per_query_limit,
                )


def load_yaml(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        return yaml.safe_load(handle) or {}


if __name__ == "__main__":
    main()
