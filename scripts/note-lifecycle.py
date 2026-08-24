#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
note-lifecycle.py — Agent Notes 四态生命周期管理（方向①：决策交接报告机制化）。

移植 DSH `.agents/notes` 机制为纯标准库脚本：记录「为什么这么做、放弃了什么」，
proposed → implemented / rejected / archived 四态 + 分类门禁 + 归档冻结。

目录树（路径编码两个维度：生命周期 + 类别）：

    notes/
      proposed/{class}/yyyy-mm-dd-slug.md    提案（实施前评审）
      implemented/{class}/yyyy-mm-dd-slug.md 决策已交付（与代码保持同步）
      rejected/{class}/yyyy-mm-dd-slug.md    否决（仅当依据仍能防错时保留）
      archived/{class}/yyyy-mm-dd-slug.md    已归档（永久冻结，hash 校验）
      README.md              目录规则（new 自动从模板生成）
      .archive-manifest.json 归档冻结清单（sha256）

分类（封闭集合，门禁拒绝其它值）：
    feature / bug-fix / simplification / architecture / process / testing

文件内格式（verify 机械检查）：
    头部三行严格为 `# Agent Note: <title>` / 空行 / `Status: <status>`。
    Status 与目录交叉校验；proposed/implemented 骨架章节；`## Alternatives considered` 必需
    （迁移前文件可用注释 `<!-- note-format: alternatives-not-recorded -->` 豁免）。

命令：
    new    --class <class> --title <标题> [--status proposed|implemented] [--root <根>]
    status <文件相对路径> --implemented | --rejected <原因> | --archived [--root <根>]
    verify [--root <根>] [--json]

退出码：0=OK/PASS；1=参数错或门禁 NOT-OK。
纯标准库；UTF-8 三通道；Windows 控制台无需 PYTHONIOENCODING。
"""
import argparse
import datetime
import hashlib
import json
import os
import re
import shutil
import sys

# 三通道统一 UTF-8（与 audit/record-error 一致）
for _stream_name in ("stdout", "stdin", "stderr"):
    _s = getattr(sys, _stream_name, None)
    if _s is not None and hasattr(_s, "reconfigure"):
        try:
            _s.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass

# 自身运行不写 __pycache__（verify-integrity 泄漏检测面）
sys.dont_write_bytecode = True

CLASSES = ("feature", "bug-fix", "simplification", "architecture", "process", "testing")
LIFECYCLES = ("proposed", "implemented", "rejected", "archived")
MANIFEST_NAME = ".archive-manifest.json"
ALT_ESCAPE = "<!-- note-format: alternatives-not-recorded -->"
SLOP_HEADINGS_IMPLEMENTED = ("## Proposal", "## Acceptance criteria", "## Plan", "## Migration plan")
REQUIRED_SECTIONS = {
    "proposed": ("## Problem", "## Proposal", "## Alternatives considered", "## Acceptance criteria", "## Risks"),
    "implemented": ("## Problem", "## Decision", "## Alternatives considered", "## Consequences"),
    "rejected": ("## Problem", "## Proposal", "## Alternatives considered"),
    "archived": ("## Problem", "## Decision", "## Alternatives considered", "## Consequences"),
}

PROPOSED_TEMPLATE = """# Agent Note: {title}

Status: proposed

## Problem

{{问题与动机，不依赖解决方案即可独立成文}}

## Proposal

{{拟议变更；可含计划、迁移步骤、未决问题}}

## Alternatives considered

- **{{替代方案 A}}**：{{为什么没选}}

## Acceptance criteria

- [ ] {{什么可观察状态意味着完成}}

## Risks

- {{可能出错的事项与该变更有意放弃的东西}}
"""

IMPLEMENTED_TEMPLATE = """# Agent Note: {title}

Status: implemented

## Problem

{{问题与动机}}

## Decision

{{现在时态描述已交付的现实}}

## Alternatives considered

- **{{替代方案 A}}**：{{为什么没选}}

## Consequences

{{权衡的代价与收益}}
"""

NOTES_README = """# notes/ —— Agent Notes 决策记录（四态生命周期）

> 由 harness-engineering `bootstrap.py --init` 生成，`scripts/note-lifecycle.py` 管理。
> 记录影响本项目的决策与提案：代码和文档承载不了的「为什么」与「放弃了什么」。

## 布局与命名

路径编码两个维度：`{lifecycle}/{class}/yyyy-mm-dd-slug.md`。

