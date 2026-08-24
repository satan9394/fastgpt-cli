# Agent Note: FastGPT CLI 分层架构：Command → Service → Client

Status: implemented

## Problem

FastGPT CLI 需要把 labring/FastGPT 的 Web 能力封装成命令行工具，涉及建库、文档管理、检索三类核心操作。
若把所有业务逻辑堆在 Cobra 命令里，命令会迅速膨胀、难以测试，且换底层传输（gRPC → REST）时要改上层。
需要一个可测试、可替换依赖的分层结构，避免命令与 FastGPT 服务端细节耦合。

## Decision

采用三层架构，严格单向依赖：`cmd`(Cobra 命令) → `internal/service`(业务逻辑) → `internal/client`(FastGPT API 访问)，公共类型与工具放在 `pkg/`。
- `cmd/`：只做参数解析、标志绑定、结果格式化输出，不碰业务。
- `internal/service/`：KB / Doc / Query 服务，持有一个 `client.Client` 接口，便于注入 mock 测试。
- `internal/client/`：定义 `Client` 接口并实现 FastGPT Server 访问（Day 5-7 落地真实调用）。
- `internal/config/`：配置读写（Day 3-4）。
- 根命令暴露三个核心子命令：`create-kb`、`upload-doc`、`query`（本阶段为占位逻辑）。

## Alternatives considered

- **扁平单文件命令**：把逻辑全写进 `main.go`/`root.go`。开发快但不可测试、不可扩展，违反分层目标，弃用。
- **Service 直接 new 具体 client**：省去接口依赖注入。但无法在测试中替换 mock，耦合服务端实现，弃用。

## Verification

- [x] `cmd/`、`internal/{service,client,config}`、`pkg/{utils,types}` 分层目录齐备
- [x] `go build ./...` 通过、`go vet ./...` 无错误
- [x] `go run . --help` 展示含 create-kb/upload-doc/query 的完整命令树
- [x] Service 层通过 `client.Client` 接口注入依赖

## Consequences

- 当前为占位逻辑，接口方法尚未定型；Day 5-7 接入真实 API 时接口可能需要演进，属预期内的迭代成本。
- `pkg/` 为可导出包，若过早暴露不稳定 API 会形成对外契约；本阶段保持最小导出面。
