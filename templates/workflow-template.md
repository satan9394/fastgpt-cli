# Workflow 模板 — Claude Code 原生图编排基底（v4.8.1 路径 A + M3 checkpoint + M3 diff/合并）

> 用途：把**已知稳定流程**（提交→CI→评审→合入、门禁四级、三 agent 流水线）显式成可枚举、
> 可续跑（resumeFromRunId）、可审计的一等工件。探索性开发保持模型驱动 + 约束纪律，**不做全局图化**。
> 运行时中立：Claude Code=Workflow 工具（本模板），Codex=脚本 pipeline，harness 不引外部图框架。
> 装配：`bootstrap --install-scripts` 会把本文件复制进项目 `templates/`（含 `.harness-config.json` 等）。
> 消费方：Claude Code 会话内用 `Workflow` 工具跑脚本本体；模板是给「把流程固化成图」的脚手架。

## 何时用 / 何时不用

**用**：流程预先可知、拓扑稳定、需要可审计/可续跑（例：提交→CI→评审→合入、门禁四级判定、N 任务批量评审后汇总）。
**不用**：探索性开发、流程未知、纯对话——保留模型驱动，别画蛇添足。

## 骨架（复制即用）

```js
// workflow 脚本：已知流程 → 图。五字段契约写在每个 agent prompt 里。
export const meta = {
  name: 'example-pipeline',
  description: '示例：提交→独立评审→修订→合入门禁（五字段契约 + 结构化输出 + 可续跑）',
  phases: [
    { title: 'Plan', detail: '确定阶段划分' },
    { title: 'Execute', detail: '并行/流水线执行' },
  ],
}

// —— agent 结构化输出 schema（强制 agent 按契约返回，返回即校验）——
const FINDINGS_SCHEMA = {
  type: 'object',
  properties: {
    goal:        { type: 'string' },   // 目标
    completion:  { type: 'string' },   // 完成标准
    verify:      { type: 'string' },   // 验证命令
    open:        { type: 'array', items: { type: 'string' } }, // 未决问题
    next:        { type: 'array', items: { type: 'string' } }, // 下一步
  },
  required: ['goal', 'completion', 'verify', 'open', 'next'],
}

// —— 五字段 prompt 契约：worker 只靠这五字段当上下文，别把全文塞给它 ——
function fiveFieldPrompt(goal, completion, verify, open, next) {
  return [
    `# 目标\n${goal}`,
    `# 完成标准\n${completion}`,
    `# 验证命令\n${verify}`,
    `# 未决问题\n- ${open.join('\n- ')}`,
    `# 下一步\n- ${next.join('\n- ')}`,
    '',
    '只输出与目标相关的产物；未决问题没解决就显式留在「未决」，不要擅自拍板。',
  ].join('\n')
}

// —— pipeline：每项独立流经多级（无需 barrier；项 A 到后级时项 B 可还在前级）——
const ITEMS = ['apples', 'oranges', 'pears']
const results = await pipeline(
  ITEMS,
  (item) => agent(fiveFieldPrompt(`处理 ${item}`, '产出可验证的中间物', `pytest -k ${item}`, ['数据源？'], ['跑通后汇总']), {
    label: `process:${item}`, phase: 'Execute',
    schema: FINDINGS_SCHEMA,          // 结构化输出：返回即校验，无需解析
  }),
  (prev, item) => agent(fiveFieldPrompt(`独立评审 ${item} 的中间物`, '挑出缺口并给证据', 'node verify.mjs', prev.open, ['按缺口修订']), {
    label: `review:${item}`, phase: 'Execute', schema: FINDINGS_SCHEMA,
  }),
)

// —— parallel（barrier）：确实需要全部结果一起才有下一步时才用 ——
const all = await parallel([
  () => agent(fiveFieldPrompt('评审 A', '…', '…', [], ['…']), { label: 'A', phase: 'Execute', schema: FINDINGS_SCHEMA }),
  () => agent(fiveFieldPrompt('评审 B', '…', '…', [], ['…']), { label: 'B', phase: 'Execute', schema: FINDINGS_SCHEMA }),
])
// all.filter(Boolean)：单个 agent 失败/被跳过 → null，别裸用

