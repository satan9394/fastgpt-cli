# 人类 onboarding（新成员上手）

> 这份文件给**人类队友**读，不是给 agent 读。它是 CLAUDE.md 的双消费版本——agent 看 CLAUDE.md 的 `@agent` 部分，你看这份。
> 团队场景第一步：跑通它。单人项目可跳过。

## 三步上手

1. **环境就绪自检**（10 分钟）：
   ```bash
   cd <项目根目录>
   # 第一次：把 skill 的脚本装进项目（bootstrap 会放 scripts/audit.py、record-error.py、STATE.json）
   python <skill 路径>/scripts/bootstrap.py --install-scripts --dir .
   python scripts/audit.py .          # 就绪检查：依赖能装、一条命令能启动、无脚本报错
   ```
   看到「[OK] 反馈层 / [OK] 基础设施」说明环境 OK；看到 [NOT-OK] 先问 owner，别硬闯。

2. **跑一个垂直切片**（30 分钟）：让项目的最小路径真实跑起来（跑测试 / 起服务 / 跑一条数据命令）。你没有见过它跑起来，后面一切约定都是空话。

3. **核对个人配置不覆盖共享红线**（10 分钟）：你的 `settings.local.json` / auto-memory 里有没有覆盖项目的共享约束（比如禁了某条 hooks、改了 deny）？共享约束 > 个人配置。新成员最常见的坑就是个人配置把团队红线静默盖掉。

## 你要知道的项目约定（问 owner 逐条确认，别猜）

- 测试命令：`<test_cmd>`（唯一，agent 和人都用这个）
- 分支与合并：`feature/` + PR，main 直推被拦（有 hook/CI）
- 规则改动的流程：走 PR + 独立评审（见 team-playbook）
- 谁维护 harness（owner 是谁、敏感路径谁批准）

## 双向标注说明

- 指令文件里 `@human` 段：你需要读（命令、目录含义、约定）。
- `@agent` 段：agent 读（不变量、陷阱），你看个大概即可。
- 两者共用段：都要读。

## 你的第一次真实事故

跑起来之后，你遇到的第一个真实问题就是最有价值的：用 `scripts/record-error.py` 记进 STATE.json（出生证明），它可能长成一条新规则。**这不是为了惩罚你，是让 harness 长出对真实情况的记忆。**
