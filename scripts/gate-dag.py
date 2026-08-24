#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
gate-dag.py — 门禁四级 DAG（Graph 路径 B，v4.4.0，纯标准库）

把 self-testing.md 的「验证手段四级门禁」从按情境选级表格重释为可执行 DAG：
节点 L1(自检) → L2(会话级 goal) → L3(确定性 gate/Stop hook) → L4(独立上下文评审)；
边 = 可判定升级条件（check 失败 / 高价值 / 不可逆 / 无人值守 / 返工超预算 / gate 不过）。

用法：
    python scripts/gate-dag.py --check                       # 无标志任务 → 应走级别（默认全 False）
    python scripts/gate-dag.py --check --check-fail --high-value
    python scripts/gate-dag.py --check --irreversible
    python scripts/gate-dag.py --audit <trajectory.json>     # 枚举实际升级路径 + 双向检测（漏边 exit 1 / 升过头只报不判错）
    python scripts/gate-dag.py --verify-consistency          # 枚举 DAG 全部边（调试可见漏边）

特征标志（人给的语义输入，不是模型自报）：
    --check-fail     L1 自检的 check 失败（命令/脚本退出码 ≠ 0）
    --high-value     高价值任务（必须到 L2 至少；链上持续升级到 L4）
    --irreversible   不可逆/高危（critical，直达 L4，跳过中间层）
    --unattended     无人值守（无人在环 → 确定性 gate 兜底）
    --rework-overflow L2 评估 fail 且返工轮次超预算
    --gate-fail      L3 确定性 gate 判不过

--audit 输入格式（两种）：
    A) 轨迹列表：  [{"task": "t1", "features": {...}, "levels_hit": ["L1", "L2"]}, ...]
    B) gate4 demo 落盘工件（result 含 gate_levels.L1_draft/L2_verdict/L3_gate_log/L4_challenge）
       自动从 gate_levels 提取实际到达级别。

退出码：0=无漏边（升过头只报不判错，不改变退出码）；1=审计发现漏边（该升没升）或参数错误；
2=审计目标不可读/结构非法。
纯只读分析工具，不执行任何门禁，不产生持久化副作用（回滚零残留）。
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

LEVELS = ("L1", "L2", "L3", "L4")
FEATURES = ("check_fail", "high_value", "irreversible", "unattended", "rework_overflow", "gate_fail")


def resolve(features):
    """给定任务特征，返回应走级别（升级路径）。返回 dict：level/path/reason。"""
    f = {k: bool(features.get(k)) for k in FEATURES}
    path = ["L1"]
    if f["irreversible"]:
        # 不可逆/高危（critical）：跳过中间层直达 L4（§2.1 任一层→L4）
        path.append("L4")
        return {"level": "L4", "path": path, "reason": "不可逆/高危（critical）→ 直达 L4 独立评审"}
    if f["high_value"]:
        # 高价值：L1→L2（有人在场复查）→L3（确定性 gate）→L4（第二意见），链上持续升级
        path += ["L2", "L3", "L4"]
        return {"level": "L4", "path": path, "reason": "高价值 → L2→L3→L4 链式升级（有人复查→确定门禁→独立第二意见）"}
    if f["check_fail"]:
        path.append("L2")
        if f["rework_overflow"] or f["unattended"]:
            path.append("L3")
            if f["gate_fail"]:
                path.append("L4")
                return {"level": "L4", "path": path, "reason": "L1 check 失败 → L2 评估 fail/无人值守 → L3 gate 不过 → L4"}
            return {"level": "L3", "path": path, "reason": "L1 check 失败 → L2 评估超预算/无人值守 → L3 确定性 gate"}
        return {"level": "L2", "path": path, "reason": "L1 check 失败 → L2 会话级 goal 复查"}
    return {"level": "L1", "path": path, "reason": "L1 check 通过且低价值可逆 → 不升级"}


def _expected_level(features):
    return resolve(features)["level"]


