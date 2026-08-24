# handoff-log Stop Hook 接线（方向②：交接档案强制化）

> 目标：会话结束时把「本轮动了哪些文件」自动追加进 `HANDOFF.md` 变更日志。
> **诚实边界**：hook 只能记录事实（动过哪些文件、用过哪些工具），记不了结论与验证——
> 追加文本显式标注「结论与验证待补」，由 agent/人 下次补记。这是半强制机制。

## Claude Code 接线（原生支持）

`.claude/settings.json` 的 `hooks.Stop` 段（与既有 PostToolUse record-error 并存）：

```json
{
  "hooks": {
    "Stop": [
      {
        "hooks": [
          {
            "type": "command",
            "command": "python .claude/hooks/handoff-log.py --from-transcript \"%s\""
          }
        ]
      }
    ]
  }
}
```

- `%s` 由 Claude Code 在 Stop hook 输入中替换为 transcript 路径（`transcript_path`）。
- `bootstrap.py --init` 已自动接线（v4.11.0）；本模板供手动/其他运行时参考。
- 幂等：matcher 已配置则跳过；用户已有 Stop hooks 不覆盖、只追加。

## 跨运行时（半强制，靠约定）

Claude Code 之外的运行时没有 transcript 自动注入：

```bash
python scripts/handoff-log.py --append "本轮做了什么" --verify "验证结果"
```

每次会话结束手动跑一次（或由 agent 在收尾时执行）。这是约定不是约束——
与所有跨运行时机制一致，如实标注。

## 常见问题

- transcript 解析失败会怎样？stderr 警告 + 不追加 + exit 0（best-effort，不阻塞会话结束）。
- 会话没动任何文件？不追加（避免噪音）。
- 想关掉自动记录？删除 settings.json 里对应 Stop 段即可，不影响 record-error hook。
