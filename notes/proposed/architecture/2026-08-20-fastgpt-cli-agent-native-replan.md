# Agent Note: FastGPT CLI 重规划——Agent-native 领域分组 + JSON 默认 + Python/Typer + AI 应用生命周期定位

Status: proposed

## Problem

现有 `fastgpt`（create-kb / upload-doc / query 平铺子命令 + cmd/internal/service/client 分层）是**标准的「人类命令行工具」**，
但本项目定位是「Agent 可调用的能力节点」（Agent Interface Layer）——让 Claude Code / Codex / OpenCode 自动管理 FastGPT。
当前命令面动词前置、输出人读为主、无自省、技术栈 Go，都不符合 Agent 第一用户的要求；且指导文件 v2 已锁定技术栈转向 Python+Typer。

## Proposal

按指导文件（唯一权威，冲突以它为准）执行重规划，分四条同时落地：

1. **定位修正（最重要）**：FastGPT CLI 的价值不是"让人不用网页聊天"，而是**「让 Agent / DevOps 自动管理 FastGPT」= AI 应用生命周期管理**（类比 kubectl/gh）。不做 `fastgpt chat` 主线；`chat` 仅作 `query chat` 内联检索能力保留。
2. **命令面改为 agent-native 领域分组**：`dataset` / `kb` / `app` / `workflow` / `agent` / `evaluation` / `benchmark` / `query` / `export` / `backup` / `schema` / `status` / `health` / `version`，动作放叶命令（`kb create`、`dataset import ./docs`、`agent run --input ...`）。命令表达高层能力，拒绝 POST /v1/... 的 API 包装。
3. **JSON 默认一等契约**：默认输出稳定 JSON、数据进 stdout、日志+进度+错误进 stderr；统一错误结构 `{error:{kind,message,details}}`；`--limit/--page` 有界；破坏性操作 `--yes/--force` 非交互。
4. **技术栈转向 Python + Typer**：`cli/`（命令组）、`api/`（真实 FastGPT API 客户端，自 Go internal/client 迁移语义）、`models/`、`output/`（统一 json/text/table/jsonl + stderr 规范）、`config/`（自 Go internal/config 迁移语义）。console_scripts 入口 `fastgpt = <pkg>.cli.main:app`，开发入口 `python -m <pkg>.cli.main`。

现有 Go 的 `internal/client(chat)`、`internal/config`（env 优先级）、`internal/service/errors.go`（429/5xx 重试）的命令语义与契约作为**迁移来源**，在 Python 里等价重建，不逐行搬运、不丢弃设计。

## Alternatives considered

- **保留 Go + Cobra 继续做人类 CLI**：Go 生态对 Agent tool / LLM / RAG 支撑弱，且已偏离 Agent 主方向；指导文件 §2.1 已明确裁决 Python+Typer 不摇摆。弃用。
- **平铺命令继续堆（create-kb/upload-doc/batch-query）**：违反"领域+动作"设计原则，#1 rule 禁止 `--action=create --type=kb`，也禁止动词+名词连写。弃用。
- **纯 Click**：功能等价，但指导文件指定 Typer；Typer 的 `--help` 自发现与类型标注更适合 Agent。采用 Typer。

## Acceptance criteria

- [ ] `python -m pytest` 通过、`ruff check` 无错误
- [ ] `fastgpt --help` 输出完整命令树（含 dataset/kb/app/workflow/agent/evaluation/query/schema/status）
- [ ] `fastgpt schema --json` 输出合法机器可读命令树
- [ ] `fastgpt kb list --json 2>/dev/null` 输出合法 JSON 且 stderr 无数据
- [ ] 现有 Go 的 chat/config/错误重试 契约语义已等价迁移到 Python（read 确认）

## Risks

- 从 Go 迁移到 Python 期间，旧 Go 目录仍保留（作迁移来源与对照），不删除；两套并存需说明主入口切到 Python。
- 未接真实后端前多数命令为契约层/空 items[] 输出，Phase 3 才接入真实 FastGPT API；需避免把占位误当已完成。
