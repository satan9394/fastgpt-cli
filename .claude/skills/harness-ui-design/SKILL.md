---
name: harness-ui-design
description: >
  治理 AI 编码代理的界面产出，让页面、组件、看板与品牌视觉保持一致。
  Use when: 任务在定视觉/设计决策——配色/字体/间距/圆角/阴影/动效等设计 tokens、组件规范、
  设计系统、DESIGN.md、多页面一致性核对、界面视觉评审；给已有页面/组件定样式、搭看板视觉。
  Skip when: 只实现不碰视觉（页面逻辑、数据绑定、交互行为、接 API）→ 不触发任何领域 skill，
  确需开发治理再走 harness-dev；纯数据/后端/API/DevOps；需求→规格拆解走 harness-requirements；
  PR/变更评审走 harness-pr-review；不值得起 DESIGN.md 的小修直接做。
metadata:
  type: domain
  tags: [harness, ui, design, tokens, DESIGN.md, frontend]
  version: "4.11.0"
  author: satan9394
  displayName: Harness UI 设计（领域 skill）
  slug: harness-ui-design
  requires: [harness-engineering]
  license: MIT
  compatibility: "运行时无关（Claude Code / OpenAI Codex / 其他 agent CLI）"
---

# Harness UI 设计

薄入口。完整方法论与五步协议在核心 harness-engineering（同包根 `SKILL.md`），本 skill 只负责「界面领域的五组件落位」与域内约定。本 skill 只承接视觉/设计决策任务，跨域任务默认不主动承接。

防串味判断准则：**任务是否在定「视觉/设计决策」**（配色/字体/间距/圆角/阴影/动效/一致性/组件规范），而不是在实现功能。只有前者进本 skill；写逻辑、绑数据、接 API 不触发本 skill。

## When to Apply / Skip

**用**，当任务是：
- 定品牌视觉：配色、字体、间距、圆角、阴影、动效 tokens。
- 建/改设计系统、组件规范、DESIGN.md。
- 给已有页面/组件定样式，搭看板/仪表盘/信息面板的视觉。
- 核对多页面一致性、做界面视觉评审。

**不用**，当任务是：
- 只实现不碰视觉：页面逻辑、数据绑定、交互行为、接 API → 不触发任何领域 skill；确需开发治理/规则沉淀再走 harness-dev。
- 需求→规格→验收标准拆解 → harness-requirements。
- PR/变更评审协议 → harness-pr-review。
- 一次改两三个文件的小修、不值得起 DESIGN.md → 直接做。

路由样例（供 description-evals 增补）：正例「这个看板的配色统一一下」→ 本 skill；负例「给列表页加数据分页逻辑」→ 不触发本 skill。

## 启用/禁用

- **真实执行面**：运行时原生 skillOverrides（settings.json）与项目 CLAUDE.md 声明，决定是否发现/加载本 skill。
- **脚本解析层**：`.harness/config.json` 与 `HARNESS_SKILLS` env（解析顺序 env > repo > user > default）是 `scripts/skill-router.py` 的输入，输出启用名单报告；接线到发现层之前，按报告名单自查遵守。config 名单用目录短名（`ui-design`）。
- 默认不主动承接跨域任务；显式禁用 > 显式启用 > 默认档位。

## 方法（薄入口，委托核心）

按五组件落位，域内约定只此一份，不复制核心共享规则：

- **指令**：产出/维护 `DESIGN.md`（设计 tokens → 组件规范 → 页面三级）；tokens 用命名引用 `{colors.primary}`，**永不内联 hex**；一个品牌/域 = 一份文件，绝不按 color.md/typography.md 拆散（跨文件丢上下文）。
- **约束**：DESIGN.md 内建 Do's and Don'ts 反向护栏区（如「不引入第二强调色」「不药丸化 CTA」）；护栏从建议升约束的硬化判定走核心 `references/growth.md`。可参数化差异用命名 token 条目吸收（如 `motion:7`、`density:compact`），不拆 skill。
- **反馈**：视觉验证用「渲染/截图比对」命令，跑出客观结果再交付；0 匹配禁止编造，明说「无匹配，用内置默认」。
- **记忆**：DESIGN.md 是界面决策的持久化记忆；全局真源 + `pages/<page>.md` 局部覆盖（局部覆盖全局），覆盖必须有依据、不得吞前人决策；文档自曝 Known Gaps（不覆盖什么）。
- **编排**：跨域/多代理时走核心 `references/team-playbook.md` 委托契约，不自己发明交接格式。

