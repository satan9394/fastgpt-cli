# 项目 B 指导文件：FastGPT CLI —— 从「传统 CLI」改造为「Agent-native CLI」

> 创建：2026-08-20（v2 已融合外部评审反馈）。适用目录：`fastgpt-cli/`
> 本文是**后续开发的唯一权威指导**，优先级高于原先的 `README.md` / `CLI参考资源使用指南.md`。
> 若与旧文档冲突，以本文为准。读完本文件，再用底部「重规划 Prompt」重启对话执行。
> **v2 更新（2026-08-20）**：吸收了一条外部评审（GPT 深度反馈）——详见下方「§0.1 外部评审融合」：
> FastGPT 定位修正（不做"聊天 CLI"，做 AI 应用生命周期 DevOps CLI，类比 kubectl/gh）、命令面扩展（dataset/app/workflow/agent/evaluation/benchmark）、平台化路线（agent-platform-cli）、开发顺序（先于 Memory）、技术栈取舍、以及 `--help`/dry-run/audit-log/permission 加分项。

---

## §0.1 外部评审融合（v2 必读，来自一份深度对话反馈）

> 以下要点与正文并存，冲突时**以本节为准**（它是最新输入）。逐条看：

**① 定位修正（最重要）**：FastGPT CLI 的**价值不是"让人不用网页去聊天"**，而是**「让 Agent / DevOps 自动管理 FastGPT」**——即 AI 应用生命周期管理，类比 `kubectl` 管 Kubernetes、`gh` 管 GitHub。**不要做 `fastgpt chat`（聊天没意义）**，要做 `app deploy`、`workflow deploy`、`evaluation run`。"chat" 只作为 app 内联能力保留，不作为 CLI 主线。

**② 命令面扩展（比原 §三 更全，以能力生命周期为准）**：
```
fastgpt
├── dataset      # 数据集：dataset create / dataset import ./docs / dataset ls / dataset delete
├── kb           # 知识库（与 dataset 平行/映射）：kb create / kb list / kb upload / kb get / kb delete
├── knowledge    # 知识同步：knowledge sync / knowledge import
├── app          # 应用：app list / app create / app deploy / app test / app describe / app delete
├── workflow     # 工作流：workflow deploy / workflow list / workflow test
├── agent        # Agent：agent run --input "..."  → {answer, tokens, sources}
├── evaluation   # 评测：evaluation run / evaluation compare
├── benchmark    # 基准：benchmark run / benchmark compare（贴合 Harness）/ 
├── query        # 检索（RAG）：query search / query chat（chat 仅此一处）
├── export / backup
├── config
├── status / health
├── schema       # 自省
└── version
```
- `agent run --input "xxx"` 输出必须结构化：`{ "answer":"...", "tokens":1234, "sources":[] }`。
- **拒绝 API 包装**：命令表达高层能力（如 `dataset import ./docs`），不是 `POST /v1/datasets`。

**③ 平台化路线（重要）**：不要止步于孤立 CLI，最终应做 **`agent-platform-cli`（aiops）**，把 FastGPT / memory / rag / agent / evaluation / benchmark 收敛进一个平台控制层：
```
aiops
├── fastgpt {app,workflow,knowledge,evaluation}
├── memory {remember,recall,inspect,benchmark}
├── rag {ingest,search}
└── agent {run,trace,evaluate}
```
本项目的目标是**先做扎实的 `fastgpt` 子模块并预留平台化结构**（命名空间/包设计上让未来可并进 aiops），而不是现在就去建平台。

**④ 开发顺序（注意）**：**先做 TencentDB Agent Memory**（体量小、边界清晰、Agent 属性强、易出亮点）→ **再做 FastGPT**（平台型，复杂度高）。FastGPT 需要有项目管理/应用发布/Workflow 生命周期/测试评估的完整设计。

