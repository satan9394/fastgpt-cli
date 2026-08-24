# 示例规则集（虚构演示，非真实犯错记录）

> ⚠️ **这不是模板**：下面的每一条都是「假设的 TypeScript 项目」里可能出现的规则，仅示范**格式与粒度**。
> 你的项目从空文件开始，**只记录真实发生过的错误**（触发信号见 references/growth.md）。
> 真实项目里凭空贴这些规则 = 违反本 Skill 的减法哲学，稀释重要规则的权重。

## 格式示范（每条：命令/不变量 + 为什么）

1. **测试**：`pnpm vitest run` —— agent 曾用错 `npm test`（指向 mocha，测试没跑）。
2. **包管理**：只用 pnpm，禁止 npm/yarn —— 装包导致 lock 文件冲突。
3. **项目结构**：components/features/lib/api 各放什么 —— agent 曾把组件放错目录。
4. **风格**：不用 TypeScript enum，用 literal union type —— 团队约定。
5. **Git**：永不直推 main；feature/ 分支 + PR；commit 格式 `type(scope): description`。
6. **架构**：单组件 <200 行；业务逻辑抽到自定义 hook，组件只做渲染。
7. **依赖**：添加新依赖前先确认现有依赖能否实现（date-fns 已装，别引 moment）。
8. **提交前检查**：`pnpm lint && pnpm type-check` 必过，不允许 eslint-disable。
9. **错误处理**：不允许空 catch；统一用 AppError 类；用户可见错误要友好。
10. **API 层**：统一走 src/api/ 下的封装，不在组件里直接 fetch。

## 判断：哪些会升级成约束（硬化）

- #5（Git 直推）后果不可逆 → 升工具拦截 + CI 阻断。
- #8（提交前检查）高频 → CI 强制，不只靠自觉。
- 其余（风格/结构/依赖）可逆低成本 → 保持建议即可。

## 生搬硬套的下场（反面）

把这份清单整段贴进一个 Python 项目：pnpm/vitest/enum/hook 全部失效，纯噪音。
`#5 Git` 被当建议执行 → 一个 agent 直推了 main。
——这就是「从空文件开始，只记真实错误」为什么是硬纪律。
