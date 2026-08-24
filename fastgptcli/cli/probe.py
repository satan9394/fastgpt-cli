"""probe command group: status / health (read-only probing).

Payload building is centralized in :func:`status_payload` / :func:`health_payload`
so the root-level ``status``/``health`` commands (main.py) and the ``probe`` group
share a single source of truth instead of duplicating logic.
"""

from __future__ import annotations

from typing import Any

import typer

from fastgptcli import __version__
from fastgptcli.cli._common import emit, get_config, json_opt
from fastgptcli.config.settings import Config, chat_api_key

app = typer.Typer(help="Read-only probe commands: status / health.")


def backend_configured(cfg: Config) -> bool:
    return bool(cfg.server.api_key) or cfg.server.host != "localhost"


def status_payload(cfg: Config) -> dict[str, Any]:
    return {
        "version": __version__,
        "server": cfg.server_addr(),
        "backend_configured": backend_configured(cfg),
        "chat_configured": bool(chat_api_key()),
        "status": "ok",
    }


def health_payload(cfg: Config) -> dict[str, Any]:
    return {
        "healthy": True,
        "server": cfg.server_addr(),
        "components": {
            "server": "configured" if backend_configured(cfg) else "not_connected",
            "chat": "configured" if chat_api_key() else "not_configured",
        },
    }


@app.command("status")
def status_cmd(
    ctx: typer.Context,
    json_flag: bool = json_opt(),
) -> None:
    """Show runtime status. Default JSON: {version, server, backend_configured, status}."""
    if json_flag:
        ctx.obj["output"] = "json"
    cfg = get_config(ctx)
    emit(ctx.obj, status_payload(cfg))


@app.command("health")
def health_cmd(
    ctx: typer.Context,
    json_flag: bool = json_opt(),
) -> None:
    """Health probe. Reports reachability of configured backends."""
    if json_flag:
        ctx.obj["output"] = "json"
    cfg = get_config(ctx)
    emit(ctx.obj, health_payload(cfg))
