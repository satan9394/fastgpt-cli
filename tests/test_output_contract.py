"""Phase 2 output-contract hardening tests.

Asserts the CLI-Spec contract end-to-end:
- default output is JSON on stdout, stderr is empty of data
- --output jsonl streams each list element as its own NDJSON line
- --limit / --page bound the result (bounded output)
- error paths write nothing to stdout and a structured error to stderr
- invalid global --output values raise a structured validation error
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

from fastgptcli.cli.main import main
from fastgptcli.models.dto import ListResult


def _run(capsys, args: list[str]):
    rc = main(args)
    captured = capsys.readouterr()
    return rc, captured.out, captured.err


# ---- default JSON + stdout purity ----


@pytest.mark.parametrize(
    "args",
    [
        ["kb", "list"],
        ["dataset", "ls"],
        ["app", "list"],
        ["workflow", "list"],
        ["status"],
        ["schema"],
    ],
)
def test_default_output_is_json_with_empty_stderr(capsys, args):
    """Without --json, default output is valid JSON and stderr is empty."""
    rc, out, err = _run(capsys, args)
    assert rc == 0
    assert err == "", f"{args} must not write to stderr in default mode: {err!r}"
    data = json.loads(out)  # valid JSON on stdout
    assert isinstance(data, dict)


def test_kb_list_jsonl_streams_items(lines_stream):
    """--output jsonl (global flag) streams each item as its own NDJSON line."""
    rc, out, err = lines_stream(["--output", "jsonl", "kb", "list"])
    assert rc == 0
    lines = [ln for ln in out.splitlines() if ln.strip()]
    assert len(lines) == 2  # two mocked knowledge bases
    parsed = [json.loads(ln) for ln in lines]
    assert {p["name"] for p in parsed} == {"alpha", "beta"}


@pytest.fixture()
def lines_stream(monkeypatch, capsys):
    """A _run variant that injects a fake backend returning two kb items."""

    def fake_kb_list(self):  # noqa: ANN001
        return ListResult(
            items=[
                {"kb_id": "kb-1", "name": "alpha", "status": "active"},
                {"kb_id": "kb-2", "name": "beta", "status": "active"},
            ]
        )

    from fastgptcli.api.fastgpt import FastGPTClient

    monkeypatch.setattr(FastGPTClient, "kb_list", fake_kb_list)

    def run(args):
        return _run(capsys, args)

    return run


# ---- bounded output ----


def test_list_limit_bounds_items(monkeypatch, capsys):
    from fastgptcli.api.fastgpt import FastGPTClient

    items = [{"kb_id": f"kb-{i}", "name": f"kb-{i}"} for i in range(5)]
    monkeypatch.setattr(
        FastGPTClient, "kb_list", lambda self: ListResult(items=list(items))
    )
    rc, out, err = _run(capsys, ["kb", "list", "--limit", "2"])
    assert rc == 0
    data = json.loads(out)
    assert len(data["items"]) == 2
    assert data["total"] == 5  # total reflects the full set, items is bounded


def test_list_page_offset(monkeypatch, capsys):
    from fastgptcli.api.fastgpt import FastGPTClient

    items = [{"kb_id": f"kb-{i}", "name": f"kb-{i}"} for i in range(5)]
    monkeypatch.setattr(
        FastGPTClient, "kb_list", lambda self: ListResult(items=list(items))
    )
    # page 2, limit 2 -> items[2:4]
    rc, out, err = _run(capsys, ["kb", "list", "--limit", "2", "--page", "2"])
    assert rc == 0
    data = json.loads(out)
    assert [i["name"] for i in data["items"]] == ["kb-2", "kb-3"]


# ---- error paths: stdout empty, structured stderr ----


@pytest.mark.parametrize(
    "args",
    [
        ["kb", "delete", "kb-1"],  # requires --yes -> validation error
        ["dataset", "delete", "ds-1"],
        ["app", "delete", "app-1"],
        ["--output", "yaml", "kb", "list"],  # invalid global output
        ["dataset", "import", "./nope", "--dataset", "ds-1"],  # bad path
    ],
)
def test_error_path_stdout_empty_stderr_structured(capsys, args):
    rc, out, err = _run(capsys, args)
    assert rc != 0
    assert out == "", f"{args} must not write data to stdout on error: {out!r}"
    assert err.strip() != ""
    parsed = json.loads(err)  # stderr carries structured error JSON
    assert "error" in parsed
    assert parsed["error"]["kind"] in {
        "validation",
        "conflict",
        "not_found",
        "auth",
        "backend",
        "transport",
        "internal",
    }


# ---- end-to-end via subprocess (real dispatch) ----


def test_subprocess_default_json_and_empty_stderr():
    """Data on stdout, nothing on stderr, valid JSON (no --json flag)."""
    proj = Path(__file__).resolve().parent.parent
    for args in (["kb", "list"], ["status"], ["schema"]):
        proc = subprocess.run(
            [sys.executable, "-m", "fastgptcli.cli.main", *args],
            capture_output=True,
            text=True,
            cwd=str(proj),
        )
        assert proc.returncode == 0, f"{args} failed: {proc.stderr}"
        assert proc.stderr == "", f"{args} wrote to stderr: {proc.stderr!r}"
        assert isinstance(json.loads(proc.stdout), dict)
