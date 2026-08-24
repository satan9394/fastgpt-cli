"""HTTP transport with retry semantics migrated from Go internal/client.

Go source semantics preserved:
- GET/POST/DELETE JSON, Bearer auth when api_key present
- retry on 429 / 5xx only (never on 4xx client errors) with backoff
- raises a typed error carrying the HTTP status code
- multipart file upload is NOT retried (a partially consumed stream cannot be
  safely replayed; documented as single-attempt)
"""

from __future__ import annotations

import io
import time
from collections.abc import Mapping
from typing import Any

import requests

from fastgptcli.output.render import CliError


class HttpStatusError(CliError):
    """Raised for non-2xx responses. 4xx are terminal; 429/5xx retried."""

    def __init__(self, code: int, message: str | None = None):
        super().__init__(message or f"HTTP {code}", kind="backend", details={"status_code": code})
        self.code = code


class HttpClient:
    """A small HTTP client mirroring the Go ChatClient transport semantics."""

    def __init__(self, base_url: str, api_key: str = "", timeout: float = 60.0, max_retry: int = 2):
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.timeout = timeout
        self.max_retry = max_retry

    # ---- methods with retry (safe to replay) ----

    def post_json(self, path: str, payload: dict[str, Any]) -> dict[str, Any]:
        """POST JSON to path with retry on 429/5xx. Returns parsed JSON dict."""
        return self._request("POST", path, json_body=payload)

    def get_json(self, path: str, params: Mapping[str, Any] | None = None) -> dict[str, Any]:
        """GET with retry on 429/5xx. Returns parsed JSON dict."""
        return self._request("GET", path, params=params)

    def delete_json(self, path: str, params: Mapping[str, Any] | None = None) -> dict[str, Any]:
        """DELETE with retry on 429/5xx. Returns parsed JSON (may be empty dict)."""
        return self._request("DELETE", path, params=params)

    # ---- multipart upload (single attempt, no retry) ----

    def upload_multipart(
        self,
        path: str,
        fields: Mapping[str, str],
        file_payload: tuple[str, bytes, str],
    ) -> dict[str, Any]:
        """POST multipart/form-data once (no retry).

        ``file_payload`` is ``(filename, bytes, content_type)``. Auth header is
        attached like other requests; returns parsed JSON.
        """
        url = f"{self.base_url}{path}"
        headers = {"Accept": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        files = {"file": (file_payload[0], io.BytesIO(file_payload[1]), file_payload[2])}
        try:
            resp = requests.post(
                url, data=dict(fields), files=files, headers=headers, timeout=self.timeout
            )
        except requests.RequestException as exc:
            raise CliError(f"上传失败: {exc}", kind="transport") from exc
        if resp.status_code >= 400:
            raise HttpStatusError(resp.status_code)
        return resp.json()

    # ---- shared core ----

    def _request(
        self,
        method: str,
        path: str,
        *,
        params: Mapping[str, Any] | None = None,
        json_body: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        url = f"{self.base_url}{path}"
        headers = {"Content-Type": "application/json", "Accept": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"

        last_err: HttpStatusError | None = None
        for attempt in range(self.max_retry + 1):
            if attempt > 0:
                time.sleep(attempt * 0.5)  # backoff: 0.5s, 1.0s ...
            try:
                return self._do_once(method, url, headers, params, json_body)
            except HttpStatusError as exc:
                last_err = exc
                # Only retry 429 and 5xx; 4xx client errors are terminal.
                if exc.code < 500 and exc.code != 429:
                    raise
        if last_err is not None:
            raise last_err
        raise HttpStatusError(0, "请求失败")

    def _do_once(
        self,
        method: str,
        url: str,
        headers: dict[str, str],
        params: Mapping[str, Any] | None,
        json_body: dict[str, Any] | None,
    ) -> dict[str, Any]:
        try:
            if method == "GET":
                resp = requests.get(url, params=dict(params or {}), headers=headers, timeout=self.timeout)
            elif method == "DELETE":
                resp = requests.delete(url, params=dict(params or {}), headers=headers, timeout=self.timeout)
            else:
                resp = requests.post(url, json=json_body, headers=headers, timeout=self.timeout)
        except requests.RequestException as exc:
            raise CliError(f"请求失败: {exc}", kind="transport") from exc
        if resp.status_code >= 400:
            raise HttpStatusError(resp.status_code)
        if not resp.text:
            return {}
        try:
            return resp.json()
        except ValueError as exc:
            raise CliError(f"响应不是 JSON: {resp.text[:200]}", kind="backend") from exc
