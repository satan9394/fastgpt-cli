"""export / backup command groups (reserved scaffolding with stable contract)."""

from __future__ import annotations

import typer

from fastgptcli.cli._common import emit, json_opt

export_app = typer.Typer(help="Export domain: export / backup.")


@export_app.command("export")
def export_data(
    ctx: typer.Context,
    dataset: str = typer.Option("", "--dataset", help="Dataset id to export."),
    output: str = typer.Option("", "--output", help="Output path."),
    json_flag: bool = json_opt(),
) -> None:
    """Export data. Default JSON: {export_id, status, path}."""
    if json_flag:
        ctx.obj["output"] = "json"
    emit(ctx.obj, {"export_id": "export-placeholder", "dataset": dataset, "path": output, "status": "ok"})


@export_app.command("backup")
def export_backup(
    ctx: typer.Context,
    name: str = typer.Option("backup", "--name", help="Backup name."),
    target: str = typer.Option("", "--target", help="Backup target dir."),
    json_flag: bool = json_opt(),
) -> None:
    """Backup knowledge/apps. Default JSON: {backup_id, status}."""
    if json_flag:
        ctx.obj["output"] = "json"
    emit(ctx.obj, {"backup_id": f"backup-{name[:8]}", "name": name, "target": target, "status": "ok"})
