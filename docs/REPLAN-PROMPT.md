> 用法：复制下面代码块内的全部内容，粘贴到新对话（项目 B：FastGPT CLI）的第一条消息，然后设定目标即可自主执行。
> 先用这份 Prompt **重新规划**，再按规划执行。上一轮方向走偏，本次以指导文件为准重来。

```
【目标】把 FastGPT CLI（fastgpt-cli/）从「传统 CLI」改造为「Agent-native CLI（Agent 可调用的 AI 应用生命周期能力节点）」。
本阶段：先读指导文件完成「重新规划」，再按新规划执行 Phase 0-1（方向校准 + 命令面重排），通过全部验证标准后自主收尾。

【第一步：先读指导文件（本对话执行重构的唯一权威）】
- E:\DeepSeek_Harness\workspace\2026_08_20\指导文件-FastGPT-CLI改造.md
  请通读全文，重点：〇结论、§0.1 外部评审融合（必读，v2：定位修正→不做聊天 CLI、命令面扩展、技术栈）、§2.1 技术栈决策、一诊断对照表、三命令面重新设计、四 CLI Spec 契约、五要抄的架构、六重规划路线。
  读完后，先按第二节「重规划路线 Phase 0」写一条 notes/proposed 架构决策（命令面改为领域分组 + JSON 默认 + 技术栈选择 + FastGPT 定位=AI 应用生命周期管理），
  再把你对「重新规划」的理解（命令树清单 + 落地顺序 + 技术栈裁决 + 定位修正）写进本对话输出，再动手。
  注意：§0.1 的定位修正（不做 fastgpt chat 主线）与命令面扩展（dataset/app/workflow/agent/evaluation/benchmark）务必吸收；§2.1 技术栈**已锁定 Python + Typer**（用户已确认），按此执行。

【第二步：背景与上下文（按需读，冲突以指导文件为准）】
- E:\DeepSeek_Harness\workspace\2026_08_20\fastgpt-cli\CLAUDE.md（harness 指针节 + .harness/manifest.json + HANDOFF.md + STATE.json）
- E:\DeepSeek_Harness\workspace\2026_08_20\fastgpt-cli\README.md
- 参考架构样例：E:\DeepSeek_Harness\workspace\2026_08_20\cli-reference\CLI-Anything\zotero\agent-harness\cli_anything\zotero\zotero_cli.py
- CLI 契约：E:\DeepSeek_Harness\workspace\2026_08_20\cli-reference\cli-spec\README.md（六原则）

【第三步：本阶段任务（对应指导文件 Phase 1 + 前置 Phase 0，且遵循 §0.1②/§2.1）】
- 确认 fastgpt-source/ 已补克隆（缺则先：git clone https://github.com/labring/FastGPT.git fastgpt-source；失败则停下报告，别用残缺目录）
- 依据 §0.1② 命令面重排：dataset create/import、kb create/list/upload/get/delete、app list/create/deploy/test、workflow deploy/list/test、agent run、evaluation run/compare、benchmark run/compare、query search/chat、export/backup、config、schema、status/health、version
- 技术栈**用 Python + Typer**（已锁定）：按指导 §五 建 `cli/`（命令组）、`api/`、`models/`、`output/`、`config/` 分层；原 Go 的 cmd/internal/pkg 代码作契约/语义迁移来源
- 根命令新增 schema（自省）、status/health（归并 probe）
- 定位修正：`fastgpt query chat` 仅保留为内联检索能力，**不作为 CLI 主线**；主线是 dataset/app/workflow/agent/evaluation 生命周期
- 拒绝 API 包装：命令表达高层能力（如 dataset import ./docs、agent run），不是 POST /v1/... 包装
- 已就绪的 chat/config/错误重试(429/5xx) 逻辑作为语义参考迁移到 Python，不丢弃
- scripts/note-lifecycle.py new --class architecture --title "<agent-native 命令面决策>"（记 proposed）
- 环境检查：python --version 可用（建议 3.10+）；Typer/pytest 可 pip 安装（走 127.0.0.1:7897 代理）；不可用停下报告，不自行装
  额外：必要时读取现有 Go 代码（internal/client(chat)、internal/config、internal/service/errors.go）确认契约语义，再在 Python 里等价重建。

【第四步：验证标准（全过才算完成）】
- Python 侧：python -m pytest 通过、ruff check 通过、（可选）typer --help 输出完整命令树
- python -m <pkg> schema --json 输出合法机器可读命令树（或安装后命令等价）
- 输出契约：默认 JSON、数据进 stdout、日志/进度/错误进 stderr（如：python -m <pkg> kb list 2>/dev/null 输出合法 JSON；KB 未接真实后端前可输出空 items[] 契约）
- 用 read 确认现有 Go chat/config/重试的契约语义已正确迁移到 Python（不丢弃设计）

【第五步：边界与隔离（必须遵守）】
- 只修改 fastgpt-cli/ 内文件；不碰 tencentdb-agent-memory-cli/ 与 cli-reference/（参考只读）
- 删除走 PowerShell 回收站（禁 rm 等彻底删除）
- 收尾用 scripts/handoff-log.py --append "..." --verify "..." 追加 HANDOFF.md

【第六步：完成时输出】
1) 你的「重新规划」概述（命令树 + 定位修正 + 技术栈裁决 + 落地顺序）
2) 改动文件清单
3) 验证命令与结果
4) 下一步建议（指导文件 Phase 2 输出契约硬化 / Phase 3 真实后端接入 / 平台化 agent-platform-cli 预留）
```
