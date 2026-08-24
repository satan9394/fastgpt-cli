# {PROJECT_NAME} — CLAUDE.md（路由器版骨架）

> 使用：复制本文件到项目根目录 → 替换全部 {占位符} → 按「一行一问：删掉会导致 agent 犯错吗？」删到最简。
> 本骨架适用：仓库内混多种类型工作。单项目用 templates/AGENTS.md-map.md。

## 工作区路由

收到任务后，先判断工作区，读取对应文件：

| 关键词 | 工作区 | 读取文件 |
|--------|--------|----------|
| {关键词A} | {工作区A} | {workspace}/{工作区A}/CLAUDE.md |
| {关键词B} | {工作区B} | {workspace}/{工作区B}/CLAUDE.md |

任务模糊 → 询问确认；涉及多工作区 → 依次读取。

## 核心命令

- 运行测试：`{test_cmd}`
- {常用命令2}：`{cmd2}`
- {常用命令3}：`{cmd3}`

## 架构不变量（不存在什么）

- 不存在 {不变量1}
- 不存在 {不变量2}
- 不存在 {不变量3}

## 指针

- 架构地图 → docs/ARCHITECTURE.md
- 设计决策 → docs/decisions/
- 活跃任务 → docs/exec-plans/

## 项目 Harness 指针（工作前必读）

本项目嵌入了 harness-engineering（v4.11.0）。开始工作前，先读下列文件了解项目治理信息：

- `.harness/manifest.json` → 嵌入清单（装了什么组件、验证结果）
- `STATE.json` → 规则与事故记忆（同错 ≥2 次 / 返工率 ≥50% 的信号源）
- `HANDOFF.md` → 当前目标 / 完成标准 / 验证命令 / 未决问题（跨会话接续权威）
- `notes/` → 决策记录（Agent Notes 四态：为什么这么做、放弃了什么）
- `docs/ARCHITECTURE.md` → 架构地图（模块职责 / 架构不变量 / 依赖层级）

读取优先级：`HANDOFF.md` 与 `.harness/manifest.json` 最先读，`STATE.json` 与 `docs/ARCHITECTURE.md` 按需读。
文件不存在说明该组件未嵌入（未跑 `bootstrap.py --init`），跳过即可。

## @human/@agent 双区块范例（团队项目用；单人项目可删 @human 段）

`@human` 段：人类队友要读的命令/约定/交接。`@agent` 段：agent 要读的陷阱/不变量。共用段都不标。

```markdown
@human
- 启动开发：`{dev_cmd}`；测试：`{test_cmd}`（唯一，别猜别的）
- 提交前看 `docs/handoffs/` 最新交接文档
- 新成员先读 HUMAN-ONBOARDING.md

@agent
- 陷阱：{陷阱1（来自一次真实事故）}
- 不变量：不存在 {不变量}，违反即 bug
```
