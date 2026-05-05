from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


class PaperItem(BaseModel):
    """Unified paper metadata emitted by all source drivers."""

    model_config = ConfigDict(extra="forbid")

    canonical_id: str
    source: str
    source_id: str | None = None

    doi: str | None = None
    arxiv_id: str | None = None
    pmid: str | None = None
    openalex_id: str | None = None
    semantic_scholar_id: str | None = None

    title: str
    abstract: str | None = None
    authors: list[str] = Field(default_factory=list)
    year: int | None = None
    published_date: str | None = None
    updated_date: str | None = None

    venue: str | None = None
    work_type: str | None = None
    fields: list[str] = Field(default_factory=list)
    keywords: list[str] = Field(default_factory=list)

    url: str | None = None
    pdf_url: str | None = None
    oa_url: str | None = None

    citation_count: int | None = None
    influential_citation_count: int | None = None

    is_open_access: bool | None = None
    license: str | None = None

    source_query: str | None = None
    fetched_at: str = Field(default_factory=utc_now_iso)

    raw_path: str | None = None

    @field_validator("title")
    @classmethod
    def title_must_not_be_empty(cls, value: str) -> str:
        cleaned = " ".join(value.split())
        if not cleaned:
            raise ValueError("title must not be empty")
        return cleaned

    @field_validator("authors", "fields", "keywords", mode="before")
    @classmethod
    def coerce_list(cls, value: Any) -> list[str]:
        if value is None:
            return []
        if isinstance(value, list):
            return [str(item).strip() for item in value if str(item).strip()]
        return [str(value).strip()] if str(value).strip() else []

    def to_jsonable(self) -> dict[str, Any]:
        return self.model_dump(mode="json")
