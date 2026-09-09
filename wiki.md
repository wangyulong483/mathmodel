# MathModel 4.0 工作流：题目到国赛提交包

本工作流适用于全国大学生数学建模竞赛，也可以用于校赛和训练题。核心目标不是“让模型写出一篇像论文的文字”，而是让题目、数据、代码、图表、论文和提交材料形成可复现的证据链。

## 0. 总原则

1. **先理解题目，再选择模型。** 不根据流行算法反推题意。
2. **先写验证，再写结论。** 每个结论都要有指标、对比、守恒、交叉验证、敏感性分析或人工可解释性证据。
3. **AI 只提出候选，不替代运行。** GPT/DeepSeek 可以拆题和审稿，不能伪造实验结果。
4. **联网资料分级。** Brave MCP 用于官方资料和论文原文；GitHub MCP 用于工程实现和模板参考；搜索摘要不能直接进参考文献。
5. **脚本可离线运行。** API 不可用时，仍能初始化、运行模型、审计和生成 DOCX。
6. **最后一次构建必须可复现。** 论文数字从代码输出或保存的结果文件读取，不靠手工回忆。

## 1. 文件契约

| 路径 | 输入/输出 | 责任 |
|:---|:---|:---|
| `input/question.md` | 输入 | 题目背景、原始数据说明、问题列表 |
| `input/todo.md` | 输入 | 队伍约束、分工、待办、禁止声称的内容 |
| `input/*` | 输入 | Excel、CSV、PDF、图片等原始材料 |
| `output/model.py` | 输出 | 可重复运行的建模代码 |
| `output/paper.md` | 输出 | 论文唯一源稿 |
| `output/figures/` | 输出 | 无内嵌标题的图片 |
| `output/tables/` | 输出 | 中间结果或导出的数据表 |
| `output/ai_plan.json` | 输出 | 结构化题目分析和研究计划 |
| `output/audit_report.*` | 输出 | 自动审计证据 |
| `output/paper.docx` | 输出 | Word 论文 |
| `output/support_materials.zip` | 输出 | 支撑材料压缩包 |
| `templates/reference.docx` | 模板 | 字体、页边距、页脚、三线表 |
| `templates/PAPER_SPEC.md` | 模板 | 可执行格式约束 |
| `mathmodel.config.json` | 配置 | 路径、比赛档案、AI 默认连接方式 |

`output/` 默认被 Git 忽略。比赛提交前从它里面选择正式论文和支撑材料，不要把临时缓存、调试图片和无关文件混入提交包。

## 2. 阶段总览

```text
准备输入
  -> 题目拆解与资料研究
  -> 数据审计
  -> 候选模型与验证设计
  -> 建模代码与结果文件
  -> 论文 Markdown
  -> 离线审计
  -> Pandoc + reference.docx
  -> DOCX 审计与人工检查
  -> 支撑材料打包
```

每个阶段都有“进入条件”和“退出条件”。退出条件不满足时，不进入下一阶段。

## 3. 阶段一：初始化

```powershell
python scripts/init_project.py --keep-reference
```

开始新题目时：

```powershell
python scripts/init_project.py --force
```

`--force` 只清空 `output/`，不会清理 `input/` 或模板。若需要保留上一次结果，使用 `--keep-output`。

初始化检查：

- Pandoc 可执行且版本为 3.x
- `python-docx`、`numpy`、`scipy`、`pandas`、`matplotlib` 等依赖可导入
- `reference.docx` 存在
- `input/question.md` 和 `input/todo.md` 已创建

## 4. 阶段二：题目理解与联网研究

### 4.1 先读本地材料

按顺序阅读：

1. `input/question.md`
2. `input/todo.md`
3. `templates/PAPER_SPEC.md`
4. `input/` 下所有数据文件的文件名、工作表、行列规模和字段含义

输出一份题目事实表：

| 字段 | 内容 |
|:---|:---|
| 研究对象 | 题目中的系统或决策对象 |
| 决策变量 | 可被模型控制或优化的量 |
| 状态变量 | 随时间、空间或样本变化的量 |
| 目标 | 要最大化、最小化、预测或分类的量 |
| 约束 | 资源、边界、物理、逻辑和公平性约束 |
| 评价指标 | 误差、收益、风险、准确率、稳定性等 |
| 题目小问 | 每问的输入、输出和交付形式 |

### 4.2 Brave MCP 研究规则

Brave MCP 适合：