**⑤ 技术栈（取舍，见本文件 §2.1）**：外部评审**不建议用 Go**，推荐 **Python + Typer/Click**（逻辑大量落在 API/LLM/RAG/Workflow/Evaluation，Python 生态更合适）。你要做的是 AI Agent Tool，不是 kubectl/terraform。**默认建议遵循评审转向 Python+Typer，除非你明确要保留现有 Go 资产。**

**⑥ Agent-native 加分项（做成必检）**：JSON 输出、`--help` 自动自发现、`--dry-run`、`--audit-log`、permission——并入正文 §四 契约。

---

## 一、为什么「走歪了」（现状诊断，逐条对照）

---

## 〇、一句话结论（先读这个）

你现在做出来的 `fastgpt`（create-kb / upload-doc / query 平铺子命令 + cmd/internal/service/client 分层）
是**标准的「人类命令行工具」**。但你要做的是**「Agent 可调用的能力节点」**——即 Agent Interface Layer。
你的定位是「把 FastGPT（企业知识库/RAG）封装成一个稳定 CLI，让 Claude Code / Codex / OpenCode 都能调用」，
所以输出要机器可读、命令要稳定、Agent 要能自省。本文件告诉你怎么改。

---

## 一、为什么「走歪了」（现状诊断，逐条对照）

| 维度 | 当前（走歪） | 应为（Agent-native） |
|---|---|---|
| 定位 | 人类用的知识库管理工具 | Agent 可调用的知识库能力节点 |
| 命令风格 | `fastgpt create-kb` / `upload-doc` / `query` 平铺 | `kb create` / `kb upload` / `kb query` 领域+动作 |
| 反模式 | `create-kb`/`upload-doc` 动词放前面（`kb` 词缺失） | 领域词分组（`kb` / `doc` / `dataset`），动作放叶命令 |
| 第一用户 | 人（TTY） | AI Agent（无 TTY，默认非交互） |
| 输出 | 人类可读为主 | 默认 JSON，机器可读为一等契约 |
| stdout | 混日志/进度/结果 | 仅数据；其余 stderr |
| 自省 | 无 | `fastgpt schema` 让 Agent 运行时发现能力 |
| Chat | 已接 OpenAI 兼容 chat（好），但命令面未按领域重排 | chat 作为 `query chat` / `dataset chat` 叶命令纳入 |
| 封装对象 | 自研 client + 部分占位 service | 直接封装真实 FastGPT API（KB/Doc/dataset/检索），不二次实现 |
| 治理 | harness 过程治理（笔记/STATE/脚本） | 照旧可用，但**不能替代**产品设计 |

核心判断：同项目 A——**harness 过程治理救不了产品设计走偏**。分层代码没错，错在「CLI 该长什么样、给谁用、怎么输出」。

---

## §2.1 技术栈决策（v2：到底 Go 还是 Python？）

外部评审明确建议 **Python + Typer/Click**，理由：你做的是 **AI Agent Tool**（逻辑大量在 API/LLM/RAG/Workflow/Evaluation），Python 生态天然契合，而 Go 更适合作 kubectl/terraform 这类企业基础设施。**逐项对照，别再犹豫：**

| 考量 | Go + Cobra（现状） | Python + Typer/Click（评审推荐） |
|---|---|---|
| Agent tool 生态 | 弱（无现成 skill/json 工具生态） | 强（Claude Code/Codex 的 Python skill、json 一等公民） |
| LLM/RAG/Workflow 库 | 少、要自己拼 | 极丰富（openai、langchain、各种 SDK） |
| 已写代码 | FastGPT 已有可用 Go 代码（chat/config/错误重试） | 需用 Python 重建 |
| 单二进制/分发 | 优（免 CGO，cross-compile） | 弱（需 venv/打包，或接 PyInstaller） |
| 简历/主方向 | Go 是加分项但偏离 Agent 方向 | Python 贴合你 Harness/Agent 主方向 |
| CLI 框架 | Cobra 工程化强 | Typer 轻量、`--help` 自发现更自动、更适合 Agent |

