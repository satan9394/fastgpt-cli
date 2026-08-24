# 独立复核 Workflow 模板 — 对版本化交付做独立上下文评审

> 用途：对 harness-engineering（或任何版本化迭代仓库）的一次版本交付做**独立复核**——评审者不参与实现，
> 用独立上下文读原始文件 + 跑命令，逐项核对目标书的完成判定，最后给出 PASS/FAIL + 遗留观察。
> 这是本项目最高频的多 agent 模式（v4.1/v4.3/v4.4 复核均为它），本模板把它参数化，避免每次新写脚本。
> 装配：`bootstrap --install-scripts` 会把本文件复制进项目 `templates/`。
> 与 `workflow-template.md` 的区别：workflow-template 是「把已知流程固化成图」的通用骨架；本文件是
> 「独立复核」这一特定流程的参数化专用模板（目标版本目录 + 复核清单）。

## 参数化输入（复制即填）

| 参数 | 含义 | 例 |
|------|------|-----|
| `TARGET_VERSION` | 待复核的版本目录（相对 harness-engineering/） | `v4.8.1` |
| `CHECKLIST` | 复核清单：阶段 → 验证命令/证据路径 → PASS 判据 | 见下方骨架 |
| `GATE_ON_FAIL` | 任一清单项 FAIL 时是否整体 exit 非 0（默认 true）——**可选扩展参数** | `true` |

> **GATE_ON_FAIL 与骨架的张力（v4.6 文档化）**：`GATE_ON_FAIL` 声明为参数，但当前骨架**不消费它**——
> 骨架只聚合 verdicts + 遗留观察并透传给主循环，不做自动 exit 判定。语义边界：该参数是**可选扩展**
> （未来某版在无人值守场景把 FAIL 项转成脚本退出码），当前骨架的 maker-checker 纪律不变——
> **结论归主循环**，模板产物是证据不是判定。用它在入口阶段做「参数替换」可以（如 `GATE_ON_FAIL=true` 写进
> 脚本常量），但不要宣称骨架会自动 gate——那属扩展未实现。

复核清单 = 「目标书完成判定」的机械化展开。每个条目 = 一条**可独立核验**的断言（读文件/跑命令/算数字），
不是「读报告信结论」。判据要写到「主循环不用猜」的程度——证据路径 + 期望值都写死。

## 骨架（复制即用）

```js
// workflow 脚本：独立复核一次版本交付。评审 agent 与实现者分离（不给自己打分）。
export const meta = {
  name: 'independent-review',
  description: `独立复核 ${TARGET_VERSION} 交付：逐项核对完成判定 + 跑命令实测（多并行评审，主循环兜底）`,
  phases: [
    { title: 'Review', detail: '每项清单一个独立评审 agent，读原始文件+跑命令' },
    { title: 'Verify', detail: '主循环对争议项实测兜底（跑同一命令对比）' },
  ],
}

// —— 评审结论 schema（每个清单项一条，最终聚合） ——
const VERDICT_SCHEMA = {
  type: 'object',
  properties: {
    item:     { type: 'string' },              // 清单项编号/名称
    status:   { type: 'string', enum: ['PASS', 'FAIL', 'PARTIAL', 'UNVERIFIABLE'] },
    evidence: { type: 'string' },              // 读了哪个文件/跑了什么命令/输出摘录
    claim:    { type: 'string' },              // 目标书/报告声称什么
    actual:   { type: 'string' },              // 独立核实到什么（不轻信报告）
    notes:    { type: 'array', items: { type: 'string' } },  // 遗留观察（low 级/阻断级）
  },
  required: ['item', 'status', 'evidence', 'claim', 'actual'],
}

// —— 清单：每项 = 独立评审 agent 的 prompt ——
// 填写时按目标书完成判定逐条展开；证据路径写绝对/相对都行，但判据必须可机械核验。
const CHECKLIST = [
  {
    item: '示例：阶段一产物落盘',
    prompt: (v) => `独立核实 ${v}/plans/v44-phase1-e1.md 声称的 thin 首过 5/5。读原始轨迹 JSON
      ${v}/test/benchmark/results/E1_D2_rep*.json，重算 rounds_to_pass 是否全=1、mm.yes 是否全 True；
      再跑 ${v}/test/benchmark/analyze.py 交叉印证。不轻信报告数字。输出 PASS/FAIL + 证据。`,
  },
  // ...按目标书补全。判据铁律：可机判就机判（读文件/跑命令/重算），别让评审 agent 只读报告。
]

// —— pipeline：每项独立评审（无需 barrier；项 A 复核时项 B 可并行） ——
const results = await pipeline(
  CHECKLIST,
  (c) => agent(c.prompt(TARGET_VERSION), {
    label: `review:${c.item}`, phase: 'Review', schema: VERDICT_SCHEMA,
  }),
  (prev, c) => {
    // —— Verify：对 FAIL/PARTIAL/UNVERIFIABLE 项，主循环兜底实测 ——
    // 此处由主循环（会话本体）对争议项重跑同一命令/重算数字，与评审 agent 的结论交叉对比。
    // 模板不做自动判定——把 prev（评审结论）透传给主循环，主循环决定是否采纳。
    return prev
  },
)

// —— 聚合：全清单 PASS 数 + 遗留观察（low 级不阻断，阻断级须列全） ——
const passed = results.filter(Boolean).filter((r) => r.status === 'PASS').length
const failed = results.filter(Boolean).filter((r) => r.status === 'FAIL').length
log(`独立复核: ${passed}/${CHECKLIST.length} PASS, ${failed} FAIL`)
return {
  target_version: TARGET_VERSION,
  summary: { total: CHECKLIST.length, passed, failed, unverifiable: results.filter(Boolean).filter((r) => r.status === 'UNVERIFIABLE').length },
  verdicts: results.filter(Boolean),
  // 遗留观察：主循环收口（low 级记录、阻断级给修复清单）——本模板不做「复核通过」自判，
  // 那是主循环的职责；模板只产出证据。
  next: ['主循环对 FAIL/PARTIAL 项实测兜底，收口遗留观察后写复核结论'],
}
```

## 纪律

- **评审者不给自己打分**：本模板的 agent 全部是独立上下文评审；实现者（生成/修订 agent）不得出现在评审里。
- **读原始文件 + 跑命令，不轻信报告**：每项判据优先「可机判」——重算数字/跑同一命令/读轨迹 JSON；
  报告文字只当线索，不当结论。
- **诚实标注**：跑不动（网关 401/命令缺失/数据不可复现）→ `UNVERIFIABLE` + 注明原因，不硬凑 PASS。
- **遗留观察分级**：`notes` 里区分 low（文档/标注级）与阻断级；阻断级必须给出具体 FAIL 证据。
- **「复核通过」由主循环宣告**：模板产物是证据（verdicts + notes），不是结论；结论归主循环（maker-checker）。
- **按版本参数化**：`TARGET_VERSION` 一换，清单从上一版复核清单复制后按目标书改判据，即再生一份新复核清单
  （自举验证：v4.5 复核清单 = v4.4 复核清单 + v45 目标书判据）。
