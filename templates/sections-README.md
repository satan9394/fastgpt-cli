# sections/ 拆分纪律（v4.7.0 M2）

配套 `templates/sections-skeleton-SKILL.md` 的说明文档。回答四个问题：
**何时拆、拆哪些节、怎么引用、边界在哪**。

## 一、何时拆（触发信号，不是拍脑袋）

SKILL.md 是五组件之一（指令层），太长本身就稀释权重。以下任一信号出现再拆：

1. **正文超长**：单文件正文 > 500 行（核心 SKILL.md 当前约 260 行，尚不需要；领域 skill 若膨胀到该量级即触发）。
2. **单次加载灌满上下文**：读者/模型进 skill 必须一次读完几十个长表、长清单才能动手。
3. **条目持续增长**：同一节的表格（范围判定、委托表、Rationalizations）连续三轮只增不减。
4. **已有结构外挂内容**：SKILL.md 里出现「见 xxx 附录 / 详见文档」的悬空指针，但内容还堆在正文里。

**不拆**：正文 < 150 行的薄 skill、一次性探索用的笔记、还没长到触发信号的普通 SKILL.md。
拆是有成本的（索引 + 引用 + 校验），不是 KPI。

## 二、拆哪些节

按「入口高频、细节低频」分界：

**留在骨架（SKILL.md 正文）**：
- frontmatter（含 version + sections 声明）
- 3-5 句简介（定位 + 与核心的关系）
- sections/ 索引
- 一句话版核心纪律（每条纪律只留结论，论证拆走）
- 委托表（核心/脚本/references 的指针）

**拆进 sections/（每节一个文件）**：
- 长表格：范围判定表、When to Apply/Skip 明细、Rationalizations（借口|现实）全集
- 方法步骤的逐节展开（五步协议在本域的完整走法）
- 长清单：Red Flags 全量自检、Verification 全量出口
- 历史/校准/背景叙述（低频率读取内容）

**不拆**：五组件模型接口本身、description 双要素契约、frontmatter 结构。拆分只改正文承载方式。

## 三、怎么引用

- **frontmatter `sections:` 数组**（主引用）：条目是相对 **SKILL.md 所在目录** 的路径，如
  `sections/01-core-discipline.md`。`verify-integrity.py` 逐条核对存在性。
- **sections/INDEX.md**（人工阅读入口）：列 `| 节 | 主题 | 何时读 |`，里面的 `.md` 链接也会被
  `verify-integrity.py` 核对。INDEX.md 或 README.md 任一作索引文件名均可。
- **正文指针**：骨架各节用相对链接指回 sections/（如「详见 `sections/02-method-detail.md`」），
  正文不复制细节正文，只留指针。
- **共享 references 仍引用不复制**：sections/ 只装本 skill 的细节，核心 `references/` 的共享规则
  依旧「引用不复制」，不得把核心正文搬进 sections/ 造成多副本漂移。

校验命令：
```
python skill/scripts/verify-integrity.py --root skill --expect-version <版本>
```
无 sections 声明时该项 SKIP（不报错）；有声明时任一引用缺失即 NOT-OK。

## 四、边界

1. **不重写五组件接口**：指令/约束/反馈/记忆/编排五组件的语义、顺序、接口定义不动；sections/
   只是指令层文件「瘦身 + 外置」的承载方式，不是新的架构层。
2. **不新增 skill/hook/monitor**：sections/ 是文件拆分，不是新 skill 实例、不注册新运行入口。
   拆完后的 SKILL.md 仍是同一个 skill 的同一个 frontmatter name。
3. **不自动搬既有文件**：对已有 SKILL.md 动手前先走受监督自我修改协议（检测→提案→验证→人在环批准）；
   本模板与纪律只提供方法，不替代既有结构变更的审批。
4. **模板/校验脚本是增强非结构改动**：`sections-skeleton-SKILL.md`、`sections-README.md`、`verify-integrity.py`
   三者都只新增文件，不改任何既有文件；bootstrap 的 templates/ 复制机制（`for f in os.listdir(templates/)`）
   自动覆盖新模板分发，bootstrap.py 本身不改。
5. **版本一致性是硬约束**：frontmatter `version` 与 `skill/.skillhub.json` 的 `version` 必须一致，
   `verify-integrity.py --expect-version` 逐 SKILL.md 核对；不一致即 NOT-OK，不做「为过 PASS 改数据」。
