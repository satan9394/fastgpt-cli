#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
skill-router.py — v4.2.0 分离式 skill 执行：领域 skill 选用/禁用解析 + 路由碰撞检查 + 运行时接线检查。

核心语义（解析优先级，高→低）：
    env HARNESS_SKILLS=dev,pr  >  repo .harness/config.json  >  user ~/.config/harness/config.json  >  内置默认
    disabled 名单 > enabled 名单 > defaultMode 档位
    （用户指令文件 CLAUDE.md 声明「本项目不用 X skill」优先级最高——那是用户层，脚本不读取）

defaultMode=off 语义（v4.3.0 定夺，保持现状并文档化）：
    off 只关闭「默认档位的基座」（all 全开 / minimal 只 dev），config `enabled` 的显式声明仍并入生效——
    off 表示「默认不启任何 skill」，不表示「忽略显式声明」。想全禁需各层 enabled 均为空（defaultMode: off
    且 enabled: []）；HARNESS_SKILLS=off 与 defaultMode: off 同义（只关默认基座、不覆盖 enabled 显式声明）。

用法：
    python scripts/skill-router.py --config .harness/config.json                       # 校验 config 并输出启用名单
    python scripts/skill-router.py --skills skill/skills                               # 扫描领域 skill 目录
    python scripts/skill-router.py --config .harness/config.json --skills skill/skills # 校验+扫描+漂移检测
    python scripts/skill-router.py --check-descriptions skill/skills                   # description 路由碰撞启发式
    python scripts/skill-router.py --check-descriptions skill/skills --samples samples.json  # v4.7.0 正/负样例路由测试
    python scripts/skill-router.py --check-wiring .claude/skills --config .harness/config.json  # 运行时接线检查
    python scripts/skill-router.py --baseline out.json / --diff base.json              # 状态快照与漂移检测

