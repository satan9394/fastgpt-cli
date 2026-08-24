# FastGPT CLI — 交接文档（下一位 Agent 请从这里开始）

> 更新时间：2026-08-21
> 本文档是后续 Agent 执行的唯一入口。已按指导文件完成 Phase 0-5，本文档记录全部状态、未决事项、和下一步。

---

## 当前完成状态

| Phase | 内容 | 状态 | 验证 |
|-------|------|------|------|
| 0 | 方向校准（定位=AI 应用生命周期 DevOps CLI，非聊天 CLI） | ✅ 完成 | architecture note 已存 |
| 1 | 项目初始化 + Python/Typer 命令面骨架 | ✅ 完成 | pytest 22 passed |
| 2 | 输出契约硬化（JSON 默认、stdout 纯净、error.kind、--limit/--page、jsonl 流式） | ✅ 完成 | pytest 37 passed |
| 3 代码级 | 真实 HTTP 客户端接入（fastgpt-source v4.16 路由/契约，mock 测试锁定） | ✅ 完成 | pytest 50 passed |
| 3 实例级 | 部署本地 FastGPT 实例 + 线上三连验证 | ⏸️ **未完成（本次中断）** | 见下方未决事项 |
| 4 | schema 自省全覆盖（schema commands list + 测试 1:1） | ✅ 完成 | pytest 55 passed |
| 5 | SKILL.md + 独立子代理端到端实测 | ✅ 完成 | 子代理 verdict PASS |
| 6 | README + audit + aiops 预留 | ⏸️ 未做 | — |

**最后验证基线**（Phase 4+5 完成时）：
```
pytest 55 passed | ruff check . All checks passed!
schema commands list --json total=40，含 params
kb list → {"items":[],"total":0}，stderr 空
scripts/audit.py . exit=0 NOT-OK=0
```

---

## Phase 3 未决事项（本地实例部署 + 线上三连）

### 已完成的部分
1. **裁剪版 compose 已写好**：`deploy-local/docker-compose.yml`（基于官方 CN pg compose，裁掉 sandbox/mcp/aiproxy/mcp-server，保留 7 个核心服务：pg/mongo/redis/minio/app/code-sandbox/plugin）
2. **端口冲突已发现并解决**：`new-api`（calciumion/new-api，OpenAI 兼容网关）**占用 3000 端口**，FastGPT app 已改映射到 **3100**（FE_DOMAIN 也改为 `http://localhost:3100`）
3. **new-api 就是用户的模型网关**：同一个 `new-api` 容器（Up 11+ hours）很可能就是 OPENCODE_API_KEY / chat 对应的后端，FastGPT 的模型 provider 应指向 `http://host.docker.internal:3000`（或 `http://172.17.0.1:3000`）
4. **compose config 校验通过**：`docker compose config --quiet` 无报错

### 下一步（接续执行）

#### Step 1：拉镜像 + 启动
```bash
cd E:\DeepSeek_Harness\workspace\2026_08_20\fastgpt-cli\deploy-local
docker compose pull   # 镜像从阿里云拉，fastgpt-app v4.16.0 约 1-2GB，可能需 5-10 分钟
docker compose up -d  # 后台启动，约 1-3 分钟等健康检查
```

#### Step 2：验证服务
```bash
# FastGPT app 在 3100（3000 被 new-api 占了）
Invoke-WebRequest -Uri "http://127.0.0.1:3100" -TimeoutSec 5 -UseBasicParsing
# 应返回 200
```

#### Step 3：获取 root token + 创建 API Key
FastGPT v4.16 的 API key 认证（HttpClient 已实现 `Authorization: Bearer <key>`）：
```bash
# 方案 A：root 登录拿 JWT token（默认 root/1234）
$body = @{username='root'; password='1234'} | ConvertTo-Json
$resp = Invoke-WebRequest -Uri "http://127.0.0.1:3100/api/support/user/account/loginByPassword" -Method POST -Body $body -ContentType "application/json" -UseBasicParsing
# resp.Content 里有 token
```
```bash
# 方案 B：直接用 ROOT_KEY 走 roothead 认证（compose 里设的 x-system-key）
# 但 CLI 的 HttpClient 只发 Authorization: Bearer，rootkey 需要 header rootkey，CLI 不支持 roothead
# 所以走方案 A 或让用户在 web 后台创建 API key
```

**推荐**：用 root/1234 登录 → 浏览器打开 `http://127.0.0.1:3100` → root 登录 → 右上角头像 → 账号 → API 密钥 → 新建（复制 key）→ 配到环境变量。

#### Step 4：配置 FastGPT 的模型 provider（用于 embedding + 检索）
FastGPT 后台登录后：AI 模型 → 模型提供商 → 添加 OpenAI 兼容 → 填入：
- 基础 URL：`http://172.17.0.1:3000/v1`（Docker 网络内访问 new-api）
- API Key：new-api 的 key（查看 `docker logs new-api | head -20` 或 new-api 后台）
- 填一个 embedding 模型名：如 `text-embedding-3-small`（或 new-api 里配置过的任何 embedding 模型）
- 如果没有 embedding 模型，dataset import 和 query search 会失败（"System not embedding model"）

