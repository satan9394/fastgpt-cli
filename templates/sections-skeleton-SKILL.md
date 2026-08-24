# sections/ 渐进披露骨架模板（v4.7.0 M2）

> 使用：把本文件内容复制到 `skills/<domain>/SKILL.md`（或核心 `skill/SKILL.md`），替换 `{占位符}`。
> 适用：**SKILL.md 已超长**（正文 > 500 行 / 指令文件膨胀）时的渐进披露骨架。
> 纪律：**骨架保留核心纪律，细节按节拆进 sections/ 渐进披露**；不重写既有 SKILL.md 结构（五组件接口不动）。
> 校验：`python skill/scripts/verify-integrity.py --root skill --expect-version <版本>` 会自动核对
>       frontmatter version 与 sections/ 引用文件是否存在（无 sections 声明则跳过）。
> 参考：`templates/sections-README.md`（何时拆 / 拆哪些节 / 引用方式 / 边界）。

```markdown
---
name: harness-{domain}
description: >
  一句话表述这个 skill 做什么（第三方视角，扁平总结，不写流程）。
  Use when: {触发场景清单，只写本域触发词，绝不写流程步骤}。
  Skip when: {反触发场景，防跨域误触发}。
metadata:
  type: {domain|methodology}
  tags: [{harness, {domain}, ...}]
  version: "{version}"          # 与 skill/.skillhub.json 的 version 一致
  author: {author}
  displayName: {显示名}
  slug: {slug}
  # 渐进披露声明：sections/ 下按节拆分，条目为相对本 SKILL.md 所在目录的路径
  sections:
    - sections/INDEX.md
    - sections/01-core-discipline.md
    - sections/02-method-detail.md
    - sections/03-scope-tables.md
---

# Harness {domain}

## 简介

{3-5 句定位：这个 skill 管什么、在五组件/五步协议里处于哪个位置、与核心的关系。
 骨架只保留定位与指针，不展开实现细节。}

## sections/ 索引（渐进披露入口）

- `sections/01-core-discipline.md` — 核心纪律（为什么这么干）
- `sections/02-method-detail.md` — 方法细节（五步协议在本域的展开）
- `sections/03-scope-tables.md` — 范围判定表（When to Apply / Skip）

> 阅读顺序：先读本骨架的简介 + 索引，按需进入对应节；不要一次性读完所有 sections/。

## 核心纪律（骨架内只留一句话，详情在 sections/）

- **建议和约束是两回事**，约束必须落目标运行时真正消费的那一层（详见 `sections/01-core-discipline.md`）。
- **能单不多**：能用单 agent 解决的不用多 agent；只有评测证明不足才加复杂度。
- **减法哲学**：每条多余规则都在稀释重要规则的权重。

## 委托（调核心哪些部分）

| 需要 | 调用核心 |
|------|---------|
| 完整协议 | 核心 `SKILL.md`「四、五步协议」 |
| 脚本 | `scripts/audit.py`、`scripts/record-error.py`、`scripts/skill-router.py` |
| 共享 references | `references/{growth|harness-audit|...}.md`（引用不复制） |
```

## sections/INDEX.md 示例（同目录建 `sections/` 后复制）

```markdown
# sections/ 索引 — {domain}

| 节 | 主题 | 何时读 |
|----|------|--------|
| 01-core-discipline.md | 核心纪律 | 第一次上手必读 |
| 02-method-detail.md | 方法细节 | 动手执行时按步骤读 |
| 03-scope-tables.md | 范围判定表 | 判断「用不用本 skill」时查 |
```

## 使用说明

- **骨架保留核心纪律**：简介 + 索引 + 一句话核心纪律 + 委托表留在骨架里，保证入口一眼能定位；
  实现细节、长表格、长清单拆进 `sections/` 各节文件。
- **渐进披露**：模型/读者先看到小骨架，按需进入对应节，避免一次灌入全部上下文。
- **不重写既有 SKILL.md 结构**：本骨架只改「正文瘦身 + sections/ 拆分」的承载方式，
  不新增/不重排五组件（指令/约束/反馈/记忆/编排）接口，不改变 description 双要素契约。
- **版本一致**：frontmatter `version` 与 `skill/.skillhub.json` 的 `version` 保持一致；
  改动版本号时两处同步，`verify-integrity.py --expect-version <版本>` 会核对。
- **引用即校验**：frontmatter `sections:` 数组和 `sections/INDEX.md` 里的 `.md` 链接都会被
  `verify-integrity.py` 检查是否存在——拆了节就把它登记进索引，删了节就同步删引用。

## 完成检查

- [ ] frontmatter 含 `version` + `sections` 数组，version 与 .skillhub.json 一致
- [ ] `sections/` 目录存在，`INDEX.md` 列出全部节文件，节文件均已创建
- [ ] 骨架正文 < 150 行；细节都在 `sections/`（不把长文留回骨架）
- [ ] 五组件接口、description 双要素契约未改动（只换承载方式）
- [ ] 跑 `python skill/scripts/verify-integrity.py --root skill --expect-version <版本>` 无 sections 相关 NOT-OK