**裁决（已锁定，2026-08-20 用户确认按外部评审执行）：**
- ✅ **本方向定为 Python + Typer**，方向最正（Agent tool）、生态最顺，和你的 Harness/Agent/Skill 主路线一致。不再摇摆。
- 现有 Go 的 chat/config/重试代码，作为**契约与语义参考/迁移来源**，用 Python 重建等价能力，不丢弃其设计。
- 设计决策（§三命令面、§四契约、§五架构、§六路线）与语言无关，全部照用。

> ✅ **已定：采用 Python + Typer**。项目结构为 `cli/`（命令组）、`api/`、`models/`、`output/`、`config/`（详见 §五）；原 Go 的 `cmd/ internal/ pkg/` 目录仅作契约/语义迁移来源。

---

## 二、正确目标：把 FastGPT 变成 Agent 的知识库能力节点

```
人 / AI Agent
        │
        ▼
     fastgpt  ← 稳定 CLI：知识库全生命周期能力
        │
        ▼
  FastGPT Server API (真实后端：KB / Dataset / Upload / RAG query / Chat)
```

设计原则（非协商项）：
1. **稳定领域+动作命令**。`kb create`、`kb upload`、`kb query`、`dataset list`……领域词分组，动作词做叶命令。绝不出现 `fastgpt --action=create --type=kb`。
2. **Agent 是第一用户**。默认非交互、幂等可重跑、失败信息可自纠。
3. **输出是契约**。默认稳定 JSON；`--output table/text` 为人机可读选项（CLI Spec 六原则）。
4. **能力自省**。`schema` / `commands list` 让 Agent 运行时学用法。
5. **调用真实 FastGPT API，不二次实现**（对齐 CLI-Anything「#1 rule」）：已就绪的 OpenAI 兼容 chat 客户端继续用；补上 KB/Doc/dataset/检索的真实客户端，替换占位 service。

---

## 三、命令面重新设计（最要改）

根命令名保持 `fastgpt`，但命令分组按**领域**。推荐以下 MVP + 渐进扩展：

```
fastgpt
├── kb                          # 知识库领域（核心）
│   ├── create                  # 建知识库（原 create-kb）
│   ├── list                    # 列出（原 list-kb）
│   ├── get                     # 查看详情（原 describe-kb）
│   ├── delete                  # 删除（幂等、需 --yes）
│   └── upload                  # 上传文档（原 upload-doc，可 --recursive）
├── doc                         # 文档领域
│   ├── list                    # 列出某库文档
│   ├── get                     # 详情
│   ├── delete                  # 删除
│   └── reindex                 # 重建索引（原 reindex-doc）
├── dataset                     # 数据集领域（若 FastGPT 暴露 dataset 概念）
│   ├── ls / describe / ...     # 与 kb 平行
├── query                       # 检索/生成领域
│   ├── search                  # RAG 检索（原 query，走真实 API）
│   ├── chat                    # 对话（原 chat，已就绪）
│   └── batch                   # 批量查询（原 batch-query）
├── export                      # 导出领域
│   ├── export                  # 导数据
│   └── backup                  # 备份
├── config                      # 配置
│   ├── show / set / init       # （已就绪，保留）
├── status / health             # 只读探测（已就绪，归并到 probe）
├── schema                      # 自省：命令树/参数/输出 shape/错误码（新增）
└── version
```

**使用示例（Agent 视角，默认机器可读）：**

```bash
# 建知识库（默认 JSON：kb_id / status）
fastgpt kb create --name "产品文档" --model text-embedding-3-small --json

# 列出（默认 JSON：items[], total）
fastgpt kb list --json

# 上传（默认 JSON：doc_id[]，进度进 stderr）
fastgpt kb upload --kb "产品文档" --path ./docs/ --recursive --json

# RAG 检索（默认 JSON：results[], scores）
fastgpt query search --kb "产品文档" --query "如何配置 API 密钥" --json

# 对话（默认 JSON、流式用 --output jsonl）
fastgpt query chat --kb "产品文档" --message "你是什么？" --json

# 动手前先探测
fastgpt status --json

# 能力自省（Agent 读它学用法）
fastgpt schema commands list --json
```

