# HANDOFF —— 项目交接档案

> 用途：跨会话/跨 agent 接续的权威档案。会话结束时更新；新会话先读本文件再动手。
> 由 harness-engineering v4.11.0 `bootstrap.py --init` 生成。骨架只含占位符，由第一次真实工作替换。

## 当前目标（Objective）
- FastGPT CLI（Go + Cobra）封装 labring/FastGPT，覆盖知识库全生命周期。
- 已完成 Day 1-2（克隆+骨架）、Day 3-4（配置管理）、Day 5-7 的 Chat 客户端部分（OpenAI 兼容对话，OpenCode Go / mimo-v2.5）。
- 已重规划为 Agent-native Python + Typer CLI（`fastgptcli/`）；Phase 0-1（方向+骨架）✅、Phase 2（输出契约硬化）✅、Phase 3 代码级✅、Phase 4（schema）✅、Phase 5（SKILL+实测）✅ 已验收。
- **下一步**：Phase 3 实例级（部署本地 FastGPT docker + 线上三连验证）→ Phase 6 收尾。详见 `HANDOFF-PHASE-STATUS.md`。

## 完成标准（Definition of Done）
- [x] Day 1-2：补克隆 fastgpt-source + go mod init + Cobra + 三个核心命令骨架
- [x] Day 3-4：配置管理 —— config.yaml 读写、环境变量覆盖、`fastgpt config show/path/init/set`
- [x] 配置注入：create-kb 未显式 `--model` 时回落 `defaults.model`
- [x] Day 5-7（部分）：`fastgpt chat` —— OpenAI 兼容 `/chat/completions` 客户端 + ChatService + Beanr 鉴权，实机验证 mimo-v2.5 应答
- [x] 单元测试：config / cmd / client / service 全过
- [x] go build ./...、go vet ./...、go test ./... 全过

## 验证命令（Verification）
- go build ./... && go vet ./... && go test ./... && go run . --help
- chat 需设环境变量 OPENCODE_API_KEY（或 FASTGPT_CHAT_API_KEY）后：`go run . chat "你好"`
- 其余环境变量：FASTGPT_SERVER_HOST 等；目录：FASTGPT_CONFIG_DIR
- 注意：拉取 Go 依赖前需设 HTTP_PROXY=http://127.0.0.1:7897（proxy.golang.org 无法直连，见 STATE.json R01）
- fastgpt-source 为**浅克隆**（--depth 1，HEAD=2f072bd / FastGPT 4.16.1，5963 文件）。git 大 pack 直连/代理会卡 0 字节，需 `git config http.postBuffer 524288000`（见 R01）。

## 边界（Boundaries）
- 只改 fastgpt-cli/ 内文件；不碰 tencentdb-agent-memory-cli/ 与 cli-reference/
- fastgpt-source/ 参考源码只读，不搬运，自研 CLI 层
- 删除一律走回收站（禁 rm）
- 安全：API 密钥只从环境变量读取（OPENCODE_API_KEY / FASTGPT_CHAT_API_KEY），不落配置/日志/档案/回复（见 STATE.json R02）

## 未决问题与下一步（Open Questions / Next Steps）
- 下一步（Day 5-7 剩余）：封装 FastGPT 具体 API client（KB/Doc 检索），替换 service 占位逻辑；接入 `internal/config.Logging` 落地 `--verbose` 日志
- 之后（第二阶段）：KB/Doc 命令真实化（list-kb/delete-kb/describe-kb/list-doc/delete-doc/reindex-doc）
- 依赖代理：proxy.golang.org 无法直连，需本地代理 7897（见 STATE.json R01）

---

## 变更日志（每轮结束追加一条）