退出码：0=正常；1=存在碰撞/漂移/接线 NOT-OK/样例路由不达标/非法 config；2=参数错误。
--samples 判据（v4.7.0）：正样例 rank-1 命中率 ≥0.8 且负样例不误命中率 ≥0.8，否则 exit 1。
--check-wiring 含 requires 依赖闭包（v4.7.0）：引用核心 harness-engineering 恒 OK；依赖缺失 NOT-OK、
存在但未启用 WARN（均并入退出码）。
纯标准库；UTF-8 三通道；Windows 控制台无需 PYTHONIOENCODING。
"""
import argparse
import json
import os
import re
import sys

# 三通道统一 UTF-8（与 audit/record-error 一致）
for _stream_name in ("stdout", "stdin", "stderr"):
    _s = getattr(sys, _stream_name, None)
    if _s is not None and hasattr(_s, "reconfigure"):
        try:
            _s.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass

DEFAULT_MODE = "all"          # all | minimal | off
MODES = ("all", "minimal", "off")
MINIMAL_DEFAULT = ("dev",)    # minimal 档位默认只启 dev
CONFIG_FILENAME = "config.json"
CONFIG_DIRNAME = ".harness"
MAX_ANCESTORS = 64
# v4.7.0 requires 依赖闭包：核心 skill（包本体）恒存在且启用，领域 skill requires 引用它不算缺失。
CORE_SKILL_NAMES = ("harness-engineering",)
STOPWORDS = {"skill", "skill的", "harness", "agent", "当", "要", "用", "本项目", "只", "任务", "场景", "时",
             "use", "when", "the", "a", "an", "this", "for", "to", "in", "on", "and", "or", "of",
             "开发", "治理", "设计", "需求", "分析", "评审"}


def _recon(text):
    """抽取中英文 token，过滤停用词，用于路由碰撞启发式。"""
    tokens = set()
    for m in re.finditer(r"[A-Za-z][A-Za-z\-]{1,}|[一-鿿]{1,4}", text or ""):
        t = m.group(0).lower().strip("-")
        if t and t not in STOPWORDS and len(t) > 1:
            tokens.add(t)
    return tokens


def find_repo_config(start_dir):
    """向上遍历（最多 64 层）找 .harness/config.json，返回路径或 None。"""
    d = os.path.abspath(start_dir)
    for _ in range(MAX_ANCESTORS):
        p = os.path.join(d, CONFIG_DIRNAME, CONFIG_FILENAME)
        if os.path.isfile(p):
            return p
        parent = os.path.dirname(d)
        if parent == d:
            break
        d = parent
    return None


def find_user_config():
    """用户级配置：Windows %APPDATA%/harness/config.json，POSIX ~/.config/harness/config.json。"""
    base = os.environ.get("APPDATA") or os.path.join(os.path.expanduser("~"), ".config")
    p = os.path.join(base, "harness", CONFIG_FILENAME)
    return p if os.path.isfile(p) else None


def load_json(path):
    try:
        with open(path, "r", encoding="utf-8") as fh:
            return json.load(fh)
    except (OSError, ValueError):
        return None


def validate_config(cfg):
    """校验 config 结构，返回错误列表（空=通过）。"""
    errs = []
    if not isinstance(cfg, dict):
        return ["config 须为 JSON 对象"]
    if "schema_version" in cfg and not isinstance(cfg["schema_version"], int):
        errs.append("schema_version 须为整数")
    mode = cfg.get("defaultMode", DEFAULT_MODE)
    if mode not in MODES:
        errs.append(f"defaultMode 非法: {mode}（须 {MODES}）")
    for key in ("enabled", "disabled"):
        v = cfg.get(key, [])
        if not isinstance(v, list) or not all(isinstance(x, str) for x in v):
            errs.append(f"{key} 须为字符串数组")
    prof = cfg.get("profiles")
    if prof is not None and not isinstance(prof, dict):
        errs.append("profiles 须为对象（name -> {enabled,disabled}）")
    return errs


def resolve_enabled(known_skills, layers):
    """按优先级逐层合并，返回 {enabled, disabled, mode}。

    layers: 按低→高排序的 config 层（default 内置 / user / repo / env）。
    语义：env(HARNESS_SKILLS) > repo > user > default；disabled 名单最高剔除。
    """
    base_mode = DEFAULT_MODE
    declared_enabled, declared_disabled = set(), set()
    env_override = None
    for layer in layers:
        if layer is None:
            continue
        if isinstance(layer, dict):
            m = layer.get("defaultMode")
            if m in MODES:
                base_mode = m
            declared_enabled |= set(layer.get("enabled") or [])
            declared_disabled |= set(layer.get("disabled") or [])
        elif isinstance(layer, str):
            # env HARNESS_SKILLS=dev,pr —— 最高优先，直接决定启用名单
            env_override = {s.strip() for s in layer.split(",") if s.strip()}
    if env_override is not None:
        enabled = env_override - declared_disabled
    else:
        if base_mode == "off":
            base = set()
        elif base_mode == "minimal":
            base = set(MINIMAL_DEFAULT)
        else:  # all
            base = set(known_skills)
        # off 档位下 base=∅，但 declared_enabled 显式声明仍并入（v4.3.0 定夺：off 只关默认基座、
        # 不覆盖显式声明；想全禁需各层 enabled 均为空；HARNESS_SKILLS=off 与 defaultMode:off 同义、
        # 同样不覆盖 enabled 显式声明）。
        enabled = (base | declared_enabled) - declared_disabled
    # 不过滤 known_skills：config 启用了磁盘缺失的 skill 由漂移检测抓出
    return {"mode": base_mode, "enabled": sorted(enabled), "disabled": sorted(declared_disabled)}


def _extract_desc(text):
    """从 frontmatter 抽取 description 全文。

    支持单行、`>` 折叠块、`|` 字面块（含 `>-`/`|-` 变体）。折叠/字面块把
    后续缩进行用空格拼接，块内空行跳过（YAML 折叠块允许空行分隔段落）。
    只在首尾 `---` 之间的 frontmatter 内扫描，正文里出现的 `description:`
    字样（代码示例/表格）不会被误当成 frontmatter 字段。
    """
    lines = text.splitlines()
    # 只在 frontmatter（首行 --- 到第二个 ---）区间内扫描；无 frontmatter 的
    # 文件不参与描述抽取（正文里的 description: 字样不能当作 frontmatter 字段）
    if not lines or lines[0].strip() != "---":
        return ""
    scan = None
    for k in range(1, len(lines)):
        if lines[k].strip() == "---":
            scan = lines[1:k]
            break
    if scan is None:
        return ""
    for i, ln in enumerate(scan):
        m = re.match(r"^description:\s*(.*)$", ln)
        if not m:
            continue
        head = m.group(1).strip()
        if not head:
            return ""
        if head[0] in ">|":
            body = []
            for l in scan[i + 1:]:
                if not l.strip():
                    continue  # 块内空行：YAML 折叠块合法，跳过继续
                if l[:1] in (" ", "\t"):
                    body.append(l.strip())
                else:
                    break
            return " ".join(body)
        if len(head) >= 2 and head[0] == head[-1] and head[0] in ("'", '"'):
            return head[1:-1]
        return head
    return ""


def scan_skills(skills_dir):
    """扫描领域 skill 目录：每个含 SKILL.md 的子目录 = 一个领域 skill。"""
    found = {}
    if not skills_dir or not os.path.isdir(skills_dir):
        return found
    for name in sorted(os.listdir(skills_dir)):
        if name.startswith("_") or name.startswith("."):
            continue
        sd = os.path.join(skills_dir, name)
        sk = os.path.join(sd, "SKILL.md")
        if os.path.isfile(sk):
            desc = ""
            try:
                text = open(sk, "r", encoding="utf-8", errors="replace").read()
                desc = _extract_desc(text)
            except OSError:
                pass
            found[name] = {"desc": desc, "path": sk}
    return found


def check_descriptions(skills_dir):
    """description 路由碰撞启发式：两两 token Jaccard 相似度。"""
    skills = scan_skills(skills_dir)
    names = sorted(skills)
    warns = []
    for i in range(len(names)):
        for j in range(i + 1, len(names)):
            a, b = names[i], names[j]
            ta, tb = _recon(skills[a]["desc"]), _recon(skills[b]["desc"])
            if not ta or not tb:
                continue
            inter = len(ta & tb)
            jacc = inter / len(ta | tb) if (ta | tb) else 0.0
            if jacc >= 0.5:
                warns.append({"pair": f"{a} <-> {b}", "jaccard": round(jacc, 2), "level": "NOT-OK",
                             "shared": sorted(ta & tb)[:8]})
            elif jacc >= 0.3:
                warns.append({"pair": f"{a} <-> {b}", "jaccard": round(jacc, 2), "level": "WARN",
                             "shared": sorted(ta & tb)[:8]})
    return warns


# ---- v4.7.0 M1 增强：description 正/负样例路由测试（rank-1）+ requires 依赖闭包 ----

# 全角 → 半角映射（全角字母/数字/标点规范化，防 Unicode 变体路由失败，v4.7 独立评审 low 修复）
_FULLWIDTH_MAP = str.maketrans({chr(0xFF01 + i): chr(0x21 + i) for i in range(94)})


def _bigrams(text):
    """混合特征：CJK 连续块内 2 字 bigram + Latin 词级 token（过滤停用词）。

    对短查询 vs 长 description 的相似度比 4 字块 token（_recon）更鲁棒：
    4 字块在短文本上错位严重（「设计新页面」切成「设计新页/面配色和」），
    bigram 保留「页面」「配色」等真实 2 字词。
    Latin 走词级 token（复用 STOPWORDS 过滤，见 _recon）而非字符 bigram——
    避免跨词边界 bigram（'quick' 内含 'ui'）与 th/he/in/on 等高频英文 bigram
    污染相似度（v4.7 独立评审 major 修复）。
    全角字母先转半角（v4.7 独立评审 low 修复）。
    特征前缀 'w:' 区分词级 token 与 CJK bigram（同字不撞车）。
    """
    features = set()
    s = (text or "").lower().translate(_FULLWIDTH_MAP)
    for m in re.finditer(r"[一-鿿]+", s):
        run = m.group(0)
        features.update(run[i:i + 2] for i in range(len(run) - 1))
    for m in re.finditer(r"[a-z][a-z\-]{1,}", s):
        w = m.group(0).strip("-")
        if w and w not in STOPWORDS and len(w) > 1:
            features.add("w:" + w)
    return features


def route_query(query, skills):
    """对一条任务描述做 rank-1 领域路由：bigram Dice 相似度取最高者。

    返回 (best_name, scores)。best_name 为 None 表示无任何交集（无法路由）。
    scores 为 {skill_short: Dice}（供 top-N 展示）。
    """
    qt = _bigrams(query)
    scores = {}
    for name, info in skills.items():
        st = _bigrams(info["desc"])
        if not qt or not st:
            scores[name] = 0.0
        else:
            scores[name] = 2.0 * len(qt & st) / (len(qt) + len(st))
    if not scores:
        return None, {}
    best = max(scores, key=scores.get)
    return (best if scores[best] > 0.0 else None), scores


def run_route_samples(skills, samples):
    """正/负样例路由测试：正样例 rank-1 命中本 skill；负样例 rank-1 不应命中本 skill。

    samples: {"<skill短名>": {"positive": [query...], "negative": [query...]}}。
    返回 (items, positive_rate, negative_rate, ok)。items 逐样例报告（含 top3 相似度）。
    达标阈值：正样例 rank-1 命中率 ≥0.8 且负样例不误命中率 ≥0.8。
    """
    items = []
    pos_hit = pos_total = neg_correct = neg_total = 0
    for skill_name in sorted(samples):
        spec = samples[skill_name] or {}
        for q in spec.get("positive", []):
            pos_total += 1
            pred, scores = route_query(q, skills)
            hit = pred == skill_name
            if hit:
                pos_hit += 1
            items.append({"kind": "positive", "skill": skill_name, "query": q, "pred": pred, "hit": hit,
                          "top3": sorted(scores.items(), key=lambda kv: -kv[1])[:3]})
        for q in spec.get("negative", []):
            neg_total += 1
            pred, scores = route_query(q, skills)
            correct = pred != skill_name
            if correct:
                neg_correct += 1
            items.append({"kind": "negative", "skill": skill_name, "query": q, "pred": pred, "correct": correct,
                          "top3": sorted(scores.items(), key=lambda kv: -kv[1])[:3]})
    pos_rate = pos_hit / pos_total if pos_total else None
    neg_rate = neg_correct / neg_total if neg_total else None
    # fail-closed（v4.7 独立评审 minor 修复）：没有任何正样例时门禁不可信——
    # 空文件/漏填的 skill 不应白嫖通过；正样例必须 ≥0.8，负样例缺省视为达标。
    ok = (pos_rate is not None and pos_rate >= 0.8) and (neg_rate is None or neg_rate >= 0.8)
    return items, pos_rate, neg_rate, ok


# ---- v4.2.0 C1 接线检查：config 声明名单 vs 运行时发现根（.claude/skills/） ----

HARNESS_PREFIX = "harness-"


def _frontmatter_meta(skill_file):
    """从 SKILL.md frontmatter 抽取 {name, description, requires}；无 frontmatter 返回空 dict。

    requires 支持标量或数组（`requires: [harness-engineering]` / `requires: harness-dev`）。
    """
    try:
        text = open(skill_file, "r", encoding="utf-8", errors="replace").read()
    except OSError:
        return {}
    lines = text.splitlines()
    if not lines or lines[0].strip() != "---":
        return {}
    fm = {}
    end = None
    for k in range(1, len(lines)):
        if lines[k].strip() == "---":
            end = k
            break
        m = re.match(r"^name\s*:\s*(.*)$", lines[k])
        if m:
            fm["name"] = m.group(1).strip().strip("'\"")
            continue
        m = re.match(r"^description\s*:\s*(.*)$", lines[k])
        if m and m.group(1).strip():
            fm["description"] = m.group(1).strip()
            continue
        # requires 容忍缩进（frontmatter 里常在 metadata 块下：`  requires: [harness-engineering]`）
        m = re.match(r"^\s*requires\s*:\s*(.*)$", lines[k])
        if m:
            raw = m.group(1).split("#", 1)[0].strip()  # 去行尾 YAML 内联注释
            reqs = []
            if raw:
                if raw.startswith("["):
                    inner = raw.strip("[]").strip()
                    reqs = [x.split("#", 1)[0].strip().strip("'\"")
                            for x in inner.split(",") if x.strip()]
                else:
                    reqs = [raw.strip("'\"")]
            elif k + 1 < len(lines):
                # YAML 块列表形式：`requires:` 后接更深缩进的 `- item`
                for bl in lines[k + 1:]:
                    if re.match(r"^\s+-\s+\S", bl):
                        reqs.append(bl.strip().lstrip("-").strip().split("#", 1)[0].strip().strip("'\""))
                    elif bl.strip() and not re.match(r"^\s*#", bl):
                        break  # 遇非列表行结束
            if reqs:
                fm["requires"] = reqs
    return fm


def scan_discovery_root(discovery_dir):
    """扫描消费者 .claude/skills/ 发现根：每个含 SKILL.md 的子目录 = 一个已接线领域 skill。

    返回 {dir_name: {"name": frontmatter name, "short": 短名, "path": SKILL.md 路径}}。
    短名推导：frontmatter name 以 harness- 开头 → 去前缀；否则用目录名。
    """
    found = {}
    if not discovery_dir or not os.path.isdir(discovery_dir):
        return found
    for name in sorted(os.listdir(discovery_dir)):
        if name.startswith("."):
            continue
        sd = os.path.join(discovery_dir, name)
        sk = os.path.join(sd, "SKILL.md")
        if not os.path.isfile(sk):
            continue
        meta = _frontmatter_meta(sk)
        fm_name = meta.get("name") or name
        short = fm_name[len(HARNESS_PREFIX):] if fm_name.startswith(HARNESS_PREFIX) else name
        found[name] = {"name": fm_name, "short": short, "path": sk, "requires": meta.get("requires") or []}
    return found


def check_wiring(discovery_dir, resolved_enabled):
    """运行时接线检查：config 解析的启用名单（短名） vs 发现根实际存在的领域 skill。

    报告四类：
    - OK：声明且已接线（config 启用的短名在发现根找到）
    - NOT-OK（声明了但没接线）：config 启用但发现根无对应 skill → skillOverrides 无可开关对象
    - WARN（接线了但没声明）：发现根有 skill 但不在 config 启用名单 → 靠 description 触发或用户显式调用
    - requires 依赖闭包（v4.7.0）：领域 skill frontmatter `requires` 引用的依赖存在且启用
      （引用核心名恒 OK；引用发现根缺失 → NOT-OK；存在但未启用 → WARN）
    返回 items 列表（status/check/action/evidence）。
    """
    items = []
    discovered = scan_discovery_root(discovery_dir)
    by_short = {}
    by_name = {}
    for dname, info in discovered.items():
        by_short.setdefault(info["short"], []).append(dname)
        # requires 引用可用短名或 frontmatter 全名解析
        by_name.setdefault(info["short"], dname)
        by_name.setdefault(info["name"], dname)
    enabled = sorted(resolved_enabled or [])
    for s in enabled:
        if s in by_short:
            items.append({
                "check": f"接线：{s} → {', '.join(by_short[s])}",
                "status": "OK", "action": "-",
                "evidence": "config 启用 & 发现根存在"})
        else:
            items.append({
                "check": f"config 启用但发现根缺失：{s}",
                "status": "NOT-OK",
                "action": "bootstrap --install-scripts 接线，或从 config enabled 移除该短名",
                "evidence": "发现根无 %s 对应 SKILL.md" % s})
    # 发现根有但 config 未启用
    for dname, info in sorted(discovered.items()):
        if info["short"] not in (enabled or []):
            items.append({
                "check": f"发现根已接线但未声明：{info['name']}（{info['short']}）",
                "status": "WARN",
                "action": "确认是否需加入 config enabled；否则该 skill 靠 description 触发/显式调用",
                "evidence": info["path"]})
    # requires 依赖闭包（v4.7.0）：被依赖 skill 存在且启用
    for dname, info in sorted(discovered.items()):
        for r in (info.get("requires") or []):
            if r in CORE_SKILL_NAMES:
                items.append({
                    "check": f"requires 依赖核心：{info['name']} → {r}",
                    "status": "OK", "action": "-",
                    "evidence": "核心（harness-engineering）恒存在且启用"})
                continue
            dep = by_name.get(r)
            dep_short = discovered.get(dep, {}).get("short") if dep else None
            if dep and dep_short in enabled:
                items.append({
                    "check": f"requires 依赖完整：{info['name']} → {r}",
                    "status": "OK", "action": "-",
                    "evidence": f"依赖 {dep} 已接线且启用"})
            elif dep:
                items.append({
                    "check": f"requires 依赖未启用：{info['name']} → {r}",
                    "status": "WARN",
                    "action": "将依赖加入 config enabled，或移除 requires 声明",
                    "evidence": f"依赖 {dep} 已接线但未在启用名单"})
            else:
                items.append({
                    "check": f"requires 依赖缺失：{info['name']} → {r}",
                    "status": "NOT-OK",
                    "action": "补齐依赖 skill 或移除 requires 声明",
                    "evidence": f"发现根无 {r}（非核心）"})
    if not items:
        items.append({"check": "接线检查（发现根为空或 config 无启用）", "status": "INFO",
                      "action": "无内容可核对", "evidence": "发现根为空"})
    return items


def to_markdown(report):
    lines = [f"# 领域 Skill 路由报告 — {report['root']}", ""]
    for sec in report["sections"]:
        lines.append(f"## {sec['name']}")
        for it in sec["items"]:
            mark = f"[{it['status']}]" if it.get("status") in ("OK", "WARN", "NOT-OK") else "[INFO]"
            lines.append(f"{mark} {it['check']}")
            if it.get("action"):
                lines.append(f"    -> {it['action']}")
            if it.get("evidence"):
                lines.append(f"    证据：{it['evidence']}")
        lines.append("")
    return "\n".join(lines)


def main():
    ap = argparse.ArgumentParser(description="分离式 skill 执行：领域 skill 选用/禁用解析 + 路由碰撞检查")
    ap.add_argument("--config", default=None, help="项目 .harness/config.json 路径（默认向上遍历查找）")
    ap.add_argument("--skills", default=None, help="领域 skill 目录（含 SKILL.md 的子目录）")
    ap.add_argument("--check-descriptions", default=None, help="仅做 description 路由碰撞启发式")
    ap.add_argument("--samples", default=None,
                    help="v4.7.0 正/负样例路由测试：JSON 文件 {\"<skill短名>\": {\"positive\": [...], "
                         "\"negative\": [...]}}；正样例 rank-1 命中本 skill / 负样例不误命中，达标 ≥80%；"
                         "需配合 --check-descriptions/--skills")
    ap.add_argument("--check-wiring", default=None,
                    help="v4.2.0 运行时接线检查：消费者 .claude/skills/ 发现根（含 SKILL.md 的子目录），"
                         "核对 config 声明名单 vs 运行时实际发现")
    ap.add_argument("--baseline", default=None, help="把当前报告存为状态快照")
    ap.add_argument("--diff", default=None, help="与状态快照对比，有 drift 退出码 1")
    ap.add_argument("--json", action="store_true", help="输出 JSON")
    ap.add_argument("--env", default=None, help="HARNESS_SKILLS 覆盖（逗号分隔），默认读环境变量")
    args = ap.parse_args()

    # 1. 领域 skill 扫描
    skills_dir = args.check_descriptions or args.skills
    known = scan_skills(skills_dir) if skills_dir else {}

    # v4.3.0（C1 最终验证）：--check-wiring 未给 --skills 时，用发现根当目录代理。
    # 消费者场景（bootstrap 装出的 .claude/skills/）没有独立目录可扫，只有发现根；
    # 若仍以 known={} 解析，defaultMode:all 的「全目录启用」会解析成空名单 → 全部误报 WARN
    # （已接线但未声明），与 bootstrap 提示的 `--check-wiring .claude/skills --config ...` 意图不符。
    # 发现根代理 = all=「全部已接线的 skill」，对齐 defaultMode:all 的真实语义。
    if args.check_wiring and not skills_dir and not known:
        _catalog = scan_discovery_root(args.check_wiring)
        known = {info["short"]: {"desc": "", "path": info["path"]} for info in _catalog.values()}

    # 2. description 路由碰撞
    collides = check_descriptions(args.check_descriptions) if args.check_descriptions else []

    # v4.7.0 M1 增强：正/负样例路由测试（--samples，需领域 skill 目录）
    samples_meta = None  # {"items", "positive_rate", "negative_rate"}
    if args.samples:
        if not known:
            print("--samples 需配合 --check-descriptions/--skills 指定领域 skill 目录", file=sys.stderr)
            return 1
        samples = load_json(args.samples)
        if samples is None:
            print("samples 不可解析: %s" % args.samples, file=sys.stderr)
            return 1
        # 形状校验（v4.7 独立评审 minor 修复）：合法 JSON 但结构错误 → 优雅报错 exit 1，不裸 traceback
        if not isinstance(samples, dict):
            print("samples 须为 JSON 对象（skill 名 -> {positive:[], negative:[]}）", file=sys.stderr)
            return 1
        for _sname, spec in samples.items():
            if not isinstance(spec, dict):
                print(f"samples[{_sname}] 须为对象（{{positive, negative}}）", file=sys.stderr)
                return 1
            for _key in ("positive", "negative"):
                _v = spec.get(_key)
                if not isinstance(_v, list) or not all(isinstance(x, str) for x in _v):
                    print(f"samples[{_sname}].{_key} 须为字符串数组", file=sys.stderr)
                    return 1
        items, pos_rate, neg_rate, ok = run_route_samples(known, samples)
        samples_meta = {"items": items, "positive_rate": pos_rate, "negative_rate": neg_rate, "ok": ok}

    # 3. config 解析
    cfg = None
    cfg_path = args.config or find_repo_config(os.getcwd())
    if cfg_path:
        cfg = load_json(cfg_path)
        if cfg is None:
            print(f"config 不可解析: {cfg_path}", file=sys.stderr)
            return 1
        errs = validate_config(cfg)
        if errs:
            for e in errs:
                print(f"非法 config: {e}", file=sys.stderr)
            return 1
    env_val = args.env if args.env is not None else os.environ.get("HARNESS_SKILLS")
    if env_val is not None and not env_val.strip():
        # 空串/纯空白视同未设置：不静默把全部领域 skill 全禁（与「未设置」走默认档位一致）
        env_val = None
    env_layer = env_val
    if env_val is not None:
        s = env_val.strip()
        if s in MODES and "," not in env_val:
            # 单个档位保留字 = 档位覆盖（HARNESS_SKILLS=off 视为 defaultMode: off 档位覆盖，与 config
            # defaultMode:off 同义，不覆盖各层 enabled 显式声明；想全禁需各层 enabled 均为空）
            print(f"INFO: HARNESS_SKILLS={s} 视为 defaultMode 档位覆盖（与 config defaultMode:off 同义，"
                  f"不覆盖各层 enabled 显式声明；想全禁需各层 enabled 均为空）",
                  file=sys.stderr)
            env_layer = {"defaultMode": s}
        elif any(tok.strip() in MODES for tok in env_val.split(",")):
            print("WARN: HARNESS_SKILLS 含档位保留字（all/minimal/off），会被当 skill 短名造成漂移误报；请用单值档位或 config defaultMode",
                  file=sys.stderr)
    user_cfg = load_json(find_user_config()) if find_user_config() else None
    layers = [{"defaultMode": DEFAULT_MODE}, user_cfg, cfg, env_layer]  # 低→高
    resolved = resolve_enabled(known.keys(), layers)

    # 4. 组装报告
    report = {"root": os.path.abspath(os.getcwd()), "sections": []}
    sec_skills = []
    for name in sorted(known):
        status = "OK" if name in resolved["enabled"] else "INFO"
        sec_skills.append({"check": f"领域 skill：{name}", "status": status,
                           "action": "-", "evidence": known[name]["path"]})
    if not known:
        sec_skills.append({"check": "领域 skill 目录", "status": "INFO",
                           "action": "用 --skills 指定目录，或确认 skills/ 下含 SKILL.md", "evidence": "未扫描到"})
    report["sections"].append({"name": "领域 skill 清单", "items": sec_skills})

    # 漂移检测：config 启用的 skill 在磁盘不存在。
    # - 未指定领域 skill 目录（skills_dir 为 None，如只 --config 校验）→ 无磁盘对照，INFO 提示（不误报）
    # - 指定了目录但目录为空/不存在（known 为空）→ 磁盘确实没有，config 启用的每一项都该报漂移
    drift_items = []
    if skills_dir is None:
        drift_items.append({"check": "漂移检测（未指定领域 skill 目录）", "status": "INFO",
                            "action": "加 --skills <目录> 启用完整漂移检测；此处仅校验与解析 config",
                            "evidence": "未扫描到领域 skill"})
    else:
        for s in resolved["enabled"]:
            if s not in known:
                drift_items.append({"check": f"config 启用但磁盘缺失：{s}", "status": "NOT-OK",
                                    "action": "删除 config 中该条目，或补齐领域 skill 目录", "evidence": s})
    report["sections"].append({"name": "漂移检测", "items": drift_items or [
        {"check": "config 与磁盘一致性", "status": "OK", "action": "-", "evidence": "无漂移"}]})

    # v4.2.0 运行时接线检查：config 声明名单 vs .claude/skills/ 实际发现（比漂移检测深一层）。
    wiring_items = []
    if args.check_wiring:
        wiring_items = check_wiring(args.check_wiring, resolved["enabled"])
    report["sections"].append({"name": "运行时接线检查（config 声明 vs 发现根）", "items": wiring_items or [
        {"check": "接线检查", "status": "INFO", "action": "用 --check-wiring <项目>/.claude/skills 启用",
         "evidence": "未指定发现根"}]})

    col_items = []
    for c in collides:
        col_items.append({"check": f"路由碰撞：{c['pair']}", "status": c["level"],
                          "action": "收紧 description 触发词，明确领域边界",
                          "evidence": f"Jaccard={c['jaccard']} 共享词={','.join(c['shared'])}"})
    report["sections"].append({"name": "description 路由碰撞", "items": col_items or [
        {"check": "description 两两相似度", "status": "OK", "action": "-", "evidence": "无显著重叠"}]})

    # v4.7.0 路由样例测试 section（--samples）
    if samples_meta is not None:
        route_items = []
        for it in samples_meta["items"]:
            passed = it.get("hit") if it["kind"] == "positive" else it.get("correct")
            top3 = ", ".join(f"{k}:{v:.2f}" for k, v in it.get("top3") or [])
            route_items.append({
                "check": f"{it['kind']}: {it['skill']} ← {it['query'][:40]}",
                "status": "OK" if passed else "NOT-OK",
                "action": "-" if passed else "收紧该 skill description 或修正样例归属",
                "evidence": f"rank-1 → {it['pred']}（top3: {top3}）"})
        route_items.append({
            "check": f"正样例 rank-1 命中率 {samples_meta['positive_rate']} / 负样例不误命中率 "
                     f"{samples_meta['negative_rate']}（达标 ≥0.8）",
            "status": "OK" if samples_meta["ok"] else "NOT-OK",
            "action": "-" if samples_meta["ok"] else "失败样本见上，需修 description 或样例",
            "evidence": "达标阈值 0.8"})
        report["sections"].append({"name": "路由样例测试（rank-1）", "items": route_items})

    sec_resolve = [
        {"check": "defaultMode", "status": "INFO", "action": "-", "evidence": resolved["mode"]},
        {"check": "启用名单", "status": "INFO", "action": "-", "evidence": ", ".join(resolved["enabled"]) or "（无）"},
        {"check": "禁用名单", "status": "INFO", "action": "-", "evidence": ", ".join(resolved["disabled"]) or "（无）"},
    ]
    report["sections"].append({"name": "解析结果", "items": sec_resolve})

    text = json.dumps(report, ensure_ascii=False, indent=2) if args.json else to_markdown(report)

    if args.baseline:
        with open(args.baseline, "w", encoding="utf-8") as fh:
            fh.write(text)
        print(f"状态快照已存 {args.baseline}")

    any_problem = any(it["status"] == "NOT-OK" for it in drift_items) or any(
        c["level"] == "NOT-OK" for c in collides) or any(
        it["status"] == "NOT-OK" for it in wiring_items) or bool(
        samples_meta is not None and not samples_meta["ok"])
    code = 1 if any_problem else 0

    def _normalize_for_diff(s):
        # 去掉报告里随 cwd/路径拼写变化的成分，使 --diff 只比较「启用状态」本身：
        # - 报告头 root / JSON root 字段 → 固定标记
        # - 证据路径整体 → 固定标记（相对/绝对/./../拼写差异全部抹平）
        # - 路径分隔 / ./ ../ 归一
        s = re.sub(r"# 领域 Skill 路由报告 — .+", "# 领域 Skill 路由报告 — <ROOT>", s)
        s = re.sub(r'"root"\s*:\s*"[^"]*"', '"root": "<ROOT>"', s)
        s = re.sub(r"证据：[^\n]*", "证据：<EV>", s)
        s = re.sub(r'"evidence"\s*:\s*"[^"]*"', '"evidence": "<EV>"', s)
        if os.sep == "\\":
            s = s.replace("\\", "/")
        s = re.sub(r"\.\./", "", s)   # 先剥 ../ 再剥 ./（../skills 不能被 ./ 拆成 .skills）
        s = s.replace("./", "")
        s = re.sub(r"/{2,}", "/", s)
        return s.strip()

    if args.diff:
        if not os.path.isfile(args.diff):
            print("快照不存在: %s" % args.diff, file=sys.stderr)
            return 2
        base = open(args.diff, "r", encoding="utf-8").read()
        if _normalize_for_diff(base) != _normalize_for_diff(text):
            print("WARN 与快照存在 drift（领域 skill 启用状态已变化）", file=sys.stderr)
            code = 1
        else:
            print("OK 与快照一致。")

    if not args.baseline and not args.diff:
        print(text)
    return code


if __name__ == "__main__":
    sys.exit(main())
