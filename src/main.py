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
from src.sources.arxiv import ArxivClient
from src.sources.base import SourceQuery
from src.sources.openalex import OpenAlexClient
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
        }.items():
            config = sources_config.get(source_name, {})
            if not config.get("enabled", False):
                logger.info("source=%s skipped because it is disabled", source_name)
                continue
            client = client_cls(config, ROOT / "data" / "raw")
            collected_ids.update(run_source(client, config, topics_config, store, logger))

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
        try:
            raw_items = client.fetch(query)
        except Exception as exc:  # noqa: BLE001 - source/query isolation is intentional
            logger.exception("source=%s query=%s failed: %s", client.name, query.label, exc)
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
        logger.info(
            "source=%s query=%s fetched=%s stored=%s new=%s",
            client.name,
            query.label,
            len(raw_items),
            normalized_count,
            new_count,
        )
    return collected_ids


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
