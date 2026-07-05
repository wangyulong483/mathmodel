# MathModel — 数学建模论文自动生成工具 v2.1

> **给定一道数学建模题，自动生成符合国赛/CUMCM 规范的 Word 论文（.docx）。**
>
> 已通过 2022 CUMCM C 题（古代玻璃成分分析与鉴别）全流程实战验证，论文经 10+ 轮评审打磨达到定稿水平。

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
│   ├── figures/            # 图表
│   └── tables/             # 数据表
├── templates/              # 可复用模板
│   ├── reference.docx      # Pandoc 样式模板（含 "Table" 三线表样式 + 页脚页码）
│   ├── PAPER_SPEC.md       # 格式规范
│   └── paper_skeleton.md   # 论文骨架
├── scripts/                # 基础设施脚本
│   ├── convert.bat         # 一键转换（Pandoc + 后处理）
│   ├── build_reference.py  # 构建 reference.docx（样式 + Table 样式 + 页脚）
│   └── postprocess_appendix.py  # 后处理（表题样式 + 列宽 + keepNext + 验证）
├── wiki.md                 # Agent 通用工作流文档（v2.1）
└── README.md               # 本文件
```

## 快速开始

### 1. 安装依赖

```bash
winget install JohnMacFarlane.Pandoc
pip install python-docx Pillow numpy scipy matplotlib scikit-learn lxml
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
scripts\convert.bat             # Pandoc 转换 + 后处理
```

## 论文格式（默认）

| 元素 | 字号 | CJK | EN | 加粗 | 对齐 |
|:---|:---|:---|:---|:---|:---|
| 标题 | 16pt（三号） | 黑体 | TNR | 是 | 居中 |
| 一级标题 | 14pt（四号） | 黑体 | TNR | 是 | 居中 |
| 二级标题 | 12pt（小四） | 黑体 | TNR | 是 | 左 |
| 三级标题 | 12pt（小四） | 黑体 | TNR | 是 | 左 |
| 正文 | 12pt（小四） | 宋体 | TNR | 否 | 两端 |
| 图表标题 | 10.5pt（五号） | 宋体 | TNR | 是 | 居中 |

A4 纸，页边距 ≥2.5cm。三线表（顶 1.5pt / 表头下 0.75pt / 底 1.5pt）由 "Table" 样式定义。

## 关键实战经验

### 样式构建
- reference.docx **必须从 Pandoc 默认生成**，不能基于 WPS 模板（styleId 不兼容）
- `create_custom_style` 不支持 CJK/Latin 字体分离 → XML 层处理
- 清除 `eastAsiaTheme` 等主题属性，否则等线覆盖黑体

### 图表
- 图号从 1 连续排列，不跳号不倒序
- model.py 用 `SINGLE`/`TWO_PANEL` 等常量统一 figsize
- 表题用 `**表N 标题**` 置于表格上方，后处理自动应用 Table Caption

### 数据一致性
- 新 Agent 修改后必须扫描全表自洽（特别是预测结果表）
- 正文引用的化学成分必须与原始数据一致
- 未实现的方法不得在论文中声称

### 学术诚实
- 有局限性就明确承认，用敏感性分析检验
- 化学先验知识可纠偏模型预测（如边界样本）
- 小样本下的网络分析定位为探索性

## 提交

只提交 `output/paper.docx`。`model.py` 在附录中引用。

## License

MIT
