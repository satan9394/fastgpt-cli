# CLI参考资源使用指南

## 📁 目录结构

```
E:\DeepSeek_Harness\workspace\2026_08_20\
├── fastgpt-cli\                          # FastGPT CLI项目
│   ├── README.md                         # 项目规划文档
│   └── fastgpt-source\                   # 占位符（需手动克隆）
├── tencentdb-agent-memory-cli\           # Agent Memory CLI项目
│   ├── README.md                         # 项目规划文档
│   └── agent-memory-source\              # ✅ 已克隆的项目代码
├── cli-reference\                        # CLI开发参考资源
│   ├── README.md                         # 资源索引
│   ├── nodejs-cli-apps-best-practices\   # ✅ CLI最佳实践
│   ├── CLI-Anything\                     # ✅ GUI转CLI指南
│   └── cli-spec\                         # ✅ CLI设计规范
├── 任务执行文档.md                        # 详细任务清单
├── 今日工作总结.md                        # 今日工作总结
├── 快速启动指南.md                        # 新对话启动指南
└── CLI参考资源使用指南.md                 # 本文档
```

---

## 🎯 资源使用建议

### 1. nodejs-cli-apps-best-practices

**文件数量**: 26个文件

**核心内容**:
- 41个CLI应用最佳实践
- 命令行体验设计
- 分发和打包策略
- 配置管理
- 测试和CI/CD

**使用场景**:
- 设计FastGPT CLI的命令结构
- 设计Agent Memory CLI的用户体验
- 学习如何提供帮助信息
- 学习如何处理错误

**快速开始**:
```bash
# 阅读README
cat E:\DeepSeek_Harness\workspace\2026_08_20\cli-reference\nodejs-cli-apps-best-practices\README.md

# 阅读中文版
cat E:\DeepSeek_Harness\workspace\2026_08_20\cli-reference\nodejs-cli-apps-best-practices\README_zh-Hans.md
```

---

### 2. CLI-Anything

**文件数量**: 1853个文件

**核心内容**:
- 7阶段GUI转CLI流水线
- 多种GUI应用的CLI化示例
- 适配器层设计模式
- 测试策略

**使用场景**:
- 学习如何将FastGPT的Web界面转化为CLI
- 学习如何将Agent Memory的功能封装为CLI
- 参考其他GUI应用的CLI化案例

**快速开始**:
```bash
# 阅读README
cat E:\DeepSeek_Harness\workspace\2026_08_20\cli-reference\CLI-Anything\README.md

# 阅读中文版
cat E:\DeepSeek_Harness\workspace\2026_08_20\cli-reference\CLI-Anything\README_CN.md

# 查看7阶段流水线
cat E:\DeepSeek_Harness\workspace\2026_08_20\cli-reference\cli-anything-plugin\HARNESS.md
```

---

### 3. CLI Spec

**文件数量**: 1个文件（文档）

**核心内容**:
- 6个CLI设计原则
- 结构化输出规范
- Schema自省规范
- 错误处理规范

**使用场景**:
- 设计FastGPT CLI的输出格式
- 设计Agent Memory CLI的错误处理
- 学习如何提供Schema命令

**快速开始**:
```bash
# 阅读文档
cat E:\DeepSeek_Harness\workspace\2026_08_20\cli-reference\cli-spec\README.md

# 访问官网
# https://clispec.dev/
```

---

## 📋 开发流程建议

### FastGPT CLI开发流程

**Phase 1: 分析（参考CLI-Anything）**
1. 分析FastGPT的Web界面功能
2. 识别核心操作（创建知识库、上传文档、查询）
3. 设计命令结构

**Phase 2: 设计（参考CLI Spec + nodejs-cli-apps-best-practices）**
1. 设计命令命名（动词+名词）
2. 设计输出格式（JSON/表格/文本）
3. 设计错误处理
4. 设计帮助信息

