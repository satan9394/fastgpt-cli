---
name: harness-dev
description: >
  开发治理：在开发场景里让 AI 编码代理守规矩——审计项目 harness 是否退化、
  按客观门禁验证改动、把反复犯的错沉淀成 STATE 规则、回收过期规则。
  Use when：搭或改 CLAUDE.md/AGENTS.md/hooks/CI 门禁；agent 反复犯同一个错想固化成规则；
  规则越堆越多想删减；审计开发项目 harness 是否退化；查 STATE 规则命中、30 天未触发、返工率。
  Skip when：单点小修、一次性探索、纯文档（含写 PR 描述）→ 直接干不触发；
  UI 改版（harness-ui-design）；需求梳理/规格（harness-requirements）；PR 评审（harness-pr-review）。
metadata:
  type: domain
  domain: dev
  tags: [harness, dev, governance, audit, gate, state]
  version: "4.11.0"
  author: satan9394
  displayName: Harness Dev（开发治理）
---

# Harness Dev（开发治理）

核心方法论在开发场景的薄入口。规则本体在核心 `SKILL.md` 与 `references/`，本 skill 只委托不复制。

**前置**：本 skill 100% 委托核心 harness-engineering 的 references/scripts。启用前先确认核心包已安装
（`<核心>/skill/SKILL.md` 与 `references/`、`scripts/audit.py` 在场）；未安装时本 skill 无委托对象，
先装核心再启用。

## When to Apply / Skip

**Apply（触发 = 有治理维度，不是「在写代码」）**：
- 搭 harness：新项目初始化开发规则（CLAUDE.md/AGENTS.md），或搭/改 hooks、CI 门禁。
- 审 harness：开发项目里 agent「变笨了」、怀疑 harness 退化，过一遍审计。
- 长/回收：agent 反复犯同一个错想固化；规则越堆越多想删减；查 STATE 命中/30 天未触发/返工率。

**Skip**：
- 单点小修（改 2-3 个文件、纯文档、有测试覆盖的 bugfix，判据见核心「一、何时不用」）、一次性探索、纯审美 → 直接干，不触发本 skill。
- 已搭 harness 的项目里改功能代码 → 按既有门禁走，不启动治理流程（除非改动涉及 harness 文件本身）。
- 写 PR 描述 → 纯文档小任务，直接干，不要路由到 pr-review。
- UI 改版/设计 → `harness-ui-design`；需求梳理/规格 → `harness-requirements`；PR 评审 → `harness-pr-review`。
- 无人值守定时巡检 → loop 工程，不在此域。

## 方法（薄入口，委托核心）

按核心 `SKILL.md` 五步协议走，本域重点在 audit / STATE / 规则沉淀 / 门禁。按项目状态选路径：

1. 全新项目 → 核心第 0.5 步最小闭环（环境就绪→垂直切片→接真实门禁→记第一条真实错误）。
2. 既有项目（审）→ 核心第 1 步盘点：`python scripts/audit.py <项目根>`，有 STATE 加 `--metrics STATE.json`。
3. 既有项目（长/沉淀）→ `references/growth.md` 触发信号 + `scripts/record-error.py` 直接入 STATE，不先全量盘点。
4. 选层/落地/验证/回收 → 核心第 2/3/4/5 步，每轮只动最痛一层。

实现角色 + 门禁角色都是本 skill 职责：干活（写码/搭 harness）与验证（verify）不混——干活的人不给自己打分，验证靠客观门禁与数据。

状态锚点 `HARNESS: dev active` 由核心 `skills/_meta/SKILL.md` 注入（M0；落地前本 skill 不自行维护）。
启用/禁用（声明层）：config 与 HARNESS_SKILLS 里写**目录短名**（`dev`/`ui-design`/…），不是 frontmatter 的 `harness-dev` 全名——写全名会被 skill-router.py 判「config 启用但磁盘缺失」漂移 NOT-OK。注意这是**配置声明层**（只被 skill-router.py 解析校验与漂移检测，不 gate 运行）；真实启用/禁用要落到运行时原生 skill 启用面（Claude Code 的 skillOverrides / 安装面）。解析/校验见委托表。

## Common Rationalizations（借口|现实）

