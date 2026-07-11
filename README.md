# MathModel — 数学建模论文自动生成工具 v3.0

> **给定一道数学建模题，自动生成符合国赛/CUMCM 规范的 Word 论文（.docx）。**
>
> 已通过 2022 CUMCM C 题（古代玻璃成分分析）和 2026 暑期培训第四次作业（AQI 预测）双场景全流程实战验证。

## 项目结构

```
mathmodel/
├── input/                  # 每次任务替换的输入
│   ├── question.md         # 题目描述与数据
│   ├── todo.md             # Agent 专属指令
│   └── *.xlsx              # 附件数据
├── output/                 # 每次任务清空重建 (.gitignore)
│   ├── paper.md            # 论文 Markdown
│   ├── paper.docx          # 最终 Word 论文（只提交此文件）
│   ├── model.py            # 建模求解代码（支撑材料）
│   ├── figures/            # 图表（12 张，300dpi，无内嵌标题）
│   └── tables/             # 数据表
├── templates/              # 可复用模板
│   ├── reference.docx      # Pandoc 样式模板（含 "Table" 三线表 + 页脚页码）
│   ├── PAPER_SPEC.md       # 格式规范
│   └── paper_skeleton.md   # 论文骨架
├── scripts/                # 基础设施脚本
│   ├── convert.bat         # 一键转换（Pandoc + 后处理）
│   ├── build_reference.py  # 构建 reference.docx（样式 + Table 样式 + 页脚）
│   └── postprocess_appendix.py  # 后处理（表标题居中 + autofit 列宽 + keepNext + 验证）
├── wiki.md                 # Agent 通用工作流文档（v3.0）
└── README.md               # 本文件
```

## 快速开始

### 1. 安装依赖

```bash
winget install JohnMacFarlane.Pandoc
pip install python-docx Pillow numpy scipy pandas matplotlib scikit-learn lxml
```

### 2. 构建模板

```bash
# 首次或格式变更时运行
python scripts/build_reference.py
```

### 3. 准备题目

把题目写入 `input/question.md`，数据放 `input/`，Agent 指令写 `input/todo.md`。

### 4. 生成论文

```bash
python output/model.py          # 建模求解 + 生成图表
# Agent 撰写 paper.md
cd output && pandoc paper.md -o paper.docx --reference-doc=../templates/reference.docx --mathml --syntax-highlighting=pygments
cd ../scripts && python postprocess_appendix.py
```

## 论文格式规范（v3.0 实战沉淀）

### 摘要

| 规则 | 说明 |
|:---|:---|
| 结构 | 开头段 → **针对问题一** → **针对问题二** → 结尾段 |
| 加粗 | **方法策略**加粗（模型名、优化方法），数字不加粗 |
| 关键词 | 空格分隔（不用分号），4-6 个 |
| 篇幅 | 300-500 字 |

### 图表

| 元素 | 位置 | 格式 | 样式 |
|:---|:---|:---|:---|
| 表标题 | 表上方、居中 | `**表N 标题**` | Table Caption（10.5pt 宋体加粗） |
| 图标题 | 图下方、居中 | `![图N 标题](path)` | Image Caption（10.5pt 宋体加粗） |
| PNG 文件 | — | **不内嵌标题** | 标题全由 Markdown 管理 |
| 符号说明 | — | **无独立表标题** | 节标题即为其标题 |

### 表格（最重要的规则）

| 规则 | 说明 |
|:---|:---|
| **每表 ≤6 列** | 超过就拆成多张窄表，每表一个独立主题 |
| **表内零 LaTeX** | `$R^2$`→`R²`，`$\varepsilon$`→`ε`，`$\gamma$`→`γ`，`+/-`→`±`（Pandoc OMML 在表单元格中不可靠） |
| **autofit 布局** | 不锁列宽，让 Word 根据内容自动分配 |
| **三线表零代码** | "Table" 样式在 reference.docx 中定义，Pandoc 自动应用 |

### 字体字号

| 元素 | 字号 | CJK | EN | 加粗 | 对齐 |
|:---|:---|:---|:---|:---|:---|
| 标题 | 16pt（三号） | 黑体 | TNR | 是 | 居中 |
| 一级标题 | 14pt（四号） | 黑体 | TNR | 是 | 居中 |
| 二级标题 | 12pt（小四） | 黑体 | TNR | 是 | 左 |
| 三级标题 | 12pt（小四） | 黑体 | TNR | 是 | 左 |
| 正文 | 12pt（小四） | 宋体 | TNR | 否 | 两端 |
| 图表标题 | 10.5pt（五号） | 宋体 | TNR | 是 | 居中 |

A4 纸，页边距 ≥2.5cm。三线表（顶 1.5pt / 表头下 0.75pt / 底 1.5pt）由 "Table" 样式定义。

### 参考文献

| 规则 | 说明 |
|:---|:---|
| 数量 | ≥8 条 |
| 可核实性 | **全部通过 EXA MCP 逐条核实**（作者、标题、期刊、年份） |
| 引用 | 正文中全部引用至少一次 |
| 作业题目 | **不作为正式参考文献**（移至附录说明） |

## 常见问题与解决方案

### 表格渲染

| 问题 | 根因 | 修复 |
|:---|:---|:---|
| 表内数学符号丢失/乱码 | Pandoc OMML 在表单元格中不可靠 | 改用 Unicode：`R²`/`ε`/`γ`/`±` |
| 宽表列多拥挤 | 8-9 列塞不进 A4 | 拆为多张窄表（每表 3-6 列），合并相似列 |
| 表标题不居中 | lxml 改 XML 与 python-docx 缓存冲突 | `p.style = doc.styles['Table Caption']` |
| 列宽不均 | fixed 布局锁死 | autofit + 清除 cell 级 w:tcW |

### 参考文献

| 问题 | 根因 | 修复 |
|:---|:---|:---|
| 文献不可核实 | Agent 编造看起来合理的数据 | EXA MCP 逐条搜索核实，存疑立即替换 |
| 作业题目当参考文献 | 缺乏区分意识 | 移至正文或附录，不列入参考文献列表 |

### 数值一致性

| 问题 | 根因 | 修复 |
|:---|:---|:---|
| 论文数值与代码不符 | 凭记忆手写 | 所有数值从 model.py 运行结果提取，审查时复现验证 |

### Pandoc

| 问题 | 根因 | 修复 |
|:---|:---|:---|
| 图片全部丢失 | 从项目根目录运行 Pandoc | 必须从 `output/` 目录运行 |
| 标题是蓝色 | Pandoc 默认主题色 | `build_reference.py` 显式设 `w:color="000000"` |
| 页面大段空白 | 标题 keepNext | 全部清除 keepNext/keepLines |

## 关键实战经验

### 样式构建
- reference.docx **必须从 Pandoc 默认生成**，不能基于 WPS 模板（styleId 不兼容）
- `create_custom_style` 不支持 CJK/Latin 字体分离 → XML 层处理
- 清除 `eastAsiaTheme` 等主题属性，否则等线覆盖黑体

### 图表
- 图号从 1 连续排列，表号独立从 1 连续
- model.py 用 `SINGLE`/`WIDE` 等常量统一 figsize
- **PNG 文件不内嵌标题**——所有标题由 paper.md 管理

### 学术诚实
- 有局限性就明确承认，用交叉验证检验
- 未实现的方法不得在论文中声称
- 测试集 100% 准确率具有误导性时，诚实说明并以 CV 指标为准

## 提交

只提交 `output/paper.docx`。`model.py` 在附录中引用。

## License

MIT
