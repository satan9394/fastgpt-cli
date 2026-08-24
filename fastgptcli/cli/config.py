"""config command group: show / path / set / init (migrated from Go config semantics)."""

from __future__ import annotations

from typing import Any

import typer

from fastgptcli.cli._common import emit, get_config, json_opt
from fastgptcli.config.settings import chat_api_key, defaults_path, save, to_dict
from fastgptcli.output.render import CliError

app = typer.Typer(help="Configuration management.")


@app.command("show")
def config_show(
    ctx: typer.Context,
    json_flag: bool = json_opt(),
) -> None:
    """Show effective config. Default JSON. API keys are never printed."""
    if json_flag:
        ctx.obj["output"] = "json"
    cfg = get_config(ctx)
    payload = to_dict(cfg)
    payload["chat_api_key_set"] = bool(chat_api_key())
    emit(ctx.obj, payload)


@app.command("path")
def config_path(
    ctx: typer.Context,
    json_flag: bool = json_opt(),
) -> None:
    """Show the config file path."""
    if json_flag:
        ctx.obj["output"] = "json"
    emit(ctx.obj, {"path": str(defaults_path())})


@app.command("set")
def config_set(
    ctx: typer.Context,
    key: str = typer.Argument(..., help="Dot path, e.g. server.host."),
    value: str = typer.Argument(..., help="Value."),
    json_flag: bool = json_opt(),
) -> None:
    """Set a config field and persist it. Supports int fields automatically."""
    if json_flag:
        ctx.obj["output"] = "json"
    cfg = get_config(ctx)
    fields = _settable_fields(cfg)
    if key not in fields:
        raise CliError(
            f"未知配置项 {key!r}（可用: {', '.join(sorted(fields))}）",
            kind="validation",
            details={"valid_keys": sorted(fields)},
        )
    fields[key](value)
    save(cfg, defaults_path())
    emit(ctx.obj, {"key": key, "path": str(defaults_path())})


@app.command("init")
def config_init(
    ctx: typer.Context,
    force: bool = typer.Option(False, "--force", help="Overwrite existing config."),
    json_flag: bool = json_opt(),
) -> None:
    """Write the default config file (idempotent unless --force)."""
    if json_flag:
        ctx.obj["output"] = "json"
    cfg = get_config(ctx)
    path = defaults_path()
    if path.exists() and not force:
        raise CliError(f"配置文件已存在: {path}（加 --force 覆盖）", kind="conflict")
    save(cfg, path)
    emit(ctx.obj, {"path": str(path), "created": True})


def _settable_fields(cfg: Any) -> dict[str, Any]:
    """Return a dict of dot-path -> setter callable for int/str fields."""
    limits = {
        "server.host": (str, "server.host"),
        "server.port": (int, "server.port"),
        "server.api_key": (str, "server.api_key"),
        "defaults.model": (str, "defaults.model"),
        "defaults.chunk_size": (int, "defaults.chunk_size"),
        "defaults.chunk_overlap": (int, "defaults.chunk_overlap"),
        "logging.level": (str, "logging.level"),
        "logging.file": (str, "logging.file"),
        "chat.base_url": (str, "chat.base_url"),
        "chat.model": (str, "chat.model"),
    }

    def make_setter(attr_path: str, kind: type) -> Any:
        parts = attr_path.split(".")

        def setter(value: str) -> None:
            obj = cfg
            for part in parts[:-1]:
                obj = getattr(obj, part)
            if kind is int:
                try:
                    parsed: Any = int(value)
                except ValueError as exc:
                    raise CliError(f"期望整数，得到 {value!r}", kind="validation") from exc
            else:
                parsed = value
            setattr(obj, parts[-1], parsed)

        return setter

    return {key: make_setter(attr, kind) for key, (kind, attr) in limits.items()}
