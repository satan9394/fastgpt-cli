#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
handoff-log.py — HANDOFF.md 变更日志追加（方向②：交接档案强制化）。

HANDOFF.md 是跨会话/跨 agent 接续的权威档案；本脚本把「每轮结束追加一条」从约定
变成可机械执行的动作（半强制：hook 自动记事实，结论由 agent/人补）。

命令：
    --append "做了什么" [--verify "验证结果"] [--dir <项目根>]
        在 <根>/HANDOFF.md 的「## 变更日志」节追加一条：
            - {日期} {做了什么} {验证结果}
        找不到该节则自动创建（幂等）。每次调用追加一条，append-only（与 STATE events 同哲学）。
    --from-transcript <transcript.json> [--dir <项目根>]
        解析 Claude Code 会话 transcript（Stop hook 输入 transcript_path 指向的文件，
        JSONL 或 JSON 数组均可），提取读/写过的文件与工具名，追加一条事实记录：
            - {日期} 会话 <id> 动过文件: {文件列表}（工具: {工具列表}）——结论与验证待补
        transcript 解析失败：stderr 警告 + 不追加 + exit 0（best-effort，不阻塞会话结束）。

诚实边界：hook 只能记录「事实」（动了哪些文件），记不了「结论与验证」——那是
agent/人 的职责，追加文本显式标注「结论与验证待补」，不伪装自动总结。

用法示例：
    python scripts/handoff-log.py --append "v4.11.0 方向① 落地" --verify "verify-integrity 全 PASS"
    python scripts/handoff-log.py --from-transcript "%s"   # Stop hook command 里用占位符

退出码：0=OK（含 best-effort 失败）；1=参数错或 HANDOFF.md 写入失败。
纯标准库；UTF-8 三通道。
"""
import argparse
import datetime
import json
import os
import re
import sys

# 三通道统一 UTF-8
for _stream_name in ("stdout", "stdin", "stderr"):
    _s = getattr(sys, _stream_name, None)
    if _s is not None and hasattr(_s, "reconfigure"):
        try:
            _s.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass

sys.dont_write_bytecode = True

SECTION = "## 变更日志"


def _today():
    return datetime.date.today().isoformat()


def _handoff_path(root):
    return os.path.join(root, "HANDOFF.md")


def _read(path):
    try:
        with open(path, "r", encoding="utf-8-sig") as fh:
            return fh.read()
    except OSError:
        return None


def _append_entry(root, entry_line):
    path = _handoff_path(root)
    text = _read(path)
    if text is None:
        text = "# HANDOFF —— 项目交接档案\n\n> 由 handoff-log.py 首次创建。\n"
    if not text.rstrip().endswith("\n"):
        text += "\n"
    if SECTION not in text:
        text += "\n---\n\n%s（每轮结束追加一条）\n" % SECTION
    text += "%s\n" % entry_line
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(text)
    return path


def _extract_from_transcript(transcript_path):
    """从 Claude Code transcript 提取 (session_id, files, tools)。

    transcript 为 JSONL（每行一个事件）或 JSON 数组。best-effort：
    解析失败返回 (None, [], [])，调用方决定不追加。
    """
    session_id = None
    files, tools = [], []
    try:
        raw = open(transcript_path, "r", encoding="utf-8-sig").read()
    except OSError as exc:
        print("handoff-log: 无法读取 transcript %s: %s" % (transcript_path, exc), file=sys.stderr)
        return None, [], []
    if not raw.strip():
        return None, [], []

    def feed(obj):
        nonlocal session_id
        if not isinstance(obj, dict):
            return
        if obj.get("sessionId"):
            session_id = obj["sessionId"]
        msg = obj.get("message")
        if not isinstance(msg, dict):
            return
        content = msg.get("content")
        if isinstance(content, list):
            for block in content:
                if not isinstance(block, dict):
                    continue
                if block.get("type") == "tool_use":
                    name = block.get("name")
                    if name:
                        tools.append(name)
                    inp = block.get("input") or {}
                    fp = inp.get("file_path") or inp.get("path")
                    if fp and isinstance(fp, str):
                        files.append(fp)

    try:
        parsed = json.loads(raw)
        if isinstance(parsed, list):
            for item in parsed:
                feed(item)
        elif isinstance(parsed, dict):
            feed(parsed)
        else:
            # 顶层不是 JSON：按 JSONL 逐行尝试
            for line in raw.splitlines():
                line = line.strip()
                if not line:
                    continue
                try:
                    feed(json.loads(line))
                except ValueError:
                    continue
    except ValueError:
        # 整文件不是合法 JSON：按 JSONL 逐行尝试
        for line in raw.splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                feed(json.loads(line))
            except ValueError:
                continue

    seen_files, seen_tools = set(), set()
    files = [f for f in files if not (f in seen_files or seen_files.add(f))]
    tools = [t for t in tools if not (t in seen_tools or seen_tools.add(t))]
    return session_id, files, tools


def cmd_append(args):
    root = os.path.abspath(args.dir or ".")
    line = "- %s %s" % (_today(), args.append)
    if args.verify:
        line += " | 验证: %s" % args.verify
    path = _append_entry(root, line)
    print("已追加到 %s" % os.path.relpath(path, root).replace("\\", "/"))
    print("  " + line)
    return 0


def cmd_transcript(args):
    root = os.path.abspath(args.dir or ".")
    session_id, files, tools = _extract_from_transcript(args.transcript)
    if not files and not tools:
        print("handoff-log: transcript 无可提取的文件/工具记录（或解析失败），不追加", file=sys.stderr)
        return 0
    line = "- %s 会话 %s 动过文件: %s（工具: %s）——结论与验证待补" % (
        _today(), session_id or "?", ", ".join(files) or "（无）", ", ".join(tools) or "（无）")
    path = _append_entry(root, line)
    print("已追加到 %s" % os.path.relpath(path, root).replace("\\", "/"))
    print("  " + line)
    return 0


def main():
    ap = argparse.ArgumentParser(description="HANDOFF.md 变更日志追加（纯标准库）")
    ap.add_argument("--append", default=None, metavar="做了什么", help="追加一条变更日志")
    ap.add_argument("--verify", default=None, metavar="验证结果", help="与 --append 搭配的验证结果")
    ap.add_argument("--from-transcript", dest="transcript", default=None, metavar="transcript.json",
                    help="从 Claude Code transcript 提取文件/工具记录并追加")
    ap.add_argument("--dir", default=None, help="项目根目录（默认当前目录）")
    args = ap.parse_args()

    if args.append is not None and args.transcript is not None:
        print("错误: --append 与 --from-transcript 只能二选一", file=sys.stderr)
        return 1
    if args.append is not None:
        return cmd_append(args)
    if args.transcript is not None:
        return cmd_transcript(args)
    print("错误: 需要 --append 或 --from-transcript", file=sys.stderr)
    return 1


if __name__ == "__main__":
    sys.exit(main())
