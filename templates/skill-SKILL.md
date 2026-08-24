# 领域 Skill 骨架模板（v4.3.0 分离式执行）

> 使用：复制本文件到 `skills/<domain>/SKILL.md` → 替换 `{占位符}` → 按本模板结构填充。
> 纪律：**薄入口，委托核心，不复制共享规则**。description 双要素契约，正文精简不膨胀。
> 参考：`v41-separated-skill-design.md` 第四节、`skill-router.py`（路由碰撞检查）。

```markdown
---
name: harness-{domain}
description: >
  一句话表述这个 skill 做什么（第三方视角，扁平总结，不写流程）。
  Use when: {触发场景清单，只写本域触发词，绝不写流程步骤}。
  Skip when: {反触发场景，防跨域误触发}。
# requires 依赖闭包（v4.7.0，可选）：依赖核心恒 OK；依赖其它领域 skill 用短名/full name。
# --check-wiring 校验：被依赖存在且启用 → OK；存在未启用 → WARN；缺失（非核心）→ NOT-OK。
# 例：requires: [harness-engineering]（依赖核心）或 requires: [harness-requirements]（依赖另一领域）。
---

# Harness {domain}

## When to Apply / Skip

| 场景 | 用/不用 |
|------|---------|
| {适用场景 1} | 用 |
| {适用场景 2} | 用 |
| {不适用场景（反触发）} | 跳过 → 委托给核心或其他领域 skill |

## 方法（薄入口，委托核心）

- {步骤 1：识别 → 委托核心哪部分}
- {步骤 2：执行核心协议/脚本}
- {步骤 3：验证出口}
> 本 skill 不复制核心五组件/五步协议正文；共享规则只在核心 references，这里引用。

## Common Rationalizations

| 借口 | 现实 |
|------|------|
| {模型/人常用的合理化借口} | {事实反驳} |

## Red Flags

- [ ] {自检项 1}
- [ ] {自检项 2}

## Verification

- {可验证出口 1：命令/清单}
- {可验证出口 2：客观判据}

## 委托

- 核心协议：→ 核心 SKILL.md 五步协议
- 脚本：→ scripts/audit.py、scripts/record-error.py、scripts/skill-router.py
- 共享 references：→ references/{growth|harness-audit|...}.md（引用不复制）
```

## 完成检查

- [ ] frontmatter description 只写触发条件（无流程步骤）
- [ ] 正文 < 200 词（描述）／正文精简（常用 skill < 500 行）
- [ ] 不复制核心共享规则（只引用）
- [ ] When to Apply / Skip 与核心和其他领域不重叠（跑 `skill-router.py --check-descriptions`）
- [ ] 每域含「实现 + 门禁」语义（dev→verify / ui→finish-gate / req→acceptance / pr→reviewer）