// —— 汇总阶段（五字段收口：把子结果并成一份五字段交接文档）——
// v4.4.0：五字段 = 边契约从「worker 上下文文档」→「落盘工件也五字段结构化」——
// synth agent 用 FIVE_FIELD schema 返回，最终 return 的 goal/completion/verify/open/next 顶层齐全。
const summary = await agent(fiveFieldPrompt('汇总以上结果', '产出五字段交接文档（goal/completion/verify/open/next 齐全）', 'node verify.mjs', [], ['交给人在环批准']), {
  label: 'synthesize', phase: 'Plan',
  schema: FINDINGS_SCHEMA,   // 复用五字段 schema：返回即校验，汇总 agent 也必须给全五字段
})
log(`summary: ${summary.completion.slice(0, 120)}…`)
// 落 JSON：脚本本体 + 轨迹 journal 自动落盘 → 可 resumeFromRunId 续跑；result 顶层即五字段交接文档
return {
  goal: summary.goal,
  completion: summary.completion,
  verify: summary.verify,
  open: summary.open,
  next: summary.next,
  // results 保留各 agent 轨迹引用供审计
  results,
}
```

## 纪律

- **确定性优先**：控制流写死在脚本里（for/if/pipeline/parallel），别让模型临场决定下一步跑什么。
- **五字段 = 边契约（v4.4：worker 上下文文档 → 落盘工件也五字段结构化）**：每个 agent 的上下文只带五字段，
  最终 return 的 goal/completion/verify/open/next 顶层齐全，落盘 JSON 本身就是五字段交接文档。
- **每 agent 必有完成标准 + 验证命令**：没写验证命令的 agent 会被判定「无客观出口」，评审/门禁接不住。
- **人类检查点**：推送/发布/删数据等不可逆操作之前放人在环批准（五字段「未决/下一步」把决策留给人）。
- **可续跑（工具层缓存）**：中途断点用 `Workflow({scriptPath, resumeFromRunId})` 续跑——脚本 + args 不变的最长前缀命中缓存，只跑改动后的部分。
- **隐私红线**：任何跨边落盘继承既有红线（脱敏、密钥不入 git）；日志不打印 token/密钥。

## M3：跨边状态对象 + checkpoint（v4.5.0，受监督协议批准）

把「五字段 = 边契约」从落盘工件格式提升为**跨边共享状态对象 + checkpoint**——每个门禁级结果显式落成
状态对象（五字段 + gate_levels + 各 L 级结果 + 未决），checkpoint 允许从**应用层状态**断点续跑
（跨会话/跨机器，不受工具层 cache 生命周期限制）。

### 状态对象 schema

```jsonc
{
  "meta": { "name": "…", "scenario": "…" },
  "goal": "…", "completion": "…", "verify": "…", "open": [], "next": [],   // 五字段（边契约）
  "gate_levels": { "L1_draft": "…", "L2_verdict": {…}, "L3_gate_log": [], "L4_challenge": {…} },
  "gate_results": {                                                        // 各 L 级结果（可回放/可被后续阶段消费）
    "L1": { "status": "done", "result": {…} },
    "L2": { "status": "done", "result": {…} },
    "L3": { "status": "done", "result": {…} },
    "L4": { "status": "done", "result": {…} }
  },
  "checkpoint": {
    "created_at": "…", "resumed_from": null,
    "completed_levels": ["L1", "L2", "L3", "L4"],                          // 续跑时已完成的级跳过
    "pending": ["人在环批准"]
  }
}
```

### checkpoint 骨架（复制即用）

```js
// 续跑：args.initial_state 传入上一份状态对象 → 已完成的门禁级直接采用状态结果（不重跑）
const initial = args?.initial_state ?? null
const completed = new Set((initial?.checkpoint?.completed_levels ?? []))
function restore(key, fallback) {
  if (completed.has(key)) {
    const r = initial?.gate_results?.[key]?.result
    if (r !== undefined && r !== null) return r
  }
  return fallback
}

// 每级：已完成 → 从状态恢复；未完成 → 才跑 agent（本级结果写入 gate_results）
let L1 = restore('L1', null)
if (!L1) {
  L1 = await agent(fiveFieldPrompt('…', '…', '…', [], []), { label: 'L1:…', phase: 'Execute', schema: FINDINGS_SCHEMA })
}
let L2 = restore('L2', null)
if (!L2) {
  L2 = await agent('独立评估…', { label: 'L2:…', phase: 'Execute', schema: VERDICT_SCHEMA })
}
// …L3/L4 同理…

