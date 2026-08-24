# notes/ —— Agent Notes 决策记录（四态生命周期）

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
