"""Tests for the REAL FastGPT HTTP client (Phase 3 route mapping).

These tests inject a fake FastGPT server (mocked requests.*) and assert the
actual routes, headers, bodies and field mappings the client uses, so the
"real API client" wiring is locked without needing a running backend.
"""

from __future__ import annotations

from unittest import mock

from fastgptcli.api.fastgpt import FastGPTClient
from fastgptcli.config.settings import Config
from fastgptcli.output.render import CliError


def _cfg(host: str = "fastgpt.example", api_key: str = "test-key") -> Config:
    cfg = Config()
    cfg.server.host = host
    cfg.server.api_key = api_key
    return cfg


def _client():
    return FastGPTClient(_cfg())


def _resp(status: int, payload=None, text: str | None = None):
    r = mock.Mock()
    r.status_code = status
    if text is not None:
        r.text = text
    else:
        import json

        r.text = json.dumps(payload if payload is not None else {})
    r.json.return_value = payload if payload is not None else {}
    return r


def _captured_post():
    calls = []

    def fake_post(url, *args, **kwargs):
        calls.append({"url": url, "json": kwargs.get("json"), "headers": kwargs.get("headers")})
        # FastGPT create routes return a raw ObjectId string, not an object.
        r = mock.Mock()
        r.status_code = 200
        r.text = '"aaaaaaaaaaaaaaaaaaaaaaaa"'
        r.json.return_value = "aaaaaaaaaaaaaaaaaaaaaaaa"
        return r

    patcher = mock.patch("requests.post", side_effect=fake_post)
    return calls, patcher


# ---- dataset routes ----


def test_dataset_create_posts_core_route_with_bearer():
    calls, patcher = _captured_post()
    with patcher:
        result = _client().dataset_create("my dataset")
    assert result["dataset_id"] == "aaaaaaaaaaaaaaaaaaaaaaaa"
    call = calls[0]
    assert call["url"].endswith("/api/core/dataset/create")
    assert call["json"]["name"] == "my dataset"
    assert call["json"]["type"] == "dataset"
    assert call["headers"]["Authorization"] == "Bearer test-key"


def test_dataset_list_maps_items_and_total():
    payload = [
        {"_id": "aaa", "name": "kb1", "type": "dataset", "intro": "one"},
        {"_id": "bbb", "name": "kb2", "type": "dataset", "intro": "two"},
    ]
    with mock.patch("requests.post", return_value=_resp(200, payload)) as m:
        result = _client().dataset_list()
    path = m.call_args.args[0]
    assert path.endswith("/api/core/dataset/list")
    assert result.total == 2
    assert result.items[0]["dataset_id"] == "aaa"
    assert result.items[0]["name"] == "kb1"


def test_dataset_delete_uses_query_id():
    with mock.patch("requests.delete", return_value=_resp(200, {})) as m:
        result = _client().dataset_delete("ds-123")
    path, kwargs = m.call_args.args[0], m.call_args.kwargs
    assert path.endswith("/api/core/dataset/delete")
    assert kwargs["params"] == {"id": "ds-123"}
    assert result["status"] == "deleted"


# ---- kb routes (kb == FastGPT dataset) ----


def test_kb_create_posts_dataset_create():
    calls, patcher = _captured_post()
    with patcher:
        result = _client().kb_create("docs")
    assert result.kb_id == "aaaaaaaaaaaaaaaaaaaaaaaa"
    assert calls[0]["url"].endswith("/api/core/dataset/create")


def test_kb_get_uses_detail_route():
    payload = {"_id": "kb-9", "name": "docs", "intro": "hi", "status": "active"}
    with mock.patch("requests.get", return_value=_resp(200, payload)) as m:
        result = _client().kb_get("kb-9")
    path, kwargs = m.call_args.args[0], m.call_args.kwargs
    assert path.endswith("/api/core/dataset/detail")
    assert kwargs["params"] == {"id": "kb-9"}
    assert result["kb_id"] == "kb-9"
    assert result["name"] == "docs"