return {
  goal: L4?.goal, completion: L4?.completion, verify: L4?.verify, open: L4?.open, next: L4?.next,
  gate_levels: { /* 各 L 级轨迹 */ },
  gate_results: { L1: {status:'done', result:L1}, L2: {status:'done', result:L2}, /* … */ },
  checkpoint: { created_at: args?.timestamp ?? 'runtime', resumed_from: initial ? 'initial_state' : null,
                completed_levels: ['L1','L2','L3','L4'], pending: L4?.open ?? [] },
}
```

### 与 resumeFromRunId 的关系区别（可叠加）

| 维度 | M3 checkpoint | resumeFromRunId |
|------|--------------|-----------------|
| 层级 | **应用层状态**（五字段+门禁结果+未决） | **工具层缓存**（agent 调用结果按前缀缓存） |
| 恢复点 | 从状态对象 `completed_levels` 之后继续 | 从脚本最长未变前缀之后继续 |
| 跨会话/跨机器 | ✅ 状态对象是文件，任何会话可读 | ❌ cache 只在会话生命周期内 |
| 叠加 | **两者都用**：状态对象管逻辑续跑，resumeFromRunId 管工具调用缓存省 token | 同上 |

边界：不引外部库；不重写五组件；M3 是「状态显式化 + 可续跑」机制增量，`initial_state` 可选参数向后兼容
（不带 = 全级重跑的原行为）。持久化安全红线继承（脱敏、密钥不入 git）。
参考实现：`test/workflow/gate4-demo.workflow.js`（v4.5.0 M3 形态）。

## M3 深化：状态对象自动 diff / 冲突合并（v4.6.0 起，受监督协议已批准）

v4.5 = 状态可落盘 + 可续跑；v4.6 = 状态可 **diff**（对比两版 checkpoint）+ 可 **merge**（多分支同时续跑
成果合并为统一状态）。工具 `scripts/state-diff-merge.py`（纯标准库，diff 只读 / merge 纯函数，不覆盖输入）。

### diff 语义（对比两版状态对象 → 字段级差异清单）

- `completed_levels`：仅 A / 仅 B / 共有 / 并集
- `gate_results` 各 L 级：仅 A 有 / 仅 B 有 / 都有（都有时逐字段比对 result → 一致/分歧）
- `gate_levels` 轨迹 + 五字段 + `checkpoint` 元数据（created_at 用于定「较新」）

```
PYTHONUTF8=1 python scripts/state-diff-merge.py --diff branch-A.json branch-B.json
# → completed_levels.union / gate_results 各级 verdict（一致/分歧/仅 A/仅 B）+ 五字段差异
```

### 冲突合并规则（多分支同时续跑）

| 维度 | 规则 |
|---|---|
| `completed_levels` | **并集**（两分支成果都不丢） |
| `gate_results` / `gate_levels` | 按 L 级取「**较新且 done**」：仅一分支有 → 取该分支；都有且一致 → 任取；都有且 done 不同 → 取较新（created_at/级内时间戳）；无法定新旧 → **冲突升人判** |
| 五字段 `goal/completion/verify` | 仅当分支完成 `synth` 其五字段才是权威结论：恰一分支完成 → 取该分支；都完成且不同 → **冲突升人判**（不静默覆盖语义结论）；`open/next` → **并集去重** |
| 冲突处理 | 任一冲突 → `status: needs_human` + `conflicts[]`，**exit 1 且不写 --out**（不静默覆盖）；人在环选定后 `--override FIELD=A|B` 重跑合并 |

```
PYTHONUTF8=1 python scripts/state-diff-merge.py --merge branch-A.json branch-B.json --out merged.json --ts "2026-08-11 12:00"
PYTHONUTF8=1 python scripts/state-diff-merge.py --merge branch-A.json branch-B.json --out merged.json --override synth=B   # 人判后重跑
```

### 与 v4.5 checkpoint 的关系

v4.5 checkpoint 管「单链断点续跑」（从 completed_levels 之后继续）；v4.6 merge 管「多分支成果合并」
（两分支各自续跑后并回统一状态）。两者叠加：merge 出的统一状态本身带 checkpoint（completed_levels = 并集），
可继续用 v4.5 语义续跑。

边界：不引外部状态框架；不重写五组件；merge 不修改输入文件（纯函数，只写 `--out`）；回滚 = 删除输出文件；
持久化安全红线继承（脱敏、密钥不入 git）。
参考实现：`test/workflow/run-m3-diff-merge-demo.py`（确定性验证 6/6）+ `test/workflow/gate4-branch-{A,B}.json`。
提案：`plans/v46-phase2-m3-diff-proposal.md`（已批准 2026-08-11）。