- 2026-08-20 Day1-2: 补克隆 fastgpt-source + go mod init + 集成 Cobra + 实现 root/create-kb/upload-doc/query 命令骨架 + 分层目录 cmd/internal{service,client,config}/pkg{utils,types} + 架构 Agent Note(proposed) + 第一个真实问题(proxy)记入 STATE.json(R01) | 验证: go build ./... 通过; go vet ./... 无错误; go run . --help 展示含 create-kb/upload-doc/query 的完整命令树

- 2026-08-20 Day3-4: 配置管理 —— config.yaml 读写(Load/Save) + 环境变量覆盖(FASTGPT_*) + config show/path/init/set 子命令 + 配置注入 create-kb(回落 defaults.model) + 单元测试(8+5) + 架构/配置 Agent Note转 implemented | 验证: go build ./... 通过; go vet ./... 无错误; go test ./... 通过; config 功能实测(默认值<文件<环境变量)全过

- 2026-08-20 Day5-7(部分): 接入 OpenAI 兼容对话 -- fastgpt chat 命令(OpenCode Go https://opencode.ai/zen/go/v1 + mimo-v2.5) + internal/client ChatClient(Bearer/超时/重试/choices校验) + ChatService + config chat节(base_url/model,密钥走env) + 单测(client/service/config) + Agent Note转 implemented + 密钥安全规则 R02 | 验证: go build/vet/test 全过; 实机 chat 调用 mimo-v2.5 返回真实应答; 无密钥/无参数时报清晰错误

- 2026-08-20 FastGPT CLI 重规划 Phase0-1：读指导文件定定位（AI 应用生命周期管理，非 chat CLI）与命令面（dataset/kb/app/workflow/agent/evaluation/benchmark/query/export/config/probe/schema/status/health/version），技术栈从 Go 转向 Python+Typer；新建 fastgptcli/ 包（cli 命令组 + api + models + output + config），notes/proposed 记一条架构决策，迁移 Go chat/429-5xx重试/config-env 语义到 Python，console_scripts fastgpt + python -m 双入口，tests 22 项 | 验证: pytest 22 passed; ruff check 0 错误; fastgpt --help 完整命令树; schema --json 合法(16 groups); kb list --json -> {items:[],total:0} 且 stderr 空; fastgpt.exe 与 python -m 双入口可用

- 2026-08-20 FastGPT CLI review 修复：按 claude 评审意见自主修复——1) schema 自省改为编译 Click 树（typer.main.get_command）以填充 help/params（原 critical）；2) schema tree/commands 增加 --json；3) status/health 去重并集中到 probe.status_payload/health_payload；4) backup/benchmark 别名在 schema 标记 alias_of；5) dataset import 保留全路径、query 移除死校验、去掉 typer is_flag 弃用（37 警告清零） | 验证: pytest 22 passed; ruff check . All checks passed; schema --json 现输出填充的 help/params; schema tree/commands --json 可用; status/health/probe 一致; 弃用警告 0; note-lifecycle 6 PASS / 0 NOT-OK

- 2026-08-20 FastGPT CLI 重规划 Phase2 输出契约硬化：output/render.py 新增 emit_jsonl/_bare/_collection NDJSON 流式；cli/_common 新增 bind_json/paginated/limit_opt/page_opt（--limit/--page 有界翻页，total 保持全集）；main 全局 --output 校验 json|jsonl|text；kb/dataset/app/workflow list 接 --page 有界；新增 tests/test_output_contract.py 15 项（默认JSON+stderr纯净/error-path stdout空+结构化stderr/jsonl逐行流式/limit-page翻页/非法--output）；README 增输出契约节与示例 | 验证: pytest 37 passed; ruff check 0 错误; kb list 2>/dev/null | json.tool 通过(stderr 空); kb delete 无 --yes -> stdout 空 + stderr 结构化 error.kind validation; --output jsonl 逐行流式、非法值 validation

