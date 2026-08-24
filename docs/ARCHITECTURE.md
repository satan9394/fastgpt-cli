# ARCHITECTURE —— 架构地图

> 用途：项目架构的单一入口（与指令文件"指针"节呼应）。由 bootstrap.py --init 生成，占位符由真实项目内容替换。
> 保持精简：只记"要记住的架构事实"，详细设计下沉到 docs/decisions/（ADR）。

## 概览
- 技术栈：{stack}
- 一句话架构：{one_line}

## 模块与职责（各目录放什么）
| 路径 | 职责 |
|------|------|
| {workspace}/{dir1}/ | {用途} |

## 架构不变量（不存在什么，违反者门禁拦截）
- 不存在 {不变量1}
- 不存在 {不变量2}

## 依赖层级（强制执行）
- {dep_hierarchy}，违反者 CI 拦截

## 决策记录指针
- 决策记录 → notes/（Agent Notes 四态，`scripts/note-lifecycle.py` 管理：proposed / implemented / rejected / archived）
- 详细设计 → docs/decisions/（ADR，一条一文件）
