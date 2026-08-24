"""Unified output layer implementing the CLI-Spec contract.

Rules (from cli-spec six principles):
- data -> stdout; logs/progress/warnings/errors -> stderr
- default output is stable JSON
- unified error structure: {"error": {"kind", "message", "details"}}
- bounded output via --limit
"""

from __future__ import annotations

import json
import sys
from typing import Any, TextIO

import click


class CliError(click.ClickException):
    """Structured error: emitted to stderr as JSON, exits non-zero.

    Subclassing click.ClickException lets Typer's standalone mode catch it and
    route it to stderr (never stdout) with a proper exit code, keeping data and
    diagnostics separated. ``kind`` is one of: validation, not_found, conflict,
    auth, backend, transport, internal.
    """

    exit_code = 1

    def __init__(self, message: str, kind: str = "internal", details: dict[str, Any] | None = None):
        super().__init__(message)
        self.kind = kind
        self.message = message
        self.details = details or {}

    def to_dict(self) -> dict[str, Any]:
        return {"error": {"kind": self.kind, "message": self.message, "details": self.details}}

    def show(self, file: TextIO | None = None) -> None:
        file = file or sys.stderr
        file.write(json.dumps(self.to_dict(), ensure_ascii=False) + "\n")


def emit_json(data: Any, *, stream: TextIO | None = None, indent: int | None = 2) -> None:
    """Write ``data`` as JSON to stdout (or an explicit stream).

    Never mixes data with logs; logs go to stderr via info().
    """
    stream = stream or sys.stdout
    text = json.dumps(_bare(data), ensure_ascii=False, indent=indent, default=_default)
    print(text, file=stream)


def emit_jsonl(data: Any, *, stream: TextIO | None = None) -> None:
    """Stream ``data`` as JSON Lines (one JSON value per line) to stdout.

    For the bounded list contract (``{"items": [...]}`` or ``{"results": [...]}``)
    each element is streamed as its own NDJSON line so large results never need to
    be buffered as one document. A scalar value is emitted as a single line.

    Always data-only (stdout); diagnostics still go to stderr via info().
    """
    stream = stream or sys.stdout
    for element in _collection(data):
        print(json.dumps(_bare(element), ensure_ascii=False, default=_default), file=stream)


def _collection(data: Any) -> list[Any]:
    """Return the iterable to stream for JSONL, or ``[data]`` for a scalar."""
    if isinstance(data, dict):
        for key in ("items", "results", "events"):
            val = data.get(key)
            if isinstance(val, list):
                return val
    return [data]


def emit_error(exc: CliError, *, stream: TextIO | None = None) -> None:
    """Write a structured error to stderr (single-line JSON)."""
    stream = stream or sys.stderr
    print(json.dumps(exc.to_dict(), ensure_ascii=False), file=stream)


def info(message: str, *, stream: TextIO | None = None) -> None:
    """Write a non-data informational/progress line to stderr."""
    stream = stream or sys.stderr
    print(message, file=stream)


def _bare(obj: Any) -> Any:
    """Coerce a DTO / modelled object to a plain JSON-serializable value."""
    if hasattr(obj, "to_dict"):
        return obj.to_dict()
    if hasattr(obj, "model_dump"):
        return obj.model_dump()
    if isinstance(obj, (list | tuple)):
        return [_bare(o) for o in obj]
    if isinstance(obj, dict):
        return {k: _bare(v) for k, v in obj.items()}
    return obj


def _default(obj: Any) -> Any:
    if hasattr(obj, "model_dump"):
        return obj.model_dump()
    if hasattr(obj, "to_dict"):
        return obj.to_dict()
    raise TypeError(f"Object of type {type(obj).__name__} is not JSON serializable")