- **生命周期**（顶层文件夹）= 状态，随状态变化移动文件：
  - `proposed/`：实施前评审的提案（尚未构建）。
  - `implemented/`：决策已交付，与实际交付内容保持同步。
  - `rejected/`：否决的提案（仅当依据仍能防错时保留）。
  - `archived/`：已归档，永久冻结（`.archive-manifest.json` 记录 sha256，篡改即 NOT-OK）。
- **类别**（嵌套文件夹）= 决策种类，封闭集合：
  `feature` / `bug-fix` / `simplification` / `architecture` / `process` / `testing`。
- 文件名日期 = 主题首次提出时间；slug 由标题生成。

## 文件格式

头部三行严格为 `# Agent Note: <title>` / 空行 / `Status: <status>`，Status 与目录交叉校验。
- `proposed/`：`## Problem` → `## Proposal` → `## Alternatives considered` → `## Acceptance criteria` → `## Risks`
- `implemented/`：`## Problem` → `## Decision` → `## Alternatives considered` → `## Consequences`
- `rejected/`：保留提案骨架，结论写在 `Status: rejected — <原因>` 行上
- `archived/`：implemented 骨架 + `Archived: YYYY-MM-DD` 行，永久冻结

`## Alternatives considered` 必需（记录决策不记录它击败了什么，就是邀请反复争论）。
迁移前文件可用注释 `<!-- note-format: alternatives-not-recorded -->` 豁免。

## 常用命令

    python scripts/note-lifecycle.py new --class architecture --title "..."           # 新建提案
    python scripts/note-lifecycle.py status notes/proposed/xxx.md --implemented       # 提案→已实现
    python scripts/note-lifecycle.py status notes/proposed/xxx.md --rejected "原因"   # 提案→否决
    python scripts/note-lifecycle.py status notes/implemented/xxx.md --archived       # 已实现→归档
    python scripts/note-lifecycle.py verify                                            # 门禁检查

## 规则

