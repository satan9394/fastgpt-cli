"""kb command group: kb create / list / upload / get / delete."""

from __future__ import annotations

import os

import typer

from fastgptcli.cli._common import bind_json, emit, get_client, json_opt, limit_opt, page_opt, paginated
from fastgptcli.output.render import CliError, info

app = typer.Typer(help="Knowledge base domain: create/list/upload/get/delete.")


@app.command("create")
def kb_create(
    ctx: typer.Context,
    name: str = typer.Argument(..., help="Knowledge base name."),
    model: str = typer.Option("", "--model", help="Embedding model."),
    json_flag: bool = json_opt(),
) -> None:
    """Create a knowledge base. Default JSON: {kb_id, name, status}."""
    if json_flag:
        ctx.obj["output"] = "json"
    client = get_client(ctx)
    emit(ctx.obj, client.kb_create(name).to_dict())


@app.command("list")
def kb_list(
    ctx: typer.Context,
    limit: int = limit_opt(),
    page: int = page_opt(),
    json_flag: bool = json_opt(),
) -> None:
    """List knowledge bases (stable contract: {items[], total})."""
    bind_json(ctx.obj, json_flag)
    client = get_client(ctx)
    result = client.kb_list()
    bounded = paginated(result.items, limit, page)
    emit(ctx.obj, {"items": bounded, "total": len(result.items)})


@app.command("upload")
def kb_upload(
    ctx: typer.Context,
    kb: str = typer.Option(..., "--kb", help="Knowledge base id/name."),
    path: str = typer.Argument(..., help="File or directory path."),
    recursive: bool = typer.Option(False, "--recursive", help="Recurse into subdirectories."),
    json_flag: bool = json_opt(),
) -> None:
    """Upload documents to a knowledge base. Progress goes to stderr."""
    if json_flag:
        ctx.obj["output"] = "json"
    files = _collect_files(path, recursive)
    if not files:
        raise CliError(f"路径下无文件: {path}", kind="validation")
    info(f"uploading {len(files)} file(s) to kb {kb}")
    client = get_client(ctx)
    result = client.kb_upload(kb, files)
    emit(ctx.obj, result)


@app.command("get")
def kb_get(
    ctx: typer.Context,
    kb_id: str = typer.Argument(..., help="Knowledge base id."),
    json_flag: bool = json_opt(),
) -> None:
    """Show a knowledge base detail."""
    if json_flag:
        ctx.obj["output"] = "json"
    client = get_client(ctx)
    emit(ctx.obj, client.kb_get(kb_id))


@app.command("delete")
def kb_delete(
    ctx: typer.Context,
    kb_id: str = typer.Argument(..., help="Knowledge base id."),
    yes: bool = typer.Option(False, "--yes", help="Confirm deletion (non-interactive)."),
    json_flag: bool = json_opt(),
) -> None:
    """Delete a knowledge base. Idempotent; requires --yes."""
    if json_flag:
        ctx.obj["output"] = "json"
    if not yes:
        raise CliError("kb delete 需要 --yes 确认（非交互默认）", kind="validation")
    info(f"deleting kb {kb_id}")
    client = get_client(ctx)
    emit(ctx.obj, client.kb_delete(kb_id))


def _collect_files(path: str, recursive: bool) -> list[str]:
    if os.path.isdir(path):
        if recursive:
            return [os.path.join(root, f) for root, _, files in os.walk(path) for f in sorted(files)]
        return sorted(f for f in os.listdir(path) if os.path.isfile(os.path.join(path, f)))
    if os.path.isfile(path):
        return [path]
    return []
