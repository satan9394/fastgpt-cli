"""OpenAI-compatible chat client migrated from Go internal/client/chat.go + types.go.

Contract preserved:
- POST {base}/chat/completions with {model, messages, max_tokens?, temperature?}
- messages cannot be empty
- retry on 429/5xx; 4xx terminal
- surfaces server-provided error.message with no api key leakage
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from fastgptcli.api.http import HttpClient
from fastgptcli.output.render import CliError


@dataclass
class ChatMessage:
    role: str
    content: str

    def to_dict(self) -> dict[str, str]:
        return {"role": self.role, "content": self.content}


@dataclass
class ChatRequest:
    model: str
    messages: list[ChatMessage]
    max_tokens: int = 0
    temperature: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "model": self.model,
            "messages": [m.to_dict() for m in self.messages],
        }
        if self.max_tokens > 0:
            payload["max_tokens"] = self.max_tokens
        if self.temperature != 0:
            payload["temperature"] = self.temperature
        return payload


@dataclass
class ChatUsage:
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0

    @classmethod
    def from_dict(cls, data: dict[str, Any] | None) -> ChatUsage | None:
        if not data:
            return None
        return cls(
            prompt_tokens=int(data.get("prompt_tokens", 0)),
            completion_tokens=int(data.get("completion_tokens", 0)),
            total_tokens=int(data.get("total_tokens", 0)),
        )


@dataclass
class ChatResponse:
    id: str = ""
    choices: list[dict[str, Any]] = field(default_factory=list)
    usage: ChatUsage | None = None
    error: dict[str, Any] | None = None


class ChatClient:
    """OpenAI-compatible /chat/completions HTTP client."""

    def __init__(
        self,
        base_url: str,
        model: str,
        api_key: str = "",
        timeout: float = 60.0,
        max_retry: int = 2,
    ) -> None:
        self.http = HttpClient(base_url, api_key=api_key, timeout=timeout, max_retry=max_retry)
        self.model = model

    def chat(self, req: ChatRequest) -> ChatResponse:
        if not req.messages:
            raise CliError("messages 不能为空", kind="validation")
        if not req.model:
            req.model = self.model
        data = self.http.post_json("/chat/completions", req.to_dict())

        out = ChatResponse(id=str(data.get("id", "")))
        if data.get("error"):
            err = data["error"]
            out.error = err
            message = err.get("message", "")
            if message:
                raise CliError(f"服务端错误: {message}", kind="backend")
        out.choices = data.get("choices", []) or []
        if not out.choices:
            raise CliError("响应无 choices 字段", kind="backend")
        out.usage = ChatUsage.from_dict(data.get("usage"))
        return out

    def first_answer(self, req: ChatRequest) -> str:
        resp = self.chat(req)
        try:
            return resp.choices[0]["message"]["content"]
        except (KeyError, IndexError) as exc:
            raise CliError("响应缺少 message.content", kind="backend") from exc
