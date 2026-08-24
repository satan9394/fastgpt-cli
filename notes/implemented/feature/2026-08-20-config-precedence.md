# Agent Note: 配置管理：默认值 < 配置文件 < 环境变量优先级

Status: implemented

## Problem

FastGPT CLI 需要可配置的服务端连接参数、默认参数与日志选项。若把参数硬编码进各命令，用户每次都要敲全参数；若把配置散落在各命令各自解析，维护成本高、优先级混乱。需要一个统一的配置来源与优先级约定。

## Decision

统一配置管理，核心是**优先级链**：命令行标志 > 环境变量(`FASTGPT_*`) > 配置文件 > 内置默认值。
- `internal/config`：`Config` 结构 + `Default()` + `Load(explicitPath)` + `Save`；`DefaultsPath()` 定位 `~/.fastgpt-cli/config.yaml`（可用 `FASTGPT_CONFIG_DIR` 覆盖目录）。
- 环境变量用 `FASTGPT_` 前缀 + 下划线路径（如 `FASTGPT_SERVER_HOST`、`FASTGPT_DEFAULTS_CHUNK_SIZE`），在 `applyEnv` 中覆盖文件名同名项。
- `config` 子命令：`show`（默认/JSON）、`path`、`init`（生成默认文件）、`set <key=value>`（点路径写回，如 `server.host`）。
- 配置通过 Cobra 标志层注入命令（`loadEffectiveConfig`），`create-kb` 未显式给 `--model` 时回落到 `defaults.model`。

## Alternatives considered

- **只用 Viper**：功能全但重，会掩盖逻辑；本项目配置面小，自研 ≤100 行且完全可控，弃用 Viper（保留 yaml.v3 做序列化）。
- **配置散落在各命令**：无单一事实来源，优先级难统一，弃用。

## Verification

- [x] `config show / path / init / set` 四个子命令可用
- [x] 默认值 < 配置文件 < 环境变量 优先级生效（经 `FASTGPT_SERVER_HOST` 实测）
- [x] `create-kb` 未指定 `--model` 时回落到 `defaults.model`
- [x] `go build ./...`、`go vet ./...` 通过

## Consequences

- `applyEnv` 对整数字段静默忽略非法值（`strconv.Atoi` 失败不报错）——有意取舍，避免环境变量污染阻断启动；后续可在 `--verbose` 下告警。
- 配置文件为明文 YAML，`api_key` 存盘未加密；Day 5-7 接入真实 API 时需评估是否支持外部密钥注入/环境变量优先。
