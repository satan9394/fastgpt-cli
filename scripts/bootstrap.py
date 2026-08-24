#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
harness-engineering bootstrap.py — 把 templates/ 骨架复制到目标目录并替换占位符。

用法：
    python scripts/bootstrap.py --type map --name mytool --dir ./mytool --runtime claude-code
    python scripts/bootstrap.py --type minimal --name cli-tool --dir ./mytool
    python scripts/bootstrap.py --install-scripts --dir ./mytool   # 把 audit/record-error 装进项目
    python scripts/bootstrap.py --init --dir ./mytool              # v4.11.0 一键嵌入（八件事一次做完）
    python scripts/bootstrap.py            # 交互式

类型：
    router   → templates/CLAUDE.md-router.md（多工作区）
    map      → templates/AGENTS.md-map.md（单项目，OpenAI 风格）
    role     → templates/agent.md-role.md（多角色 Writer/Evaluator）
    minimal  → 最小单文件指令（inline 生成）

运行时（--runtime）：
    claude-code → 写 CLAUDE.md（Claude Code 消费）
    codex       → 写 AGENTS.md（OpenAI Codex 消费）
    auto        → 探测：有 AGENTS.md/.github → codex；有 .cursor → cursor；默认 claude-code

--install-scripts：把 scripts/audit.py、scripts/record-error.py（及 state-diff-merge.py 等确定性工具）与
    templates/STATE.json 复制进目标项目，解决「skill 包内脚本在消费者项目里不存在」的断链；
    v4.2.0 起同时把 skills/{dev,ui-design,requirements,pr-review}/ 复制进
    <项目>/.claude/skills/<frontmatter-name>/（目录名=frontmatter name，幂等不覆盖），
    让领域 skill 进入运行时原生发现根、可被 skillOverrides 开关（C1 接线）。
    v4.7.0 起复制清单含 state-diff-merge.py（M3 状态对象 diff/合并工具，消费者自动装上）。

--init（v4.11.0 一键嵌入）：把 --type map/minimal + --install-scripts + hooks 接线 + 交接档案 +
    架构地图 + manifest 清单 + notes 决策记录 + 装完自检合并为一条命令。八件事：
    1. 探测运行时 → 写指令文件（CLAUDE.md / AGENTS.md / .cursor/rules）
    2. 装 10 脚本 + templates + STATE.json + .harness/config.json
    3. 接 4 领域 skill 进 .claude/skills/
    4. hooks 接线：写/合并 .claude/settings.json 的 PostToolUse（record-error，matcher 收窄示例）
       + Stop（handoff-log --from-transcript，会话结束自动追加 HANDOFF 变更日志事实记录）
    5. 生成 HANDOFF.md 占位 + docs/ARCHITECTURE.md 占位
    6. 建 notes/ 决策记录树（Agent Notes 四态：README + .archive-manifest.json）
    7. 装完自检：跑 audit.py . + skill-router.py --check-wiring
    8. 写 .harness/manifest.json 嵌入清单（含 notes 组件），输出"嵌入成功报告"