进制约定（必须遵守）：
- **禁止** `fastgpt --action=create --type=...` 旗标驱动。
- **禁止** `create-kb`/`upload-doc`/`list-kb`/`batch-query` 这类「动词+名词连写」平铺命令——全部收纳为 `kb create`、`kb upload`、`kb list`、`query batch`。
- **禁止**把进度/日志/错误混进 stdout。

---

## 四、机器可读契约（CLI Spec 六原则，逐条照做）

| 原则 | 落地要求 |
|---|---|
| ① 结构化输出 | 副作用命令默认打印稳定 JSON（定死字段名，勿用 map 顺序漂移） |
| ② Schema 自省 | `fastgpt schema` 输出命令树/参数/输出 shape/错误 kind |
| ③ stderr/stdout 分离 | 数据→stdout；日志、进度、警告、错误→stderr |
| ④ 非交互默认 | 无 TTY 不阻塞；破坏性操作用 `--yes/--force` 而非交互确认 |
| ⑤ 安全重试 | 说明重复运行行为；删除/备份给幂等语义（再跑安全） |
| ⑥ 有界输出 | `--limit/--page`；大结果支持 `--output jsonl` 流式 |

统一错误结构：`{ "error": { "kind": "validation", "message": "...", "details": {...} } }`。
可保留现有 `internal/service/errors.go` 的 HTTP 状态 + 429/5xx 重试逻辑，只补统一的 stdout/stderr 与 kind。

---

## 五、要抄的架构（Python + Typer 目标结构；现有 Go 作契约/语义迁移来源）

参考 CLI-Anything 包结构与 OpenCode 模块划分，目标目录（**Python 包，自研不等同搬运**）：

```
fastgpt-cli/
├── cli/
│   ├── __init__.py
│   ├── main.py          # Typer app 入口（root），即 fastgpt 命令
│   ├── cli/
│   │   ├── dataset.py   # dataset 命令组
│   │   ├── kb.py        # kb 命令组
│   │   ├── app.py       # app 命令组
│   │   ├── workflow.py  # workflow 命令组
│   │   ├── agent.py     # agent 命令组（agent run → {answer,tokens,sources}）
│   │   ├── evaluation.py# evaluation / benchmark 命令组
│   │   ├── query.py     # query 命令组（search/chat，chat 非主线）
│   │   ├── export.py    # export / backup
│   │   ├── schema.py    # 自省命令（新增）
│   │   └── probe.py     # status/health
│   ├── api/             # 真实 FastGPT API 客户端（KB/Doc/dataset/检索/chat；自 Go internal/client 迁移语义）
│   ├── models/          # 共享类型 + 输出 DTO
│   ├── output/          # （新增）统一 json/text/table/jsonl + stderr 规范
│   └── config/          # 配置（自 Go internal/config 迁移语义）
├── pyproject.toml       # 打包：console_scripts 入口 fastgpt = cli.main:app
├── tests/               # pytest：命令树/输出契约/客户端单测
├── fastgpt-source/      # 只读契约参考（已补克隆）
├── .claude/skills/      # 已有 harness skill 照旧；新增领域 SKILL.md
└── scripts/             # 治理脚本（已存在，保留）
```

**关键新增：**
1. `output/`：统一 `--json/--output/--limit` + stderr 规范。
2. `cli/schema.py`：动态生成命令树 JSON（Typer 遍历或注册表）。
3. 真实 FastGPT API 客户端（dataset/kb/app/workflow/agent/检索）——这是从「骨架」到「能力节点」的实打实一步。
4. `.claude/skills/fastgpt/SKILL.md`：教 Agent 怎么用这个 CLI（命令/JSON/错误处理/示例）。

