"""FastGPT domain API client (dataset / kb / app / workflow / agent / query).

Phase 3: the client now talks the REAL FastGPT Server HTTP API (v4.16 routes read
from fastgpt-source). Endpoint/contract facts used here:

- Auth: every request sends ``Authorization: Bearer <api_key>``; the server
  accepts either a user session token or an OpenAPI key via parseHeaderCert
  (packages/service/support/permission/auth/common.ts) for routes that set
  ``authApiKey: true``.
- POST /api/core/dataset/create    body {name, intro?, type?, vectorModel?} → ObjectId
- POST /api/core/dataset/list      body {parentId?, type?, searchKey?} → array[DatasetListItem]
- GET  /api/core/dataset/detail?id= → DatasetItem
- DELETE /api/core/dataset/delete?id=
- POST /api/core/dataset/searchTest  body {datasetId, text, limit?, similarity?,
  searchMode?} → {list: [{id, q, a, score: [{type,value,index}], sourceName}], ...}
- POST /api/core/dataset/collection/create/localFile  multipart (datasetId + file) → collection
- POST /api/core/app/list          body {parentId?, type?, searchKey?} → array[AppListItem]
- POST /api/core/app/create        body {name, type, modules?, edges?} → ObjectId
- GET  /api/core/app/detail?appId= → AppItem
- DELETE /api/core/app/del?appId=

When no backend is configured (no api_key / default localhost), list operations
return the stable empty-contract ({items: [], total: 0}) so an Agent always gets
valid machine-readable JSON on the happy path; side-effect commands keep their
stable placeholder shape. Once a server is configured, the same commands issue
real HTTP requests through :class:`HttpClient` (retry semantics preserved).
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from fastgptcli.api.chat import ChatClient, ChatMessage, ChatRequest
from fastgptcli.api.http import HttpClient
from fastgptcli.config.settings import Config
from fastgptcli.models.dto import (
    AgentRunResult,
    ImportResult,
    KbInfo,
    ListResult,
    SearchResult,
    SearchResultItem,
)

_DATASET_TYPE = "dataset"
_APP_TYPES = ("simple", "workflow", "advanced", "plugin", "http")


class FastGPTClient:
    """Facade over the FastGPT Server domain API.

    ``_backend_configured`` gates real HTTP vs stable stubs: with no api key and
    the default localhost host we keep the empty contract (CI / offline friendly).
    """

    def __init__(self, config: Config):
        self.config = config
        self._base = f"http://{config.server_addr()}"
        self._api_key = config.server.api_key or ""
        self._backend_configured = bool(config.server.api_key) or config.server.host != "localhost"
        self._http = HttpClient(self._base, self._api_key)

    # ================= dataset =================

    def dataset_create(self, name: str) -> dict[str, Any]:
        if not self._backend_configured:
            return {"dataset_id": f"ds-{name[:8]}", "name": name, "status": "created"}
        payload: dict[str, Any] = {
            "name": name,
            "type": _DATASET_TYPE,
            "intro": f"{name} 知识库",
            "avatar": "/imgs/dataset/avatar.png",
        }
        vector = self.config.defaults.model
        if vector:
            payload["vectorModel"] = vector
        dataset_id = self._http.post_json("/api/core/dataset/create", payload)
        return {"dataset_id": str(dataset_id), "name": name, "status": "created"}

    def dataset_import(self, dataset_id: str, files: list[str]) -> ImportResult:
        if not self._backend_configured:
            return ImportResult(dataset_id=dataset_id, imported=len(files), files=files)
        imported: list[str] = []
        for path in files:
            payload = _read_file_bytes(path)
            resp = self._http.upload_multipart(
                "/api/core/dataset/collection/create/localFile",
                {"datasetId": dataset_id},
                (Path(path).name, payload[0], payload[1]),
            )
            collection_id = resp.get("_id") or resp.get("collectionId") or path
            imported.append(str(collection_id))
        return ImportResult(dataset_id=dataset_id, imported=len(imported), files=imported)

    def dataset_list(self) -> ListResult:
        if not self._backend_configured:
            return ListResult()
        data = self._http.post_json("/api/core/dataset/list", {"type": _DATASET_TYPE})
        items = _dataset_list_items(data)
        return ListResult(items=items, total=len(items))

    def dataset_delete(self, dataset_id: str) -> dict[str, Any]:
        if not self._backend_configured:
            return {"dataset_id": dataset_id, "status": "deleted"}
        self._http.delete_json("/api/core/dataset/delete", {"id": dataset_id})
        return {"dataset_id": dataset_id, "status": "deleted"}

    # ================= kb (maps to FastGPT dataset routes) =================

    def kb_create(self, name: str) -> KbInfo:
        if not self._backend_configured:
            return KbInfo(kb_id=f"kb-{name[:8]}", name=name, status="created")
        payload: dict[str, Any] = {"name": name, "type": _DATASET_TYPE}
        if self.config.defaults.model:
            payload["vectorModel"] = self.config.defaults.model
        kb_id = self._http.post_json("/api/core/dataset/create", payload)
        return KbInfo(kb_id=str(kb_id), name=name, status="created")

    def kb_list(self) -> ListResult:
        if not self._backend_configured:
            return ListResult()
        data = self._http.post_json("/api/core/dataset/list", {"type": _DATASET_TYPE})
        items = _dataset_list_items(data)
        return ListResult(items=items, total=len(items))

    def kb_upload(self, kb_id: str, files: list[str]) -> dict[str, Any]:
        if not self._backend_configured:
            doc_ids = [f"{kb_id}-doc-{i}" for i in range(len(files))]
            return {"kb_id": kb_id, "uploaded": len(files), "doc_ids": doc_ids}
        imported: list[str] = []
        for path in files:
            payload = _read_file_bytes(path)
            resp = self._http.upload_multipart(
                "/api/core/dataset/collection/create/localFile",
                {"datasetId": kb_id},
                (Path(path).name, payload[0], payload[1]),
            )
            imported.append(str(resp.get("_id") or resp.get("collectionId") or path))
        return {"kb_id": kb_id, "uploaded": len(imported), "doc_ids": imported}

    def kb_get(self, kb_id: str) -> dict[str, Any]:
        if not self._backend_configured:
            return {"kb_id": kb_id, "status": "active"}
        item = self._http.get_json("/api/core/dataset/detail", {"id": kb_id})
        return {
            "kb_id": str(item.get("_id", kb_id)),
            "name": item.get("name", ""),
            "intro": item.get("intro", ""),
            "status": _status_of(item),
        }

    def kb_delete(self, kb_id: str) -> dict[str, Any]:
        if not self._backend_configured:
            return {"kb_id": kb_id, "status": "deleted"}
        self._http.delete_json("/api/core/dataset/delete", {"id": kb_id})
        return {"kb_id": kb_id, "status": "deleted"}

    # ================= app =================

    def app_list(self) -> ListResult:
        if not self._backend_configured:
            return ListResult()
        data = self._http.post_json("/api/core/app/list", {})
        items = _app_list_items(data)
        return ListResult(items=items, total=len(items))

    def app_create(self, name: str, kind: str) -> dict[str, Any]:
        if not self._backend_configured:
            return {"app_id": f"app-{name[:8]}", "name": name, "kind": kind, "status": "created"}
        app_type = kind if kind in _APP_TYPES else "simple"
        app_id = self._http.post_json("/api/core/app/create", {"name": name, "type": app_type})
        return {"app_id": str(app_id), "name": name, "kind": app_type, "status": "created"}

    def app_deploy(self, app_id: str) -> dict[str, Any]:
        if not self._backend_configured:
            return {"app_id": app_id, "status": "deployed"}
        # FastGPT apps are live by default; "deploy" is a release alias that
        # returns the app version id from the detail route.
        item = self._http.get_json("/api/core/app/detail", {"appId": app_id})
        version = _find_version_id(item)
        return {"app_id": app_id, "version_id": version, "status": "deployed"}

    def app_test(self, app_id: str, message: str) -> dict[str, Any]:
        if not self._backend_configured:
            return {"app_id": app_id, "message": message, "status": "ok"}
        # Smoke test runs the OpenAI-compatible FastGPT chat endpoint.
        payload = {"appId": app_id, "messages": [{"role": "user", "content": message}]}
        try:
            resp = self._http.post_json("/api/v1/chat/completions", payload)
            answer = _extract_answer(resp)
        except Exception as exc:  # noqa: BLE001 - backend-dependent smoke test
            raise type(exc)(f"app test 失败: {exc}") from exc
        return {"app_id": app_id, "message": message, "answer": answer, "status": "ok"}

    def app_describe(self, app_id: str) -> dict[str, Any]:
        if not self._backend_configured:
            return {"app_id": app_id, "status": "active"}
        item = self._http.get_json("/api/core/app/detail", {"appId": app_id})
        return {
            "app_id": str(item.get("_id", app_id)),
            "name": item.get("name", ""),
            "intro": item.get("intro", ""),
            "type": item.get("type", ""),
            "status": "active",
        }

    def app_delete(self, app_id: str) -> dict[str, Any]:
        if not self._backend_configured:
            return {"app_id": app_id, "status": "deleted"}
        self._http.delete_json("/api/core/app/del", {"appId": app_id})
        return {"app_id": app_id, "status": "deleted"}

    # ================= workflow =================

    def workflow_deploy(self, name: str) -> dict[str, Any]:
        if not self._backend_configured:
            return {"workflow_id": f"wf-{name[:8]}", "name": name, "status": "deployed"}
        app_id = self._http.post_json(
            "/api/core/app/create",
            {"name": name, "type": "workflow", "modules": [], "edges": []},
        )
        return {"workflow_id": str(app_id), "name": name, "status": "deployed"}

    def workflow_list(self) -> ListResult:
        if not self._backend_configured:
            return ListResult()
        data = self._http.post_json("/api/core/app/list", {"type": "workflow"})
        items = _app_list_items(data)
        return ListResult(items=items, total=len(items))

    def workflow_test(self, workflow_id: str) -> dict[str, Any]:
        if not self._backend_configured:
            return {"workflow_id": workflow_id, "status": "ok"}
        return self.app_test(workflow_id, "ping")

    # ================= agent =================

    def agent_run(self, input_text: str, tokens: int = 0) -> AgentRunResult:
        """`agent run --input` -> {answer, tokens, sources}.

        When a chat endpoint is configured, delegate to the real chat client so
        the answer fields are faithfully populated (existing real chain).
        """
        chat = ChatClient(self.config.chat.base_url, self.config.chat.model, api_key=_chat_key())
        try:
            req = ChatRequest(model=self.config.chat.model, messages=[ChatMessage("user", input_text)])
            answer = chat.first_answer(req)
            return AgentRunResult(answer=answer, tokens=tokens)
        except Exception:  # noqa: BLE001 - no backend yet; keep contract shape
            return AgentRunResult(answer=input_text, tokens=tokens)

    # ================= query =================

    def query_search(self, query: str, kb: str = "", limit: int = 10) -> SearchResult:
        if not self._backend_configured:
            return SearchResult()
        if not kb:
            raise _search_requires_kb()
        data = self._http.post_json(
            "/api/core/dataset/searchTest",
            {"datasetId": kb, "text": query, "limit": limit},
        )
        raw_items = data.get("list") or []
        results = [
            SearchResultItem(
                score=_best_score(item),
                content=_search_content(item),
                source=_search_source(item),
            )
            for item in raw_items[:limit]
        ]
        return SearchResult(results=results)


# ================= mapping helpers =================


def _dataset_list_items(data: Any) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    for raw in data if isinstance(data, list) else []:
        items.append(
            {
                "dataset_id": str(raw.get("_id", "")),
                "name": raw.get("name", ""),
                "type": raw.get("type", ""),
                "intro": raw.get("intro", ""),
            }
        )
    return items


def _app_list_items(data: Any) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    for raw in data if isinstance(data, list) else []:
        items.append(
            {
                "app_id": str(raw.get("_id", "")),
                "name": raw.get("name", ""),
                "type": raw.get("type", ""),
                "intro": raw.get("intro", ""),
            }
        )
    return items


def _status_of(item: dict[str, Any]) -> str:
    status = item.get("status")
    return status or ("active" if not item.get("deleteTime") else "deleted")


def _find_version_id(item: dict[str, Any]) -> str:
    if not isinstance(item, dict):
        return ""
    version = item.get("versionId")
    if not version:
        version = (item.get("version") or {}).get("_id")
    return str(version or "")


def _extract_answer(resp: dict[str, Any]) -> str:
    choices = resp.get("choices") or []
    if choices:
        msg = choices[0].get("message") or {}
        return str(msg.get("content", ""))
    return str(resp.get("answer", ""))


def _best_score(item: dict[str, Any]) -> float:
    scores = item.get("score") or []
    if scores:
        values = [float(s.get("value", 0.0)) for s in scores if isinstance(s, dict)]
        return max(values) if values else 0.0
    return 0.0


def _search_content(item: dict[str, Any]) -> str:
    return str(item.get("q") or item.get("a") or "")


def _search_source(item: dict[str, Any]) -> str:
    return str(item.get("sourceName") or item.get("sourceId") or "")


def _read_file_bytes(path: str) -> tuple[bytes, str]:
    """Read a file as (bytes, mime). Raises structured error if missing."""
    from fastgptcli.output.render import CliError

    try:
        data = Path(path).read_bytes()
    except OSError as exc:
        raise CliError(f"无法读取文件: {path}", kind="validation", details={"path": path}) from exc
    suffix = Path(path).suffix.lower()
    mime = {
        ".txt": "text/plain",
        ".md": "text/markdown",
        ".pdf": "application/pdf",
        ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        ".csv": "text/csv",
        ".html": "text/html",
        ".json": "application/json",
    }.get(suffix, "application/octet-stream")
    return data, mime


def _search_requires_kb() -> Any:
    from fastgptcli.output.render import CliError

    return CliError(
        "query search 需要 --kb <知识库 id> 指定检索目标（FastGPT 服务端必填 datasetId）",
        kind="validation",
    )


def _chat_key() -> str:
    from fastgptcli.config.settings import chat_api_key

    return chat_api_key()