def test_kb_delete_maps_to_dataset_delete():
    with mock.patch("requests.delete", return_value=_resp(200, {})) as m:
        result = _client().kb_delete("kb-9")
    assert m.call_args.args[0].endswith("/api/core/dataset/delete")
    assert result["status"] == "deleted"


def test_kb_upload_posts_multipart_local_file(tmp_path):
    f = tmp_path / "a.txt"
    f.write_text("hello", encoding="utf-8")
    with mock.patch("requests.post", return_value=_resp(200, {"_id": "col-1"})) as m:
        result = _client().kb_upload("kb-9", [str(f)])
    path, kwargs = m.call_args.args[0], m.call_args.kwargs
    assert path.endswith("/api/core/dataset/collection/create/localFile")
    assert kwargs["data"] == {"datasetId": "kb-9"}
    assert "file" in kwargs["files"]
    assert result["uploaded"] == 1
    assert result["doc_ids"] == ["col-1"]


# ---- query search route + field mapping ----


def test_query_search_posts_search_test_and_maps_results():
    payload = {
        "list": [
            {
                "id": "d1",
                "q": "如何配置 API 密钥",
                "a": "在设置页配置",
                "score": [{"type": "embedding", "value": 0.91, "index": 0}],
                "sourceName": "guide.md",
            }
        ],
        "duration": "0.023s",
        "limit": 10,
    }
    with mock.patch("requests.post", return_value=_resp(200, payload)) as m:
        result = _client().query_search("如何配 key", kb="ds-1", limit=10)
    path, kwargs = m.call_args.args[0], m.call_args.kwargs
    assert path.endswith("/api/core/dataset/searchTest")
    assert kwargs["json"] == {"datasetId": "ds-1", "text": "如何配 key", "limit": 10}
    assert len(result.results) == 1
    item = result.results[0]
    assert item.score == 0.91
    assert "如何配置 API 密钥" in item.content
    assert item.source == "guide.md"


def test_query_search_requires_kb_when_backend_configured():
    client = _client()
    try:
        client.query_search("hello", kb="", limit=10)
    except CliError as exc:
        assert exc.kind == "validation"
        return
    raise AssertionError("expected validation error when --kb missing")


# ---- app routes ----


def test_app_list_posts_core_app_list():
    payload = [{"_id": "app-1", "name": "客服", "type": "workflow"}]
    with mock.patch("requests.post", return_value=_resp(200, payload)) as m:
        result = _client().app_list()
    assert m.call_args.args[0].endswith("/api/core/app/list")
    assert result.total == 1
    assert result.items[0]["app_id"] == "app-1"


def test_app_create_posts_core_app_create():
    calls, patcher = _captured_post()
    with patcher:
        result = _client().app_create("support", "workflow")
    assert result["app_id"] == "aaaaaaaaaaaaaaaaaaaaaaaa"
    calls[0]["url"].endswith("/api/core/app/create")
    assert calls[0]["json"] == {"name": "support", "type": "workflow"}


def test_app_delete_uses_query_app_id():
    with mock.patch("requests.delete", return_value=_resp(200, [])) as m:
        result = _client().app_delete("app-1")
    assert m.call_args.args[0].endswith("/api/core/app/del")
    assert m.call_args.kwargs["params"] == {"appId": "app-1"}
    assert result["status"] == "deleted"


# ---- stub-mode gating ----


def test_no_backend_still_returns_empty_contract():
    """Without api key and with default localhost, list ops stay stub-empty."""
    cfg = Config()
    cfg.server.host = "localhost"
    cfg.server.api_key = ""
    client = FastGPTClient(cfg)
    assert not client._backend_configured
    assert client.dataset_list().total == 0
    assert client.kb_list().total == 0
    assert client.app_list().total == 0
    assert client.query_search("x", kb="", limit=5).results == []
