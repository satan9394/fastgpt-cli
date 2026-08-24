"""Shared helpers for the CLI command groups.

Loads configuration into Typer context object and provides a default-JSON emit
path that keeps stdout data-only and routes logs/errors to stderr.
"""

from __future__ import annotations

from typing import Any

import typer

from fastgptcli.api.fastgpt import FastGPTClient
from fastgptcli.config.settings import Config
from fastgptcli.output.render import emit_json, emit_jsonl


def load_runtime(config_path: str | None = None) -> tuple[Config, str]:
    """Load config (with path) for the command tree."""
    from fastgptcli.config.settings import load

    cfg, path = load(config_path)
    return cfg, str(path)


def get_client(app: typer.Context) -> FastGPTClient:
    obj: dict[str, Any] = app.obj or {}
    return obj["client"]


def get_config(app: typer.Context) -> Config:
    obj: dict[str, Any] = app.obj or {}
    return obj["config"]


def emit(obj: dict[str, Any], data: Any) -> None:
    """Emit a command result. Default is JSON on stdout.

    ``--output jsonl`` streams each element as an NDJSON line (bounded list
    contract streams its items), ``--output text`` prints a human-readable line.
    All modes keep stdout data-only; logs/progress go to stderr.
    """
    mode = obj.get("output", "json")
    if mode == "jsonl":
        emit_jsonl(data)
        return
    if mode == "json":
        emit_json(data)
        return
    # text/table rendering is a human convenience; keeps stdout data-only too.
    if isinstance(data, dict):
        if "items" in data and isinstance(data["items"], list):
            for item in data["items"]:
                print(_cell(item))
            if not data["items"]:
                print("[]")
            return
        if "items" not in data:
            print(_cell(data))
            return
    emit_json(data)


def _cell(item: dict[str, Any]) -> str:
    if "name" in item and "id" in item:
        return f"{item['id']}\t{item['name']}"
    if "name" in item:
        return str(item["name"])
    return str(item)


def materialize(obj: dict[str, Any]) -> dict[str, Any]:
    """Ensure the runtime context (client) is materialized on the Typer object."""
    if "client" not in obj:
        cfg = obj["config"]
        obj["client"] = FastGPTClient(cfg)
    return obj


def json_opt() -> Any:
    """A fresh `--json` flag for a leaf command signature (JSON is already the default).

    A ``bool`` default makes Typer treat this as a flag; ``is_flag=True`` is omitted
    to avoid the Typer deprecation warning.
    """
    return typer.Option(False, "--json", help="Force JSON output.")


def bind_json(obj: dict[str, Any], json_flag: bool) -> None:
    """Force JSON output mode when --json is supplied (JSON is already the default)."""
    if json_flag:
        obj["output"] = "json"


def paginated(items: list[Any], limit: int, page: int) -> list[Any]:
    """Bound ``items`` by a 1-based page window: [ (page-1)*limit : page*limit ]."""
    if limit <= 0:
        return []
    start = max((page - 1) * limit, 0)
    return items[start : start + limit]


def limit_opt(default: int = 50) -> Any:
    """A bounded-output --limit option (CLI-Spec principle 6)."""
    return typer.Option(default, "--limit", help="Max items (bounded output).")


def page_opt() -> Any:
    """A 1-based --page option for paged list commands (CLI-Spec principle 6)."""
    return typer.Option(1, "--page", help="1-based page number for pagination.")

