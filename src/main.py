from __future__ import annotations

import argparse
import logging
from collections.abc import Iterable
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Any

from src.app.config import RuntimeConfig, load_runtime_config
from src.app.runtime import candidate_export_path
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


DISCOVERY_CLIENTS: dict[str, Any] = {
    "openalex": OpenAlexClient,
    "arxiv": ArxivClient,
    "pubmed": PubMedClient,
    "biorxiv": BiorxivClient,
    "medrxiv": MedrxivClient,
}

ENRICHMENT_CLIENTS: dict[str, Any] = {
    "crossref": CrossrefClient,
    "semantic_scholar": SemanticScholarClient,
}


@dataclass(frozen=True)
class PipelineResult:
    export_path: Path
    exported_count: int
    collected_count: int
    empty_export_skipped: bool = False


@dataclass(frozen=True)
class SourcePreview:
    name: str
    source_type: str
    enabled: bool
    max_total: int | None
    per_query_limit: int | None
    days_back: int | None
    planned_queries: tuple[SourceQuery, ...]
    estimated_max_records: int


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Run the Paper Radar metadata pipeline.")
    parser.add_argument("--config-dir", type=Path, default=None)
    parser.add_argument(
        "--source-preview",
        action="store_true",
        help="Show configured sources and planned queries without accessing the network.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Alias for --source-preview.",
    )
    parser.add_argument(
        "--allow-empty-export",
        action="store_true",
        help="Write an empty candidate export when no records are collected.",
    )
    args = parser.parse_args(argv)
    runtime = load_runtime_config(config_dir=args.config_dir)
    if args.source_preview or args.dry_run:
        print(render_source_preview(build_source_preview(runtime)), end="")
        return
    run_pipeline(runtime, allow_empty_export=args.allow_empty_export)


def run_pipeline(runtime: RuntimeConfig, *, allow_empty_export: bool = False) -> PipelineResult:
    logger = setup_logging(runtime.paths.logs_dir)
    sources_config = runtime.sources
    topics_config = runtime.topics
    store = PaperStore(runtime.paths.database_path)
    collected_ids: set[str] = set()

    try:
        for source_name, client_cls in DISCOVERY_CLIENTS.items():
            config = sources_config.get(source_name, {})
            if not config.get("enabled", False):
                logger.info("source=%s skipped because it is disabled", source_name)
                continue
            client = client_cls(config, runtime.paths.raw_dir)
            collected_ids.update(run_source(client, config, topics_config, store, logger))

        collected_ids.update(
            run_enrichment(
                "crossref",
                CrossrefClient,
                sources_config.get("crossref", {}),
                store,
                collected_ids,
                logger,
                runtime.paths.raw_dir,
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
                runtime.paths.raw_dir,
            )
        )
        detect_and_store_duplicates(store, collected_ids, logger)

        output_path = candidate_export_path(runtime)
        if not collected_ids and not allow_empty_export:
            logger.warning(
                "no candidate records collected; skipping export to avoid overwriting %s. "
                "Use --allow-empty-export to write an empty candidate export.",
                output_path,
            )
            return PipelineResult(
                export_path=output_path,
                exported_count=0,
                collected_count=0,
                empty_export_skipped=True,
            )
        exported = export_jsonl(store.fetch_paper_items(collected_ids), output_path)
        logger.info("exported=%s path=%s", exported, output_path)
        return PipelineResult(
            export_path=output_path,
            exported_count=exported,
            collected_count=len(collected_ids),
        )
    finally:
        store.close()


def build_source_preview(runtime: RuntimeConfig) -> list[SourcePreview]:
    previews: list[SourcePreview] = []
    for source_name, config in runtime.sources.items():
        enabled = bool(config.get("enabled", False))
        source_type = _source_type(source_name)
        max_total = _optional_int(config.get("max_total"))
        per_query_limit = _optional_int(config.get("per_query_limit"))
        days_back = _optional_int(config.get("days_back"))
        planned_queries: tuple[SourceQuery, ...] = ()
        estimated_max_records = 0

        if enabled and source_name in DISCOVERY_CLIENTS:
            planned_queries = tuple(build_planned_queries(source_name, config, runtime.topics))
            estimated_max_records = sum(int(query.limit or 0) for query in planned_queries)
        elif enabled and source_name in ENRICHMENT_CLIENTS:
            estimated_max_records = max_total or 0

        previews.append(
            SourcePreview(
                name=source_name,
                source_type=source_type,
                enabled=enabled,
                max_total=max_total,
                per_query_limit=per_query_limit,
                days_back=days_back,
                planned_queries=planned_queries,
                estimated_max_records=estimated_max_records,
            )
        )
    return previews


def build_planned_queries(
    source_name: str,
    config: dict[str, Any],
    lanes: dict[str, Any],
) -> list[SourceQuery]:
    max_total = int(config.get("max_total", 50))
    total_planned = 0
    planned: list[SourceQuery] = []
    for query in build_queries(source_name, config, lanes):
        if total_planned >= max_total:
            break
        remaining = max_total - total_planned
        limit = min(int(query.limit or remaining), remaining)
        planned_query = replace(query, limit=limit)
        planned.append(planned_query)
        total_planned += limit
    return planned


def render_source_preview(previews: Iterable[SourcePreview]) -> str:
    enabled = [preview for preview in previews if preview.enabled]
    disabled = [preview for preview in previews if not preview.enabled]
    lines = [
        "# Source Preview",
        "",
        "Network access: disabled",
        "",
        "Enabled sources:",
    ]
    if enabled:
        for preview in enabled:
            lines.extend(_render_preview_source(preview))
    else:
        lines.append("- none")

    lines.extend(["", "Disabled sources:"])
    if disabled:
        for preview in disabled:
            lines.append(
                f"- {preview.name} ({preview.source_type}): "
                f"max_total={_display_limit(preview.max_total)} "
                f"per_query_limit={_display_limit(preview.per_query_limit)} "
                f"days_back={_display_limit(preview.days_back)} "
                f"estimated_max_records={preview.estimated_max_records}"
            )
    else:
        lines.append("- none")
    return "\n".join(lines) + "\n"


def _render_preview_source(preview: SourcePreview) -> list[str]:
    details = [
        f"- {preview.name} ({preview.source_type}):",
        f"  max_total={_display_limit(preview.max_total)}",
        f"  per_query_limit={_display_limit(preview.per_query_limit)}",
        f"  days_back={_display_limit(preview.days_back)}",
        f"  estimated_max_records={preview.estimated_max_records}",
    ]
    if preview.planned_queries:
        details.append("  planned_queries:")
        details.extend(
            f"    - {query.label} limit={_display_limit(query.limit)}" for query in preview.planned_queries
        )
    elif preview.source_type == "enrichment":
        details.append("  planned_queries: enrichment depends on collected candidates")
    else:
        details.append("  planned_queries: none")
    return details


def _source_type(source_name: str) -> str:
    if source_name in DISCOVERY_CLIENTS:
        return "discovery"
    if source_name in ENRICHMENT_CLIENTS:
        return "enrichment"
    return "config-only"


def _optional_int(value: Any) -> int | None:
    if value is None:
        return None
    return int(value)


def _display_limit(value: int | None) -> str:
    if value is None:
        return "unset"
    return str(value)


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
    raw_dir: Path,
) -> set[str]:
    if not config.get("enabled", False):
        logger.info("source=%s skipped because it is disabled", source_name)
        return set()
    client = client_cls(config, raw_dir)
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


if __name__ == "__main__":
    main()
