#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
record-error.py — 把一次「违规/返工/重复解释」事件写入 STATE.json，并更新对应规则命中计数。
生长回路（growth-loop）的数据输入口：让「同错≥2 次」从人盯会话变成可计算事实。

时间失效语义（v4.4.0 Graph 路径 C，兼容升级）：
- 规则新增写 `valid_time`（本次生效起点，同 born 但保精度）；`rule_removed` 不再删除规则，
  改为标 `revoked: true` + `expiry: <撤销时间>` 保留在 rules[]（审计查询按过期过滤）。
- 已撤销/过期规则可再 `rule_added`（re-add 清除 revoked/expiry、重置 hits）——删后重加 = 振荡，
  由 audit.py 事件日志判定（人盯变脚本判）。
- 旧数据无 valid_time/expiry 的规则按「永不过期」处理，完全兼容。

归档/compaction 语义（v4.5.0 Graph 路径 C 深化）：
- 撤销/过期超阈值（默认 90 天，`--archive-days` 可配）的规则从 rules[] 主表**迁入 archived 段**，
  保留完整记录（id/text/born/valid_time/expiry/revoked/hits 等）供审计——主表不无限膨胀（compaction）。
- **events 永不归档**（append-only 审计日志）——这是 detect_oscillations 跨归档窗口关联的前提：
  归档前删除、归档后重加，振荡仍由 events 判出，不因归档断链。
- 归档自动触发（每次事件写入后跑归档 pass）+ 可显式 `--archive` 手动压缩。
- 旧数据无 archived 键 → 默认空段；无时间字段规则永不过期 → 永不归档，完全兼容。

安全特性（v3.2 硬化）：
- 原子写（临时文件 + os.replace）
- 并发写串行化（Windows msvcrt / POSIX fcntl 文件锁，尽力而为）
- 敏感事件（手机/邮箱/密钥，含全角手机号与现代令牌格式）对所有事件类型【包括 rule_added】写入前直接拒绝
- --rule 用 re.fullmatch 校验 ^R\\d+$；rule_removed 必须带 --rule；生效规则重复 rule_added 报错
- --from-stdin 供 hook 用（stdin 已 reconfigure utf-8，中文不崩；事件文本不拼 shell，防注入）
- stdout 不回显事件原文（堵日志侧密钥泄露）

用法：
    python scripts/record-error.py --init
    python scripts/record-error.py --type rule_added --rule R01 --layer constraint --event "首次事故: 直推 main 被拦"
    python scripts/record-error.py --rule R01 --event "违规: 再次直推 main"
    python scripts/record-error.py --type rework --event "Jinja2 filter 500 重写"
    python scripts/record-error.py --from-stdin --rule R01     # 事件从 stdin 读
    python scripts/record-error.py --rule R01 --from-stdin --dedup-window 300  # 5 分钟内同事件去重（0=关闭）
    python scripts/record-error.py --archive --archive-days 90  # 手动归档压缩（撤销/过期超 90 天迁入 archived）