- 2026-08-20 接入 DeepSeek 官方 LLM（自主决策落地）：fastgptcli/config/settings.py ChatConfig 默认改指向 DeepSeek 官方 API（base_url=https://api.deepseek.com、model=deepseek-v4-flash，选轻量模型）；chat_api_key() 增 DEEPSEEK_API_KEY 环境变量回退（key 只走 env，不落盘）；tests/test_config.py 同步补 DEEPSEEK_API_KEY 用例 | 验证: pytest 37 passed；ruff check fastgptcli tests All checks passed；config show chat.base_url=https://api.deepseek.com、model=deepseek-v4-flash；e2e: fastgpt query chat 经 DeepSeek 官方返回合法 JSON 回复（exit 0）；DeepSeek 官方 /models 确认 deepseek-v4-flash 有效，key 验证通过

- 2026-08-21 FastGPT CLI Phase3+4+5：Phase3 代码级已完成（真实 HTTP 路由 mock 测试 13 项）；Phase4 schema 自省全覆盖（schema commands list --json 扁平 40 条含 params，tests/test_schema_coverage.py 5 项 1:1 验证）；Phase5 SKILL.md + 独立子代理 7 步端到端实测 verdict PASS（唯一缺口"扁平 schema 缺 params"已修复）；audit.py exit=0 无 NOT-OK | 验证: pytest 55 passed; ruff check All checks passed; schema commands list --json total=40 含 params; 子代理 7 步契约全过

- 2026-08-21 FastGPT 本地部署准备（用户要求）：写 deploy-local/docker-compose.yml（基于官方 CN pg compose 裁剪：保留 pg/mongo/redis/minio/app/code-sandbox/plugin，裁 sandbox/mcp/aiproxy；端口 app=3100 因 3000 被 new-api 占用；FE_DOMAIN=http://localhost:3100）；compose config 校验通过；docker compose pull 启动后用户要求停止。下一步：重新 pull + up -d → localhost:3100 → root/1234 登录 → 创建 API key → 配 embedding 模型 → 三连验证（详见 HANDOFF-PHASE-STATUS.md）

- 2026-08-21 FastGPT CLI Phase4+5：Phase4 schema 自省全覆盖——schema commands 改为命令组，新增 schema commands list --json 扁平命令清单（40 条 name/path/group/help/params，含顶层 status/health/version 与嵌套 schema commands list；params 自包含参数签名，agent 无需再查 tree）；schema commands 裸调用同输出；tests/test_schema_coverage.py 5 项锁定 schema 与真实命令树 1:1（双向无缺/无幻影）+ 契约字段 + params 完整性 + 预期命令面。Phase5 Agent 可发现——新增 .claude/skills/fastgpt/SKILL.md（frontmatter 合法，manifest domain_skills 登记）；派独立子代理仅凭 CLI 内省（--help+schema）端到端 7 步（discover/list/create/upload/agent/error/search）实测，verdict PASS，唯一发现（扁平清单缺参数签名）已修复；audit.py 无 NOT-OK、skill-router 无漂移 | 验证: pytest 55 passed; ruff check . All checks passed; schema commands list --json total=40 且含 params; 独立子代理 7 步契约全过 verdict PASS; audit.py exit=0 无 NOT-OK; skill-router 无 WARN/NOT-OK; kb list 默认 JSON stderr 空

- 2026-08-21 Phase 3 实例部署准备：写 deploy-local/docker-compose.yml（基于官方 CN pg compose 裁剪，保留 pg/mongo/redis/minio/app/code-sandbox/plugin 7 服务，裁 sandbox/mcp/aiproxy，app 端口 3100 避开 new-api 3000 占用）；发现 new-api(calciumion) 已占 3000 且运行中（可用作 FastGPT 模型 provider）；compose config 校验通过；docker compose pull 启动后用户要求暂停；写 HANDOFF-NEXT-AGENT.md 完整交接文档；所有后台作业已 kill，docker 容器已清理 | 验证: pytest 55 passed; ruff All checks passed; deploy-local/docker-compose.yml config 校验通过; new-api 3000 运行中; HANDOFF-NEXT-AGENT.md 已就绪
