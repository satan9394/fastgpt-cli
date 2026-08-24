# 两个 CLI 项目开发规划与提示词（harness 架构实践版）

> 创建：2026-08-20。用途：把 harness-engineering v4.11.0 架构分别用于两个 CLI 项目的开发实践。
> 两个项目**各开一个新对话**分别执行（环境隔离），本文件是总规划 + 两份可直接复制的启动提示词。
> harness 架构源：`E:\Code_file\Claude_code\2026\08\03\harness-engineering\v4.11.0\skill\`（只读参考，迭代在源仓库进行）。

> ⚠️ **方向纠正（2026-08-20 追加）**：本文件原规划把两个项目按**传统 CLI（Cobra 平铺子命令）**开发，方向已走偏。
> 正确方向是 **Agent-native CLI（Agent 可调用的能力节点 / Agent Interface Layer）**。开发一律改用新文件：
> - 项目 A 指导：`指导文件-AgentMemory-CLI改造.md`（v2，含外部评审融合）+ `启动提示词-AgentMemory-重规划.md`
> - 项目 B 指导：`指导文件-FastGPT-CLI改造.md`（v2，含外部评审融合）+ `启动提示词-FastGPT-重规划.md`
> **v2 要点**：① Memory 价值最高（⭐5，Agent 基础设施）、FastGPT 定位修正为 AI 应用生命周期 DevOps CLI（类比 kubectl/gh，不做 chat 主线，扩展 app/workflow/agent/evaluation/benchmark 命令面）；② 最终走向 `agent-platform-cli`（aiops）平台化（先 Memory → 再 FastGPT）；③ 技术栈**已锁定 Python + Typer**（用户已确认按外部评审执行，Agent tool 生态），原 Go 代码作契约/迁移来源；④ 加分项：`--help` 自发现、`--dry-run`、`--audit-log`、permission。
> 本文件保留作背景与 harness 过程治理参考；命令面设计以指导文件为准。

---

## 一、总体方案

### 1.1 背景

- 我们正在迭代 harness-engineering 架构（当前 v4.11.0，交接报告能力已交付）。
- 手头有两个项目要改造成 CLI 工具（Go + Cobra），目标是简历亮点。
- 做法：把 harness 架构分别装进两个项目，让每个项目在 harness 治理下开发（指令/约束/反馈/记忆/编排五组件），同时两个项目完全隔离。

### 1.2 两个项目

| 项目 | 目录 | 原项目源码 | 目标 |
|---|---|---|---|
| Agent Memory CLI | `tencentdb-agent-memory-cli/` | `agent-memory-source/`（已克隆，腾讯云 TencentDB Agent Memory） | 把 AI Agent 记忆管理封装成 CLI（store/recall/search） |
| FastGPT CLI | `fastgpt-cli/` | `fastgpt-source/`（克隆不完整，需补） | 把企业知识库管理封装成 CLI（create-kb/upload-doc/query） |

### 1.3 环境隔离设计（已落地）

每个项目**自带完整 harness 组件**，互不干扰：

- 独立的：`CLAUDE.md`（含"项目 Harness 指针"节）、`scripts/`（10 个脚本）、`notes/`（决策记录）、`STATE.json`（规则与事故记忆）、`.harness/`（manifest + config）、`.claude/`（hooks + 领域 skill 接线）、`HANDOFF.md`、`docs/ARCHITECTURE.md`。
- 各自的原项目源码在各自目录内（A 看 `agent-memory-source/`，B 看 `fastgpt-source/`）。
- 共享但不冲突：harness skill 源（只读）、Go 工具链（`D:\Technology_application\go\bin`，已入用户 PATH）。
- 隔离纪律：项目 A 的新对话**只允许修改 A 目录**，不碰 B 和 cli-reference；B 同理。

### 1.4 当前状态（2026-08-20 已就绪）

- ✅ 两个项目均已 `bootstrap.py --init` 装好 harness v4.11.0（audit 0 / wiring OK / 10 脚本 / notes 树 / 双 hooks / manifest）。
- ✅ Go 1.26.7 已装：`D:\Technology_application\go\bin\go.exe`（新终端 `go` 可用；找不到时用完整路径）。
- ✅ 本规划文档。
- ⚠️ FastGPT 的 `fastgpt-source/` 克隆不完整（只有 .git），B 对话第一步补克隆。
- 📌 提示词中 `github.com/<yourname>/...` 请替换为实际 GitHub 用户名。

---

## 二、项目 A：Agent Memory CLI 开发

### 2.1 开发路线（对应 任务执行文档.md 第二节）

- **Day 1-2（本次新对话）**：Go 模块 + Cobra + 分层目录（cmd/ internal/service internal/storage internal/client internal/config pkg/）+ root 命令 + store/recall/search 三个核心命令骨架。
- Day 3-4：本地 SQLite 存储（schema：memories 表 + 类型/时间索引）+ JSON 导入导出。
- Day 5-7：封装 TencentDB API 客户端（SyncMemory / PullMemory）+ 认证 + 重试。

### 2.2 启动提示词

**独立文件（复制整段到新对话 A 即可自主执行）**：`启动提示词-AgentMemory.md`
（文件内代码块即完整提示词，粘贴到新对话第一条消息后设定目标即可。）

---

## 三、项目 B：FastGPT CLI 开发

### 3.1 开发路线（对应 任务执行文档.md 第一节）

- **Day 1-2（本次新对话）**：补克隆 fastgpt-source → Go 模块 + Cobra + 分层目录（cmd/ internal/service internal/client internal/config pkg/）+ root 命令 + create-kb/upload-doc/query 三个核心命令骨架。
- Day 3-4：配置文件设计（yaml：server/defaults/logging）+ 配置读写。
- Day 5-7：封装 FastGPT API 客户端（CreateKnowledgeBase / UploadDocument）+ 认证。

### 3.2 启动提示词

**独立文件（复制整段到新对话 B 即可自主执行）**：`启动提示词-FastGPT.md`
（文件内代码块即完整提示词，粘贴到新对话第一条消息后设定目标即可。）

---

## 四、harness 用法速查（两个项目通用，装进项目后即用）

| 命令 | 用途 | 示例 |
|---|---|---|
| `python scripts/audit.py .` | 审计 harness 健康（五组件 + 数据/隐私） | 定期跑，NOT-OK 即处理 |
| `python scripts/note-lifecycle.py new --class architecture --title "..."` | 记决策提案（proposed） | 每个架构决定一条 |
| `python scripts/note-lifecycle.py status notes/proposed/... --implemented` | 决策落地 | 骨架自动改写 |
| `python scripts/note-lifecycle.py verify` | 门禁：状态/分类/章节/归档冻结 | 提交前跑 |
| `python scripts/record-error.py --init` | 初始化事故记忆 | 第一次跑 |
| `python scripts/handoff-log.py --append "..." --verify "..."` | 会话结束追加 HANDOFF 变更日志 | 每轮收尾 |
| `python scripts/skill-router.py --check-wiring .claude/skills --config .harness/config.json` | 领域 skill 接线校验 | 装完即 OK |

## 五、完成判定与后续

- **每个新对话的完成判定**：提示词第 4 步验证标准全过 + 输出三要素（改动清单/验证结果/下一步）。
- **会话收尾**：HANDOFF.md 变更日志由 handoff-log 追加；决策笔记在 notes/；事故在 STATE.json——三者构成该项目的"交接报告"，下个对话先读 CLAUDE.md 指针节即可续接。
- **简历整合**：两个项目各自完成后，按 `任务执行文档.md` 第三节模板写简历（35+ 命令、分层架构、性能指标——**只写真实达成的**，不预填）。
- **harness 迭代**：两个项目的实践反馈（踩坑/新需求）回到 harness-engineering 源仓库（v4.12 触发式），形成"实践 → 迭代"闭环。