#### Step 5：跑三连
```bash
# 设置 CLI 环境变量
$env:FASTGPT_SERVER_HOST = "127.0.0.1"
$env:FASTGPT_SERVER_PORT = "3100"
$env:FASTGPT_SERVER_API_KEY = "<从上面拿到的 API key>"

cd E:\DeepSeek_Harness\workspace\2026_08_20\fastgpt-cli
python -m fastgptcli.cli.main dataset create "测试数据集"        # → {dataset_id: "xxx"}
python -m fastgptcli.cli.main dataset import ./docs --dataset xxx  # → 上传文档（需要已配 embedding 模型）
python -m fastgptcli.cli.main query search "test" --kb xxx      # → RAG 检索结果
```

### 已知障碍
1. **embedding 模型配置**：FastGPT 开箱无模型，必须在后台配置至少一个 embedding 模型，dataset import 和 query search 才能工作。需要用户提供模型 API key 或确认 new-api 里已有 embedding 模型。
2. **CLI 密钥约定**：只从环境变量 `FASTGPT_SERVER_API_KEY` 读取，不写入配置文件/日志/回复。

---

## 项目文件结构

```
fastgpt-cli/
├── fastgptcli/               # Python 包（CLI 核心）
│   ├── cli/
│   │   ├── main.py           # Typer 根入口
│   │   ├── _common.py        # 共享 helpers (emit, paginated, bind_json)
│   │   ├── {dataset,kb,app,workflow,agent,evaluation,query,export,config,probe,schema}.py
│   │   └── schema.py         # schema commands list (40 条，含 params)
│   ├── api/
│   │   ├── http.py           # HttpClient (GET/POST/DELETE + multipart, 429/5xx 重试)
│   │   ├── chat.py           # OpenAI 兼容 chat 客户端
│   │   └── fastgpt.py        # FastGPTClient（真实 HTTP 路由 + stub 回退）
│   ├── models/dto.py         # ListResult, SearchResult, AgentRunResult 等
│   ├── output/render.py      # emit_json / emit_jsonl / CliError / info
│   └── config/settings.py    # Config + load（default<file<env）+ chat_api_key
├── tests/
│   ├── test_cli.py           # 命令树 + 输出契约
│   ├── test_output_contract.py  # Phase 2 输出契约断言
│   ├── test_api_fastgpt_real.py # Phase 3 真实 HTTP 路由映射 (mock)
│   ├── test_schema_coverage.py  # Phase 4 schema 1:1 覆盖
│   ├── test_chat.py          # Go 迁移的 chat/重试语义
│   ├── test_config.py        # 配置优先级
│   └── conftest.py
├── deploy-local/
│   └── docker-compose.yml    # FastGPT 本地部署（裁剪版，app 端口 3100）
├── .claude/skills/fastgpt/
│   └── SKILL.md              # Phase 5 Agent 领域 skill
├── .harness/manifest.json    # 含 fastgpt domain skill 登记
├── README.md                 # 含 Phase 3-5 章节
├── HANDOFF.md                # 跨会话交接档案
├── pyproject.toml            # console_scripts: fastgpt = fastgptcli.cli.main:main
└── CLAUDE.md                 # 项目 Harness 指针
```

---

## 快速验证（随时可跑，不依赖真实后端）

```bash
cd E:\DeepSeek_Harness\workspace\2026_08_20\fastgpt-cli

# 测试（55 项全绿）
python -m pytest -q

# Lint
python -m ruff check .

# schema 自省（40 条命令，含 params）
python -m fastgptcli.cli.main schema commands list --json 2>/dev/null | python -m json.tool

# kb list 默认 JSON
python -m fastgptcli.cli.main kb list 2>/dev/null | python -m json.tool

# jsonl 流式
python -m fastgptcli.cli.main --output jsonl kb list

# 错误路径
python -m fastgptcli.cli.main kb delete kb-1 2>&1  # → stdout 空 + stderr 结构化 error.kind=validation
```

---

## 关键设计决策

1. **定位**：Agent-native AI 应用生命周期 DevOps CLI（kubectl/gh 风格），非聊天 CLI
2. **技术栈**：Python + Typer 0.9.0，原 Go（cmd/internal/pkg）仅作契约迁移来源
3. **命令面**：13 个领域组（dataset/kb/app/workflow/agent/evaluation/benchmark/query/export/config/probe/schema）+ 顶层 status/health/version
4. **输出契约**：默认 JSON、数据→stdout、日志+错误→stderr、统一 error.kind JSON
5. **real-client 门控**：`_backend_configured` = 有 api_key 或 host 非 localhost → 走真实 HTTP；否则 stub 空契约
6. **kb vs dataset**：FastGPT 4.x 里"知识库" = dataset，CLI 的 kb 命令映射到 dataset API

---

## 未决问题（供下一个 Agent 决策）

1. **Phase 3 线上三连**：compose 已写好（deploy-local/），待拉镜像+启动+配置模型+跑三连（见上方 Step 1-5）
2. **Phase 6 收尾**：README 进一步完善、scripts/audit.py . NOT-OK=0、aiops 平台化预留
3. **app deploy / app test**：真实 HTTP 客户端中 `app_deploy` 映射为 `GET /detail`（返回 version_id），`app_test` 映射为 `/v1/chat/completions` smoke test——语义待在线上验证
4. **dataset import 真实链路**：实现代理 post → presign → PUT → collection/localFile multipart，已写好 multipart 上传（`upload_multipart`），mock 测试锁定路由；线上验证需 embedding 模型
5. **env 规范**：`FASTGPT_SERVER_HOST/PORT/API_KEY`（从环境变量读，不落配置）