纪律：生成的骨架只含占位符，不允许生成「看起来像真规则」的伪规则。
纯标准库。
"""
import argparse
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

HERE = os.path.dirname(os.path.abspath(__file__))
PKG = os.path.abspath(os.path.join(HERE, ".."))
TEMPLATES = os.path.join(PKG, "templates")

# v4.2.0 C1 接线：bootstrap 复制这 4 个领域 skill 进消费者 .claude/skills/<frontmatter-name>/。
# 目录短名 -> 包内目录；frontmatter name 在复制时从 SKILL.md 读取（harness-dev 等）。
DOMAIN_SKILLS = ("dev", "ui-design", "requirements", "pr-review")

# v4.10.0 --init：hooks 接线默认 matcher（安全示例：收窄到具体违规命令，不裸 "Bash"）
INIT_HOOK_MATCHER = "Bash(git push*)"
INIT_HOOK_COMMAND = "python .claude/hooks/record-error.py --rule R01 --from-stdin --dedup-window 300"

# v4.11.0 --init：Stop hook（会话结束 → handoff-log 从 transcript 提取文件/工具，追加 HANDOFF 变更日志）
INIT_STOP_COMMAND = "python .claude/hooks/handoff-log.py --from-transcript \"%s\""

# v4.11.0 --init：脚本复制清单（与 install_scripts 保持一致）
INIT_SCRIPTS = ("audit.py", "record-error.py", "bootstrap.py", "gen-eval-fixtures.py",
                "skill-router.py", "gate-dag.py", "state-diff-merge.py", "harness-mcp.py",
                "note-lifecycle.py", "handoff-log.py")


def _merge_settings_hooks(out_dir):
    """把 record-error PostToolUse hook + handoff-log Stop hook 合并进 .claude/settings.json
    （幂等，不覆盖用户已有 hooks）。

    读已有 settings.json（可能含用户自定 hooks）→ 仅在对应配置未存在时追加 →
    原子写回。返回 (status, path) 供报告使用。
    """
    settings_path = os.path.join(out_dir, ".claude", "settings.json")
    existing = {}
    if os.path.isfile(settings_path):
        try:
            existing = json.load(open(settings_path, "r", encoding="utf-8"))
        except (ValueError, OSError):
            existing = {}
    hooks = existing.setdefault("hooks", {})
    post = hooks.setdefault("PostToolUse", [])
    for entry in post:
        if isinstance(entry, dict) and entry.get("matcher") == INIT_HOOK_MATCHER:
            post_ok = True
            break
    else:
        post_ok = False
        post.append({
            "matcher": INIT_HOOK_MATCHER,
            "hooks": [{"type": "command", "command": INIT_HOOK_COMMAND}],
        })
    stop = hooks.setdefault("Stop", [])
    stop_ok = any(
        "handoff-log.py" in " ".join(h.get("command", "") for h in e.get("hooks", []))
        for e in stop if isinstance(e, dict) and e.get("hooks")
    )
    if not stop_ok:
        stop.append({
            "hooks": [{"type": "command", "command": INIT_STOP_COMMAND}],
        })
    if post_ok and stop_ok:
        return "skipped", settings_path  # 都已配置，幂等
    os.makedirs(os.path.dirname(settings_path), exist_ok=True)
    with open(settings_path, "w", encoding="utf-8") as fh:
        json.dump(existing, fh, ensure_ascii=False, indent=2)
    return "configured", settings_path


def _write_json(path, obj):
    """原子写 JSON（ensure_ascii=False + indent=2，UTF-8）。"""
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(obj, fh, ensure_ascii=False, indent=2)


def _write_manifest(out_dir, project_name, runtime, instruction_file, installed_skills,
                    audit_exit, wiring_ok, checked_at):
    """写 .harness/manifest.json（嵌入清单：装了什么 + 验证结果）。返回路径。"""
    manifest = {
        "schema_version": 1,
        "harness_version": "4.11.0",
        "created_at": checked_at,
        "project": {"name": project_name, "type": "default", "runtime": runtime},
        "components": {
            "instruction": instruction_file,
            "scripts": list(INIT_SCRIPTS),
            "domain_skills": list(installed_skills),
            "state_json": os.path.isfile(os.path.join(out_dir, "STATE.json")),
            "harness_config": os.path.isfile(os.path.join(out_dir, ".harness", "config.json")),
            "hooks": {"configured": os.path.isfile(os.path.join(out_dir, ".claude", "settings.json")),
                      "file": ".claude/settings.json"},
            "handoff": "HANDOFF.md",
            "architecture": "docs/ARCHITECTURE.md",
            "notes": os.path.isfile(os.path.join(out_dir, "notes", "README.md")),
        },
        "verify": {"audit_exit": audit_exit, "wiring_ok": wiring_ok, "checked_at": checked_at},
    }
    manifest_dir = os.path.join(out_dir, ".harness")
    os.makedirs(manifest_dir, exist_ok=True)
    manifest_path = os.path.join(manifest_dir, "manifest.json")
    with open(manifest_path, "w", encoding="utf-8") as fh:
        json.dump(manifest, fh, ensure_ascii=False, indent=2)
    return manifest_path


def _self_check(out_dir, runtime):
    """装完自检：跑 audit.py + skill-router --check-wiring。返回 (audit_exit, wiring_ok)。"""
    audit_exit = 1
    wiring_ok = False
    scripts_dir = os.path.join(out_dir, "scripts")
    audit_py = os.path.join(scripts_dir, "audit.py")
    if os.path.isfile(audit_py):
        import subprocess
        try:
            r = subprocess.run([sys.executable, audit_py, out_dir], capture_output=True, timeout=120)
            audit_exit = r.returncode
        except Exception:
            audit_exit = 2
    router_py = os.path.join(scripts_dir, "skill-router.py")
    if os.path.isfile(router_py):
        import subprocess
        try:
            r = subprocess.run(
                [sys.executable, router_py, "--check-wiring",
                 os.path.join(out_dir, ".claude", "skills"),
                 "--config", os.path.join(out_dir, ".harness", "config.json")],
                capture_output=True, timeout=120)
            wiring_ok = r.returncode == 0
        except Exception:
            wiring_ok = False
    return audit_exit, wiring_ok


def init_embed(out_dir, name=None, runtime="auto", mode="single", modifiers=None):
    """v4.11.0 --init 一键嵌入：八件事一次做完。返回 0/1。"""
    os.makedirs(out_dir, exist_ok=True)
    if not name:
        name = os.path.basename(out_dir.rstrip("\\/")) or "myproject"
    if runtime == "auto":
        runtime = detect_runtime(out_dir)
    modifiers = list(modifiers or [])

    print("== harness-engineering v4.11.0 --init 一键嵌入 ==")
    print("目标目录: %s | 项目名: %s | 运行时: %s" % (out_dir, name, runtime))

    # 1) 指令文件（map 骨架；codex→AGENTS.md，cursor→.cursor/rules，默认 CLAUDE.md）
    if runtime == "codex":
        instruction_file = "AGENTS.md"
    elif runtime == "cursor":
        instruction_file = ".cursor/rules/project.mdc"
    else:
        instruction_file = "CLAUDE.md"
    text = load_template("map")
    mapping = {
        "PROJECT_NAME": name, "name": name, "workspace": name,
        "test_cmd": "pytest", "invariant": "本骨架尚无不变量，首次真实事故后替换",
    }
    body = replace_placeholders(text, mapping)
    out_path = os.path.join(out_dir, instruction_file)
    if not os.path.exists(out_path):
        os.makedirs(os.path.dirname(out_path), exist_ok=True)
        with open(out_path, "w", encoding="utf-8") as fh:
            fh.write(body)
        print("1/8 指令文件: %s（%d 行，骨架含占位符）" % (instruction_file, body.count("\n") + 1))
    else:
        print("1/8 指令文件: %s 已存在，未覆盖（幂等）" % instruction_file)

    # 2) 脚本 + templates + STATE + .harness/config
    install_scripts(out_dir, mode=mode, modifiers=modifiers, force_profile=False)

    # 3) 领域 skill 接线
    installed_skills, skipped_skills = install_domain_skills(out_dir)
    # 幂等重跑时 installed 为空：从 .claude/skills/ 实际发现回填，保证 manifest 记录真实接线
    if not installed_skills:
        discovered = []
        skills_root = os.path.join(out_dir, ".claude", "skills")
        if os.path.isdir(skills_root):
            for entry in sorted(os.listdir(skills_root)):
                if os.path.isfile(os.path.join(skills_root, entry, "SKILL.md")):
                    discovered.append(entry)
        installed_skills = discovered

    # 4) hooks 接线（PostToolUse record-error + Stop handoff-log）
    hook_status, hook_path = _merge_settings_hooks(out_dir)
    print("4/8 hooks 接线: %s（%s，PostToolUse record-error + Stop handoff-log）" % (hook_status, hook_path))

    # 5) HANDOFF + ARCHITECTURE 占位
    handoff_path = os.path.join(out_dir, "HANDOFF.md")
    if not os.path.isfile(handoff_path):
        _copy2_skip_same(os.path.join(TEMPLATES, "HANDOFF.md"), handoff_path, "HANDOFF.md")
    arch_dir = os.path.join(out_dir, "docs")
    os.makedirs(arch_dir, exist_ok=True)
    arch_path = os.path.join(arch_dir, "ARCHITECTURE.md")
    if not os.path.isfile(arch_path):
        _copy2_skip_same(os.path.join(TEMPLATES, "ARCHITECTURE.md"), arch_path, "docs/ARCHITECTURE.md")

    # 6) notes/ 决策记录树（Agent Notes 四态：README + 归档冻结清单）
    notes_dir = os.path.join(out_dir, "notes")
    notes_readme = os.path.join(notes_dir, "README.md")
    if not os.path.isfile(notes_readme):
        os.makedirs(notes_dir, exist_ok=True)
        _copy2_skip_same(os.path.join(TEMPLATES, "notes-README.md"), notes_readme, "notes/README.md")
    notes_manifest = os.path.join(notes_dir, ".archive-manifest.json")
    if not os.path.isfile(notes_manifest):
        os.makedirs(notes_dir, exist_ok=True)
        import datetime as _dt
        _write_json(notes_manifest, {"schema_version": 1, "created_at": _dt.date.today().isoformat(),
                                     "archived": {}})
    print("6/8 notes 决策记录: %s（README + .archive-manifest.json）" % os.path.relpath(notes_dir, out_dir))

    import datetime
    checked_at = datetime.datetime.now().isoformat(timespec="seconds")

    # 7) 装完自检
    print("7/8 装完自检: 运行 audit + skill-router --check-wiring ...")
    audit_exit, wiring_ok = _self_check(out_dir, runtime)

    # 8) manifest 嵌入清单
    manifest_path = _write_manifest(out_dir, name, runtime, instruction_file, installed_skills,
                                    audit_exit, wiring_ok, checked_at)
    print("8/8 manifest: %s" % manifest_path)

    print("\n== 嵌入成功报告 ==")
    print("指令文件: %s | 脚本: %d 个 | 领域 skill: %s" % (
        instruction_file, len(INIT_SCRIPTS), ", ".join(installed_skills) or "（无新增）"))
    print("hooks: %s（PostToolUse + Stop）| HANDOFF: %s | ARCHITECTURE: %s | notes/: %s" % (
        hook_status, os.path.relpath(handoff_path, out_dir), "docs/ARCHITECTURE.md", "已建"))
    print("audit 退出码: %s（0=健康，1=NOT-OK，2=参数错，3=drift）" % audit_exit)
    print("skill-router wiring: %s" % ("OK" if wiring_ok else "NOT-OK（声明 vs 发现漂移）"))
    print("manifest: schema v1 / harness v4.11.0 / %s" % checked_at)
    print("\n下一步: 编辑 HANDOFF.md 填目标与验证命令 → 跑 python scripts/record-error.py --init → 进生长回路")
    print("决策记录: python scripts/note-lifecycle.py new --class architecture --title \"你的决策\"")
    return 0


def _copy2_skip_same(src, dst, label=None):
    """shutil.copy2 的安全版：源==目标时跳过并提示，不再抛 SameFileError。

    消费者把 skill 副本装进自身（--install-scripts --dir <自身所在目录>）时，
    源目录与目标目录是同一个，copy2 会把每个文件拷给自己 → SameFileError
    （v4.1.0 已有）。自装场景下脚本/templates 已就地存在，跳过即可；
    STATE.json、.harness/config.json、hooks、领域 skill 接线仍正常安装。

    返回 True=已复制，False=跳过（源==目标）。
    """
    if os.path.abspath(src) == os.path.abspath(dst):
        print("跳过 %s: 源与目标相同（自装场景，就地已有）" % (label or dst))
        return False
    try:
        if os.path.samefile(src, dst):
            print("跳过 %s: 源与目标是同一文件（硬链接/符号链接）" % (label or dst))
            return False
    except OSError:
        pass  # 任一不存在则交由 copy2 正常报错
    shutil.copy2(src, dst)
    return True


def _frontmatter_name(skill_file):
    """读取 SKILL.md frontmatter 的 name 字段；解析失败返回 None。"""
    try:
        text = open(skill_file, "r", encoding="utf-8").read()
    except OSError:
        return None
    lines = text.splitlines()
    if not lines or lines[0].strip() != "---":
        return None
    for k in range(1, len(lines)):
        if lines[k].strip() == "---":
            break
        m = re.match(r"^\s*name\s*:\s*([^\s#]+)", lines[k])
        if m:
            return m.group(1).strip().strip("'\"")
    return None


def install_domain_skills(out_dir):
    """复制 4 个领域 skill 进 <out_dir>/.claude/skills/<frontmatter-name>/。

    目录名 = frontmatter name（harness-dev 等），与 skillOverrides 的 key 一致。
    幂等：已存在同名目录/SKILL.md 不覆盖（提示跳过）。
    返回 (installed, skipped) 两个列表。
    """
    installed, skipped = [], []
    dst_root = os.path.join(out_dir, ".claude", "skills")
    for d in DOMAIN_SKILLS:
        src_skill = os.path.join(PKG, "skills", d, "SKILL.md")
        if not os.path.isfile(src_skill):
            continue
        fm_name = _frontmatter_name(src_skill) or d
        dst_skill = os.path.join(dst_root, fm_name, "SKILL.md")
        if os.path.isfile(dst_skill):
            skipped.append("%s（已存在，未覆盖）" % fm_name)
            continue
        os.makedirs(os.path.dirname(dst_skill), exist_ok=True)
        _copy2_skip_same(src_skill, dst_skill, "领域 skill %s" % fm_name)
        installed.append(fm_name)
    return installed, skipped

MINIMAL = """# {name}