def _levels_from_gate_levels(gate_levels):
    hit = []
    if gate_levels.get("L1_draft"):
        hit.append("L1")
    if gate_levels.get("L2_verdict"):
        hit.append("L2")
    if gate_levels.get("L3_gate_log"):
        hit.append("L3")
    if gate_levels.get("L4_challenge"):
        hit.append("L4")
    return hit


def audit(trajectories, verbose=False):
    """给定轨迹列表（task/features/levels_hit），枚举实际升级路径 + 双向检测（v4.6.0）。

    返回 (findings, over_escalations)：
    - findings（漏边 = 该升没升）：实际级别未达应走级别 → 纪律问题 → 调用方 exit 1。
    - over_escalations（升过头 = 实际最高级 > 应走级别）：中间级未触发该级必要特征仍走到更高级
      （低价值可逆任务直接 L4 = 资源浪费/越权评审）→ 脚本只报不判错（exit 0），交由人在环看。
      注：max(hit) > expected 已蕴含「中间级未触发必要特征」——若中间级必要特征在，resolve 会把
      expected 提到该级；实际越过 expected 即说明越过的那几级缺特征。
    """
    findings = []
    over_escalations = []
    for t in trajectories:
        task = t.get("task", "?")
        feats = t.get("features", {})
        exp = resolve(feats)
        hit = t.get("levels_hit") or []
        # 漏边：实际到达级别 < 应到达级别（该升没升）
        exp_level = exp["level"]
        if exp_level in ("L2", "L3", "L4") and exp_level not in hit:
            findings.append({
                "task": task, "expected": exp_level, "hit": hit,
                "missing_edge": "→".join(exp["path"]), "reason": exp["reason"],
            })
        # 升过头：实际走到的最高级 > 应走级别（该降没降/升过头）
        hit_idx = [LEVELS.index(l) for l in hit if l in LEVELS]
        hit_max = max(hit_idx, default=-1)
        exp_idx = LEVELS.index(exp_level)
        if hit_max > exp_idx:
            over_escalations.append({
                "task": task, "expected": exp_level, "actual_max": LEVELS[hit_max],
                "hit": hit, "expected_path": "→".join(exp["path"]),
                "reason": "实际最高级 %s > 应走级别 %s（%s）——中间级未触发该级必要特征，属升过头（脚本只报不判错）" % (
                    LEVELS[hit_max], exp_level, exp["reason"]),
            })
    return findings, over_escalations


