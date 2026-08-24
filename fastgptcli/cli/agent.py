"""agent command group: `agent run` -> {answer, tokens, sources}."""

from __future__ import annotations

import typer

from fastgptcli.cli._common import emit, get_client, json_opt

app = typer.Typer(help="Agent execution domain.")


@app.command("run")
def agent_run(
    ctx: typer.Context,
    input: str = typer.Option(..., "--input", help="Agent input prompt."),  # noqa: A002 - required option name
    model: str = typer.Option("", "--model", help="Override model."),
    json_flag: bool = json_opt(),
) -> None:
    """Run an agent. Structured JSON output: {answer, tokens, sources}."""
    if json_flag:
        ctx.obj["output"] = "json"
    client = get_client(ctx)
    result = client.agent_run(input)
    emit(ctx.obj, result.to_dict())
