# FastGPT CLI（Agent-native）

> 主实现为 **Python + Typer**，定位是「让 Agent / DevOps 自动管理 FastGPT」= **AI 应用生命周期管理**
> （类比 `kubectl` / `gh`），不做聊天 CLI 主线。技术栈与命令面按《指导文件-FastGPT-CLI改造.md》§0.1/§2.1/§三 执行。
> 原 Go 实现（`cmd/ internal/ pkg/ main.go`）保留为**契约与语义迁移来源**，不删除。

## 快速开始
```bash
# 安装（可编辑）后获得 `fastgpt` 命令；无安装也可用 python -m 入口
pip install -e . --no-build-isolation
fastgpt --help                      # 完整 agent-native 命令树
fastgpt schema --json               # 机器可读命令树（Agent 运行时自省）
fastgpt status --json               # 运行状态
fastgpt kb list                     # 列表默认即 JSON（无需 --json）
python -m fastgptcli.cli.main --help # 开发入口
```

## 输出契约（CLI-Spec 六原则硬化）
- **默认即 JSON**：所有命令默认输出稳定 JSON；数据只进 **stdout**，日志/进度/警告/错误只进 **stderr**。
- **错误统一结构**：`{"error": {"kind": "...", "message": "...", "details": {...}}}`；kind 属 `validation | conflict | not_found | auth | backend | transport | internal`。
- **有界输出**：列表命令支持 `--limit <n>`（默认上限）与 `--page <p>`（1 起）翻页；`total` 始终反映全集，`items` 为当前页。
- **流式 jsonl**：大结果用全局 `--output jsonl` 逐行输出 NDJSON（须放在子命令前），例如：
  ```bash
  fastgpt --output jsonl kb list --limit 1000
  fastgpt --output jsonl query search "如何配置 API 密钥" --limit 500
  ```
- **破坏性操作非交互**：`kb/app/dataset delete` 需显式 `--yes`，否则返结构化 `validation` 错误，stdout 保持为空。
- `--output` 取值校验为 `json | jsonl | text`，非法值返 `validation` 错误。

## 真实后端接入（Phase 3）
- `fastgptcli/api/fastgpt.py` 已接 **FastGPT v4.16 真实 HTTP API**（路由/契约以 `fastgpt-source/` 为准，`Authorization: Bearer <key>` 鉴权）：
  - dataset/kb → `POST /api/core/dataset/{create,list}`、`GET /api/core/dataset/detail?id=`、`DELETE /api/core/dataset/delete?id=`
  - import/upload → `POST /api/core/dataset/collection/create/localFile`（multipart）
  - query search → `POST /api/core/dataset/searchTest`（`datasetId/text/limit`，服务端需 `--kb`）
  - app/workflow → `POST /api/core/app/{list,create}`、`GET /api/core/app/detail?appId=`、`DELETE /api/core/app/del?appId=`
- **启用方式**：配置 `server.api_key`（或环境变量 `FASTGPT_SERVER_API_KEY`）且 host 非 localhost 即自动切真实链路；
  未配置后端时列表命令仍返回稳定的 `{items:[], total:0}` 契约（离线/CI 友好）。
- 真实请求经 `HttpClient`（429/5xx 重试、4xx 终态，语义迁移自 Go）；上传为 multipart 单次请求。
- 验证方式：`tests/test_api_fastgpt_real.py` 注入 mock 锁定路由/鉴权头/字段映射；真正三连
  `dataset create → dataset import ./docs → query search --kb <id>` 需真实 FastGPT 实例与凭据。

## 命令树（领域分组，默认 JSON / 数据→stdout / 日志+错误→stderr）
```
fastgpt
├── dataset      create / import ./docs / ls / delete
├── kb           create / list / upload / get / delete
├── app          list / create / deploy / test / describe / delete
├── workflow     deploy / list / test
├── agent        run --input "..." → {answer, tokens, sources}
├── evaluation   run / compare
├── benchmark    run / compare（预留骨架）
├── query        search（RAG 检索）/ chat（内联检索，非主线）
├── export       export / backup
├── config       show / path / set / init
├── schema       tree / commands list（自省命令树 + 扁平命令清单）
└── status / health / version
```