事件类型：violation / rework / explanation / rule_added / rule_removed / rule_hardened / rule_loosened / rule_archived
"""
import argparse
import datetime
import hashlib
import json
import os
import re
import sys
import tempfile
import time

# 三通道统一 UTF-8（stdout 上轮已修；stdin/stderr 是本轮补全，修 --from-stdin 中文崩溃）
for _stream_name in ("stdout", "stdin", "stderr"):
    _s = getattr(sys, _stream_name, None)
    if _s is not None and hasattr(_s, "reconfigure"):
        try:
            _s.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass

# 并发锁（Windows msvcrt / POSIX fcntl；不可用时降级为无锁）
try:
    import msvcrt  # Windows
except ImportError:
    msvcrt = None
try:
    import fcntl  # POSIX
except ImportError:
    fcntl = None

HERE = os.path.dirname(os.path.abspath(__file__))
TEMPLATE = os.path.join(HERE, "..", "templates", "STATE.json")
if not os.path.exists(TEMPLATE):
    # 消费者项目可能只装了 scripts/ 没装 templates/：退回到已存在 STATE.json 或就地新建
    TEMPLATE = os.path.join(HERE, "..", "STATE.json")
    if not os.path.exists(TEMPLATE):
        TEMPLATE = os.path.join(HERE, "STATE.json")
TYPES = ("violation", "rework", "explanation", "rule_added", "rule_removed", "rule_hardened", "rule_loosened", "rule_archived")
RULE_ID_RE = re.compile(r"^R\d+$")
MAX_EVENT_LEN = 500
MAX_EVENTS = 5000

# 敏感模式：手机（ASCII+全角）、邮箱、现代密钥格式（sk-proj-/sk-ant-/sk_live_/gho_/ghu_/ghs_/ghr_/github_pat_/AIza/glx-/Bearer）
SENSITIVE = [
    (re.compile(r"1[3-9]\d{9}"), "手机号"),
    (re.compile(r"[１-９]\d{10}|[０-９]{11}"), "全角手机号"),
    (re.compile(r"\b[\w.+-]+@[\w-]+\.\w{2,}\b"), "邮箱"),
    (re.compile(r"sk-proj-[A-Za-z0-9_-]{16,}|sk-ant-api03-[A-Za-z0-9_-]{16,}|sk-[A-Za-z0-9]{20,}|sk_live_[A-Za-z0-9]{16,}"), "疑似密钥"),
    (re.compile(r"ghp_[A-Za-z0-9]{20,}|gho_[A-Za-z0-9]{20,}|ghu_[A-Za-z0-9]{20,}|ghs_[A-Za-z0-9]{20,}|ghr_[A-Za-z0-9]{20,}|github_pat_[A-Za-z0-9_]{20,}|AIza[0-9A-Za-z_-]{20,}|glx-[A-Za-z0-9]{20,}|Bearer\s+[A-Za-z0-9._-]{16,}"), "疑似密钥"),
]


def has_sensitive(text):
    found = []
    for rx, name in SENSITIVE:
        if rx.search(text):
            found.append(name)
    return found


def parse_ts(ts):
    s = str(ts).strip()
    for fmt in ("%Y-%m-%d %H:%M", "%Y-%m-%d"):
        try:
            return datetime.datetime.strptime(s, fmt)
        except ValueError:
            continue
    return None


def load_state(path):
    with open(path, "r", encoding="utf-8") as fh:
        return json.load(fh)


def save_state_atomic(path, state):
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=os.path.dirname(path) or ".", suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            json.dump(state, fh, ensure_ascii=False, indent=2)
        os.replace(tmp, path)
    except Exception:
        if os.path.exists(tmp):
            os.remove(tmp)
        raise


def _locked(path, fn):
    """对 STATE.json 的读-改-写加文件锁串行化（尽力而为；锁不可用时降级无锁）。

    只有「加锁」失败才降级无锁执行；事务 fn() 自身的异常原样向上抛，
    交给 main() 报「写入失败」——不能把事务异常当成锁失败重跑整个事务
    （否则配合 --dedup-window 会把真实错误吞成「去重跳过」）。
    """
    lockpath = path + ".lock"
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
        return fn()  # 事务异常原样抛出
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


def _dedup_seen(path, event, rule_id, etype, window):
    """窗口去重：同 (type, rule, event) 指纹在 window 秒内重复时返回 True（跳过写入）。

    指纹只存 sha256 哈希（事件原文在写入前已被敏感拦截），去重文件不落原文。
    window <= 0 时关闭（保持「每次真实事件都记」的全量语义）。
    """
    if window <= 0:
        return False
    fpr = hashlib.sha256("|".join([etype, rule_id or "", event]).encode("utf-8")).hexdigest()
    dp = path + ".dedup"
    seen = {}
    if os.path.isfile(dp):
        try:
            seen = json.load(open(dp, "r", encoding="utf-8"))
        except (OSError, ValueError):
            seen = {}
    now = time.time()
    alive = {k: v for k, v in seen.items() if now - v < window}
    if fpr in alive:
        return True
    alive[fpr] = now
    save_state_atomic(dp, alive)
    return False


def _archive_candidates(state, archive_days, now_dt):
    """返回应归档的规则列表：revoked/过期 且 失效时间早于阈值。

    - revoked 且有 expiry → 用 expiry 判定；仅 revoked 无 expiry → 用 valid_time 兜底（防御，不丢归档）。
    - 无 revoked/expiry 的规则（含旧数据）→ 永不过期，永不归档。
    - archive_days <= 0 → 关闭归档（保持 v4.4 全保留语义）。
    """
    if archive_days <= 0:
        return []
    threshold = now_dt - datetime.timedelta(days=archive_days)
    out = []
    for r in state.get("rules", []):
        revoked = r.get("revoked")
        exp = r.get("expiry")
        if not (revoked or exp):
            continue
        d = parse_ts(exp) if exp else None
        if d is None:
            d = parse_ts(r.get("valid_time"))
        if d is not None and d < threshold:
            out.append(r)
    return out


def _archive_pass(state, archive_days, ts):
    """把撤销/过期超阈值的规则迁入 archived 段（保留审计痕迹），返回归档规则 id 列表。

    - 归档只移规则记录，**不归档 events**（append-only 审计日志）——detect_oscillations 跨窗口仍可判。
    - 每条归档写一条 rule_archived 事件（审计痕迹：何时归档、归档了谁）。
    - 返回空列表 = 无归档发生。
    """
    if archive_days <= 0:
        return []
    now_dt = datetime.datetime.strptime(ts, "%Y-%m-%d %H:%M")
    cands = _archive_candidates(state, archive_days, now_dt)
    if not cands:
        return []
    archived = state.setdefault("archived", [])
    events = state.setdefault("events", [])
    ids = []
    for r in cands:
        archived.append(r)
        events.append({"ts": ts, "type": "rule_archived", "rule": r.get("id"),
                       "detail": "归档: 撤销/过期超阈值（compaction）"})
        ids.append(r.get("id"))
    state["rules"] = [r for r in state.get("rules", []) if r not in cands]
    meta = state.setdefault("meta", {})
    meta["archived_total"] = meta.get("archived_total", 0) + len(cands)
    meta["last_archived"] = ts
    return ids


def main():
    ap = argparse.ArgumentParser(description="向 STATE.json 追加生长事件")
    ap.add_argument("--state", default="STATE.json")
    ap.add_argument("--rule", default=None)
    ap.add_argument("--type", choices=TYPES, default="violation")
    ap.add_argument("--layer", choices=["instruction", "constraint", "memory"], default="instruction")
    ap.add_argument("--event", default=None)
    ap.add_argument("--ts", default=None)
    ap.add_argument("--from-stdin", action="store_true")
    ap.add_argument("--init", action="store_true")
    ap.add_argument("--dedup-window", type=int, default=0,
                    help="同 (type,rule,event) 去重窗口秒数（0=关闭，默认）")
    ap.add_argument("--archive-days", type=int, default=90,
                    help="归档阈值天数：撤销/过期超过该天数迁入 archived（0=关闭归档）")
    ap.add_argument("--archive", action="store_true",
                    help="只跑归档压缩 pass（不写业务事件）；与 --init 互斥")
    args = ap.parse_args()

    if args.from_stdin:
        args.event = sys.stdin.read().strip()

    path = os.path.abspath(args.state)
    if not os.path.exists(path) and args.init:
        st = load_state(TEMPLATE)
        st.setdefault("archived", [])  # v4.5.0 归档段（schema v2 可选扩展）
        save_state_atomic(path, st)
        print(f"已创建 {path}")
        return 0
    if args.init and os.path.exists(path):
        print(f"STATE.json 已存在: {path}（无需 init）")
        return 0
    if not os.path.exists(path):
        print(f"STATE.json 不存在: {path}（先 --init 创建，或检查路径）", file=sys.stderr)
        return 1
    if args.archive:
        # 只跑归档 pass，不写业务事件
        def archive_only():
            st = load_state(path)
            ids = _archive_pass(st, args.archive_days, args.ts or datetime.datetime.now().strftime("%Y-%m-%d %H:%M"))
            if not ids:
                print("无归档候选（撤销/过期未超阈值或归档关闭）")
                return
            save_state_atomic(path, st)
            print(f"已归档 {len(ids)} 条: {', '.join(ids)}")
        try:
            _locked(path, archive_only)
        except (OSError, ValueError, TypeError, json.JSONDecodeError) as e:
            print(f"归档失败: {e}", file=sys.stderr)
            return 1
        return 0
    if not args.event:
        print("缺少事件（--event / --from-stdin，--init 除外）", file=sys.stderr)
        return 1

    # --ts 校验（畸形时间戳拒绝，避免指标静默失真）
    if args.ts and parse_ts(args.ts) is None:
        print(f"非法时间戳: {args.ts}（须 YYYY-MM-DD 或 YYYY-MM-DD HH:MM）", file=sys.stderr)
        return 1

    # 敏感事件拦截：所有事件类型（含 rule_added）一视同仁
    sensitive = has_sensitive(args.event)
    if sensitive:
        print(f"拒绝写入：事件含敏感内容（{', '.join(sensitive)}）。请脱敏后再记；密钥/完整 PII 禁止进 STATE.json（git 历史不可删）。", file=sys.stderr)
        return 1

    if len(args.event) > MAX_EVENT_LEN:
        print(f"事件过长（>{MAX_EVENT_LEN} 字符），截断写入", file=sys.stderr)
        args.event = args.event[:MAX_EVENT_LEN]

    ts = args.ts or datetime.datetime.now().strftime("%Y-%m-%d %H:%M")

    def txn():
        rule_id = None
        if args.rule:
            rid = args.rule.strip().upper()
            if not RULE_ID_RE.fullmatch(rid):
                raise ValueError(f"规则 id 格式非法: {args.rule}（须 ^R\\d+$）")
            rule_id = rid
        state = load_state(path)
        if args.rule:
            found = False
            revoked = False
            for r in state.get("rules", []):
                if r.get("id") == rule_id:
                    found = True
                    # 时间失效语义：revoked 标记或 expiry 存在即视为已失效（旧数据无这两个字段 → 生效）
                    revoked = bool(r.get("revoked") or r.get("expiry"))
                    if args.type == "rule_added":
                        if not revoked:
                            raise ValueError(f"规则已存在且生效: {rule_id}（要改它请用 violation/hardened 事件，不要重复 rule_added）")
                        # revoked → 允许 re-add，走下方 re-add 分支（振荡由 audit 事件判定）
                    elif revoked:
                        raise ValueError(f"规则已失效: {rule_id}（已被撤销/过期，请先用 --type rule_added 重新声明）")
                    elif args.type in ("violation", "explanation"):
                        r["hits"] = r.get("hits", 0) + 1
                        r["last_hit"] = ts
                    elif args.type in ("rule_hardened", "rule_loosened"):
                        r["layer"] = "constraint" if args.type == "rule_hardened" else "instruction"
                    break
            if not found and args.type == "rule_added":
                state.setdefault("rules", []).append({
                    "id": rule_id, "text": args.event, "born": ts[:10],
                    "incident": args.event, "layer": args.layer,
                    "valid_time": ts,  # v4.4.0 时间失效：本次生效起点（born 保留首个出生日）
                    "hits": 0, "last_hit": None, "last_eval": None,
                })
            elif found and args.type == "rule_added" and revoked:
                # 撤销/过期后 re-add：清除失效标记、更新生效时间、重置命中（振荡留给 audit 判定）
                for r in state.get("rules", []):
                    if r.get("id") == rule_id:
                        r.pop("revoked", None)
                        r.pop("expiry", None)
                        r["valid_time"] = ts
                        r["hits"] = 0
                        r["last_hit"] = None
                        break
            elif not found:
                hint = "先用 --type rule_added 创建" if args.type != "rule_removed" else "无法移除（该规则不存在）"
                raise ValueError(f"规则 id 不存在: {rule_id}（{hint}）")

        if args.type == "rule_removed" and not rule_id:
            raise ValueError("rule_removed 必须带 --rule（否则无法定位要删的规则）")

        # 去重检查放在所有校验之后：失败事务不留指纹，避免污染窗口内后续合法记录
        if _dedup_seen(path, args.event, rule_id, args.type, args.dedup_window):
            print(f"去重跳过：{args.type}（窗口内已记录，未写入 STATE.json）")
            return

        events = state.setdefault("events", [])
        events.append({"ts": ts, "type": args.type, "rule": rule_id, "detail": args.event})
        if len(events) > MAX_EVENTS:
            print(f"WARN 事件数超过 {MAX_EVENTS}；events 永不归档（append-only 审计日志），如需控容看 growth.md「归档/compaction 语义」节", file=sys.stderr)

        if args.type == "rule_removed" and rule_id:
            # v4.4.0 时间失效：删除式回收 → 带 expiry 的查询过滤。
            # 规则保留在 rules[]（标 revoked+expiry），audit 按过期过滤；删后重加 = 振荡，由 audit 事件判定。
            for r in state.get("rules", []):
                if r.get("id") == rule_id:
                    r["revoked"] = True
                    r["expiry"] = ts
                    break
            else:
                raise ValueError(f"规则不存在: {rule_id}，无法移除")

        meta = state.setdefault("meta", {})
        meta["total_incidents"] = meta.get("total_incidents", 0) + 1
        if args.type == "rule_added":
            meta["rules_added"] = meta.get("rules_added", 0) + 1
        if args.type == "rule_removed":
            meta["rules_removed"] = meta.get("rules_removed", 0) + 1

        # v4.5.0 归档/compaction：每次写入后跑归档 pass（撤销/过期超阈值迁入 archived，events 不归档）
        archived_ids = _archive_pass(state, args.archive_days, ts)
        if archived_ids:
            print(f"归档 {len(archived_ids)} 条规则: {', '.join(archived_ids)}（events 保留，振荡仍可判）", file=sys.stderr)

        save_state_atomic(path, state)
        # 不回显事件原文（堵日志侧密钥泄露）
        extra = ""
        if rule_id:
            for r in state.get("rules", []):
                if r.get("id") == rule_id:
                    extra = f"（rule={rule_id}，hits={r.get('hits')}）"
                    break
        print(f"已记录 [{args.type}]{extra}")

    try:
        _locked(path, txn)
    except (OSError, ValueError, TypeError, json.JSONDecodeError) as e:
        print(f"写入失败: {e}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
