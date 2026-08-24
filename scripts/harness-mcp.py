#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
harness-mcp.py — 纯标准库 MCP（Model Context Protocol）server（零第三方依赖）。

把 harness-engineering 项目知识文件（.harness/manifest.json、STATE.json、HANDOFF.md、
docs/ARCHITECTURE.md）按 MCP 协议暴露给生产 Agent（Claude Code / Codex / Cursor / DSH 均可接）。

- 传输：stdio，newline-delimited JSON（每行一个 JSON-RPC 2.0 对象，UTF-8）。
- 能力：resources（resources/list、resources/read）+ tools（tools/list、tools/call）。
- 基线协议版本：2025-03-26（initialize 时回显客户端支持的已知版本，否则回落 2025-03-26）。
- 用法：python harness-mcp.py [--project <项目根>]
        --project 缺省时从 cwd 向上探测 .harness/manifest.json 或 STATE.json 定位项目根。
- 日志一律走 stderr（stdout 是协议通道，绝不被日志污染）。

report_error 语义对齐同目录 record-error.py（内联实现，不依赖子进程）：
- rule_id 必须已存在且生效（revoked/expiry 即失效）；敏感信息（手机/邮箱/密钥）写入前拦截；
- 原子写（临时文件 + os.replace）；并发锁文件放系统临时目录（项目目录不落 .lock 文件）；
- 事件不回显原文（堵日志侧密钥泄露）；事件超 500 字符截断。
"""
import argparse
import datetime
import hashlib
import json
import os
import re
import sys
import tempfile
from types import SimpleNamespace

# 并发锁：Windows msvcrt / POSIX fcntl；不可用时降级无锁（与 record-error.py 同策略）
try:
    import msvcrt  # Windows
except ImportError:
    msvcrt = None
try:
    import fcntl  # POSIX
except ImportError:
    fcntl = None

SERVER_NAME = "harness-mcp"
SERVER_VERSION = "1.0.0"
KNOWN_PROTOCOL_VERSIONS = ("2024-11-05", "2025-03-26", "2025-06-18", "2025-11-25")
DEFAULT_PROTOCOL_VERSION = "2025-03-26"

RULE_ID_RE = re.compile(r"^R\d+$")
MAX_EVENT_LEN = 500
MAX_EVENTS = 5000

# 敏感模式与 record-error.py 保持一致（改动时两边同步）
SENSITIVE = [
    (re.compile(r"1[3-9]\d{9}"), "手机号"),
    (re.compile(r"[１-９]\d{10}|[０-９]{11}"), "全角手机号"),
    (re.compile(r"\b[\w.+-]+@[\w-]+\.\w{2,}\b"), "邮箱"),
    (re.compile(r"sk-proj-[A-Za-z0-9_-]{16,}|sk-ant-api03-[A-Za-z0-9_-]{16,}|sk-[A-Za-z0-9]{20,}|sk_live_[A-Za-z0-9]{16,}"), "疑似密钥"),
    (re.compile(r"ghp_[A-Za-z0-9]{20,}|gho_[A-Za-z0-9]{20,}|ghu_[A-Za-z0-9]{20,}|ghs_[A-Za-z0-9]{20,}|ghr_[A-Za-z0-9]{20,}|github_pat_[A-Za-z0-9_]{20,}|AIza[0-9A-Za-z_-]{20,}|glx-[A-Za-z0-9]{20,}|Bearer\s+[A-Za-z0-9._-]{16,}"), "疑似密钥"),
]

RESOURCE_DEFS = [
    {"uri": "harness://manifest", "name": "manifest",
     "rel": os.path.join(".harness", "manifest.json"), "mimeType": "application/json",
     "description": "项目嵌入清单（harness_version / project / components / verify）"},
    {"uri": "harness://state", "name": "state",
     "rel": "STATE.json", "mimeType": "application/json",
     "description": "规则注册表 + events append-only 审计日志（schema v2）"},
    {"uri": "harness://handoff", "name": "handoff",
     "rel": "HANDOFF.md", "mimeType": "text/markdown",
     "description": "项目交接档案（目标/完成标准/验证命令/边界/未决问题）"},
    {"uri": "harness://architecture", "name": "architecture",
     "rel": os.path.join("docs", "ARCHITECTURE.md"), "mimeType": "text/markdown",
     "description": "架构地图（模块职责/架构不变量/依赖层级）"},
]


class McpError(Exception):
    """JSON-RPC 协议级错误（对应 MCP 规范的 error 响应）。"""

    def __init__(self, code, message, data=None):
        super().__init__(message)
        self.code = code
        self.message = message
        self.data = data


# ---------- 工具函数 ----------

def has_sensitive(text):
    found = []
    for rx, name in SENSITIVE:
        if rx.search(text):
            found.append(name)
    return found


def find_project_root(start):
    """从 start 向上探测 .harness/manifest.json 或 STATE.json，返回项目根或 None。"""
    d = os.path.abspath(start)
    while True:
        if (os.path.isfile(os.path.join(d, ".harness", "manifest.json"))
                or os.path.isfile(os.path.join(d, "STATE.json"))):
            return d
        parent = os.path.dirname(d)
        if parent == d:
            return None
        d = parent


def _load_json(path):
    with open(path, "r", encoding="utf-8") as fh:
        return json.load(fh)


def _save_json_atomic(path, obj):
    """原子写：同目录临时文件 + os.replace（项目目录唯一的瞬时文件，允许）。"""
    d = os.path.dirname(os.path.abspath(path)) or "."
    os.makedirs(d, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=d, suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            json.dump(obj, fh, ensure_ascii=False, indent=2)
        os.replace(tmp, path)
    except BaseException:
        try:
            os.remove(tmp)
        except OSError:
            pass
        raise


def _lock_path_for(state_path):
    """并发锁放系统临时目录（键 = 状态文件绝对路径的 sha1），项目目录不落 .lock 文件。"""
    h = hashlib.sha1(os.path.abspath(state_path).encode("utf-8")).hexdigest()[:16]
    return os.path.join(tempfile.gettempdir(), "harness-mcp-" + h + ".lock")


def _locked(state_path, fn):
    """读-改-写串行化（尽力而为）：加锁失败降级无锁；事务异常原样抛出。"""
    lockpath = _lock_path_for(state_path)
    try:
        lf = open(lockpath, "a+b")
    except OSError:
        return fn()
    try:
        lf.write(b"x")
        lf.flush()
        if msvcrt:
            lf.seek(0)
            msvcrt.locking(lf.fileno(), msvcrt.LK_LOCK, 1)
        elif fcntl:
            fcntl.flock(lf.fileno(), fcntl.LOCK_EX)
    except (OSError, ValueError):
        return fn()  # 仅加锁失败才无锁执行
    try:
        return fn()
    finally:
        try:
            if msvcrt:
                lf.seek(0)
                msvcrt.locking(lf.fileno(), msvcrt.LK_UNLCK, 1)
            elif fcntl:
                fcntl.flock(lf.fileno(), fcntl.LOCK_UN)
        except Exception:
            pass
        lf.close()


# ---------- 工具实现 ----------

def _rule_status(r):
    if r.get("revoked"):
        return "revoked"
    if r.get("expiry"):
        return "expired"
    return "active"


def _pretty(obj):
    return json.dumps(obj, ensure_ascii=False, indent=2)


def tool_read_manifest(args, ctx):
    path = os.path.join(ctx.project_root, ".harness", "manifest.json")
    if not os.path.isfile(path):
        return f"manifest.json 不存在: {path}", True
    try:
        data = _load_json(path)
    except (OSError, ValueError) as e:
        return f"manifest.json 读取/解析失败: {e}", True
    field = (args.get("field") or "").strip()
    if field:
        cur = data
        for part in field.split("."):
            if isinstance(cur, dict) and part in cur:
                cur = cur[part]
            else:
                return f"字段不存在: {field}", True
        return _pretty(cur), False
    return _pretty(data), False


def tool_query_rules(args, ctx):
    path = os.path.join(ctx.project_root, "STATE.json")
    if not os.path.isfile(path):
        return f"STATE.json 不存在: {path}", True
    try:
        state = _load_json(path)
    except (OSError, ValueError) as e:
        return f"STATE.json 读取/解析失败: {e}", True
    status = (args.get("status") or "all").strip().lower()
    keyword = (args.get("keyword") or "").strip()
    if status not in ("all", "active", "revoked", "expired"):
        return f"status 非法: {status}（可选 all/active/revoked/expired）", True
    rules = []
    for r in state.get("rules", []):
        st = _rule_status(r)
        if status != "all" and st != status:
            continue
        if keyword:
            hay = " ".join(str(r.get(k) or "") for k in ("id", "text", "incident", "layer", "born", "valid_time"))
            if keyword.lower() not in hay.lower():
                continue
        out = dict(r)
        out["status"] = st
        rules.append(out)
    result = {
        "matched": len(rules),
        "total_rules": len(state.get("rules", [])),
        "filter": {"status": status, "keyword": keyword or None},
        "rules": rules,
    }
    return _pretty(result), False


def tool_report_error(args, ctx):
    state_path = os.path.join(ctx.project_root, "STATE.json")
    rule_id = (args.get("rule_id") or "").strip().upper()
    if not RULE_ID_RE.fullmatch(rule_id):
        return f"规则 id 格式非法: {rule_id}（须 ^R\\d+$）", True
    etype = (args.get("event_type") or "violation").strip().lower()
    if etype not in ("violation", "rework", "explanation"):
        return f"event_type 非法: {etype}（可选 violation/rework/explanation）", True
    event = (args.get("event") or "").strip()
    if not event:
        return "缺少 event（事件描述不能为空）", True
    sensitive = has_sensitive(event)
    if sensitive:
        return ("拒绝写入：事件含敏感内容（%s）。请脱敏后再记；密钥/完整 PII 禁止进 STATE.json"
                % ", ".join(sensitive)), True
    truncated = False
    if len(event) > MAX_EVENT_LEN:
        event = event[:MAX_EVENT_LEN]
        truncated = True
    ts = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")

    def txn():
        try:
            state = _load_json(state_path)
        except (OSError, ValueError) as e:
            raise ValueError(f"STATE.json 读取/解析失败: {e}")
        found = None
        for r in state.get("rules", []):
            if r.get("id") == rule_id:
                found = r
                break
        if found is None:
            raise ValueError(f"规则 id 不存在: {rule_id}（先用 record-error.py --type rule_added 创建规则）")
        if found.get("revoked") or found.get("expiry"):
            raise ValueError(f"规则已失效: {rule_id}（已被撤销/过期，请先用 --type rule_added 重新声明）")
        if etype in ("violation", "explanation"):
            found["hits"] = found.get("hits", 0) + 1
            found["last_hit"] = ts
        events = state.setdefault("events", [])
        events.append({"ts": ts, "type": etype, "rule": rule_id, "detail": event})
        warn = None
        if len(events) > MAX_EVENTS:
            warn = f"事件数超过 {MAX_EVENTS}（events 永不归档，append-only）"
        meta = state.setdefault("meta", {})
        meta["total_incidents"] = meta.get("total_incidents", 0) + 1
        _save_json_atomic(state_path, state)
        return found.get("hits", 0), warn

    try:
        hits, warn = _locked(state_path, txn)
    except (OSError, ValueError, TypeError) as e:
        return f"写入失败: {e}", True
    msg = f"已记录 [{etype}]（rule={rule_id}，hits={hits}）"
    if truncated:
        msg += "；事件超长已截断至 500 字符"
    if warn:
        msg += f"；WARN {warn}"
    return msg, False


TOOL_DEFS = [
    {
        "name": "read_manifest",
        "description": "读取项目嵌入清单 .harness/manifest.json：无参数返回全文；传 field（支持点路径如 project.name、components.handoff）返回单字段。",
        "inputSchema": {
            "type": "object",
            "properties": {
                "field": {"type": "string", "description": "可选：要读取的字段（点路径）"}
            },
        },
    },
    {
        "name": "query_rules",
        "description": "从 STATE.json rules[] 查询规则注册表：可按 status（all/active/revoked/expired）与 keyword（匹配 id/text/incident/layer/born/valid_time）过滤，返回结构化规则（id/text/layer/hits/valid_time/revoked 等）。",
        "inputSchema": {
            "type": "object",
            "properties": {
                "status": {"type": "string", "enum": ["all", "active", "revoked", "expired"],
                           "description": "可选：按状态过滤，默认 all"},
                "keyword": {"type": "string", "description": "可选：关键词（不区分大小写子串匹配）"},
            },
        },
    },
    {
        "name": "report_error",
        "description": "把违规/返工/解释事件追加进 STATE.json events（append-only 审计日志）：rule_id 必须已存在且生效；敏感内容（手机/邮箱/密钥）拒绝写入；原子写。事件原文不回显。",
        "inputSchema": {
            "type": "object",
            "properties": {
                "rule_id": {"type": "string", "description": "规则 id（^R\\d+$，如 R01）"},
                "event": {"type": "string", "description": "事件描述（违规/返工事实，≤500 字符，禁含敏感信息）"},
                "event_type": {"type": "string", "enum": ["violation", "rework", "explanation"],
                               "description": "可选：事件类型，默认 violation"},
            },
            "required": ["rule_id", "event"],
        },
    },
]
TOOL_HANDLERS = {
    "read_manifest": tool_read_manifest,
    "query_rules": tool_query_rules,
    "report_error": tool_report_error,
}


# ---------- 协议分发 ----------

def handle_initialize(params, ctx):
    requested = (params.get("protocolVersion") or "").strip()
    chosen = requested if requested in KNOWN_PROTOCOL_VERSIONS else DEFAULT_PROTOCOL_VERSION
    return {
        "protocolVersion": chosen,
        "capabilities": {"resources": {}, "tools": {}},
        "serverInfo": {"name": SERVER_NAME, "version": SERVER_VERSION},
        "instructions": (
            "harness-mcp 暴露项目知识文件：resources 提供 harness://manifest、harness://state、"
            "harness://handoff、harness://architecture；tools 提供 read_manifest / query_rules / "
            "report_error。当前项目根: %s" % ctx.project_root
        ),
    }


def handle_resources_list(params, ctx):
    return {"resources": [
        {"uri": d["uri"], "name": d["name"], "description": d["description"], "mimeType": d["mimeType"]}
        for d in RESOURCE_DEFS
    ]}


def handle_resources_read(params, ctx):
    uri = params.get("uri")
    if not uri or not isinstance(uri, str):
        raise McpError(-32602, "Invalid Params: missing uri")
    for d in RESOURCE_DEFS:
        if d["uri"] == uri:
            path = os.path.join(ctx.project_root, d["rel"])
            if not os.path.isfile(path):
                raise McpError(-32002, "Resource not found", {"uri": uri})
            try:
                with open(path, "r", encoding="utf-8") as fh:
                    text = fh.read()
            except OSError as e:
                raise McpError(-32603, "Failed to read resource: %s" % e, {"uri": uri})
            return {"contents": [{"uri": uri, "mimeType": d["mimeType"], "text": text}]}
    raise McpError(-32002, "Resource not found", {"uri": uri})


def handle_tools_list(params, ctx):
    return {"tools": TOOL_DEFS}


def handle_tools_call(params, ctx):
    name = params.get("name")
    args = params.get("arguments") or {}
    if not isinstance(name, str) or not name:
        raise McpError(-32602, "Invalid Params: missing tool name")
    if not isinstance(args, dict):
        raise McpError(-32602, "Invalid Params: arguments must be an object")
    handler = TOOL_HANDLERS.get(name)
    if handler is None:
        raise McpError(-32602, "Unknown tool: %s" % name)
    try:
        text, is_error = handler(args, ctx)
    except McpError:
        raise
    except Exception as e:  # 工具执行异常 → isError 结果（LLM 可见可自纠），不崩进程
        text, is_error = "工具执行异常: %s" % e, True
    return {"content": [{"type": "text", "text": text}], "isError": is_error}


def dispatch(method, params, ctx):
    if method == "initialize":
        return handle_initialize(params, ctx)
    if method == "ping":
        return {}
    if method == "resources/list":
        return handle_resources_list(params, ctx)
    if method == "resources/templates/list":
        return {"resourceTemplates": []}
    if method == "resources/read":
        return handle_resources_read(params, ctx)
    if method == "tools/list":
        return handle_tools_list(params, ctx)
    if method == "tools/call":
        return handle_tools_call(params, ctx)
    raise McpError(-32601, "Method not found: %s" % method)


def send(obj):
    data = json.dumps(obj, ensure_ascii=False)
    sys.stdout.buffer.write(data.encode("utf-8") + b"\n")
    sys.stdout.buffer.flush()


def handle_line(line, ctx):
    try:
        msg = json.loads(line)
    except ValueError:
        send({"jsonrpc": "2.0", "id": None,
              "error": {"code": -32700, "message": "Parse error: invalid JSON"}, "result": None})
        return
    if not isinstance(msg, dict) or not isinstance(msg.get("method"), str):
        send({"jsonrpc": "2.0", "id": msg.get("id") if isinstance(msg, dict) else None,
              "error": {"code": -32600, "message": "Invalid Request"}, "result": None})
        return
    method = msg["method"]
    if "id" not in msg:  # 通知：无 id，不回响应
        return
    rid = msg["id"]
    params = msg.get("params") or {}
    if not isinstance(params, dict):
        send({"jsonrpc": "2.0", "id": rid,
              "error": {"code": -32602, "message": "Invalid Params: params must be an object"}, "result": None})
        return
    try:
        result = dispatch(method, params, ctx)
        send({"jsonrpc": "2.0", "id": rid, "result": result})
    except McpError as e:
        err = {"code": e.code, "message": e.message}
        if e.data is not None:
            err["data"] = e.data
        send({"jsonrpc": "2.0", "id": rid, "error": err, "result": None})
    except Exception as e:  # 兜底：任何异常 → 结构化错误，绝不崩溃
        print("harness-mcp: internal error: %r" % (e,), file=sys.stderr)
        send({"jsonrpc": "2.0", "id": rid,
              "error": {"code": -32603, "message": "Internal error: %s" % e}, "result": None})


def main():
    ap = argparse.ArgumentParser(
        description="harness-mcp：纯标准库 MCP server，暴露 harness-engineering 项目知识文件")
    ap.add_argument("--project", default=None,
                    help="项目根目录（含 .harness/manifest.json 或 STATE.json）；缺省从 cwd 向上探测")
    ap.add_argument("--version", action="version", version="%s %s" % (SERVER_NAME, SERVER_VERSION))
    args = ap.parse_args()

    if args.project:
        root = os.path.abspath(args.project)
        if not (os.path.isfile(os.path.join(root, ".harness", "manifest.json"))
                or os.path.isfile(os.path.join(root, "STATE.json"))):
            print("harness-mcp: 项目根缺少知识文件: %s（无 .harness/manifest.json 或 STATE.json）" % root,
                  file=sys.stderr)
            return 2
    else:
        root = find_project_root(os.getcwd())
        if root is None:
            print("harness-mcp: 未找到项目根（向上探测 .harness/manifest.json / STATE.json 无果）；"
                  "请用 --project 指定", file=sys.stderr)
            return 2

    ctx = SimpleNamespace(project_root=root)
    print("harness-mcp %s: serving project %s" % (SERVER_VERSION, root), file=sys.stderr)

    try:
        for raw in sys.stdin.buffer:  # 逐行读；EOF 自然结束
            line = raw.decode("utf-8", errors="replace").strip()
            if not line:
                continue
            try:
                handle_line(line, ctx)
            except OSError:
                break  # 输出管道关闭（客户端退出）→ 优雅结束
    except KeyboardInterrupt:
        return 130
    return 0


if __name__ == "__main__":
    sys.exit(main())
