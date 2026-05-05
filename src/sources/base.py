from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol

import requests

from src.models.paper import PaperItem
from src.utils.dates import iso_week_label, utc_now_iso


@dataclass(slots=True)
class SourceQuery:
    lane: str
    query: str
    query_type: str = "keyword"
    days_back: int | None = None
    limit: int | None = None

    @property
    def label(self) -> str:
        return f"{self.lane}:{self.query_type}:{self.query}"


@dataclass(slots=True)
class RawItem:
    source: str
    source_id: str | None
    query: SourceQuery
    data: dict[str, Any]
    raw_path: str | None
    fetched_at: str


class BaseSourceClient(Protocol):
    name: str

    def fetch(self, query: SourceQuery) -> list[RawItem]:
        ...

    def normalize(self, raw: RawItem) -> PaperItem:
        ...


class JsonSourceClient:
    name = "base"

    def __init__(self, config: dict[str, Any], raw_dir: Path, session: requests.Session | None = None):
        self.config = config
        self.raw_dir = raw_dir
        self.session = session or requests.Session()

    def save_raw(
        self,
        response: dict[str, Any] | list[Any] | str,
        source: str,
        query: SourceQuery,
        *,
        page: int = 1,
        suffix: str = "json",
    ) -> str:
        source_dir = self.raw_dir / source / iso_week_label()
        source_dir.mkdir(parents=True, exist_ok=True)
        safe_lane = _safe_filename(query.lane)
        safe_query = _safe_filename(query.query)[:64]
        path = source_dir / f"{safe_lane}_{query.query_type}_{safe_query}_{page:03d}.{suffix}"
        if suffix == "json":
            path.write_text(json.dumps(response, ensure_ascii=False, indent=2), encoding="utf-8")
        else:
            path.write_text(str(response), encoding="utf-8")
        return str(path)


class PlaceholderSourceClient(JsonSourceClient):
    """Disabled V1 source placeholder with the same public shape as real drivers."""

    name = "placeholder"

    def fetch(self, query: SourceQuery) -> list[RawItem]:
        return []

    def normalize(self, raw: RawItem) -> PaperItem:
        raise NotImplementedError(f"{self.name} is reserved for a later implementation")


def fetched_now() -> str:
    return utc_now_iso()


def _safe_filename(value: str) -> str:
    return re.sub(r"[^A-Za-z0-9_.-]+", "_", value).strip("_") or "query"
