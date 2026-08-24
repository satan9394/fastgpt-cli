"""query command group: query search (RAG retrieval) / query chat (inline, non-mainline)."""

from __future__ import annotations

import typer

from fastgptcli.api.chat import ChatClient, ChatMessage, ChatRequest
from fastgptcli.cli._common import emit, get_client, get_config, json_opt
from fastgptcli.config.settings import chat_api_key
from fastgptcli.output.render import CliError

app = typer.Typer(help="Query domain: RAG search + inline chat.")


@app.command("search")
def query_search(
    ctx: typer.Context,
    query: str = typer.Argument(..., help="Search query."),
    kb: str = typer.Option(
        "",
        "--kb",
        help="Knowledge base (dataset) id to scope search. Required when a backend is configured.",
    ),
    limit: int = typer.Option(10, "--limit", help="Max results."),
    json_flag: bool = json_opt(),
) -> None:
    """RAG retrieval. Default JSON: {results:[{score, content, source}]}."""
    if json_flag:
        ctx.obj["output"] = "json"
    client = get_client(ctx)
    result = client.query_search(query, kb=kb, limit=limit)
    emit(ctx.obj, result.to_dict())


@app.command("chat")
def query_chat(
    ctx: typer.Context,
    message: str = typer.Option(..., "--message", help="Chat message."),
    max_tokens: int = typer.Option(0, "--max-tokens", help="Optional token cap."),
    json_flag: bool = json_opt(),
) -> None:
    """Inline chat capability (not the main line). Uses the OpenAI-compatible chat endpoint."""
    if json_flag:
        ctx.obj["output"] = "json"
    cfg = get_config(ctx)
    chat = ChatClient(cfg.chat.base_url, cfg.chat.model, api_key=chat_api_key())
    req = ChatRequest(model=cfg.chat.model, messages=[ChatMessage("user", message)], max_tokens=max_tokens)
    try:
        answer = chat.first_answer(req)
    except CliError:
        raise
    except Exception as exc:  # noqa: BLE001
        raise CliError(f"chat 失败: {exc}", kind="transport") from exc
    emit(ctx.obj, {"answer": answer})