def main():
    ap = argparse.ArgumentParser(description="门禁四级 DAG（Graph 路径 B）")
    ap.add_argument("--check", action="store_true", help="按特征标志返回应走级别")
    ap.add_argument("--audit", metavar="JSON", default=None, help="轨迹列表/gate4 工件 → 枚举路径+漏边检测")
    ap.add_argument("--verify-consistency", action="store_true", help="枚举 DAG 全部边（调试可见漏边）")
    ap.add_argument("--json", action="store_true", help="输出 JSON")
    for fl in FEATURES:
        ap.add_argument("--" + fl.replace("_", "-"), action="store_true", help="任务特征 %s" % fl)
    args = ap.parse_args()

    mode = sum((args.check, args.audit is not None, args.verify_consistency))
    if mode != 1:
        print("必须且只能指定一种模式（--check / --audit <json> / --verify-consistency）", file=sys.stderr)
        return 2

    if args.verify_consistency:
        # 枚举 DAG 全部边：对特征布尔空间抽样遍历，列出每个特征组合 → 应走路径（调试可见漏边）
        import itertools
        combos = list(itertools.product([False, True], repeat=len(FEATURES)))
        edges = []
        for combo in combos:
            feats = dict(zip(FEATURES, combo))
            r = resolve(feats)
            edges.append({"features": {k: bool(v) for k, v in feats.items()}, "level": r["level"], "path": r["path"]})
        n_l1 = sum(1 for e in edges if e["level"] == "L1")
        n_l2 = sum(1 for e in edges if e["level"] == "L2")
        n_l3 = sum(1 for e in edges if e["level"] == "L3")
        n_l4 = sum(1 for e in edges if e["level"] == "L4")
        summary = {
            "edge_count": len(edges),
            "by_level": {"L1": n_l1, "L2": n_l2, "L3": n_l3, "L4": n_l4},
            "note": "共 %d 种特征组合全部可枚举（布尔空间 2^6）；调试时漏一条边在 path 列直接可见" % len(edges),
        }
        if args.json:
            print(json.dumps({"summary": summary, "edges": edges}, ensure_ascii=False, indent=2))
        else:
            print("门禁四级 DAG — 全部边枚举（%d 组合）" % len(edges))
            print("按级别分布: " + "  ".join("%s=%d" % (k, v) for k, v in summary["by_level"].items()))
            for e in edges:
                flagstr = " ".join("%s" % k for k, v in e["features"].items() if v) or "（无特征）"
                print("  %-28s → %s  [%s]" % (flagstr, "→".join(e["path"]), e["level"]))
        return 0

    if args.check:
        feats = {k: getattr(args, k) for k in FEATURES}
        r = resolve(feats)
        if args.json:
            print(json.dumps(r, ensure_ascii=False, indent=2))
        else:
            print("应走级别: %s" % r["level"])
            print("升级路径: %s" % "→".join(r["path"]))
            print("理由: %s" % r["reason"])
        return 0

    if args.audit:
        p = args.audit
        if not os.path.isfile(p):
            print("审计目标不存在: %s" % p, file=sys.stderr)
            return 2
        try:
            data = json.load(open(p, "r", encoding="utf-8"))
        except (OSError, ValueError):
            print("审计目标不可解析（非合法 JSON）: %s" % p, file=sys.stderr)
            return 2
        # 归一化为轨迹列表
        if isinstance(data, list):
            trajectories = data
        elif isinstance(data, dict) and "gate_levels" in data:
            # gate4 demo 工件：自动提取实际到达级别（特征默认全 False → 无特征任务应走 L1）
            trajectories = [{
                "task": data.get("meta", {}).get("name", "gate4-demo"),
                "features": {},
                "levels_hit": _levels_from_gate_levels(data["gate_levels"]),
            }]
        else:
            print("审计目标结构非法：须为轨迹列表或含 gate_levels 的工件", file=sys.stderr)
            return 2
        findings, over_escalations = audit(trajectories)
        if args.json:
            print(json.dumps({
                "trajectory_count": len(trajectories),
                "missing_edges": findings,
                "over_escalations": over_escalations,
                "exit": 1 if findings else 0,
                "note": "升过头（over_escalations）只报不判错，不计入 exit；漏边（missing_edges）exit 1",
            }, ensure_ascii=False, indent=2))
        else:
            print("门禁四级 DAG 审计 — %d 条轨迹（双向检测：漏边 + 升过头）" % len(trajectories))
            for t in trajectories:
                exp = resolve(t.get("features", {}))
                hit = t.get("levels_hit") or []
                hit_idx = [LEVELS.index(l) for l in hit if l in LEVELS]
                over = max(hit_idx, default=-1) > LEVELS.index(exp["level"])
                mark = "✓" if (exp["level"] in hit and not over) else ("⚠ 升过头" if over else "✗ 漏边！")
                print("  %s: 实际=%s  应走=%s(%s)  %s" % (
                    t.get("task", "?"), "→".join(hit) or "（未记录）",
                    exp["level"], "→".join(exp["path"]), mark))
            if over_escalations:
                print("升过头 %d 处：实际最高级 > 应走级别，中间级未触发必要特征（只报不判错，exit 不因它改变）" % len(over_escalations))
                for oe in over_escalations:
                    print("  - %s: 实际最高 %s > 应走 %s（%s）" % (
                        oe["task"], oe["actual_max"], oe["expected"], oe["expected_path"]))
            if findings:
                print("漏边 %d 处：该升没升（调试可见）" % len(findings))
                for fn in findings:
                    print("  - %s: 应走 %s（%s）实际只到 %s" % (
                        fn["task"], fn["missing_edge"], fn["reason"], "→".join(fn["hit"]) or "未记录"))
                return 1
            print("无漏边；若上方列出升过头则为如实标注（脚本只报不判错）。")
        return 0


if __name__ == "__main__":
    sys.exit(main())
