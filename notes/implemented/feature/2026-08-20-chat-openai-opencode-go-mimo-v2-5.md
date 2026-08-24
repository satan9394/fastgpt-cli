# Agent Note: chat 命令接入 OpenAI 兼容对话（OpenCode Go / mimo-v2.5）

Status: implemented

## Problem

FastGPT CLI 需要提供与 LLM 对话能力（`chat` 命令）。选型上，OpenCode Go 提供 OpenAI 兼容的 `/chat/completions` 端点，含 `mimo-v2.5` 等模型；协议与 OpenAI 标准兼容，接入成本低。需要一个 client → service → cmd 的完整调用链，并把端点/模型做成可配置。

## Decision

新增 `chat` 命令接入 OpenAI 兼容对话补全：
- 端点：OpenCode Go `https://opencode.ai/zen/go/v1`，模型默认 `mimo-v2.5`（可经 `--base-url`/`--model` 或配置 `chat.base_url`/`chat.model` 覆盖）。
- `internal/client`：新增 `Client` 接口的 `Chat(...)` 方法 + `ChatClient` HTTP 实现（Bearer 鉴权、超时、429/5xx 重试、`choices` 校验、`error` 字段透出）。
- `internal/service`：`ChatService` 依赖注入 `client.Client`，透传 `MaxTokens`/`Temperature`。
- `cmd/chat`：读取配置与运行时参数，密钥仅从环境变量读取（`OPENCODE_API_KEY` 或 `FASTGPT_CHAT_API_KEY`），支持 `--api-key` 临时覆盖但**不持久化**。

## Alternatives considered

- **直接对接小米官方的 `api.xiaomimimo.com`**：也是 OpenAI 兼容，但用户明确指定 OpenCode Go 端点（`sk-` 前缀密钥对应 OpenCode Go），且 OpenCode Go 聚合模型、按订阅计费更贴合本项目场景。若后续换官方端点，仅改 `config.set chat.base_url` 即可，无需改代码。
- **用 SDK 库**：本项目 client 面小，自研 HTTP 客户端 ≤150 行且完全可控、可测，弃用外部 SDK。

## Verification

- [x] `fastgpt chat` 命令出现在命令树，调用 `/chat/completions` 成功返回（实机验证 mimo-v2.5 应答）
- [x] `internal/client` ChatClient + `internal/service` ChatService 实现且单测通过
- [x] 密钥仅从环境变量读取，不落配置/日志/档案
- [x] `go build ./...`、`go vet ./...`、`go test ./...` 全过

## Consequences

- 密钥安全：`--api-key` 会出现在进程参数/shell 历史。文档与帮助已提示优先用环境变量；后续可在 config set 中禁止写入 chat 相关密钥字段。
- 思考模式：mimo-v2.5 默认思维链 `enabled`，自定义 `temperature`/`top_p` 会被后端强制为推荐值——本项目 `Temperature` 默认 0（不发送），规避该限制。
- 计费：每次 `chat` 调用消耗 OpenCode Go 订阅额度；非交互式单次调用，不引入循环消耗。
