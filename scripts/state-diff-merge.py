#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
state-diff-merge.py — M3 状态对象自动 diff / 冲突合并（v4.6.0 阶段二，纯标准库）

把跨边状态对象（五字段 + gate_levels + gate_results + checkpoint）当可比对/可合并的数据对象：
- --diff <A> <B>：对比两版 checkpoint → 字段级差异清单（只读分析，零副作用）
- --merge <A> <B> --out <M>：多分支同时续跑成果合并 → completed_levels 并集 + gate_results 按 L 级取
  「较新且 done」+ 语义性五字段分歧 / 时间无法定新旧 → 冲突升人判（exit 1，不产出被静默覆盖的统一状态）

与 v4.5 M3 的关系：v4.5 = 状态可落盘 + 可续跑（checkpoint 应用层断点）；v4.6 = 状态可 diff + 可合并
（状态显式化延伸，把 checkpoint 当可比对/可合并的数据对象）。不引外部状态框架、不重写五组件。

用法：
    PYTHONUTF8=1 python scripts/state-diff-merge.py --diff <A.json> <B.json> [--json]
    PYTHONUTF8=1 python scripts/state-diff-merge.py --merge <A.json> <B.json> --out <M.json> [--ts "YYYY-MM-DD HH:MM"] [--json]
    PYTHONUTF8=1 python scripts/state-diff-merge.py --merge <A.json> <B.json> --out <M.json> --override synth=B
        # 人判后重跑：指定某字段/级取 A 或 B 分支（--override <level_or_field>=A|B，可多次）

