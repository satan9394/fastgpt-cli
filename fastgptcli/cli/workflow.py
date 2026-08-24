"""workflow command group: workflow deploy / list / test."""

from __future__ import annotations

import typer

from fastgptcli.cli._common import bind_json, emit, get_client, json_opt, limit_opt, page_opt, paginated
from fastgptcli.output.render import info

app = typer.Typer(help="Workflow lifecycle domain.")


@app.command("deploy")
def workflow_deploy(
    ctx: typer.Context,
    name: str = typer.Argument(..., help="Workflow name."),
    source: str = typer.Option("", "--source", help="Workflow definition file (json/yaml)."),
    json_flag: bool = json_opt(),
) -> None:
    """Deploy a workflow. Default JSON: {workflow_id, name, status}."""
    if json_flag:
        ctx.obj["output"] = "json"
    client = get_client(ctx)
    info(f"deploying workflow {name}")
    emit(ctx.obj, client.workflow_deploy(name))


@app.command("list")
def workflow_list(
    ctx: typer.Context,
    limit: int = limit_opt(),
    page: int = page_opt(),
    json_flag: bool = json_opt(),
) -> None:
    """List workflows (stable contract: {items[], total})."""
    bind_json(ctx.obj, json_flag)
    client = get_client(ctx)
    result = client.workflow_list()
    bounded = paginated(result.items, limit, page)
    emit(ctx.obj, {"items": bounded, "total": len(result.items)})


@app.command("test")
def workflow_test(
    ctx: typer.Context,
    workflow_id: str = typer.Argument(..., help="Workflow id."),
    json_flag: bool = json_opt(),
) -> None:
    """Test a workflow end-to-end."""
    if json_flag:
        ctx.obj["output"] = "json"
    client = get_client(ctx)
    emit(ctx.obj, client.workflow_test(workflow_id))
