"""Root Typer app entry for fastgpt-cli (the `fastgpt` command).

Loads config into the context object, registers all domain command groups,
handles the global --output/--config flags, and exposes top-level status/health
commands. Structured errors (CliError) are routed to stderr as JSON so stdout
stays data-only.
"""

from __future__ import annotations

import sys

import typer

from fastgptcli import __version__
from fastgptcli.cli import agent, dataset, evaluation, export, kb, probe, query, schema, workflow
from fastgptcli.cli import app as app_cmd
from fastgptcli.cli import config as config_cmd
from fastgptcli.cli._common import emit, get_config
from fastgptcli.output.render import CliError, emit_error

app = typer.Typer(
    name="fastgpt",
    help="FastGPT CLI — Agent-native AI application lifecycle management (kubectl/gh-style).",
    add_completion=False,
    invoke_without_command=False,
)


@app.callback()
def common_callback(
    ctx: typer.Context,
    config: str = typer.Option(None, "--config", "-c", help="Config file path.", rich_help_panel="Global"),
    output: str = typer.Option(
        "json",
        "--output",
        "-o",
        help="Output format: json (default), jsonl (stream), text.",
        rich_help_panel="Global",
    ),
) -> None:
    """Root group callback: materialize config + runtime into ctx.obj."""
    if output not in ("json", "jsonl", "text"):
        raise CliError(f"未知输出格式 {output!r}（可用: json, jsonl, text）", kind="validation")
    from fastgptcli.config.settings import load

    cfg, _ = load(config)
    obj: dict[str, object] = {"config": cfg, "output": output}

    from fastgptcli.api.fastgpt import FastGPTClient

    obj["client"] = FastGPTClient(cfg)
    ctx.obj = obj


# Domain command groups.
app.add_typer(dataset.app, name="dataset", help="Data set domain: create/import/ls/delete.")
app.add_typer(kb.app, name="kb", help="Knowledge base domain: create/list/upload/get/delete.")
app.add_typer(app_cmd.app, name="app", help="AI application lifecycle domain.")
app.add_typer(workflow.app, name="workflow", help="Workflow lifecycle domain.")
app.add_typer(agent.app, name="agent", help="Agent execution domain: run -> {answer, tokens, sources}.")
app.add_typer(evaluation.evaluation_app, name="evaluation", help="Evaluation domain: run/compare.")
app.add_typer(evaluation.benchmark_app, name="benchmark", help="Benchmark domain: run/compare (reserved).")
app.add_typer(query.app, name="query", help="Query domain: RAG search + inline chat.")
app.add_typer(export.export_app, name="export", help="Export/backup domain.")
app.add_typer(export.export_app, name="backup", help="Backup (alias of export backup).")
app.add_typer(config_cmd.app, name="config", help="Configuration management.")
app.add_typer(probe.app, name="probe", help="Probe commands: status/health.")
schema.register(app)
app.add_typer(schema.app, name="schema", help="Self-introspection command tree.")


@app.command("status")
def status_cmd(
    ctx: typer.Context,
    json_flag: bool = typer.Option(False, "--json", help="Force JSON output."),
) -> None:
    """Show runtime status (top-level). Default JSON."""
    if json_flag:
        ctx.obj["output"] = "json"
    emit(ctx.obj, probe.status_payload(get_config(ctx)))


@app.command("health")
def health_cmd(
    ctx: typer.Context,
    json_flag: bool = typer.Option(False, "--json", help="Force JSON output."),
) -> None:
    """Health probe (top-level). Default JSON."""
    if json_flag:
        ctx.obj["output"] = "json"
    emit(ctx.obj, probe.health_payload(get_config(ctx)))


@app.command("version")
def version_cmd(
    ctx: typer.Context,
    json_flag: bool = typer.Option(False, "--json", help="Force JSON output."),
) -> None:
    """Print the CLI version as JSON."""
    if json_flag:
        ctx.obj["output"] = "json"
    emit(ctx.obj, {"name": "fastgpt", "version": __version__})


def main(argv: list[str] | None = None) -> int:
    """Programmatic dispatch used by the `fastgpt` console script and
    `python -m fastgptcli.cli.main`.

    Invokes the compiled Click command with ``standalone_mode=False`` so that
    structured CliErrors are emitted as JSON to stderr (never stdout) with a
    proper non-zero exit code, keeping stdout data-only per the CLI spec.
    """
    import click
    from typer.main import get_command

    args = list(sys.argv[1:] if argv is None else argv)
    cmd = get_command(app)
    try:
        cmd.main(args=args, prog_name="fastgpt", standalone_mode=False)
    except click.exceptions.Exit as exc:
        # Normal exit (e.g. --help prints and exits 0).
        return int(exc.exit_code or 0)
    except click.exceptions.UsageError as exc:
        emit_error(CliError(str(exc), kind="validation"))
        return 2
    except CliError as exc:
        emit_error(exc)
        return int(exc.exit_code)
    except Exception as exc:  # noqa: BLE001 - last-resort structured internal error
        emit_error(CliError(str(exc), kind="internal"))
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

