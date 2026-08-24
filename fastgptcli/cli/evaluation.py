"""evaluation / benchmark command groups (reserved scaffolding).

Both expose `run` and `compare` as stable entry points; full harness wiring is a
later phase, but the command surface and JSON contract are already defined.
"""

from __future__ import annotations

import typer

from fastgptcli.cli._common import emit, json_opt

evaluation_app = typer.Typer(help="Evaluation domain: run / compare.")
benchmark_app = typer.Typer(help="Benchmark domain: run / compare (reserved).")


def _eval_id(kind: str, name: str) -> str:
    return f"{kind}-{name[:8]}"


@evaluation_app.command("run")
def evaluation_run(
    ctx: typer.Context,
    suite: str = typer.Option(..., "--suite", help="Evaluation suite name."),
    dataset: str = typer.Option("", "--dataset", help="Target dataset id."),
    json_flag: bool = json_opt(),
) -> None:
    """Run an evaluation suite. Default JSON: {evaluation_id, status}."""
    if json_flag:
        ctx.obj["output"] = "json"
    emit(ctx.obj, {"evaluation_id": _eval_id("eval", suite), "suite": suite, "status": "done"})


@evaluation_app.command("compare")
def evaluation_compare(
    ctx: typer.Context,
    base: str = typer.Argument(..., help="Base run id."),
    target: str = typer.Argument(..., help="Target run id."),
    json_flag: bool = json_opt(),
) -> None:
    """Compare two evaluation runs. Default JSON: {base, target, verdict}."""
    if json_flag:
        ctx.obj["output"] = "json"
    emit(ctx.obj, {"base": base, "target": target, "verdict": "pending"})


@benchmark_app.command("run")
def benchmark_run(
    ctx: typer.Context,
    name: str = typer.Argument(..., help="Benchmark name."),
    items: int = typer.Option(0, "--items", help="Number of benchmark items."),
    json_flag: bool = json_opt(),
) -> None:
    """Run a benchmark (reserved). Default JSON: {benchmark_id, status}."""
    if json_flag:
        ctx.obj["output"] = "json"
    emit(ctx.obj, {"benchmark_id": _eval_id("bench", name), "name": name, "status": "done", "items": items})


@benchmark_app.command("compare")
def benchmark_compare(
    ctx: typer.Context,
    base: str = typer.Argument(..., help="Base run id."),
    target: str = typer.Argument(..., help="Target run id."),
    json_flag: bool = json_opt(),
) -> None:
    """Compare two benchmark runs (reserved)."""
    if json_flag:
        ctx.obj["output"] = "json"
    emit(ctx.obj, {"base": base, "target": target, "verdict": "pending"})
