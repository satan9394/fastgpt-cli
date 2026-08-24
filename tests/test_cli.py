"""Tests for the fastgpt command tree and JSON output contract.

Invokes the real dispatcher (main) with capsys to assert stdout/stdout purity.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from fastgptcli.cli.main import main

REQUIRED_GROUPS = [
    "dataset",
    "kb",
    "app",
    "workflow",
    "agent",
    "evaluation",
    "query",
    "schema",
    "status",
    "health",
]
REQUIRED_BENCHMARK = ["benchmark", "export", "backup", "config", "probe", "version"]


def _run(capsys, args: list[str]):
    rc = main(args)
    captured = capsys.readouterr()
    return rc, captured.out, captured.err


def test_help_shows_domain_tree(capsys):
    """fastgpt --help must list the full domain command tree."""
    rc, out, _ = _run(capsys, ["--help"])
    assert rc == 0
    for group in REQUIRED_GROUPS + REQUIRED_BENCHMARK:
        assert group in out, f"missing group in --help: {group}"


def test_schema_json_is_valid_and_complete(capsys):
    """fastgpt schema --json outputs a valid machine-readable command tree."""
    rc, out, err = _run(capsys, ["schema", "--json"])
    assert rc == 0
    assert err == "", "schema --json must not write to stderr"
    data = json.loads(out)
    assert data["name"] == "fastgpt"
    names = {g["name"] for g in data["groups"]}
    for group in REQUIRED_GROUPS:
        assert group in names, f"schema missing group {group}"
    kb = next(g for g in data["groups"] if g["name"] == "kb")
    assert "list" in {c["name"] for c in kb["commands"]}
    agent = next(g for g in data["groups"] if g["name"] == "agent")
    assert "run" in {c["name"] for c in agent["commands"]}


def test_kb_list_json_default_json_with_empty_items(capsys):
    """fastgpt kb list --json outputs {items:[], total:0} (no backend yet)."""
    rc, out, err = _run(capsys, ["kb", "list", "--json"])
    assert rc == 0
    assert err == "", "kb list must not write to stderr"
    data = json.loads(out)
    assert data["items"] == []
    assert data["total"] == 0


def test_status_json_contract(capsys):
    rc, out, _ = _run(capsys, ["status", "--json"])
    assert rc == 0
    data = json.loads(out)
    assert data["status"] == "ok"
    assert "version" in data


def test_agent_run_contract(capsys):
    """agent run --input -> {answer, tokens, sources}."""
    rc, out, _ = _run(capsys, ["agent", "run", "--input", "hello", "--json"])
    assert rc == 0
    data = json.loads(out)
    assert set(data.keys()) == {"answer", "tokens", "sources"}
    assert isinstance(data["sources"], list)


def test_dataset_ls_contract(capsys):
    rc, out, _ = _run(capsys, ["dataset", "ls", "--json"])
    assert rc == 0
    data = json.loads(out)
    assert data["items"] == []
    assert data["total"] == 0


def test_destructive_commands_require_yes(capsys):
    """Non-interactive default: deletion without --yes is a structured validation error."""
    for args in (["kb", "delete", "kb-1"], ["dataset", "delete", "ds-1"], ["app", "delete", "app-1"]):
        rc, out, err = _run(capsys, args)
        assert rc == 1
        assert out == "", f"{args} must not write data to stdout on error"
        assert err != "", f"{args} should emit a structured error to stderr"
        parsed = json.loads(err)
        assert parsed["error"]["kind"] == "validation"


def test_unexpected_args_are_usage_error(capsys):
    rc, out, err = _run(capsys, ["kb", "bogus"])
    assert rc == 2
    assert out == ""
    assert err != ""


def test_stdout_data_only_for_list_via_subprocess():
    """End-to-end: data on stdout, nothing on stderr, valid JSON."""
    proj = Path(__file__).resolve().parent.parent
    for args in (["kb", "list", "--json"], ["dataset", "ls", "--json"], ["status", "--json"]):
        proc = subprocess.run(
            [sys.executable, "-m", "fastgptcli.cli.main", *args],
            capture_output=True,
            text=True,
            cwd=str(proj),
        )
        assert proc.returncode == 0, f"{args} failed: {proc.stderr}"
        assert proc.stderr == "", f"{args} wrote to stderr: {proc.stderr!r}"
        data = json.loads(proc.stdout)
        assert isinstance(data, dict)