- 官方竞赛规则、论文格式和提交通知
- 标准、政策、政府公开数据和原始论文
- 算法原始论文、教材或官方文档
- 数据集的来源、定义和时间范围

搜索策略：

1. 先搜官方域名和精确标题。
2. 再搜算法原始论文或权威教材。
3. 最后搜工程实践和问题排查。
4. 打开原文核对作者、标题、年份、机构和链接。
5. 将资料记录在研究日志中，注明“用于假设、方法、数据解释还是格式”。

禁止：

- 把搜索摘要直接当作文献
- 让 AI 补齐没有查到的作者、页码或 DOI
- 用博客替代官方规则
- 用一篇资料支撑与它无关的结论

### 4.3 GitHub MCP 研究规则

GitHub MCP 适合：

- 查找 Pandoc、DOCX、Python 数模项目的目录结构
- 比较测试、日志、配置和命令行接口
- 查看公开仓库的 issue、release 和实现细节

建议优先关注：

- [CUMCMThesis](https://github.com/latexstudio/CUMCMThesis)
- [math-modeling-skill](https://github.com/XiaoMaColtAI/math-modeling-skill)
- [pandoc_docx_template](https://github.com/Achuan-2/pandoc_docx_template)

GitHub 代码不能直接当作论文结论。引用算法时回到原始论文或官方文档，引用工程时注明仓库和版本。

## 5. 阶段三：AI 题目拆解

设置 API 后运行：

```powershell
python scripts/ai_assistant.py plan --force
```

助手输出 `output/ai_plan.json`，至少包含：

- 题目摘要
- 每个子问题的目标、数据、候选模型
- 每个模型的验证方法
- 数据清单
- 论文结构建议
- 需要联网核实的研究任务
- 禁止声称的未实现方法

GPT/DeepSeek 连接参数由环境变量覆盖：

```text
MM_AI_PROVIDER
MM_AI_API_STYLE       responses 或 chat
MM_AI_BASE_URL
MM_AI_API_KEY
MM_AI_MODEL
MM_AI_TEMPERATURE
MM_AI_TIMEOUT
```

默认配置是 DeepSeek-compatible；GPT 使用 OpenAI Responses API；其他兼容服务通常使用 Chat Completions。API Key 不能写入仓库。

## 6. 阶段四：数据审计

在建模前完成：

- 字段和单位核对
- 行列数、时间范围、主键、重复值检查
- 缺失值、异常值和离群值统计
- 类别不平衡和样本泄漏检查
- 训练/验证/测试划分原则
- 单位换算和标准化规则

将数据审计结果写入 `output/`，并在论文 5.2 节说明。任何删除、插值、截尾、归一化都要能解释。

## 7. 阶段五：建模与求解

`output/model.py` 推荐结构：

```python
# 0. 配置与随机种子
# 1. 数据加载与校验
# 2. 数据预处理
# 3. 模型定义
# 4. 参数估计或优化
# 5. 交叉验证/回测/守恒检查
# 6. 敏感性与情景分析
# 7. 结果导出
# 8. 绘图
```

最低要求：

- 固定随机种子
- 明确输入输出路径
- 输出关键参数、指标和运行状态
- 保存结果表或 JSON，论文从结果文件取数
- 对优化问题记录边界、初值、停止条件和收敛状态
- 对预测问题使用时间切分、交叉验证或滚动回测
- 对分类问题报告类别分布、混淆矩阵和宏平均指标
- 对机理模型检查守恒、非负性、边界和量纲

建模选择原则：

1. 先建立可解释基线。
2. 再增加复杂度，并说明复杂度换来了什么。
3. 复杂模型必须有公平的验证和消融/对比。
4. 边界解和不稳定解必须进入局限性，而不是隐藏。

## 8. 阶段六：论文 Markdown

推荐结构：

```text
摘要
1 问题重述
2 问题分析
3 模型假设
4 符号说明
5 模型建立与求解
6 模型评价
参考文献
附录
```

写作规则：

- 摘要按“针对问题一、针对问题二……”写，并报告验证结果。
- 表题在表上方，图题在图下方。
- 每一个表和图都在正文中被引用。
- 正文公式使用 LaTeX，表格单元格优先使用 Unicode。
- 不在图片中嵌入标题，避免重复题注。
- 不使用目录、身份信息、训练过程聊天记录和“本题答案”等非论文措辞。

公式示例：

```markdown
$$
J(\theta)=\sum_{i=1}^{n}\left(y_i-\hat y_i(\theta)\right)^2 \qquad (1)
$$
```

避免 `\tag{}`、`\left`、`\right`、`\bigl`、`\bigr` 和自定义宏。

## 9. 阶段七：自动审计

```powershell
python scripts/audit_project.py
```

审计器检查：

- 必要章节和目录风险
- 摘要长度风险、关键词分隔
- 表格列数
- 公式定界符和高风险命令
- 图片路径是否存在
- 图号、表号连续性
- 参考文献数量和未引用条目
- 模型代码与论文中部分方法的明显不一致
- 已生成 DOCX 的页脚、表格样式、图片和 keepNext

自动审计通过不等于数学正确。它只负责把容易遗漏的结构性问题提前暴露出来。

## 10. 阶段八：构建 DOCX

```powershell
python scripts/build_paper.py
```

构建顺序：

1. 运行模型
2. 审计 Markdown
3. 切换到 `output/` 目录运行 Pandoc
4. 应用 `templates/reference.docx`
5. 后处理表格 autofit、题注样式和分页属性
6. 审计生成的 DOCX

只转换已有论文：

```powershell
python scripts/build_paper.py --skip-model
```

Windows 包装命令：

```powershell
scripts\convert.bat
```

不要从项目根目录直接运行 Pandoc，否则 `figures/xxx.png` 等相对路径容易失效。

## 11. 模板与表格

`reference.docx` 负责：

- A4 页面和页边距
- CJK/Latin 字体分离
- 标题、正文、题注字号
- 页脚 PAGE 字段
- `Table` 三线表样式

`postprocess_appendix.py` 只负责：

- 题注应用命名样式
- 表格宽度 100% 和 autofit
- 清除意外的 keepNext/keepLines
- 检查页脚、图片和表格样式

不要同时启用多套“写入三线表边框”的脚本。旧的 `postprocess_tables.py`、`fix_table_style.py`、`fix_reference.py` 和 `fix_code_style.py` 仅保留作历史兼容，新的任务使用 `build_reference.py`、`build_paper.py` 和 `postprocess_appendix.py`。

## 12. 阶段九：AI 论文审查

先运行离线审计，再设置 API：

```powershell
python scripts/ai_assistant.py review --force
```

AI 审查结果必须按以下顺序处理：

1. 阻断问题：缺章节、数字无法复现、图表路径错误、公式无法转换
2. 数学风险：假设不成立、验证泄漏、边界解、样本不足
3. 数据风险：单位混乱、异常值处理不透明、论文数字与结果文件不一致
4. 写作风险：把方法写成结果、夸大精度、缺少局限性
5. 格式风险：题注位置、表格过宽、参考文献未引用

AI 给出的修改建议必须回到代码或原文核验，不能直接全部接受。

## 13. 阶段十：支撑材料与提交前检查

```powershell
python scripts/package_support.py
```

提交前人工核对：

- 官方网站和当年通知中的文件类型、大小、命名和截止时间
- 论文是否包含身份泄露
- 论文和支撑材料是否是两个清晰、可打开的文件
- `paper.docx` 是否能在 Word/WPS 中打开
- 公式、图片、页码、表格三线样式是否正常
- 支撑材料能否从干净环境运行
- 论文中的每个关键数字是否能定位到代码输出

## 14. 故障排查

| 现象 | 处理 |
|:---|:---|
| 图片丢失 | 从 `output/` 目录运行 Pandoc，或直接使用 `build_paper.py` |
| 表格出现竖线 | 重建 `reference.docx`，确认使用 Pandoc 3.x 和 `Table` 样式 |
| 标题变蓝 | 运行 `python scripts/build_reference.py` |
| 页面大块空白 | 检查 `keepNext/keepLines`，运行 DOCX 后处理 |
| 表内公式乱码 | 将单元格公式改成 Unicode；复杂公式放到正文段落 |
| AI 不能调用 | 检查 `MM_AI_API_KEY`、base URL、API style 和 model；离线流程仍可继续 |
| 论文数值不一致 | 删除手填数字，改为从结果 JSON/CSV 读取并重新构建 |
| 参考文献存疑 | 回到 Brave MCP 搜索原文，无法核实就替换或删除 |

## 15. 推荐的最小闭环

```powershell
python scripts/init_project.py --keep-reference
python scripts/ai_assistant.py plan --force
# 编写 output/model.py 和 output/paper.md
python scripts/build_paper.py
python scripts/ai_assistant.py review --force
python scripts/package_support.py
```

最后一次运行必须保留 `output/audit_report.json`，它是队伍内部检查“论文为什么这样写”的证据，而不是装饰文件。