现有 Go 的 `internal/service/chat.go`、`internal/config`、`internal/service/errors.go`（429/5xx 重试）的**命令语义与契约**作为迁移来源，在 Python 里重建等价能力并补齐测试；不追求逐行搬运。

---

## 六、重规划路线（分阶段，每阶段可独立验证）

> 每阶段结束时用 `scripts/handoff-log.py --append ...` 记进度。构建/验证一律走 Python。

- **Phase 0 · 方向校准（半天）**：读本文 + `cli-reference/CLI-Anything/zotero/agent-harness/cli_anything/zotero/zotero_cli.py` + `cli-reference/cli-spec/README.md`。在 `notes/proposed/` 记一条架构决策：「命令面改为 agent-native 领域分组 + JSON 默认 + 转向 Python/Typer + FastGPT 定位=AI 应用生命周期」。
- **Phase 1 · 项目初始化 + 命令树骨架（1-2天）**：建 `pyproject.toml`（console_scripts `fastgpt`）、`cli/` 包与领域命令组（dataset/kb/app/workflow/agent/evaluation/query/export/schema/status/version）；根命令可 `fastgpt --help`。目标：`fastgpt schema --json` 输出机器可读命令树；`python -m pytest` 通过。**验证**：`fastgpt kb list --json 2>/dev/null` 输出合法 JSON（KB 未接真实后端前可空 items[]）且 stderr 无数据。
- **Phase 2 · 输出契约硬化（1天）**：新增 `output/`，所有命令默认 JSON、数据进 stdout、日志进 stderr、`--limit` 有界；错误统一 `error.kind`。补 pytest 断言 stdout 纯净性。**验证**：`fastgpt kb list 2>/dev/null | python -m json.tool` 通过。
- **Phase 3 · 真实后端接入（2-3天）**：封装 FastGPT 真实 dataset/kb/app/workflow/检索 API 到 `api/`；`query search`/`agent run` 走真实链路。**验证**：对一个真实知识库完成 `fastgpt dataset create → fastgpt dataset import ./docs → fastgpt query search` 三连并核对返回。
- **Phase 4 · 自省与会话（1天）**：`schema` 覆盖全部命令；实现 `session`（可选）。**验证**：`fastgpt schema commands list --json` 与真实命令一一对应。
- **Phase 5 · Agent 可发现（半天）**：写 `.claude/skills/fastgpt/SKILL.md`；让一个编码 Agent 只用 CLI 完成「建库 → 传 2 文 → 检索 → agent run」真实任务（对齐 CLI-Anything Phase 6.5 / Agent test）。
- **Phase 6 · 收尾**：更新 README 命令示例为新结构；`scripts/audit.py .` NOT-OK 为 0；预留 `agent-platform-cli`（aiops）并入结构。

---

## 七、立即要做 vs 不要做

**要：** 命令面领域分组、默认 JSON、加 `schema`、真实后端接入、SKILL.md、phase0 决策笔记。
**不要：** 推翻已就绪的 chat/config/错误重试；不要在 `create-kb` 平铺路上继续堆命令；不要把 harness 治理当产品设计。

---

## 八、参考材料（按需读）

- 方向定位：HKUDS/CLI-Anything 主 README 与 `cli-anything-plugin/HARNESS.md`（7 阶段 SOP + 架构原则）。
- 现成样例：`cli-reference/CLI-Anything/zotero/agent-harness/cli_anything/zotero/zotero_cli.py`。
- CLI 契约：`cli-reference/cli-spec/README.md`（六原则）。
- 你的方向笔记：`CLI项目开发规划与提示词.md`、`CLI参考资源使用指南.md`（作背景，命令设计以本文为准）。

**请用下面这份 Prompt 重启这个项目的新对话，让它读本文并重新规划。**
