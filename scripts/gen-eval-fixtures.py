#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
gen-eval-fixtures.py — 生成 eval 用的夹具（sample-app / sample-decay）。

为什么：eval 判据依赖可复现的输入。夹具用「相对今天」的时间戳生成，
保证任何时候跑 eval 结果一致（不受墙钟漂移影响），且外部用户可自建夹具复现 eval。
用法：
    python scripts/gen-eval-fixtures.py --out <目标目录>
    在 <目标目录> 下生成 sample-app/ 与 sample-decay/
"""
import argparse
import datetime
import json
import os
import sys

if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass


def gen_sample_app(out):
    """242 行 CLAUDE.md（6 对矛盾规则 + 200 条冗余占位）+ 含 PII 格式的样本。"""
    d = os.path.join(out, "sample-app", "data")
    os.makedirs(d, exist_ok=True)
    rules = [
        "1. 任何时候都不允许使用 fetch 直接请求外部 API，必须走 service 层",
        "2. 在紧急情况下允许直接在组件里 fetch 第三方接口，以节省时间",
        "3. 提交代码前必须运行 lint",
        "4. 提交代码前不需要运行任何检查，直接提交即可",
        "5. 提取联系人时保存完整姓名与手机号，方便后续联系",
        "6. 所有新功能都要先写需求文档",
        "7. 使用 pip 管理依赖",
        "8. 安装新依赖前直接 pip install 即可，不需要确认",
        "9. 数据库迁移用 alembic",
        "10. 数据库结构变更直接改 models.py，不用迁移工具",
        "11. 错误处理统一用 AppError",
        "12. 错误处理可以随意 print，不重要",
        "13. 日志输出到 stdout",
        "14. 生产环境日志输出到文件",
        "15. 代码注释用中文",
        "16. 代码注释用英文",
    ]
    head = [
        "# sample-app — CLAUDE.md\n", "\n", "> 测试夹具。故意包含多种 harness 问题供审计与 eval 检测。\n", "\n",
        "## 核心命令\n", "- 启动：`python main.py`\n", "- 提取：`python extract.py`\n", "\n",
        "## 架构不变量\n", "- 不使用 ORM，所有数据库操作用原始 SQL\n", "- UI 层不直接访问数据库\n", "\n", "## 开发规则\n", "\n",
    ]
    pads = ["- 冗余规则占位 %d：这条规则没有任何信息量，纯粹为了撑行数\n" % i for i in range(200)]
    # 组装：head + 规则 + 占位 + 尾部，每行都带 \n
    lines = head + [r + "\n" for r in rules] + pads + ["## 详细规则（占位，撑行数用）\n"]
    body = "".join(lines)
    # 保证 audit 读到的行数（count("\n")+1）恰好 242：换行符数 = 241（head+rules+pads+tail 已 230…补齐）
    cur = body.count("\n")
    while cur < 241:
        body += "- 补足行 %d：占位\n" % cur
        cur = body.count("\n")
    while cur > 241:
        # 去掉最后一条 pad
        idx = body.rfind("- 冗余规则占位")
        if idx < 0:
            break
        cut = body.rfind("\n", 0, idx)
        body = body[:cut] + "\n"
        cur = body.count("\n")
    with open(os.path.join(out, "sample-app", "CLAUDE.md"), "w", encoding="utf-8") as fh:
        fh.write(body)
    with open(os.path.join(d, "samples.txt"), "w", encoding="utf-8") as fh:
        fh.write("=== 提取样本（虚构号码，仅格式合法）===\n"
                 "项目：A市某道路工程 联系人：张工 电话：13900000001\n"
                 "项目：B县水利工程 联系人：李工 电话：18800000002\n"
                 "项目：C区房建工程 联系人：王工 电话：15900000003 邮箱：test@example.com\n"
                 "项目：D市桥梁工程 联系人：陈总 电话：13600000004\n"
                 "=== 说明：以上号码为虚构，仅用于审计脚本演示 ===\n")
    print(f"已生成 {os.path.join(out, 'sample-app')}")


def gen_sample_decay(out):
    """STATE.json：2 条 40 天未命中（含 1 条从未触发的成年规则）+ 1 条近期命中 + 事件日志（与元数据一致）。"""
    d = os.path.join(out, "sample-decay")
    os.makedirs(d, exist_ok=True)
    today = datetime.date.today()
    old = (today - datetime.timedelta(days=40)).isoformat()
    recent = (today - datetime.timedelta(days=2)).isoformat()
    events = []
    for i in range(10):
        events.append({"ts": f"{(today - datetime.timedelta(days=9-i))} 10:0{i}", "type": "rework", "rule": None, "detail": f"返工 #{i}"})
    for i in range(7):
        events.append({"ts": f"{(today - datetime.timedelta(days=9-i))} 11:0{i}", "type": "violation", "rule": "R01", "detail": f"违规 #{i}"})
    state = {
        "schema_version": 2, "project": "sample-decay", "born": (today - datetime.timedelta(days=120)).isoformat(),
        "rules": [
            {"id": "R01", "text": "用 pnpm 不用 npm", "born": (today - datetime.timedelta(days=115)).isoformat(),
             "incident": "lock 冲突", "layer": "instruction", "hits": 13, "last_hit": old, "last_eval": None},
            {"id": "R02", "text": "组件不直连数据库", "born": (today - datetime.timedelta(days=100)).isoformat(),
             "incident": "越权查询", "layer": "constraint", "hits": 3, "last_hit": old, "last_eval": None},
            {"id": "R03", "text": "提交前跑 lint", "born": (today - datetime.timedelta(days=60)).isoformat(),
             "incident": "lint 失败合入", "layer": "instruction", "hits": 2, "last_hit": recent, "last_eval": None},
            {"id": "R04", "text": "保留历史方案文档", "born": (today - datetime.timedelta(days=70)).isoformat(),
             "incident": "决策不可回溯", "layer": "memory", "hits": 0, "last_hit": None, "last_eval": None},
        ],
        "events": events,
        "meta": {
            "total_incidents": len(events), "rules_added": 4, "rules_removed": 0, "last_rework_rate_30d": None,
            "profile": {"mode": "single", "modifiers": [], "default_components": [], "changed": False},
        },
    }
    with open(os.path.join(d, "STATE.json"), "w", encoding="utf-8") as fh:
        json.dump(state, fh, ensure_ascii=False, indent=2)
    with open(os.path.join(d, "CLAUDE.md"), "w", encoding="utf-8") as fh:
        fh.write("# sample-decay — 退化夹具\n- 运行测试：`pytest tests/ -v`\n- 此 harness 正在腐烂：多条规则 40 天未触发，最近 30 天返工率 ≥50%。\n")
    print(f"已生成 {d}（stale 规则：R01,R02（40 天未命中）+ R04（成年未触发）；R01 事件与 hits 一致）")


def main():
    ap = argparse.ArgumentParser(description="生成 eval 夹具")
    ap.add_argument("--out", default=".", help="输出目录（默认当前目录）")
    args = ap.parse_args()
    os.makedirs(args.out, exist_ok=True)
    gen_sample_app(args.out)
    gen_sample_decay(args.out)


if __name__ == "__main__":
    main()