- 每个非平凡变更必须在同一变更中新增或更新至少一份 Agent Note。
- 绝不归档 proposed：过时提案转为 rejected。
- 归档后永久冻结：禁止编辑/移动/删除（verify 用 hash 强制）。
- 历史版本 plans/（冻结版本目录）不迁移、零复制，本目录为新增机制起点。
"""


HERE = os.path.dirname(os.path.abspath(__file__))
PKG = os.path.abspath(os.path.join(HERE, ".."))
TEMPLATES = os.path.join(PKG, "templates")


def _notes_readme_text():
    """README 单一事实源：优先读 templates/notes-README.md，回退内置常量。"""
    tpl = os.path.join(TEMPLATES, "notes-README.md")
    try:
        with open(tpl, "r", encoding="utf-8-sig") as fh:
            return fh.read()
    except OSError:
        return NOTES_README


def _now():
    return datetime.date.today().isoformat()


def _slugify(title):
    """标题 → ASCII kebab-case slug（保留字母数字，其余转 '-'）。"""
    s = title.strip().lower()
    s = re.sub(r"[^a-z0-9]+", "-", s)
    s = s.strip("-")
    return s[:48].rstrip("-") or "note"


def _root_dir(arg_root):
    return os.path.abspath(arg_root or ".")


def _notes_dir(root):
    return os.path.join(root, "notes")


def _read(path):
    try:
        with open(path, "r", encoding="utf-8-sig") as fh:
            return fh.read()
    except OSError:
        return None


def _write(path, text):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(text)


def parse_header(text):
    """解析头部块：返回 (title, status, archived_date, ok)。

    ok=False 表示格式不符合三行规则（不阻断读取，verify 会报）。
    """
    if not text:
        return None, None, None, False
    lines = text.splitlines()
    if not lines or not lines[0].startswith("# Agent Note: "):
        return None, None, None, False
    title = lines[0][len("# Agent Note: "):].strip()
    status = None
    archived = None
    for ln in lines[1:6]:
        if ln.startswith("Status:"):
            status = ln[len("Status:"):].strip()
            break
    for ln in lines[1:6]:
        m = re.match(r"^Archived:\s*(\S+)", ln)
        if m:
            archived = m.group(1)
            break
    return title, status, archived, True


def _lifecycle_of(path, notes_root):
    """从路径取生命周期与类别：(lifecycle, class) 或 (None, None)。"""
    rel = os.path.relpath(path, notes_root).replace("\\", "/")
    parts = rel.split("/")
    if len(parts) >= 3 and parts[0] in LIFECYCLES and parts[1] in CLASSES:
        return parts[0], parts[1]
    return None, None


# ---------- new ----------
def cmd_new(args):
    root = _root_dir(args.root)
    if args.cls not in CLASSES:
        print("错误: --class 必须是 %s 之一" % "/".join(CLASSES), file=sys.stderr)
        return 1
    if args.status not in ("proposed", "implemented"):
        print("错误: --status 只支持 proposed|implemented", file=sys.stderr)
        return 1
    notes = _notes_dir(root)
    if not os.path.isfile(os.path.join(notes, "README.md")):
        _write(os.path.join(notes, "README.md"), _notes_readme_text())
        print("notes/README.md 已生成（首次使用）")
    if not os.path.isfile(os.path.join(notes, MANIFEST_NAME)):
        _write(os.path.join(notes, MANIFEST_NAME),
               json.dumps({"schema_version": 1, "created_at": _now(), "archived": {}},
                          ensure_ascii=False, indent=2))
    rel = os.path.join(args.status, args.cls, "%s-%s.md" % (_now(), _slugify(args.title)))
    path = os.path.join(notes, rel)
    if os.path.exists(path):
        print("错误: 已存在 %s（改标题或先处理该文件）" % rel, file=sys.stderr)
        return 1
    template = PROPOSED_TEMPLATE if args.status == "proposed" else IMPLEMENTED_TEMPLATE
    _write(path, template.format(title=args.title))
    print("新建 %s  (%s)" % (os.path.relpath(path, root).replace("\\", "/"), args.status))
    return 0


# ---------- status ----------
def _rewrite_header(text, new_status=None, archived=None):
    """替换 Status 行；archived 给定时间则在 Status 行后插入 Archived 行。返回新文本。"""
    lines = text.splitlines()
    out = []
    inserted_archived = False
    for i, ln in enumerate(lines):
        if ln.startswith("Status:") and new_status is not None:
            out.append("Status: " + new_status)
            if archived and not inserted_archived:
                out.append("Archived: %s" % archived)
                inserted_archived = True
            continue
        if i <= 5 and ln.startswith("Archived:") and archived is None:
            continue  # 非归档移动时去掉旧 Archived 行（防御）
        out.append(ln)
    # 若 Status 行不存在但给了新状态，补在头部区
    if new_status is not None and not any(l.startswith("Status:") for l in out[:6]):
        out.insert(2, "Status: " + new_status)
        if archived:
            out.insert(3, "Archived: %s" % archived)
    return "\n".join(out) + ("\n" if text.endswith("\n") else "")


def _rename_sections(text):
    """proposed → implemented 的机械骨架改写：Proposal→Decision，Acceptance criteria→Verification，Risks→Consequences。"""
    text = text.replace("## Proposal", "## Decision", 1)
    text = text.replace("## Acceptance criteria", "## Verification", 1)
    text = text.replace("## Risks", "## Consequences", 1)
    return text


def cmd_status(args):
    root = _root_dir(args.root)
    notes = _notes_dir(root)
    path = os.path.abspath(os.path.join(root, args.file))
    if not os.path.isfile(path):
        print("错误: 文件不存在 %s" % args.file, file=sys.stderr)
        return 1
    lifecycle, cls = _lifecycle_of(path, notes)
    if lifecycle is None:
        print("错误: 文件不在 notes/{proposed|implemented|rejected|archived}/{class}/ 下", file=sys.stderr)
        return 1
    text = _read(path) or ""
    title, status, _archived, ok = parse_header(text)
    if not ok:
        print("错误: 头部格式不符合 `# Agent Note: <title>` / 空行 / `Status: <status>`", file=sys.stderr)
        return 1
    flags = [f for f in ("implemented", "rejected", "archived") if getattr(args, f)]
    if len(flags) != 1:
        print("错误: 必须且只能指定 --implemented / --rejected <原因> / --archived 之一", file=sys.stderr)
        return 1
    target = flags[0]

    # 状态机校验
    if lifecycle == "proposed" and target in ("implemented", "rejected"):
        pass
    elif lifecycle == "implemented" and target == "archived":
        if status != "implemented":
            print("错误: 只有 implemented 状态的 note 才能归档（当前 Status: %s）" % status, file=sys.stderr)
            return 1
    else:
        print("错误: 不支持的状态迁移 %s → %s（允许: proposed→implemented/rejected, implemented→archived）"
              % (lifecycle, target), file=sys.stderr)
        return 1

    if target == "implemented":
        new_text = _rename_sections(_rewrite_header(text, new_status="implemented"))
    elif target == "rejected":
        if not args.rejected:
            print("错误: --rejected 需要原因参数", file=sys.stderr)
            return 1
        new_text = _rewrite_header(text, new_status="rejected — %s" % args.rejected)
    else:  # archived
        new_text = _rewrite_header(text, new_status="implemented", archived=_now())

    dest_dir = os.path.join(notes, target, cls)
    os.makedirs(dest_dir, exist_ok=True)
    dest = os.path.join(dest_dir, os.path.basename(path))
    if os.path.abspath(dest) != os.path.abspath(path) and os.path.exists(dest):
        print("错误: 目标已存在 %s" % os.path.relpath(dest, root).replace("\\", "/"), file=sys.stderr)
        return 1
    _write(path, new_text)  # 先改内容再移动，保证任何时刻文件与状态自洽
    if os.path.abspath(dest) != os.path.abspath(path):
        shutil.move(path, dest)
    print("状态迁移 %s → %s: %s" % (
        lifecycle, target, os.path.relpath(dest, root).replace("\\", "/")))

    if target == "archived":
        manifest_path = os.path.join(notes, MANIFEST_NAME)
        manifest = json.loads(_read(manifest_path) or "{}")
        manifest.setdefault("archived", {})[os.path.relpath(dest, notes).replace("\\", "/")] = {
            "sha256": hashlib.sha256(open(dest, "rb").read()).hexdigest(),
            "archived_at": datetime.datetime.now().isoformat(timespec="seconds"),
        }
        _write(manifest_path, json.dumps(manifest, ensure_ascii=False, indent=2))
        print("归档清单已更新: %s" % MANIFEST_NAME)
    return 0


# ---------- verify ----------
def _check_note(path, notes):
    rel = os.path.relpath(path, notes).replace("\\", "/")
    lifecycle, cls = _lifecycle_of(path, notes)
    results = []
    if lifecycle is None:
        results.append((rel, "NOT-OK", "路径不在合法 生命周期/类别 结构下"))
        return results
    text = _read(path) or ""
    title, status, archived, ok = parse_header(text)
    if not ok:
        results.append((rel, "NOT-OK", "头部格式不符合规则"))
        return results
    # 状态-目录交叉校验
    expect_status = lifecycle
    if lifecycle == "rejected":
        if not (status or "").startswith("rejected"):
            results.append((rel, "NOT-OK", "Status 应为 rejected — <原因>，实际: %s" % status))
    elif lifecycle == "archived":
        if status != "implemented":
            results.append((rel, "NOT-OK", "归档 note 的 Status 应为 implemented，实际: %s" % status))
        if not archived:
            results.append((rel, "NOT-OK", "归档 note 缺少 `Archived: YYYY-MM-DD` 行"))
    elif status != lifecycle:
        results.append((rel, "NOT-OK", "Status=%s 与目录 %s/ 不一致" % (status, lifecycle)))
    # 必需章节
    alt_escaped = ALT_ESCAPE in text
    for sec in REQUIRED_SECTIONS.get(lifecycle, ()):
        if sec == "## Alternatives considered" and alt_escaped:
            continue
        if sec not in text:
            results.append((rel, "NOT-OK", "缺少必需章节 %s" % sec))
    # implemented 禁用的 slop 标题
    if lifecycle in ("implemented", "archived"):
        for bad in SLOP_HEADINGS_IMPLEMENTED:
            if bad in text:
                results.append((rel, "NOT-OK", "implemented 骨架禁止 %s（应改为 Decision/Verification/Consequences）" % bad))
    # 归档冻结
    if lifecycle == "archived":
        manifest = json.loads(_read(os.path.join(notes, MANIFEST_NAME)) or "{}")
        entry = manifest.get("archived", {}).get(rel)
        cur = hashlib.sha256(open(path, "rb").read()).hexdigest()
        if entry is None:
            results.append((rel, "NOT-OK", "归档文件不在 .archive-manifest.json 中（冻结清单缺失）"))
        elif entry.get("sha256") != cur:
            results.append((rel, "NOT-OK", "归档文件被篡改（hash 与冻结清单不一致）"))
        else:
            results.append((rel, "PASS", "归档冻结 hash 一致"))
    # 健康 note：显式 PASS（避免"无输出=没检查"的误解）
    if not any(r[1] == "NOT-OK" for r in results):
        results.append((rel, "PASS", "状态/分类/章节/冻结 全部一致"))
    return results


def cmd_verify(args):
    root = _root_dir(args.root)
    notes = _notes_dir(root)
    if not os.path.isdir(notes):
        print("verify: %s 不存在（尚未初始化 notes/，跑 --init 或 note-lifecycle.py new）" % notes, file=sys.stderr)
        return 1
    results = []
    if not os.path.isfile(os.path.join(notes, "README.md")):
        results.append(("notes/README.md", "NOT-OK", "缺失（用 note-lifecycle.py new 生成）"))
    else:
        results.append(("notes/README.md", "PASS", "存在"))
    if not os.path.isfile(os.path.join(notes, MANIFEST_NAME)):
        results.append((".archive-manifest.json", "NOT-OK", "缺失（用 note-lifecycle.py new 生成）"))
    else:
        results.append((".archive-manifest.json", "PASS", "存在"))

    note_files = []
    for lifecycle in LIFECYCLES:
        lc_dir = os.path.join(notes, lifecycle)
        if not os.path.isdir(lc_dir):
            continue
        for cls in sorted(os.listdir(lc_dir)):
            cls_dir = os.path.join(lc_dir, cls)
            if not os.path.isdir(cls_dir):
                continue
            for fn in sorted(os.listdir(cls_dir)):
                if fn.endswith(".md"):
                    note_files.append(os.path.join(cls_dir, fn))
    for p in note_files:
        results += _check_note(p, notes)

    # 归档清单反向校验：清单条目对应的文件必须存在
    manifest = json.loads(_read(os.path.join(notes, MANIFEST_NAME)) or "{}")
    for rel in manifest.get("archived", {}):
        if not os.path.isfile(os.path.join(notes, rel)):
            results.append(("归档清单条目 " + rel, "NOT-OK", "对应文件缺失"))

    not_ok = [r for r in results if r[1] == "NOT-OK"]
    n_pass = sum(1 for r in results if r[1] == "PASS")
    summary = {"notes": len(note_files), "pass": n_pass, "not_ok": len(not_ok)}
    if args.json:
        print(json.dumps({
            "tool": "note-lifecycle-verify",
            "root": root,
            "results": [{"check": c, "status": s, "detail": d} for (c, s, d) in results],
            "summary": summary,
            "exit": 1 if not_ok else 0,
        }, ensure_ascii=False, indent=2))
    else:
        for c, s, d in results:
            print("[%s] %s  —  %s" % (s, c, d))
        print()
        print("SUMMARY: notes=%d | %d PASS / %d NOT-OK  → exit %s" % (
            len(note_files), n_pass, len(not_ok), 1 if not_ok else 0))
    return 1 if not_ok else 0


def main():
    ap = argparse.ArgumentParser(description="Agent Notes 四态生命周期管理（纯标准库）")
    sub = ap.add_subparsers(dest="cmd", required=True)

    p_new = sub.add_parser("new", help="新建 Agent Note（默认 proposed）")
    p_new.add_argument("--class", dest="cls", required=True, help="类别: %s" % "/".join(CLASSES))
    p_new.add_argument("--title", required=True, help="标题（生成 slug 与文件名）")
    p_new.add_argument("--status", default="proposed", choices=["proposed", "implemented"])
    p_new.add_argument("--root", default=None, help="项目根目录（默认当前目录）")

    p_st = sub.add_parser("status", help="状态迁移（移动文件 + 更新 Status 行）")
    p_st.add_argument("file", help="note 相对路径，如 notes/proposed/architecture/2026-08-17-x.md")
    p_st.add_argument("--implemented", action="store_true", help="proposed → implemented（机械改写骨架）")
    p_st.add_argument("--rejected", default=None, metavar="原因", help="proposed → rejected（Status 写原因）")
    p_st.add_argument("--archived", action="store_true", help="implemented → archived（冻结 + 记 hash）")
    p_st.add_argument("--root", default=None)

    p_v = sub.add_parser("verify", help="门禁：状态-目录一致性/分类白名单/必需章节/归档冻结")
    p_v.add_argument("--root", default=None)
    p_v.add_argument("--json", action="store_true")

    args = ap.parse_args()
    if args.cmd == "new":
        return cmd_new(args)
    if args.cmd == "status":
        return cmd_status(args)
    return cmd_verify(args)


if __name__ == "__main__":
    sys.exit(main())
