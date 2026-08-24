"""schema command: machine-readable command tree introspection (CLI-Spec principle 2).

Compiles the Typer root app into its Click command tree via ``typer.main.get_command``
and walks that compiled tree, so ``help`` text and ``params`` are fully resolved
(``registered_commands``/``registered_groups`` expose uncompiled metadata). This gives
an Agent an accurate, self-discoverable command tree at runtime.
"""

from __future__ import annotations

from typing import Any

import typer

from fastgptcli.cli._common import emit

app = typer.Typer(
    help="Self-introspection: discover the command tree at runtime.",
    invoke_without_command=True,
)

_ROOT: typer.Typer | None = None


def register(root: typer.Typer) -> None:
    """Bind the root Typer app so schema can compile and introspect the full tree."""
    global _ROOT
    _ROOT = root


def _compiled_root() -> Any:
    """Return the compiled Click root command (falls back to a stub if unbound)."""
    from typer.main import get_command

    if _ROOT is None:
        return typer.Typer()
    return get_command(_ROOT)


def _type_name(tp: Any) -> str:
    name = getattr(tp, "name", None)
    if name:
        return name
    type_repr = type(tp).__name__
    # map common click param types to readable names
    if type_repr == "StringParamType":
        return "str"
    if type_repr == "IntParamType":
        return "int"
    if type_repr == "BoolParamType":
        return "bool"
    if type_repr == "ChoiceParamType":
        choices = ", ".join(getattr(tp, "choices", []) or [])
        return f"choice[{choices}]" if choices else "choice"
    return type_repr.lower()


def _param_info(param: Any) -> dict[str, Any]:
    return {
        "name": getattr(param, "name", ""),
        "required": bool(getattr(param, "required", False)),
        "type": _type_name(getattr(param, "type", None)),
        "help": (getattr(param, "help", "") or ""),
    }


def _introspect_group(group: Any, seen_groups: dict[str, str] | None = None) -> list[dict[str, Any]]:
    """Walk a compiled Click group into a list of node dicts.

    A Click Group holds ``.commands`` (dict of name -> Command/Group). Nodes that are
    themselves groups are recursed; others are leaves.

    ``seen_groups`` is used only at the top level to detect groups that wrap the same
    underlying commands (e.g. ``backup`` re-exporting ``export``), marking the later
    one with ``alias_of``. Nested groups each get their own fresh ledger, so inner
    commands are never spuriously flagged as aliases.
    """
    nodes: list[dict[str, Any]] = []
    if seen_groups is None:
        seen_groups = {}
    commands = getattr(group, "commands", None) or {}
    for name, node in commands.items():
        if hasattr(node, "commands"):
            sub: dict[str, Any] = {
                "type": "group",
                "name": name,
                "help": (getattr(node, "help", "") or "").strip(),
                "commands": _introspect_group(node),
            }
            sig = _group_signature(sub)
            if sig in seen_groups and name != seen_groups[sig]:
                sub["alias_of"] = seen_groups[sig]
            else:
                seen_groups.setdefault(sig, name)
            nodes.append(sub)
        else:
            nodes.append(
                {
                    "type": "command",
                    "name": name,
                    "help": (getattr(node, "help", "") or "").strip(),
                    "params": [_param_info(p) for p in list(getattr(node, "params", None) or [])],
                }
            )
    return nodes


def _group_signature(node: dict[str, Any]) -> str:
    """Signature of a group by its (sorted) subcommand names, to detect aliases.

    Name-independent: two groups exposing the same set of subcommands are treated
    as aliases (e.g. ``backup`` re-exporting ``export``). Only applied at the top
    level, where each nested group is walked with its own fresh ledger.
    """
    names = sorted(c["name"] for c in node.get("commands", []))
    return f"commands={names}"


def _tree_payload() -> dict[str, Any]:
    root = _compiled_root()
    groups = _introspect_group(root)
    return {"name": "fastgpt", "groups": groups}


def _flatten_commands(group: Any, prefix: list[str] | None = None) -> list[dict[str, Any]]:
    """Flatten the compiled command tree into a flat command inventory.

    Each leaf becomes one entry ``{name, path, group, help, params}`` where
    ``path`` is the full invocation path (``"dataset create"``); top-level
    commands (``status``/``health``/``version``) have an empty ``group``.
    ``params`` mirrors the tree's per-command parameter info, so the flat list is
    self-contained for an Agent (no need to also read `schema tree`). This powers
    ``schema commands list`` and the coverage guarantee that schema reflects the
    real command tree 1:1.
    """
    prefix = prefix or []
    nodes: list[dict[str, Any]] = []
    commands = getattr(group, "commands", None) or {}
    for name, node in commands.items():
        if hasattr(node, "commands"):
            nodes.extend(_flatten_commands(node, prefix + [name]))
        else:
            nodes.append(
                {
                    "name": name,
                    "path": " ".join(prefix + [name]),
                    "group": prefix[0] if prefix else "",
                    "help": (getattr(node, "help", "") or "").strip(),
                    "params": [_param_info(p) for p in list(getattr(node, "params", None) or [])],
                }
            )
    return nodes


def _commands_payload() -> dict[str, Any]:
    commands = _flatten_commands(_compiled_root())
    return {"name": "fastgpt", "commands": commands, "total": len(commands)}


def _emit_tree(ctx: typer.Context) -> None:
    emit(ctx.obj, _tree_payload())


def _emit_commands(ctx: typer.Context) -> None:
    emit(ctx.obj, _commands_payload())


@app.callback()
def schema_main(
    ctx: typer.Context,
    json_flag: bool = typer.Option(False, "--json", help="Force JSON output."),
) -> None:
    """When invoked without a subcommand, print the full schema tree as JSON."""
    if json_flag:
        if ctx.obj is None:
            ctx.obj = {}
        ctx.obj["output"] = "json"
    if ctx.invoked_subcommand is None:
        _emit_tree(ctx)


@app.command("tree")
def schema_tree(
    ctx: typer.Context,
    json_flag: bool = typer.Option(False, "--json", help="Force JSON output."),
) -> None:
    """Output the full command tree as JSON (alias of `schema`)."""
    if json_flag:
        ctx.obj["output"] = "json"
    _emit_tree(ctx)


commands_app = typer.Typer(
    help="List all commands as a flat inventory (coverage self-check).",
    invoke_without_command=True,
)


@commands_app.callback()
def schema_commands(
    ctx: typer.Context,
    json_flag: bool = typer.Option(False, "--json", help="Force JSON output."),
) -> None:
    """Flat command inventory. `schema commands list` is the explicit form."""
    if json_flag:
        ctx.obj["output"] = "json"
    if ctx.invoked_subcommand is None:
        _emit_commands(ctx)


@commands_app.command("list")
def schema_commands_list(
    ctx: typer.Context,
    json_flag: bool = typer.Option(False, "--json", help="Force JSON output."),
) -> None:
    """List every command path (name, path, group) — mirrors the real command tree."""
    if json_flag:
        ctx.obj["output"] = "json"
    _emit_commands(ctx)


app.add_typer(commands_app, name="commands")