> 由 harness-engineering bootstrap 生成。从空文件开始，只记录真实犯过的错。

## 核心命令
- 运行测试：`{test_cmd}`
- 架构不变量（占位，首次真实事故后替换）：不存在 {invariant}

## 指针
- 架构地图 → docs/ARCHITECTURE.md（尚无则建）

> 占位：此文件还没有真实规则。第一次真实事故后，按 growth-loop 触发信号加一条，并用 scripts/record-error.py 记进 STATE.json 的 rules。
"""


def load_template(ttype):
    files = {
        "router": "CLAUDE.md-router.md",
        "map": "AGENTS.md-map.md",
        "role": "agent.md-role.md",
    }
    fname = files.get(ttype)
    if not fname:
        return None
    with open(os.path.join(TEMPLATES, fname), "r", encoding="utf-8") as fh:
        return fh.read()


def detect_runtime(out_dir):
    if os.path.isfile(os.path.join(out_dir, "AGENTS.md")) or os.path.isdir(os.path.join(out_dir, ".github")):
        return "codex"
    if os.path.isdir(os.path.join(out_dir, ".cursor")):
        return "cursor"
    return "claude-code"


def replace_placeholders(text, mapping):
    def sub(m):
        key = m.group(1)
        return mapping.get(key, m.group(0))
    return re.sub(r"\{([A-Za-z0-9_]+)\}", sub, text)


def install_scripts(out_dir, mode="single", modifiers=None, force_profile=False):
    """把 scripts/ + templates/ 复制进项目，解决相对路径断链。"""
    os.makedirs(out_dir, exist_ok=True)
    copied = []
    src_scripts = os.path.join(PKG, "scripts")
    dest_scripts = os.path.join(out_dir, "scripts")
    os.makedirs(dest_scripts, exist_ok=True)
    for f in ("audit.py", "record-error.py", "bootstrap.py", "gen-eval-fixtures.py", "skill-router.py", "gate-dag.py",
              "state-diff-merge.py", "harness-mcp.py", "note-lifecycle.py", "handoff-log.py"):
        s = os.path.join(src_scripts, f)
        if os.path.isfile(s):
            if _copy2_skip_same(s, os.path.join(dest_scripts, f), "scripts/%s" % f):
                copied.append(f"scripts/{f}")
    # 复制 templates/（record-error --init 与 bootstrap --type 骨架依赖）
    src_templates = os.path.join(PKG, "templates")
    if os.path.isdir(src_templates):
        dst_templates = os.path.join(out_dir, "templates")
        os.makedirs(dst_templates, exist_ok=True)
        for f in os.listdir(src_templates):
            if os.path.isfile(os.path.join(src_templates, f)):
                _copy2_skip_same(os.path.join(src_templates, f), os.path.join(dst_templates, f), "templates/%s" % f)
        copied.append("templates/")
    # 写 profile（模式选择器持久化）：读已存在，仅显式 --mode 或首次才覆盖
    if modifiers is None:
        modifiers = []
    dest_state = os.path.join(out_dir, "STATE.json")
    fresh_state = not os.path.isfile(dest_state)
    if fresh_state:
        _copy2_skip_same(os.path.join(PKG, "templates", "STATE.json"), dest_state, "STATE.json")
        copied.append("STATE.json")
    try:
        import json
        st = json.load(open(dest_state, "r", encoding="utf-8"))
        old_profile = st.get("meta", {}).get("profile") or {}
        if force_profile or not old_profile or old_profile.get("mode") is None:
            st.setdefault("meta", {})["profile"] = {
                "mode": mode, "modifiers": modifiers,
                "default_components": [], "changed": False,
            }
            st["schema_version"] = 2
            json.dump(st, open(dest_state, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
            copied.append("STATE.json profile")
            print("STATE.json profile 已写入（mode=%s）" % mode)
        else:
            # v4.11.0（评审 low-5）：区分「模板默认」与「真实已存在」，避免首跑误读为目录非全新
            origin = "模板默认" if fresh_state else "已存在"
            print("STATE.json profile 已就绪（%s，mode=%s）；显式 --mode/--reset-profile 才改"
                  % (origin, old_profile.get("mode")))
    except Exception:
        pass
    # 安装 .harness/config.json（领域 skill 选用/禁用模板；已存在则不覆盖）
    dest_harness = os.path.join(out_dir, ".harness", "config.json")
    if not os.path.isfile(dest_harness):
        os.makedirs(os.path.dirname(dest_harness), exist_ok=True)
        _copy2_skip_same(os.path.join(PKG, "templates", ".harness-config.json"), dest_harness, ".harness/config.json")
        copied.append(".harness/config.json")
    hooks = os.path.join(out_dir, ".claude", "hooks")
    os.makedirs(hooks, exist_ok=True)
    _copy2_skip_same(os.path.join(src_scripts, "record-error.py"), os.path.join(hooks, "record-error.py"),
                     ".claude/hooks/record-error.py")
    copied.append(".claude/hooks/record-error.py")
    _copy2_skip_same(os.path.join(src_scripts, "handoff-log.py"), os.path.join(hooks, "handoff-log.py"),
                     ".claude/hooks/handoff-log.py")
    copied.append(".claude/hooks/handoff-log.py")
    # v4.2.0 C1 接线：复制 4 个领域 skill 进 .claude/skills/<frontmatter-name>/（幂等）
    installed_skills, skipped_skills = install_domain_skills(out_dir)
    print("已安装脚本: " + ", ".join(copied))
    print(f"模式: {mode}" + (f" + {', '.join(modifiers)}" if modifiers else ""))
    if installed_skills:
        print("已接线领域 skill 进 .claude/skills/: " + ", ".join(installed_skills))
    else:
        print("已接线领域 skill: （无新增）")
    if skipped_skills:
        print("跳过（已存在不覆盖）: " + ", ".join(skipped_skills))
    print("现在可跑: python scripts/audit.py .  与  python scripts/record-error.py --init")
    print("接线校验: python scripts/skill-router.py --check-wiring .claude/skills --config .harness/config.json")


def _ask(prompt, default):
    """交互输入；stdin 关闭（CI/管道）时用默认值，不裸崩。"""
    try:
        v = input(prompt).strip()
    except EOFError:
        return default
    return v or default


def main():
    ap = argparse.ArgumentParser(description="harness-engineering 脚手架")
    ap.add_argument("--init", action="store_true", help="v4.11.0 一键嵌入：指令+脚本+skill+hooks+交接+notes+manifest+自检一次做完")
    ap.add_argument("--type", choices=["router", "map", "role", "minimal"], default=None)
    ap.add_argument("--name", default=None, help="项目名")
    ap.add_argument("--dir", default=None, help="输出目录（默认当前目录）")
    ap.add_argument("--runtime", choices=["claude-code", "codex", "cursor", "auto"], default="auto")
    ap.add_argument("--test-cmd", default="pytest", help="测试命令（minimal 用）")
    ap.add_argument("--invariant", default="本骨架尚无不变量，首次真实事故后替换", help="架构不变量（minimal 用）")
    ap.add_argument("--mode", choices=["single", "team", "production"], default=None,
                    help="启用模式：single=单人（默认）/ team=小团队 / production=公司生产（仅显式给出才覆盖已有 profile）")
    ap.add_argument("--oss", action="store_true", help="开源协作变体（红线落 CI）")
    ap.add_argument("--compliance", action="store_true", help="高合规变体（隐私升 NOT-OK）")
    ap.add_argument("--reset-profile", action="store_true", help="强制重写 profile（即使已存在）")
    ap.add_argument("--output-file", default=None)
    ap.add_argument("--install-scripts", action="store_true", help="同时把 audit/record-error 装进项目")
    args = ap.parse_args()

    if not args.dir:
        args.dir = _ask("输出目录 (默认 .): ", ".")
    out_dir = os.path.abspath(args.dir)
    os.makedirs(out_dir, exist_ok=True)

    if args.init:
        modifiers = [m for m, flag in (("oss", args.oss), ("compliance", args.compliance)) if flag]
        return init_embed(out_dir, name=args.name, runtime=args.runtime,
                          mode=args.mode or "single", modifiers=modifiers)

    if args.install_scripts and not args.type:
        modifiers = [m for m, flag in (("oss", args.oss), ("compliance", args.compliance)) if flag]
        install_scripts(out_dir, mode=args.mode or "single", modifiers=modifiers,
                        force_profile=(args.reset_profile or args.mode is not None))
        return 0

    if not args.type:
        args.type = _ask("骨架类型 [router/map/role/minimal] (默认 map): ", "map")
    if not args.name:
        args.name = _ask("项目名: ", os.path.basename(out_dir.rstrip("\\/")) or "myproject")

    runtime = args.runtime
    if runtime == "auto":
        runtime = detect_runtime(out_dir)

    if not args.output_file:
        if args.type == "map" and runtime == "codex":
            args.output_file = "AGENTS.md"
        elif runtime == "cursor":
            args.output_file = ".cursor/rules/project.mdc"
        else:
            args.output_file = "CLAUDE.md"

    if args.type == "minimal":
        text = MINIMAL
    else:
        text = load_template(args.type)
        if text is None:
            print(f"未知类型: {args.type}", file=sys.stderr)
            return 1

    # {workspace} 用项目名（相对可移植），不用绝对路径，避免换机失效
    mapping = {
        "PROJECT_NAME": args.name,
        "name": args.name,
        "workspace": args.name,
        "test_cmd": args.test_cmd,
        "invariant": args.invariant,
    }
    body = replace_placeholders(text, mapping)

    out_path = os.path.join(out_dir, args.output_file)
    # 路径穿越防护：拒绝写出 --dir 之外（跨盘时 commonpath 抛 ValueError，同样拒绝）
    try:
        same_root = os.path.commonpath([os.path.abspath(out_path), out_dir]) == out_dir
    except ValueError:
        same_root = False
    if not same_root:
        print(f"拒绝：输出文件 {args.output_file} 落在输出目录之外", file=sys.stderr)
        return 1
    if os.path.exists(out_path):
        ans = _ask(f"{out_path} 已存在，覆盖? [y/N]: ", "n")
        if ans.strip().lower() not in ("y", "yes"):
            print("已取消")
            return 0
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as fh:
        fh.write(body)
    lines = body.count("\n") + 1
    print(f"已生成 {out_path}（{lines} 行）→ 运行时消费: {runtime}")
    print("提醒：生成的只是骨架，未填占位符留给第一次真实事故。再跑 --install-scripts 装审计脚本。")

    if args.install_scripts:
        modifiers = [m for m, flag in (("oss", args.oss), ("compliance", args.compliance)) if flag]
        install_scripts(out_dir, mode=args.mode or "single", modifiers=modifiers,
                        force_profile=(args.reset_profile or args.mode is not None))
    return 0


if __name__ == "__main__":
    sys.exit(main())