**Phase 3: 实现（参考Cobra框架）**
1. 搭建项目结构
2. 实现核心命令
3. 实现配置管理
4. 实现错误处理

**Phase 4: 测试（参考nodejs-cli-apps-best-practices）**
1. 编写单元测试
2. 编写集成测试
3. 测试用户体验

**Phase 5: 文档（参考CLI-Anything）**
1. 编写使用文档
2. 编写开发文档
3. 编写示例代码

---

### Agent Memory CLI开发流程

**Phase 1: 分析（参考CLI-Anything）**
1. 分析TencentDB Agent Memory的功能
2. 识别核心操作（存储、召回、搜索、同步）
3. 设计命令结构

**Phase 2: 设计（参考CLI Spec + nodejs-cli-apps-best-practices）**
1. 设计命令命名
2. 设计输出格式
3. 设计错误处理
4. 设计帮助信息

**Phase 3: 实现（参考Cobra框架）**
1. 搭建项目结构
2. 实现核心命令
3. 实现配置管理
4. 实现错误处理

**Phase 4: 测试（参考nodejs-cli-apps-best-practices）**
1. 编写单元测试
2. 编写集成测试
3. 测试用户体验

**Phase 5: 文档（参考CLI-Anything）**
1. 编写使用文档
2. 编写开发文档
3. 编写示例代码

---

## 🔧 技术选型确认

### Go语言CLI框架

**推荐使用Cobra**:
- 功能强大，生态完善
- FastGPT本身是Go写的
- 支持子命令、标志、帮助信息

**参考资源**:
- Cobra文档: https://cobra.dev/
- Cobra示例: https://github.com/spf13/cobra/blob/main/cobra_command.go

### 输出格式设计

**参考CLI Spec的6个原则**:
1. 结构化输出（JSON）
2. Schema自省
3. 错误/输出分离
4. 非交互式默认
5. 安全重试
6. 有界输出

**示例**:
```bash
# 默认人类可读
agent-memory recall --query "测试"

# JSON输出
agent-memory recall --query "测试" --output json

# 表格输出
agent-memory recall --query "测试" --output table
```

---

## 📚 进一步学习

### 必读文档

1. **nodejs-cli-apps-best-practices/README.md**
   - 41个最佳实践的详细说明
   - 每个实践都有示例代码

2. **CLI-Anything/cli-anything-plugin/HARNESS.md**
   - 7阶段流水线的详细说明
   - 如何将GUI应用转化为CLI

3. **cli-spec/README.md**
   - 6个设计原则的详细说明
   - 如何设计结构化输出

### 推荐阅读

1. **Cobra框架文档**
   - https://cobra.dev/
   - 学习如何使用Cobra构建CLI

2. **Go CLI教程**
   - https://github.com/spf13/cobra/blob/main/cobra_command.go
   - 学习Cobra的最佳实践

3. **CLI设计指南**
   - https://clig.dev/
   - 学习CLI设计的通用原则

---

## ✅ 下一步行动

### 立即执行

1. **阅读参考文档**
   - 阅读nodejs-cli-apps-best-practices的README
   - 阅读CLI-Anything的README
   - 阅读CLI Spec的README

2. **设计命令结构**
   - 为FastGPT CLI设计命令
   - 为Agent Memory CLI设计命令

3. **开始开发**
   - 从Agent Memory CLI开始（代码已就绪）
   - 搭建项目结构
   - 实现核心命令

### 后续任务

1. **完善功能**
   - 实现所有命令
   - 实现配置管理
   - 实现错误处理

2. **测试验证**
   - 编写单元测试
   - 编写集成测试
   - 测试用户体验

3. **文档编写**
   - 编写使用文档
   - 编写开发文档
   - 编写示例代码

4. **发布上线**
   - 编译为二进制文件
   - 编写安装脚本
   - 发布到GitHub

---

**文档创建时间**: 2026-08-20 01:00
**状态**: 已完成资源收集和使用指南编写
