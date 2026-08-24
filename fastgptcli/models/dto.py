"""Shared output DTOs / models for fastgpt-cli commands.

These define the stable JSON contract field names (order-independent dicts),
matching the CLI-Spec structured-output principle.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


def _empty_list() -> list[dict[str, Any]]:
    return []


@dataclass
class ListResult:
    """Standard list contract: items[] + total."""

    items: list[dict[str, Any]] = field(default_factory=_empty_list)
    total: int = 0

    def to_dict(self) -> dict[str, Any]:
        return {"items": self.items, "total": self.total}


@dataclass
class DatasetInfo:
    dataset_id: str
    name: str
    status: str

    def to_dict(self) -> dict[str, Any]:
        return {"dataset_id": self.dataset_id, "name": self.name, "status": self.status}


@dataclass
class ImportResult:
    dataset_id: str
    imported: int
    files: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {"dataset_id": self.dataset_id, "imported": self.imported, "files": self.files}


@dataclass
class KbInfo:
    kb_id: str
    name: str
    status: str

    def to_dict(self) -> dict[str, Any]:
        return {"kb_id": self.kb_id, "name": self.name, "status": self.status}


@dataclass
class AgentRunResult:
    """Structured output for `agent run`: {answer, tokens, sources}."""

    answer: str
    tokens: int = 0
    sources: list[dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {"answer": self.answer, "tokens": self.tokens, "sources": self.sources}


@dataclass
class SearchResultItem:
    score: float = 0.0
    content: str = ""
    source: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {"score": self.score, "content": self.content, "source": self.source}


@dataclass
class SearchResult:
    results: list[SearchResultItem] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {"results": [r.to_dict() for r in self.results]}
