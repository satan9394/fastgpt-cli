---
name: harness-pr-review
description: 评审代码与 PR：给带证据的 accept/request-changes 结论。Use when: 审代码/PR/MR、合入或合并前对改动做评审（review gate）、重大变更（迁移/删除/权限/数据）评审验收、被要求给 accept/request-changes 结论、第二视角复查改动。Skip when: 开发实现阶段、两三个文件的小修、纯 UI 交付验收、首次设计或需求澄清、搭建或配置门禁。
metadata:
  type: domain-skill
  tags: [review, pr, code-review, gate, acceptance, domain]
  version: "4.11.0"
  displayName: Harness PR / 评审（可禁用）
  slug: harness-pr-review
  disable-model-invocation: true
---

# Harness PR / 评审

评审域 skill：只负责「审」，不负责「写」。实现阶段请用 harness-dev，不要用本 skill。

**启用/禁用（诚实披露）**：本 skill 默认不自动按 description 触发——frontmatter 的 `disable-model-invocation: true` 是 Claude Code 原生字段（语义：阻止 Claude 自动加载本 skill，仍可被用户显式 `/harness-pr-review` 调用），前提是本 skill 进入 Claude Code 发现面。真正让 skill 离开可调用列表：① 用户级 `settings.local.json` 的 `skillOverrides`（Claude Code 原生发现层，格式按官方 settings schema，key 用 frontmatter name `harness-pr-review`）；② 项目 CLAUDE.md 写「本项目不用 harness-pr-review」。`.harness/config.json` 的 `disabled` 名单与 `HARNESS_SKILLS` env 是**配置声明层**，只被 `scripts/skill-router.py` 解析校验与漂移检测（配套核心「领域 skill 治理」章节后语义才完整）；只写 config 不写 skillOverrides = 只声明不生效。

## When to Apply / Skip

**Apply**（本域触发场景）：
- 代码评审：要审一个改动/PR/MR，要结论，不是要接着改。
- 合入门禁：合入/合并到主干前对改动做评审（review gate），或评审被要求给 accept / request-changes。
- 重大变更评审验收：多文件、跨模块、不可逆变更（迁移/删除/权限/数据）上线前验收。
- 第二视角：干活 agent 说「我做完了」，需要独立上下文复审确认。

**Skip**（别用本 skill）：
- 开发实现阶段：正在写代码、改 bug、跑测试——那是 harness-dev 的活。
- 首次设计/需求澄清、定义需求验收标准（不是验收改动）——那是 harness-requirements 的活。
- 纯 UI 交付验收——那是 harness-ui-design 的活。
- 两三个文件的小修——降级：不升级评审仪式，但至少走一级自检（跑一次测试/lint）。
- 搭建/配置门禁（不是跑评审门禁）——那是核心 harness-engineering 的活。

## 方法

薄入口，不重写评审协议，按下列五条执行并委托核心：

1. **独立上下文评审（调用本 skill = 执行第 4 级门禁）**：评审者用 fresh 独立上下文，只给「改动 + 验收标准」，不给干活过程的中间对话——干活的人不给自己打分。Claude Code 可用原生命令 `/code-review`（2.1.223+，`/review` 为别名）承载独立上下文审查；其输出必须过「只报正确性/需求缺口」过滤（对齐双轴边界，防整单照收），`ultra` 走云端有成本、门禁选级仍归 harness-dev；其他运行时仍用 fresh 子代理/独立会话，不依赖此命令。第 4 级边界见核心 `references/self-testing.md`，本 skill 不重述 ladder。
2. **双轴评审，逐轴汇报、不合并不重排**：轴 A 正确性（逻辑、边界、数据正确性、回归风险）；轴 B 需求缺口（对照原 issue/验收标准，需求满足了没有、漏没漏）。两轴各出结论，不在中途混合、不边审边改。
3. **只报正确性相关的缺口**：只报影响正确性或需求的缺口，其余视为可选（判据见核心 SKILL.md 第 4 步验证）——追每个发现就是过度工程化。
4. **门禁选级归实现侧**：第 1-4 级怎么选、何时升到第 4 级，是 harness-dev 的验证职责（高价值/不可逆变更才上第 4 级，小改动第 1 级自检足够）——门禁表见核心 `references/self-testing.md`，本 skill 不复制。
5. **grilling 设计树访谈**（仅当评审卡在「要改的决策不清晰」）：把要 stress-test 的决策映射成设计树，按前沿（前置已定的问题）逐轮一次问完，每题带推荐答案，环境事实自己查、决策留给用户。停止条件可操作：全部前沿节点已回答、无剩余未答前置问题即本轮结束（前沿为空 = 无静默假设）。示例：「该不该独立拆库」→ 前沿「仓储层是否拆」→「迁移方案」→「回滚路径」，每节点给推荐答案 + 环境事实自查项。本机制不依赖工具（来源见 grilling）；无法映射成可回答节点时降级为普通逐项提问，不硬套。