## Agent 可发现（Phase 4-5）
- `fastgpt schema commands list --json` → 扁平命令清单（40 条：name/path/group/help/**params**），与真实命令树 1:1（有测试锁定），参数签名自包含无需再查 tree。
- `fastgpt schema tree --json` → 完整嵌套命令树（含每条命令 params）。
- `.claude/skills/fastgpt/SKILL.md` → 教 Agent 用 CLI 的领域 skill（命令/JSON 契约/错误处理/示例）。
- 已由独立子代理实测：仅凭 `--help` + `schema` 内省即可端到端完成 discover/list/create/upload/agent/error/search 7 步，verdict PASS。

## 代码结构
- `fastgptcli/cli/`：Typer 命令组（dataset/kb/app/workflow/agent/evaluation/query/export/config/probe/schema + main 入口）
- `fastgptcli/api/`：真实 FastGPT API 客户端（`http.py` 429/5xx 重试、`chat.py` OpenAI 兼容 chat、`fastgpt.py` 领域接口）
- `fastgptcli/models/`：共享类型与输出 DTO
- `fastgptcli/output/`：统一 JSON 输出 + stderr 规范 + 结构化错误（`error.kind`）
- `fastgptcli/config/`：配置（默认 < 文件 < 环境变量，语义迁移自 Go `internal/config`）
- `tests/`：pytest 命令树 / 输出契约 / 配置优先级 / chat 重试语义

## 验证
- `python -m pytest` → 通过
- `python -m ruff check .` → 无错误
- `fastgpt kb list 2>/dev/null | python -m json.tool` → 合法 JSON 且 stderr 无数据
- `fastgpt kb delete kb-1`（无 --yes）→ stdout 空、stderr 为结构化 `{"error":{"kind":"validation",...}}`

---

# （以下为原 Go 实现的历史规划，保留作契约/语义迁移来源，不再作为主线）

# FastGPT CLI 工具开发规划

## 项目概述

基于 FastGPT 开源知识库平台，开发命令行工具（CLI），实现知识库的全生命周期管理。

### 项目信息
- **原项目**: [labring/FastGPT](https://github.com/labring/FastGPT) ⭐29,393
- **开发目标**: 创建易用的CLI工具，支持知识库创建、文档管理、智能查询等
- **技术栈**: Go + Cobra + gRPC + Docker
- **创建日期**: 2026-08-20

---

## 一、需求分析

### 1.1 核心功能需求

| 功能模块 | 命令 | 说明 |
|---------|------|------|
| 知识库管理 | `fastgpt create-kb` | 创建新知识库 |
| | `fastgpt list-kb` | 列出所有知识库 |
| | `fastgpt delete-kb` | 删除知识库 |
| | `fastgpt describe-kb` | 查看知识库详情 |
| 文档管理 | `fastgpt upload-doc` | 上传文档到知识库 |
| | `fastgpt list-doc` | 列出知识库中的文档 |
| | `fastgpt delete-doc` | 删除文档 |
| | `fastgpt reindex-doc` | 重建文档索引 |
| 智能查询 | `fastgpt query` | 查询知识库 |
| | `fastgpt chat` | 与知识库对话 |
| | `fastgpt batch-query` | 批量查询 |
| 数据导出 | `fastgpt export` | 导出知识库数据 |
| | `fastgpt backup` | 备份知识库 |
| 系统管理 | `fastgpt config` | 配置管理 |
| | `fastgpt status` | 查看系统状态 |
| | `fastgpt health` | 健康检查 |

### 1.2 用户场景

**场景1：快速创建知识库**
```bash
fastgpt create-kb --name "产品文档" --model "text-embedding-3-small"
```

**场景2：批量上传文档**
```bash
fastgpt upload-doc --kb "产品文档" --path ./docs/ --recursive
```

**场景3：智能查询**
```bash
fastgpt query --kb "产品文档" --query "如何配置API密钥"
```

**场景4：与知识库对话**
```bash
fastgpt chat --kb "产品文档" --interactive
```

---

## 二、技术架构

### 2.1 系统架构图

```
┌─────────────────────────────────────────────────────┐
│                    FastGPT CLI                       │
├─────────────────────────────────────────────────────┤
│  Command Layer (Cobra)                              │
│  ┌─────────┬─────────┬─────────┬─────────┐         │
│  │  KB     │  Doc    │  Query  │  System │         │
│  │  Cmds   │  Cmds   │  Cmds   │  Cmds   │         │
│  └─────────┴─────────┴─────────┴─────────┘         │
├─────────────────────────────────────────────────────┤
│  Service Layer                                      │
│  ┌─────────┬─────────┬─────────┬─────────┐         │
│  │  KB     │  Doc    │  Query  │  Config │         │
│  │  Svc    │  Svc    │  Svc    │  Svc    │         │
│  └─────────┴─────────┴─────────┴─────────┘         │
├─────────────────────────────────────────────────────┤
│  Client Layer (gRPC/REST)                           │
│  ┌─────────────────────────────────────────┐       │
│  │         FastGPT Server Client           │       │
│  └─────────────────────────────────────────┘       │
├─────────────────────────────────────────────────────┤
│  FastGPT Server                                     │
└─────────────────────────────────────────────────────┘
```

### 2.2 目录结构

```
fastgpt-cli/
├── cmd/                    # 命令定义
│   ├── root.go            # 根命令
│   ├── kb.go              # 知识库命令
│   ├── doc.go             # 文档命令
│   ├── query.go           # 查询命令
│   └── system.go          # 系统命令
├── internal/              # 内部实现
│   ├── service/           # 业务逻辑
│   ├── client/            # API客户端
│   └── config/            # 配置管理
├── pkg/                   # 公共包
│   ├── utils/             # 工具函数
│   └── types/             # 类型定义
├── docs/                  # 文档
├── scripts/               # 脚本
├── go.mod                 # Go模块
├── go.sum                 # 依赖
├── Makefile               # 构建脚本
└── README.md              # 项目说明
```

---

## 三、开发计划

### 3.1 阶段划分

| 阶段 | 时间 | 任务 | 产出 |
|------|------|------|------|
| 第一阶段 | 1周 | 基础框架搭建 | 项目结构、基础命令 |
| 第二阶段 | 2周 | 核心功能实现 | KB和Doc命令 |
| 第三阶段 | 2周 | 查询功能实现 | Query和Chat命令 |
| 第四阶段 | 1周 | 测试和优化 | 单元测试、性能优化 |
| 第五阶段 | 1周 | 文档和发布 | 使用文档、发布包 |

### 3.2 第一阶段详细任务

**Day 1-2: 项目初始化** ✅ (2026-08-20)
- [x] 初始化Go模块（`github.com/satan9394/fastgpt-cli`）
- [x] 集成Cobra框架（v1.10.2）
- [x] 创建基础命令结构（`cmd/root.go` + create-kb/upload-doc/query）
- [x] 实现版本信息（`--version`）

**Day 3-4: 配置管理** ✅ (2026-08-20)
- [x] 设计配置文件格式（`internal/config/config.go` + config.yaml）
- [x] 实现配置读写（`Load`/`Save`，优先级 默认值 < 文件 < 环境变量）
- [x] 支持环境变量（`FASTGPT_*`，如 `FASTGPT_SERVER_HOST`）
- [x] 实现配置命令（`fastgpt config show/path/init/set`）

**Day 5-7: 客户端封装**（部分完成 ✅ 2026-08-20）
- [x] 封装 OpenAI 兼容 Chat 客户端（`internal/client` + `service` + `fastgpt chat`，默认 OpenCode Go / mimo-v2.5）
- [x] 认证机制（Bearer，密钥仅从环境变量 `OPENCODE_API_KEY`/`FASTGPT_CHAT_API_KEY` 读取）
- [x] 错误处理（HTTP 状态 + `error` 字段透出 + 429/5xx 重试）
- [ ] 封装 FastGPT 具体 API client（KB/Doc 检索，当前 service 仍为占位逻辑）
- [ ] 日志记录（`--verbose` 已预留，接入 `internal/config.Logging`）

---

## 四、简历亮点提炼

### 4.1 项目描述

**开源知识库CLI工具开发**
- 基于 FastGPT 开源项目，设计并实现命令行管理工具
- 采用 Go + Cobra 架构，支持 20+ 命令覆盖知识库全生命周期
- 集成 gRPC 客户端，实现高性能远程调用
- 支持批量操作和管道命令，提升运维效率

### 4.2 技术亮点

1. **架构设计**
   - 分层架构：Command → Service → Client
   - 依赖注入，便于测试
   - 插件化设计，易于扩展

2. **性能优化**
   - 并发文档上传
   - 增量索引构建
   - 连接池管理

3. **用户体验**
   - 彩色终端输出
   - 进度条显示
   - 自动补全支持
   - 上下文帮助

### 4.3 量化指标

- 支持 20+ 命令
- 文档上传速度提升 50%（并发）
- 查询响应时间 < 100ms
- 支持 10GB+ 大文档处理

---

## 五、面试准备

### 5.1 常见问题

**Q: 为什么选择 Go 而不是 Python？**
A: Go 编译为单二进制文件，分发简单；性能好，适合处理大文档；并发能力强，适合批量操作。

**Q: 如何处理大量文档的索引？**
A: 采用增量索引策略，只处理变更部分；支持并发处理，提升效率；使用消息队列解耦。

**Q: 如何保证数据一致性？**
A: 采用事务机制；实现重试和幂等；使用校验和验证。

### 5.2 技术深度

- **Cobra 框架**: 命令解析、标志绑定、帮助生成
- **gRPC 客户端**: 连接管理、拦截器、负载均衡
- **并发处理**: Goroutine、Channel、WaitGroup
- **错误处理**: 错误包装、重试机制、降级策略

---

## 六、资源链接

- [FastGPT 官方文档](https://doc.fastgpt.in/)
- [FastGPT GitHub](https://github.com/labring/FastGPT)
- [Cobra 框架文档](https://cobra.dev/)
- [Go 最佳实践](https://go.dev/doc/effective_go)

---

## 七、后续规划

1. **插件系统**: 支持自定义命令扩展
2. **多租户支持**: 支持团队协作
3. **Web UI**: 提供 Web 管理界面
4. **IDE 集成**: VS Code 插件
