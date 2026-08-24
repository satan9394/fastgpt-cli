"""dataset command group: dataset create / import ./docs / ls / delete."""

from __future__ import annotations

import os

import typer

from fastgptcli.cli._common import bind_json, emit, get_client, json_opt, limit_opt, page_opt, paginated
from fastgptcli.output.render import CliError, info

app = typer.Typer(help="Data set (dataset) domain: create/import/ls/delete.")


@app.command("create")
def dataset_create(
    ctx: typer.Context,
    name: str = typer.Argument(..., help="Dataset name."),
    json_flag: bool = json_opt(),
) -> None:
    """Create a dataset. Default JSON: {dataset_id, name, status}."""
    if json_flag:
        ctx.obj["output"] = "json"
    client = get_client(ctx)
    emit(ctx.obj, client.dataset_create(name))


@app.command("import")
def dataset_import(
    ctx: typer.Context,
    path: str = typer.Argument(..., help="Directory or file to import, e.g. ./docs."),
    dataset_id: str = typer.Option("", "--dataset", help="Target dataset id."),
    json_flag: bool = json_opt(),
) -> None:
    """Import documents from a path into a dataset (high-level bulk import)."""
    if json_flag:
        ctx.obj["output"] = "json"

    files: list[str] = []
    if os.path.isdir(path):
        files = sorted(
            os.path.join(path, f)
            for f in os.listdir(path)
            if os.path.isfile(os.path.join(path, f))
        )
    elif os.path.isfile(path):
        # Preserve the full path so the API client can locate the file (matches kb.py).
        files = [path]
    else:
        raise CliError(f"路径不存在: {path}", kind="validation")

    if not dataset_id:
        raise CliError("dataset import 需要 --dataset <id> 指定目标数据集", kind="validation")

    client = get_client(ctx)
    result = client.dataset_import(dataset_id, files)
    emit(ctx.obj, result.to_dict())


@app.command("ls")
def dataset_ls(
    ctx: typer.Context,
    limit: int = limit_opt(),
    page: int = page_opt(),
    json_flag: bool = json_opt(),
) -> None:
    """List datasets (stable contract: {items[], total})."""
    bind_json(ctx.obj, json_flag)
    client = get_client(ctx)
    result = client.dataset_list()
    bounded = paginated(result.items, limit, page)
    emit(ctx.obj, {"items": bounded, "total": len(result.items)})


@app.command("delete")
def dataset_delete(
    ctx: typer.Context,
    dataset_id: str = typer.Argument(..., help="Dataset id to delete."),
    yes: bool = typer.Option(False, "--yes", help="Confirm deletion (non-interactive)."),
    json_flag: bool = json_opt(),
) -> None:
    """Delete a dataset. Idempotent; requires --yes."""
    if json_flag:
        ctx.obj["output"] = "json"
    if not yes:
        # Non-interactive default: refuse without explicit --yes (CLI-Spec principle 4).
        raise CliError("dataset delete 需要 --yes 确认（非交互默认）", kind="validation")
    info(f"deleting dataset {dataset_id}")
    client = get_client(ctx)
    emit(ctx.obj, client.dataset_delete(dataset_id))
