---
name: fastgpt
description: >
  FastGPT CLI（fastgpt）—— AI 应用生命周期管理（kubectl/gh 风格）：知识库/数据集全生命周期、
  AI 应用部署、工作流、Agent 执行、RAG 检索、评测基准、配置与自省。
  Use when：要通过命令行管理 FastGPT 知识库（dataset/kb）、上传文档、检索（query search）、
  管理 AI 应用（app）、部署工作流（workflow）、执行 agent run、跑 evaluation/benchmark、
  查 status/health/version、读 schema 自省命令树、改 config。
  Skip when：只是用网页聊天；需要修改 FastGPT 服务端代码本身（那是 fastgpt-source 的活）。
metadata:
  type: domain
  domain: fastgpt
  tags: [fastgpt, cli, rag, knowledge-base, dataset, app, workflow, agent]
  version: "1.0.0"
  author: satan9394
  displayName: FastGPT CLI（Agent 生命周期管理）
---

# FastGPT CLI（fastgpt）

`fastgpt` 是 **Agent-native** 的命令行：默认输出稳定 JSON、数据只进 stdout、日志/进度/错误只进
stderr、错误统一 `{"error":{"kind","message","details"}}`。第一用户是 AI Agent，不是人。

**自省优先**：不确定命令/参数时先跑 `fastgpt schema --json`（命令树）或
`fastgpt schema commands list --json`（扁平命令清单），不要猜。

## 快速开始

```bash
fastgpt --help                        # 命令树
fastgpt schema commands list --json   # 全部命令路径（40 条）
fastgpt status                        # 运行状态（默认 JSON）
fastgpt kb list                       # 知识库列表（默认 JSON）
```

## 命令面（领域分组）

| 领域 | 命令 | 说明 |
|---|---|---|
| dataset | create / import ./docs / ls / delete | 数据集（= 知识库）生命周期 |
| kb | create / list / upload / get / delete | 知识库（FastGPT 里与 dataset 同源） |
| app | list / create / deploy / test / describe / delete | AI 应用生命周期 |
| workflow | deploy / list / test | 工作流（app type=workflow） |
| agent | run --input "..." | 执行 → `{answer, tokens, sources}` |
| query | search --kb <id> "问题" / chat | RAG 检索 / 内联对话 |
| evaluation / benchmark | run / compare | 评测与基准（预留） |
| export / backup | export / backup | 导出与备份（backup 是 export 别名） |
| config | show / path / set / init | 配置管理 |
| probe | status / health | 只读探测 |
| schema | tree / commands list | 自省 |
| （顶层） | status / health / version | 顶层只读 |

## 输出契约（必读）

- **默认即 JSON**：`fastgpt kb list` 直接输出 `{"items":[...],"total":N}`，无需 `--json`。
- **stdout/stderr 分离**：数据→stdout；进度/日志/警告→stderr；错误→stderr。
- **错误结构**：`{"error":{"kind":"validation|conflict|not_found|auth|backend|transport|internal","message":"...","details":{...}}}`。
  - 解析时先看 stdout 是否为合法 JSON；若是错误，读 stderr 的 `error.kind` 决定如何自纠。
- **有界输出**：列表命令 `--limit <n>`（默认上限）+ `--page <p>`（1 起）；`total` 是全集，`items` 是当前页。
- **流式**：大结果用全局 `--output jsonl`（放子命令前）：`fastgpt --output jsonl kb list --limit 1000`。
- **破坏性操作非交互**：`kb/app/dataset delete` 必须显式 `--yes`，否则返 `validation` 错误。

## 典型任务

### 1. 建知识库并上传文档（Phase 3 真实链路）

```bash
# 无后端时是空契约桩；配了 FASTGPT_SERVER_API_KEY + host 后走真实 HTTP
fastgpt kb create "产品文档"                       # → {"kb_id":"...","name":"产品文档","status":"created"}
fastgpt kb upload --kb <kb_id> ./docs/             # 进度进 stderr，结果 JSON 进 stdout
```

### 2. RAG 检索（需后端，--kb 必填）

```bash
fastgpt query search "如何配置 API 密钥" --kb <dataset_id> --limit 10
# → {"results":[{"score":0.91,"content":"...","source":"guide.md"},...]}
```

### 3. Agent 执行

```bash
fastgpt agent run --input "总结一下产品文档的部署步骤"
# → {"answer":"...","tokens":1234,"sources":[]}
```

### 4. 破坏性操作（幂等 + 确认）

```bash
fastgpt kb delete <kb_id>            # 报 validation 错误（缺 --yes）
fastgpt kb delete <kb_id> --yes      # 成功 → {"kb_id":"...","status":"deleted"}
```

### 5. 故障自纠

- 看到 `error.kind=validation` → 读 message/details 修正参数（如缺 `--yes`、缺 `--kb`）。
- `error.kind=backend` → 服务端问题（HTTP 4xx/5xx），检查地址/凭据/重试。
- `error.kind=auth` → 检查 `FASTGPT_SERVER_API_KEY`（仅环境变量，绝不落配置/日志）。

## 配置与鉴权

- 优先级：默认值 < 配置文件（`~/.fastgpt-cli/config.yaml` 或 `FASTGPT_CONFIG_DIR`）< 环境变量 `FASTGPT_*`。
- API 密钥**只从环境变量读**：`FASTGPT_SERVER_API_KEY`（后端）、`FASTGPT_CHAT_API_KEY`/`OPENCODE_API_KEY`（chat/agent）。
- `fastgpt config show` 永不打明文密钥，只报 `chat_api_key_set: true/false`。

## 边界

- 只操作 `fastgpt-cli/` 项目自身与远程 FastGPT 服务；不改 `fastgpt-source/`（参考只读）。
- 删除走 PowerShell 回收站，禁 rm。
- 收尾用 `scripts/handoff-log.py --append "<内容>" --verify "<结果>"` 更新 HANDOFF.md。
