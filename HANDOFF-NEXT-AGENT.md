# FastGPT CLI — 交接文档（下一位 Agent 请从这里开始）

> 更新时间：2026-08-21 12:00 UTC+8
> 本文档是唯一权威入口。所有之前的对话进度已整合到此。

## 项目概述

FastGPT CLI 是 **Agent-native 的 AI 应用生命周期管理工具**（类比 kubectl/gh），定位为封装 FastGPT 知识库/RAG/Agent 全链路。技术栈 Python + Typer，命令面 13 个领域组 + 顶层命令。

**项目根目录**：`E:\DeepSeek_Harness\workspace\2026_08_20\fastgpt-cli\`
**运行入口**：`python -m fastgptcli.cli.main <args>`（开发）或 `fastgpt <args>`（安装后）
**测试**：`python -m pytest -q`（55 项全绿）
**Lint**：`python -m ruff check .`（全通过）

---

## 当前状态（截至本轮会话结束）

### ✅ 已完成（Phase 0-5）

| Phase | 内容 | 验证标准 | 状态 |
|-------|------|----------|------|
| 0 | 方向校准：定位 AI 应用生命周期 DevOps CLI（非聊天 CLI） | 架构笔记已存 | ✅ |
| 1 | Python + Typer 项目初始化 + 命令面骨架（13 域组 + 顶层命令） | pytest 22 passed | ✅ |
| 2 | 输出契约硬化：默认 JSON、stdout 纯净、error.kind 结构化、--limit/--page、--output jsonl | pytest 37 passed + kb list \| json.tool 通过 | ✅ |
| 3 代码级 | 真实 HTTP 客户端接入（fastgpt-source v4.16 路由/契约，mock 测试锁定） | pytest 50 passed + mock 13 项路由映射锁定 | ✅ |
| 4 | schema 自省全覆盖：schema commands list 40 条含 params，与真实命令树 1:1 | pytest 55 passed + schema 1:1 验证 | ✅ |
| 5 | SKILL.md + 独立子代理 7 步端到端实测（discover/list/create/upload/agent/error/search） | 子代理 verdict PASS | ✅ |

### ⏸️ 未完成

| 内容 | 阻塞原因 |
|------|----------|
| **Phase 3 实例级**：部署 FastGPT 本地 Docker 实例 + 线上三连验证 | 用户要求暂停（本轮中断） |
| Phase 6：README 完善 + aiops 平台化预留 | 需先完成 Phase 3 |

---

## 🔧 下一步：Phase 3 实例级部署（核心未完成项）

### 已就绪的素材

**1. 裁剪版 docker-compose** 已写好：
```
fastgpt-cli/deploy-local/docker-compose.yml
```
- 基于官方 CN docker-compose.pg.yml（PG 向量版）
- **保留 7 服务**：pgvector / mongo / redis / minio / fastgpt-app / code-sandbox / plugin
- **裁掉**：mcp-server / opensandbox / volume-manager / agent-sandbox-proxy / aiproxy / aiproxy-pg（节省资源）
- **app 端口 3100**（3000 被已有的 `new-api` 容器占用）
- FE_DOMAIN = `http://localhost:3100`
- compose config 校验通过

**2. new-api 占用 3000 端口**（calciumion/new-api:latest，Up 11+ 小时）：
- 这就是用户的 OpenAI 兼容模型网关
- FastGPT 可以用它做模型 provider（通过 `http://host.docker.internal:3000`）
- FASTGPT_SERVER_API_KEY 从环境变量读取（`FASTGPT_SERVER_HOST=127.0.0.1`, `FASTGPT_SERVER_PORT=3100`）

### 执行步骤

**Step 1：拉镜像 + 启动**
```powershell
cd E:\DeepSeek_Harness\workspace\2026_08_20\fastgpt-cli\deploy-local
docker compose pull     # 从阿里云 registry 拉，fastgpt-app ~1GB，可能 5-10 分钟
docker compose up -d    # 后台启动
docker compose logs -f fastgpt-app   # 等待 "Ready in X ms" 后 Ctrl+C
docker compose ps       # 确认所有服务 healthy
```

**Step 2：验证 FastGPT 可访问**
```powershell
# 浏览器打开 http://127.0.0.1:3100
# 或命令行：
Invoke-WebRequest -Uri "http://127.0.0.1:3100" -TimeoutSec 10
```

**Step 3：登录 root 账号 + 创建 API Key**
```
用户名：root
密码：1234（compose 里 x-default-root-psw）
```
登录后：
1. 右上角头像 → 账号设置 → **API 密钥** → **新建**
2. 复制 API Key
3. 设置 CLI 环境变量：
```powershell
$env:FASTGPT_SERVER_HOST = "127.0.0.1"
$env:FASTGPT_SERVER_PORT = "3100"
$env:FASTGPT_SERVER_API_KEY = "<复制的 API Key>"
```