**展示证据而非断言**：评审结论必须带「命令 + 返回 + 结果」，不是「我觉得好了」——证据纪律见核心 `references/self-testing.md` 第一节，此处不重述。

## Common Rationalizations

| 借口 | 现实 |
|------|------|
| 「我自己审过了」 | 干活的人不给自己打分——需要独立上下文评审者，自己再读一遍不是独立评审 |
| 「小改动不用审」 | 小改动 ≠ 免审——降级但至少走第 1 级自检（跑一次测试/lint）；删除/权限/数据类小改动照样出大事 |
| 「测试过了就等于审过了」 | 测试覆盖预期路径，审的是预期之外——两件事都要做 |
| 「这是原型，不用审」 | 原型会变成产品；原型只降级门禁等级，不是免审 |
| 「每个发现都要修」 | 缺口只报正确性相关的，其余可选——追全部发现=过度工程化 |
| 「这个评审者和我一个会话，省事」 | 省掉的正是独立性——同上下文=自审，失去意义 |

## Red Flags（自检）

- 评审者用了干活的同一份上下文/同一会话 → 不是独立评审，是自审。
- 结论是「看着没问题」，没有一条「命令 + 输出」证据 → 未过 Verification。
- 双轴混合：一边发现一边改代码、两轴结论互相污染 → 重排。
- 报了一堆风格/品味/完美主义缺口，但没有正确性缺口 → 过度工程化信号。
- 验收标准写得不客观（「看起来能跑」）→ 先要求补可验证门禁再评。
- 缺口缺证据（「这个逻辑有问题」却给不出触发命令/行号）→ 回去补证据。

## Verification（可验证出口）

评审结论必须包含以下内容，缺一条不算完成：

1. **证据**：每条缺口带触发它的命令与输出（测试失败行、断言输出、PR diff 对应行号），不是断言；证据纪律细则见核心 SKILL.md 第 4 步验证。
2. **结论**：明确 PASS / FAIL（或 accept / request-changes），不含糊、不留「基本可以」。
3. **缺口范围**：只报正确性 / 需求缺口；风格类意见降级为可选提示或删除。
4. **双轴各报**：轴 A 正确性与轴 B 需求缺口各自给结论，不合并不重排。
5. **独立性自查**：本次评审上下文独立于实现者（fresh 会话/子代理）吗？不独立 → 重新走独立上下文。本 skill 的调用即第 4 级门禁，级数不再单独声明。

## 委托

本 skill 只做领域入口，不复制共享规则。评审协议本体在核心包：

- 独立评审边界、证据纪律（命令+输出、Seems right 永不通过）、门禁四级：核心 `SKILL.md` 第 4 步验证 + `references/self-testing.md`。
- 独立上下文评审的运行时实现载体：Claude Code 原生 `/code-review`（2.1.223+，`/review` 别名，ultra 云端深度审查）；其他运行时用 fresh 子代理/独立会话——这是运行时实现，非框架协议本身。
- 双轴评审（正确性/需求缺口）、独立上下文评审、grilling 设计树访谈：本域引入的领域机制，按上面「方法」执行；若与核心 references 冲突，以核心单一事实源为准。
- 启用/禁用、路由碰撞、漂移检测：`scripts/skill-router.py` + `.harness/config.json`（配置声明层，见顶部「启用/禁用」）。

引用不复制：核心 `references/` 是评审共享规则的单一事实源，本 skill 出现漂移时以核心为准。