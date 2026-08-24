# 自动化错误捕获 hook（安全示例）

> 用途：把「agent 违规/返工」从人盯会话变成自动记录，喂给 STATE.json（生长回路的数据输入）。
> 示例按 Claude Code 的 hooks 格式写；其他运行时用等效机制。
> **安全原则（本模板是范例，不是让你照抄命令注入）**：
> 1. 事件文本永远走 stdin，**绝不拼进 shell command**（工具输出含 `"` / `$( )` 即 RCE）。
> 2. matcher 尽量收窄到具体违规命令，别用裸 "Bash"（否则每次 Bash 都触发假违规）。
> 3. 脚本路径必须是真实存在的绝对/相对路径（先把 record-error.py 复制到 .claude/hooks/）。

## 安装（把脚本装进项目）

```bash
# 方式一：用 bootstrap 一键安装
python <skill>/scripts/bootstrap.py --install-scripts --dir ./

# 方式二：手动
cp <skill>/scripts/record-error.py .claude/hooks/record-error.py
python .claude/hooks/record-error.py --init
```

## .claude/settings.json 配置片段（安全版）

```json
{
  "hooks": {
    "PostToolUse": [
      {
        "matcher": "Bash(git push*)",
        "hooks": [
          {
            "type": "command",
            "command": "python .claude/hooks/record-error.py --rule R01 --from-stdin"
          }
        ]
      }
    ]
  }
}
```

说明：
- **matcher 收窄到具体命令**（这里只匹配含 `git push` 的 Bash 调用），不是裸 `"Bash"`——否则每次 Bash 都触发假违规。
- 事件文本由 Claude Code 从 stdin 传入（`--from-stdin`），不经过 shell 拼接 → 无注入面。
- `--rule R01` 是示例：R01 必须在 STATE.json 里已存在（否则 record-error 报「规则 id 不存在」）。若违规不能确定归因，用 `--type rework` 不归因，别硬造规则 id。
- record-error.py 内置敏感事件拦截（手机/邮箱/密钥，含全角手机号与现代令牌格式）写入前拒绝，密钥/完整 PII 不会进 git 历史。

## 去重与防刷（v4.0.1 起内建 `--dedup-window`）

record-error.py **内置窗口去重**：`--dedup-window <秒>` 让同 `(type, rule, event)` 指纹在窗口内重复出现时跳过写入（不重复计数、不刷 hits）。默认 `0` = 关闭，保持「每次真实事件都记」的全量语义；高频 hook 场景建议开启。

```json
{
  "matcher": "Bash(git push*)",
  "hooks": [
    {
      "type": "command",
      "command": "python .claude/hooks/record-error.py --rule R01 --from-stdin --dedup-window 300"
    }
  ]
}
```

说明：
- 指纹 = `sha256(type|rule|event)`，去重文件（`STATE.json.dedup`）只存哈希不存原文——事件在写入前已被敏感拦截，密钥/PII 不会进任何文件。
- 去重是尽力而为：窗口内第 1 次必记，第 2 次起同指纹跳过。
- 低频项目（每天几次事件）可不开启，保留完整审计日志。
- **原则**：宁可多记一条，不靠伪造规则/刷 hits 凑数（record-error 会拒绝不存在的规则 id）。

## 落到纪律

- 捕获到的信号**只记录，不自动改 harness**。改规则必须走「受监督自我修改协议」（SKILL.md 五）。
- 周期（每 N 次事件或每月）跑 `python scripts/audit.py . --metrics STATE.json`，看命中分布和返工率。
