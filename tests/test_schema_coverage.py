"""Phase 4: schema introspection coverage tests.

Guarantees that `schema commands list` reflects the REAL compiled command tree
1:1 (no phantom commands, no missing commands). The expected inventory is built
by independently walking the compiled Click root — not from the schema output —
so the two sides are truly cross-checked.
"""

from __future__ import annotations

import json

from typer.main import get_command

from fastgptcli.cli.main import app as root_app
from fastgptcli.cli.main import main


def _run(capsys, args: list[str]):
    rc = main(args)
    captured = capsys.readouterr()
    return rc, captured.out, captured.err


def _real_leaf_paths(group, prefix: list[str] | None = None) -> list[str]:
    """Independently walk the compiled Click tree to real leaf command paths."""
    prefix = prefix or []
    paths: list[str] = []
    for name, node in (getattr(group, "commands", None) or {}).items():
        if hasattr(node, "commands"):
            paths.extend(_real_leaf_paths(node, prefix + [name]))
        else:
            paths.append(" ".join(prefix + [name]))
    return sorted(paths)


def _schema_paths(capsys) -> list[str]:
    rc, out, err = _run(capsys, ["schema", "commands", "list", "--json"])
    assert rc == 0
    assert err == "", "schema commands list must keep stderr empty"
    data = json.loads(out)
    assert data["name"] == "fastgpt"
    assert data["total"] == len(data["commands"])
    return sorted(c["path"] for c in data["commands"])


def test_schema_commands_list_covers_real_tree_exactly(capsys):
    """schema commands list == real compiled command tree (both directions)."""
    real = _real_leaf_paths(get_command(root_app))
    schema = _schema_paths(capsys)
    missing = set(real) - set(schema)
    extra = set(schema) - set(real)
    assert real == schema, f"schema mismatch: missing={missing} extra={extra}"


def test_schema_commands_list_entries_have_path_group_name(capsys):
    rc, out, err = _run(capsys, ["schema", "commands", "list", "--json"])
    assert rc == 0
    data = json.loads(out)
    for entry in data["commands"]:
        assert entry["path"]
        assert entry["name"]
        assert "group" in entry
        assert isinstance(entry["params"], list)
        # path must be a chain of groups ending with the command name
        # (nested groups like `schema commands list` produce deeper paths)
        assert entry["path"].endswith(entry["name"])
        if entry["group"]:
            assert entry["path"].startswith(entry["group"])


def test_schema_commands_list_includes_params(capsys):
    """The flat inventory is self-contained: params mirror the tree's."""
    rc, out, err = _run(capsys, ["schema", "commands", "list", "--json"])
    assert rc == 0
    data = json.loads(out)
    by_path = {c["path"]: c for c in data["commands"]}
    search = by_path["query search"]
    assert "kb" in {p["name"] for p in search["params"]}
    assert "limit" in {p["name"] for p in search["params"]}
    run = by_path["agent run"]
    assert "input" in {p["name"] for p in run["params"]}
    delete = by_path["kb delete"]
    assert "yes" in {p["name"] for p in delete["params"]}


def test_schema_commands_bare_matches_list(capsys):
    """Bare `schema commands` and `schema commands list` produce the same inventory."""
    rc1, out1, err1 = _run(capsys, ["schema", "commands"])
    rc2, out2, err2 = _run(capsys, ["schema", "commands", "list"])
    assert rc1 == rc2 == 0
    assert err1 == err2 == ""
    assert json.loads(out1) == json.loads(out2)


def test_expected_command_surface_present(capsys):
    """The documented command surface must all appear in the inventory."""
    _, out, _ = _run(capsys, ["schema", "commands", "list", "--json"])
    paths = {c["path"] for c in json.loads(out)["commands"]}
    expected = {
        "dataset create",
        "dataset import",
        "dataset ls",
        "dataset delete",
        "kb create",
        "kb list",
        "kb upload",
        "kb get",
        "kb delete",
        "app list",
        "app create",
        "app deploy",
        "app test",
        "app describe",
        "app delete",
        "workflow deploy",
        "workflow list",
        "workflow test",
        "agent run",
        "evaluation run",
        "evaluation compare",
        "benchmark run",
        "benchmark compare",
        "query search",
        "query chat",
        "export export",
        "export backup",
        "config show",
        "config path",
        "config set",
        "config init",
        "probe status",
        "probe health",
        "schema tree",
        "schema commands list",
        "status",
        "health",
        "version",
    }
    assert expected <= paths, f"missing from schema inventory: {expected - paths}"