**Step 4：配置模型（embedding + chat）**
登录 FastGPT 后台 → **AI 模型** → 添加模型：
- **Chat 模型**：Base URL 填 `http://host.docker.internal:3000/v1`（指向 new-api），API Key 填 new-api 的 key，模型名填 new-api 支持的模型（如 `deepseek-v4-flash` 或 `mimo-v2.5`）
- **Embedding 模型**：Base URL 填 `http://host.docker.internal:3000/v1`，模型名填 `text-embedding-3-small` 或其他 embedding 模型（**检索必须有 embedding 模型**）

如果 new-api 没有 embedding 模型，用户需要提供一个支持 embedding 的 API key（如 OpenAI 的），或者用本地的 ollama 等。

**Step 5：跑三连验证**
```powershell
cd E:\DeepSeek_Harness\workspace\2026_08_20\fastgpt-cli

# 1. 建数据集
python -m fastgptcli.cli.main dataset create "测试数据集"
# → stdout: {"dataset_id": "66f...", "name": "测试数据集", "status": "created"}

# 2. 导入文档（需要一个 .txt 或 .pdf 文件）
echo "FastGPT 是一个 AI Agent 构建平台" > test.txt
python -m fastgptcli.cli.main dataset import ./test.txt --dataset <dataset_id>
# → stdout: {"dataset_id": "...", "imported": 1, "files": [...]}

# 3. 搜索
python -m fastgptcli.cli.main query search "什么是 FastGPT" --kb <dataset_id>
# → stdout: {"results": [{"score": 0.85, "content": "...", "source": "test.txt"}]}
```

---

## 关键文件清单

```
fastgpt-cli/
├── fastgptcli/
│   ├── cli/
│   │   ├── main.py              # 根入口（console_scripts fastgpt）
│   │   ├── _common.py           # emit / bind_json / paginated / limit_opt / page_opt
│   │   ├── schema.py            # schema commands list（40 条，含 params）
│   │   ├── query.py             # query search --kb 透传
│   │   └── {dataset,kb,app,workflow,agent,evaluation,export,config,probe}.py
│   ├── api/
│   │   ├── fastgpt.py           # ★ 真实 HTTP 客户端（Phase 3 路由，_backend_configured 门控）
│   │   ├── http.py              # HttpClient（GET/POST/DELETE + multipart，429/5xx 重试）
│   │   └── chat.py              # OpenAI 兼容 chat 客户端
│   ├── models/dto.py            # ListResult / SearchResult / AgentRunResult 等
│   ├── output/render.py         # emit_json / emit_jsonl / CliError（error.kind）
│   └── config/settings.py       # Config（default < file < env，密钥仅 env）
├── tests/                        # 55 项测试
│   ├── test_cli.py              # 命令树 + 默认 JSON
│   ├── test_output_contract.py  # Phase 2 stdout 纯净性
│   ├── test_api_fastgpt_real.py # Phase 3 真实 HTTP 路由 mock
│   ├── test_schema_coverage.py  # Phase 4 schema 1:1 覆盖
│   ├── test_chat.py             # Go 迁移语义（429/5xx 重试）
│   └── test_config.py           # 配置优先级
├── deploy-local/
│   └── docker-compose.yml       # ★ FastGPT 本地部署（app=3100，7 服务裁剪版）
├── .claude/skills/fastgpt/
│   └── SKILL.md                 # Agent 领域 skill
├── HANDOFF.md                   # 变更日志（完整历史）
├── HANDOFF-NEXT-AGENT.md        # ★ 本轮新增：下一 Agent 完整接手指引
└── README.md                    # 含 Phase 3-5 章节
```

## 验证命令（随时可跑，不依赖后端）

```powershell
cd E:\DeepSeek_Harness\workspace\2026_08_20\fastgpt-cli
python -m pytest -q              # 55 passed
python -m ruff check .           # All checks passed!
python -m fastgptcli.cli.main schema commands list --json   # total=40, 含 params
python -m fastgptcli.cli.main kb list 2>/dev/null | python -m json.tool  # {"items":[],"total":0}
python -m fastgptcli.cli.main --output jsonl kb list       # NDJSON 流式
```

## 边界（必须遵守）

1. 只修改 `fastgpt-cli/` 内文件；不碰 `tencentdb-agent-memory-cli/` 与 `cli-reference/`
2. 删除一律走 PowerShell 回收站
3. 密钥只从环境变量读（FASTGPT_SERVER_API_KEY / FASTGPT_CHAT_API_KEY / OPENCODE_API_KEY / DEEPSEEK_API_KEY）
4. 代理：127.0.0.1:7897；Docker 内部绕过代理（NO_PROXY 已配）
5. typer 0.9.0 旧版：boolean flag 用 `bool` 默认值，勿用 `is_flag=True`
6. 收尾追加 HANDOFF.md 用 `python scripts/handoff-log.py --append "..." --verify "..."`

## 指导文件（后续必读）

- **唯一权威**：`E:\DeepSeek_Harness\workspace\2026_08_20\指导文件-FastGPT-CLI改造.md`
- CLI Spec 六原则：`E:\DeepSeek_Harness\workspace\2026_08_20\cli-reference\cli-spec\README.md`
- FastGPT 源码参考（只读）：`fastgpt-cli/fastgpt-source/`（重点：`document/public/deploy/docker/main/cn/docker-compose.pg.yml`）