| 借口 | 现实 |
|------|------|
| 我只是改代码，没搭 harness，不用管这套 | 已搭 harness 就按既有门禁走；没搭 harness 的单点小修直接做，别启动治理流程 |
| 项目只用 Claude Code，AGENTS.md 不用写 | 约束要落目标运行时真正消费的层（核心「二、约束组件」+「七、运行时中立」）：Claude 读 CLAUDE.md/hooks，Codex 才读 AGENTS.md；落错层 = 只是建议 |
| 规则数量没变，说明 harness 健康 | 数量不说明健康——看 STATE 数据：30 天未触发、返工率、同错重复次数 |
| 这个 bug 只改两个文件 | 单点小修有门禁就跑门禁，不为此搭新 harness；完成判定靠门禁不靠「觉得行」 |

共享判定（完成判定=客观门禁、建议≠约束、减法哲学、STATE append-only、返工率≥50% 先修门禁）见核心 `growth.md` 与核心第 4 步，此处不复制。

## Red Flags（自检）

- 单点小修/纯文档也启动 bootstrap→audit→选层全流程（把治理变成仪式）。
- 规则沉淀跳过 `record-error.py` 直接写进 CLAUDE.md（无出生证明，30 天后无法回收）。
- 把通用 harness 纪律抄进本 skill 正文（多副本必漂移——本 skill 自身就该被审计抓住）。
- 只改 `.harness/config.json` 不同步运行时发现层（skillOverrides/安装面），禁用不生效。

五组件同时上、凭空造规则、红线落错层等通用自检 → 核心 `SKILL.md` 第 2 步 + `references/harness-audit.md`。

## Verification（可验证出口）

1. 核心在场自检：`<核心>/skill/SKILL.md`、`references/`、`scripts/audit.py` 都存在；缺失 → 先装核心，非零退出。
2. 路由落地自测：`python scripts/skill-router.py --config .harness/config.json --skills <核心>/skills` → 启用名单与 _meta 展示一致、无漂移（退出码 0）；config 里是目录短名。
3. 审计出口：`python scripts/audit.py <项目根> --metrics STATE.json` → 退出码 0（无 NOT-OK）；基线 `--baseline` 存、周期 `--diff` 查退化。
4. 委托被消费实测：本 skill 引用的每条核心命令与判据实测一遍，输出「命令 + 返回 + 通过/失败」。
5. 验证门禁四级 + 数据正确性抽样 + 约束被消费 → 核心第 4 步判据（`references/self-testing.md`），此处不复制。
6. STATE 生长：30 天未触发规则已有删/留判定（证据：audit --metrics stale 名单）+ 返工率 <50%；若规则数上升而 violation 不降 → 跑约束被消费实测并查门禁管错对象（`growth.md` 判据）。
7. harness 变更：走核心「受监督自我修改协议」（检测→PR→验证→人在环批准），此处不复制。

## 委托（调核心哪些部分）

| 需要 | 调用核心 |
|------|---------|
| 前置依赖 | **核心 harness-engineering 包本身**（未装先装核心；委托悬空 = 无操作件） |
| 选用/禁用 + 漂移检测 | `.harness/config.json` + `scripts/skill-router.py`（config 校验/漂移/`--check-descriptions` 路由碰撞） |
| 五步协议全流程 | 核心 `SKILL.md`「四、五步协议」（第 0/0.5/1/2/3/4/5 步） |
| 完整审计清单 | `references/harness-audit.md` + `scripts/audit.py` |
| 生长/回收/STATE 度量 | `references/growth.md` + `scripts/record-error.py` + `templates/STATE.json` |
| 验证门禁四级 | `references/self-testing.md` + 核心第 4 步 |
| 指令层演化（多模块/膨胀） | `references/instruction-ladder.md` |
| 运行时落层（跨运行时） | 核心「七、运行时中立」+ `references/runtime-matrix.md` |
| 模式/默认严格度 | `references/mode-matrix.md`（单人默认） |
| 团队/多人 | `references/team-playbook.md` |
| 脚本/模板安装 | `scripts/bootstrap.py`、`templates/` |
| 受监督自我修改 + 隐私红线 | 核心「六、受监督自我修改协议」+ `references/growth.md`「隐私硬纪律」 |
| 状态锚点注入 | 核心 `skills/_meta/SKILL.md`（M0；落地前本 skill 不维护） |

共享规则只在核心 references 一份，本 skill 不复制——多副本必漂移。