"""app command group: app list / create / deploy / test / describe / delete."""

from __future__ import annotations

import typer

from fastgptcli.cli._common import bind_json, emit, get_client, json_opt, limit_opt, page_opt, paginated
from fastgptcli.output.render import CliError, info

app = typer.Typer(help="Application (AI app) lifecycle domain.")


@app.command("list")
def app_list(
    ctx: typer.Context,
    limit: int = limit_opt(),
    page: int = page_opt(),
    json_flag: bool = json_opt(),
) -> None:
    """List AI applications (stable contract: {items[], total})."""
    bind_json(ctx.obj, json_flag)
    client = get_client(ctx)
    result = client.app_list()
    bounded = paginated(result.items, limit, page)
    emit(ctx.obj, {"items": bounded, "total": len(result.items)})


@app.command("create")
def app_create(
    ctx: typer.Context,
    name: str = typer.Argument(..., help="Application name."),
    kind: str = typer.Option("simple", "--kind", help="App kind: simple / workflow / agent."),
    json_flag: bool = json_opt(),
) -> None:
    """Create an AI application. Default JSON: {app_id, name, kind, status}."""
    if json_flag:
        ctx.obj["output"] = "json"
    client = get_client(ctx)
    emit(ctx.obj, client.app_create(name, kind))


@app.command("deploy")
def app_deploy(
    ctx: typer.Context,
    app_id: str = typer.Argument(..., help="Application id to deploy."),
    json_flag: bool = json_opt(),
) -> None:
    """Deploy an application (publish/release)."""
    if json_flag:
        ctx.obj["output"] = "json"
    client = get_client(ctx)
    info(f"deploying app {app_id}")
    emit(ctx.obj, client.app_deploy(app_id))


@app.command("test")
def app_test(
    ctx: typer.Context,
    app_id: str = typer.Argument(..., help="Application id."),
    message: str = typer.Option("", "--message", help="Test prompt."),
    json_flag: bool = json_opt(),
) -> None:
    """Smoke-test an application with a message."""
    if json_flag:
        ctx.obj["output"] = "json"
    client = get_client(ctx)
    emit(ctx.obj, client.app_test(app_id, message))


@app.command("describe")
def app_describe(
    ctx: typer.Context,
    app_id: str = typer.Argument(..., help="Application id."),
    json_flag: bool = json_opt(),
) -> None:
    """Show an application detail."""
    if json_flag:
        ctx.obj["output"] = "json"
    client = get_client(ctx)
    emit(ctx.obj, client.app_describe(app_id))


@app.command("delete")
def app_delete(
    ctx: typer.Context,
    app_id: str = typer.Argument(..., help="Application id."),
    yes: bool = typer.Option(False, "--yes", help="Confirm deletion (non-interactive)."),
    json_flag: bool = json_opt(),
) -> None:
    """Delete an application. Idempotent; requires --yes."""
    if json_flag:
        ctx.obj["output"] = "json"
    if not yes:
        raise CliError("app delete 需要 --yes 确认（非交互默认）", kind="validation")
    info(f"deleting app {app_id}")
    client = get_client(ctx)
    emit(ctx.obj, client.app_delete(app_id))