执行要点：
1. 动手前先输出一行「Design Read」（本页基调 + 唯一强调色 + 字体个性）；缺品牌上下文/设计系统未知时必须先问，其余一次问完，不反复打断。
2. 优先级：Accessibility 最高、装饰性最低。本域暂无自有 references/，细则以 DESIGN.md 的 Do's and Don'ts 为准，不另行下沉。
3. 校验分两类：机械可计数的（tokens 无游离 hex、护栏逐条过）用计数；视觉类用截图比对。两者都贴「命令 + 返回 + 结果」，无匹配/不可数即明说，不编造。

## Common Rationalizations

| 借口 | 现实 |
|------|------|
| 先能用再美化，视觉以后再说 | 视觉拖到最后=全站不一致+整页返工；tokens 是前馈成本最低的约束，先落最小 tokens 表 |
| 页面小不用管设计 | 小改动正是 token 漂移入口；一次只改一个组件，新变体作独立条目 |
| 直接在代码里改色值更快 | 内联 hex=复制即漂移；一致性靠命名 token 引用，不靠人记住 |
| 参考大厂设计抄过来就行 | 复制把版权与审美不一致一起抄进来；用诚实标注的美学近似 |
| 可访问性用户没提就不做 | Accessibility 是优先级 CRITICAL，不是装饰项 |
| 多风格并排铺让用户挑 | 多风格=双倍漂移面；用 token 条目调 variance，不铺平行实现 |

## Red Flags（自检，命则排除）

- 付费门控：核心能力锁在 premium/basic、会员解锁 → 排除。
- 可疑模型/生成链路：不在稳定模型线、无文档支撑的可疑模型名 → 排除其生成链路。
- 营销计数当能力：把「N 技术栈 / N 配色」等统计量当设计能力 → 只信可执行机制，不信热度。
- star/fork 比例异常或增速与社区活跃度不符 → 只信可执行机制，不信热度。
- 声称未实现：只有 schema 没有文件的块库、手写映射注册表 → 不依赖未落地的声明。
- 同一设计关切两份副本（两套 color tokens、两份 DESIGN.md）→ 一份为准，见漂移即清理。
- 把「看起来对」当验证 → 必须有可核验门禁。

## Verification（可验证出口）

1. **DESIGN.md 存在**：含 tokens → 组件 → 页面三层，每层至少一个命名 token 条目。
2. **tokens 一致**：代码/组件中无游离 hex，全部 `{token}` 引用；schema/lint 校验命令可跑、结果贴出。
3. **反向护栏过检**：Do's and Don'ts 逐条核对，任何一条违背即不交付。
4. **交付物清单**：页面/组件清单 + 每条对应 DESIGN.md 出处。
5. **视觉门禁**：渲染/截图比对命令可跑，贴「命令 + 返回 + 结果」；门禁按核心 SKILL.md 第 4 步门禁四级执行。
6. **范围边界**：Known Gaps 写明不覆盖什么。

## 委托（调核心哪些部分）

- 完整流程/五步协议/入口判定：核心 `SKILL.md`。
- 护栏硬化判定、回收度量：核心 `references/growth.md`。
- 门禁四级 + 展示证据而非断言：核心 `SKILL.md` 第 4 步验证。
- 改 DESIGN.md/tokens 的受监督自我修改协议：核心 `SKILL.md` 六。
- 多代理/委托契约/配置分层：核心 `references/team-playbook.md`。
- 选用/禁用解析与路由碰撞检查：`scripts/skill-router.py`。
- 不复制核心内容；本 skill 只提供「界面的五组件落位 + 域内约定」。