退出码：0=正常（diff 完成，或 merge 无冲突已写出）；1=merge 发现冲突（needs_human，不写 --out）；2=参数/文件错误。
纯只读/纯函数工具：diff 不写任何文件；merge 只写 --out（不覆盖输入）；回滚 = 删除输出文件。
"""
import argparse
import json
import os
import sys

# 三通道统一 UTF-8（Windows 控制台不乱码）
for _stream_name in ("stdout", "stdin", "stderr"):
    _s = getattr(sys, _stream_name, None)
    if _s is not None and hasattr(_s, "reconfigure"):
        try:
            _s.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass

LEVELS = ("L1", "L2", "L3", "L4", "synth", "signoff")
SEMANTIC_FIELDS = ("goal", "completion", "verify")  # 语义性五字段（分歧 → 冲突升人判）
LIST_FIELDS = ("open", "next")                       # 列表字段（并集去重）


def _load(path):
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def _get_created(state):
    return str((state.get("checkpoint") or {}).get("created_at") or "")


def _level_order(level):
    return LEVELS.index(level) if level in LEVELS else 100


def _union_ordered(seq):
    seen, out = set(), []
    for x in seq:
        if x not in seen:
            seen.add(x)
            out.append(x)
    return out


def _newer_branch(a, b, level):
    """按「较新且 done」判定：优先该级 result 内时间戳，其次整体 checkpoint.created_at。
    返回 'A' / 'B'；无法定新旧返回 None（→ 冲突）。"""
    for state in (a, b):
        res = ((state.get("gate_results") or {}).get(level) or {}).get("result")
        if isinstance(res, dict):
            for k in ("ts", "timestamp", "created_at", "updated_at"):
                if isinstance(res.get(k), str) and res[k].strip():
                    # 该分支有级内时间戳 → 直接比较级内时间戳
                    ta = ((a.get("gate_results") or {}).get(level) or {}).get("result", {}).get(k)
                    tb = ((b.get("gate_results") or {}).get(level) or {}).get("result", {}).get(k)
                    if isinstance(ta, str) and isinstance(tb, str) and ta and tb:
                        if ta == tb:
                            return None
                        return "A" if ta > tb else "B"
    ca, cb = _get_created(a), _get_created(b)
    if ca and cb and ca != cb:
        return "A" if ca > cb else "B"
    return None


def diff(a, b, name_a="A", name_b="B"):
    """对比两版状态对象 → 字段级差异清单（只读，零副作用）。"""
    cl_a = list((a.get("checkpoint") or {}).get("completed_levels") or [])
    cl_b = list((b.get("checkpoint") or {}).get("completed_levels") or [])
    ga = (a.get("gate_results") or {})
    gb = (b.get("gate_results") or {})
    levels = _union_ordered(list(ga.keys()) + list(gb.keys()))

    gr_rows = []
    for lv in sorted(levels, key=_level_order):
        in_a, in_b = lv in ga, lv in gb
        if in_a and in_b:
            ra, rb = ga[lv], gb[lv]
            same_status = ra.get("status") == rb.get("status")
            same_result = ra.get("result") == rb.get("result")
            gr_rows.append({"level": lv, "in": "both",
                            "status_A": ra.get("status"), "status_B": rb.get("status"),
                            "result_same": same_result,
                            "verdict": "一致" if (same_status and same_result) else "分歧"})
        else:
            gr_rows.append({"level": lv, "in": "A" if in_a else "B",
                            "status": ga.get(lv, gb.get(lv)).get("status")})

    five = {}
    for f in SEMANTIC_FIELDS + LIST_FIELDS:
        va, vb = a.get(f), b.get(f)
        if isinstance(va, list) or isinstance(vb, list):
            five[f] = {"same": va == vb, "only_A": [x for x in (va or []) if x not in (vb or [])],
                       "only_B": [x for x in (vb or []) if x not in (va or [])]}
        else:
            five[f] = {"same": va == vb}

    return {
        "branch": {"A": name_a, "B": name_b},
        "completed_levels": {
            "only_A": [l for l in cl_a if l not in cl_b],
            "only_B": [l for l in cl_b if l not in cl_a],
            "both": [l for l in cl_a if l in cl_b],
            "union": _union_ordered(cl_a + cl_b),
        },
        "gate_results": gr_rows,
        "five_field": five,
        "checkpoint": {
            "created_at_A": _get_created(a), "created_at_B": _get_created(b),
            "resumed_from_A": (a.get("checkpoint") or {}).get("resumed_from"),
            "resumed_from_B": (b.get("checkpoint") or {}).get("resumed_from"),
        },
    }


def merge(a, b, ts=None, overrides=None, name_a="A", name_b="B"):
    """合并两分支状态对象 → 统一状态 + 冲突清单。
    规则：completed_levels 并集；gate_results/gate_levels 按 L 级取「较新且 done」；
    语义性五字段（goal/completion/verify）分歧 → 冲突；open/next 并集去重；冲突 → needs_human。
    overrides: {字段/级: 'A'|'B'} 人判后指定取哪分支（不产生冲突）。"""
    overrides = overrides or {}
    conflicts = []
    # ---- gate_results 逐级 ----
    ga, gb = (a.get("gate_results") or {}), (b.get("gate_results") or {})
    all_lv = _union_ordered(list(ga.keys()) + list(gb.keys()))
    merged_gr = {}
    pick_note = {}
    for lv in sorted(all_lv, key=_level_order):
        in_a, in_b = lv in ga, lv in gb
        if overrides.get(lv) == "A":
            merged_gr[lv] = ga[lv]; pick_note[lv] = "A(override)"; continue
        if overrides.get(lv) == "B":
            merged_gr[lv] = gb[lv]; pick_note[lv] = "B(override)"; continue
        if in_a and not in_b:
            merged_gr[lv] = ga[lv]; pick_note[lv] = "A"; continue
        if in_b and not in_a:
            merged_gr[lv] = gb[lv]; pick_note[lv] = "B"; continue
        # 都有
        ra, rb = ga[lv], gb[lv]
        da, db = ra.get("status") == "done", rb.get("status") == "done"
        if da and db:
            if ra.get("result") == rb.get("result"):
                merged_gr[lv] = ra; pick_note[lv] = "A(identical)"
            else:
                newer = _newer_branch(a, b, lv)
                if newer == "A":
                    merged_gr[lv] = ra; pick_note[lv] = "A(newer)"
                elif newer == "B":
                    merged_gr[lv] = rb; pick_note[lv] = "B(newer)"
                else:
                    conflicts.append({"where": f"gate_results.{lv}", "reason": "两分支均 done 且结果不同、无法定新旧",
                                      "A": str(ra.get("result"))[:120], "B": str(rb.get("result"))[:120]})
                    merged_gr[lv] = ra  # 冲突时占位取 A（但整体 needs_human，不写输出）
                    pick_note[lv] = "conflict(needs_human)"
        elif da:
            merged_gr[lv] = ra; pick_note[lv] = "A(done)"
        elif db:
            merged_gr[lv] = rb; pick_note[lv] = "B(done)"
        else:
            merged_gr[lv] = ra; pick_note[lv] = "A(pending)"
    # ---- 语义性五字段：仅当分支完成 synth（产出最终交接文档）才是权威结论 ----
    # 规则（不静默覆盖语义结论）：两分支都完成 synth 且结论不同 → 冲突升人判；恰一分支完成 synth →
    # 取该分支（另一分支携带的是 base 占位五字段，非语义结论）；都未完成 synth → 相同则保留、不同则冲突。
    synth_done = {
        "A": (ga.get("synth") or {}).get("status") == "done",
        "B": (gb.get("synth") or {}).get("status") == "done",
    }
    five_source = {}
    for f in SEMANTIC_FIELDS:
        va, vb = a.get(f), b.get(f)
        if overrides.get(f) == "A" or overrides.get(f) == "B":
            five_source[f] = overrides[f] + "(override)"
        elif va == vb:
            five_source[f] = "A(identical)"
        elif synth_done["A"] and not synth_done["B"]:
            five_source[f] = "A(synth-authoritative)"
        elif synth_done["B"] and not synth_done["A"]:
            five_source[f] = "B(synth-authoritative)"
        else:
            conflicts.append({"where": f"five_field.{f}", "reason": "两分支语义性结论不同，不静默覆盖",
                              "A": str(va)[:120], "B": str(vb)[:120]})
            five_source[f] = "conflict(needs_human)"
    # ---- open/next 并集去重 ----
    merged_open = _union_ordered(list(a.get("open") or []) + list(b.get("open") or []))
    merged_next = _union_ordered(list(a.get("next") or []) + list(b.get("next") or []))
    # ---- gate_levels：同键随对应 result 走 ----
    gla, glb = (a.get("gate_levels") or {}), (b.get("gate_levels") or {})
    merged_gl = {}
    for k in _union_ordered(list(gla.keys()) + list(glb.keys())):
        if overrides.get(k) == "A":
            merged_gl[k] = gla[k]; continue
        if overrides.get(k) == "B":
            merged_gl[k] = glb[k]; continue
        in_a, in_b = k in gla, k in glb
        if in_a and in_b:
            merged_gl[k] = gla[k] if gla[k] == glb[k] else (gla[k] if _newer_branch(a, b, k) == "A" else glb[k])
        elif in_a:
            merged_gl[k] = gla[k]
        else:
            merged_gl[k] = glb[k]
    # ---- checkpoint ----
    cl_a = list((a.get("checkpoint") or {}).get("completed_levels") or [])
    cl_b = list((b.get("checkpoint") or {}).get("completed_levels") or [])
    cl_union = _union_ordered(cl_a + cl_b)
    ca, cb = _get_created(a), _get_created(b)
    created = ts or (ca if ca >= cb else cb) or "runtime"
    resumed = " | ".join(sorted({x for x in [
        (a.get("checkpoint") or {}).get("resumed_from"),
        (b.get("checkpoint") or {}).get("resumed_from"),
    ] if x}))
    merged = {
        "meta": a.get("meta") or b.get("meta"),
        "goal": a.get("goal"), "completion": a.get("completion"), "verify": a.get("verify"),
        "open": merged_open, "next": merged_next,
        "gate_levels": merged_gl,
        "gate_results": merged_gr,
        "checkpoint": {
            "created_at": created,
            "resumed_from": resumed or None,
            "completed_levels": cl_union,
            "pending": merged_open,
        },
        "merge_meta": {
            "method": "v46-state-merge",
            "branches": {"A": name_a, "B": name_b},
            "completed_levels_rule": "union",
            "gate_results_rule": "per-level newer-and-done; conflict → needs_human",
            "five_field_rule": "synth-authoritative wins; both-synth-differ → conflict (no silent overwrite); open/next union",
            "pick": pick_note, "five_field_source": five_source,
        },
    }
    return merged, conflicts


def _dump(obj, as_json):
    if as_json:
        print(json.dumps(obj, ensure_ascii=False, indent=2))
    else:
        print(json.dumps(obj, ensure_ascii=False, indent=2))


def main():
    ap = argparse.ArgumentParser(description="M3 状态对象自动 diff / 冲突合并（纯标准库只读/纯函数）")
    ap.add_argument("--diff", nargs=2, metavar=("A", "B"), default=None, help="对比两版状态对象 → 字段级差异清单")
    ap.add_argument("--merge", nargs=2, metavar=("A", "B"), default=None, help="合并两分支状态对象 → --out 统一状态")
    ap.add_argument("--out", default=None, help="merge 输出路径（不覆盖输入）")
    ap.add_argument("--ts", default=None, help="合并时间戳（YYYY-MM-DD HH:MM），覆盖 created_at")
    ap.add_argument("--override", action="append", default=[], metavar="FIELD=A|B",
                    help="人判后指定某字段/级取 A 或 B 分支（可多次）")
    ap.add_argument("--json", action="store_true", help="输出 JSON")
    args = ap.parse_args()

    mode = (args.diff is not None) + (args.merge is not None)
    if mode != 1:
        print("必须且只能指定一种模式（--diff <A> <B> / --merge <A> <B> --out <M>）", file=sys.stderr)
        return 2
    if args.merge and not args.out:
        print("--merge 必须指定 --out", file=sys.stderr)
        return 2

    overrides = {}
    for o in args.override:
        if "=" not in o or o.rsplit("=", 1)[1] not in ("A", "B"):
            print("--override 格式须为 FIELD=A|B", file=sys.stderr)
            return 2
        overrides[o.rsplit("=", 1)[0]] = o.rsplit("=", 1)[1]

    paths = args.diff or args.merge
    try:
        a = _load(paths[0]); b = _load(paths[1])
    except (OSError, ValueError) as e:
        print(f"状态对象不可解析: {e}", file=sys.stderr)
        return 2

    if args.diff:
        r = diff(a, b, os.path.basename(paths[0]), os.path.basename(paths[1]))
        print(json.dumps(r, ensure_ascii=False, indent=2))
        return 0

    merged, conflicts = merge(a, b, ts=args.ts, overrides=overrides,
                              name_a=os.path.basename(paths[0]), name_b=os.path.basename(paths[1]))
    if conflicts:
        merged["status"] = "needs_human"
        merged["conflicts"] = conflicts
        print(json.dumps(merged, ensure_ascii=False, indent=2))
        print("merge 冲突 %d 处：语义性结论或时间无法定新旧 → 升人判（未写 --out，不静默覆盖）。"
              "人在环选定后可用 --override FIELD=A|B 重跑。" % len(conflicts), file=sys.stderr)
        return 1
    merged["status"] = "merged"
    with open(args.out, "w", encoding="utf-8") as f:
        json.dump(merged, f, ensure_ascii=False, indent=2)
    print(json.dumps({"status": "merged", "out": args.out, "completed_levels": merged["checkpoint"]["completed_levels"],
                      "gate_results_pick": merged["merge_meta"]["pick"]}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
