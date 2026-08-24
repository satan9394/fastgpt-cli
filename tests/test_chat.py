"""Tests for the HTTP client retry semantics and chat client migrated from Go.

The Go client (internal/client/chat.go) retries on 429 / 5xx with backoff and
treats 4xx as terminal; these tests lock that behavior in Python.
"""

from __future__ import annotations

from unittest import mock

import pytest

from fastgptcli.api.chat import ChatClient, ChatMessage, ChatRequest
from fastgptcli.api.http import HttpClient, HttpStatusError
from fastgptcli.output.render import CliError


def _fake_response(status: int, payload=None):
    resp = mock.Mock()
    resp.status_code = status
    resp.json.return_value = payload or {}
    return resp


def test_post_retries_on_429_then_succeeds():
    """429 is retried; a later success returns the parsed JSON."""
    client = HttpClient("http://x", max_retry=2)
    calls = {"n": 0}

    def fake_post(*a, **k):
        calls["n"] += 1
        if calls["n"] <= 2:
            return _fake_response(429)
        return _fake_response(200, {"ok": True})

    with mock.patch("requests.post", side_effect=fake_post), mock.patch("time.sleep"):
        data = client.post_json("/chat/completions", {"a": 1})
    assert data == {"ok": True}
    assert calls["n"] == 3  # first two failed, third succeeded


def test_post_retries_on_5xx_then_succeeds():
    client = HttpClient("http://x", max_retry=2)
    calls = {"n": 0}

    def fake_post(*a, **k):
        calls["n"] += 1
        if calls["n"] == 1:
            return _fake_response(503)
        return _fake_response(200, {"ok": True})

    with mock.patch("requests.post", side_effect=fake_post), mock.patch("time.sleep"):
        data = client.post_json("/x", {})
    assert data == {"ok": True}


def test_post_does_not_retry_on_4xx():
    """4xx client errors are terminal (no retry), matching Go semantics."""
    client = HttpClient("http://x", max_retry=2)
    calls = {"n": 0}

    def fake_post(*a, **k):
        calls["n"] += 1
        return _fake_response(404, {"error": {"message": "not found"}})

    with mock.patch("requests.post", side_effect=fake_post), mock.patch("time.sleep"):
        with pytest.raises(HttpStatusError) as exc:
            client.post_json("/x", {})
    assert exc.value.code == 404
    assert calls["n"] == 1  # never retried


def test_post_gives_up_after_max_retries_on_429():
    client = HttpClient("http://x", max_retry=2)
    calls = {"n": 0}

    def fake_post(*a, **k):
        calls["n"] += 1
        return _fake_response(429)

    with mock.patch("requests.post", side_effect=fake_post), mock.patch("time.sleep"):
        with pytest.raises(HttpStatusError):
            client.post_json("/x", {})
    assert calls["n"] == 3  # initial + 2 retries


def test_chat_empty_messages_validation():
    chat = ChatClient("http://x", "model")
    with pytest.raises(CliError) as exc:
        chat.chat(ChatRequest(model="m", messages=[]))
    assert exc.value.kind == "validation"


def test_chat_surfaces_server_error():
    """Server-provided error.message is surfaced without leaking keys."""
    def fake_post(*a, **k):
        return _fake_response(200, {"error": {"message": "quota exceeded"}})

    chat = ChatClient("http://x", "model")
    with mock.patch("requests.post", side_effect=fake_post), mock.patch("time.sleep"):
        with pytest.raises(CliError) as exc:
            chat.chat(ChatRequest(model="m", messages=[ChatMessage("user", "hi")]))
    assert exc.value.kind == "backend"
    assert "quota exceeded" in exc.value.message


def test_chat_returns_first_choice():
    def fake_post(*a, **k):
        return _fake_response(
            200,
            {"id": "x", "choices": [{"message": {"role": "assistant", "content": "hi back"}}]},
        )

    chat = ChatClient("http://x", "model")
    with mock.patch("requests.post", side_effect=fake_post), mock.patch("time.sleep"):
        answer = chat.first_answer(ChatRequest(model="m", messages=[ChatMessage("user", "hi")]))
    assert answer == "hi back"
