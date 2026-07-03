# MathModel — 数学建模论文自动生成工具

> **给定一道数学建模题，自动生成符合国赛/CUMCM 规范的 Word 论文（.docx）。**

## 项目结构

```
mathmodel/
├── input/                  # 每次任务替换的输入
│   ├── question.md         # 题目描述与数据
│   ├── todo.md             # Agent 专属指令
│   └── *.xlsx / *.csv      # 附件数据
├── output/                 # 每次任务生成的输出 (.gitignore)
│   ├── paper.md            # 论文 Markdown
│   ├── paper.docx          # 最终 Word 论文
│   ├── model.py            # 建模求解代码
│   └── fig*.png            # 图表
├── templates/              # 可复用模板
│   ├── reference.docx      # Pandoc 样式模板
│   ├── PAPER_SPEC.md       # 格式规范（字号/字体/三线表）
│   └── paper_skeleton.md   # 论文骨架
├── scripts/                # 基础设施脚本
│   ├── convert.bat         # 一键转换 + 后处理
│   ├── fix_reference.py    # 样式模板构建
│   └── postprocess_appendix.py  # 三线表/页码/样式修复
├── wiki.md                 # Agent 通用工作流文档
└── README.md               # 本文件
```

- **`input/`** 放题目和数据——每次任务唯一要改的
- **`output/`** 放所有生成物——gitignore，不留历史
- **`templates/`** 和 **`scripts/`** 是基础设施——跨任务复用

## 快速开始

### 1. 安装依赖

```bash
winget install JohnMacFarlane.Pandoc
pip install python-docx Pillow numpy scipy matplotlib scikit-learn
```

### 2. 准备题目

把题目写入 `input/question.md`，数据文件放入 `input/`，Agent 指令写入 `input/todo.md`。

### 3. Agent 执行

Agent 按 `wiki.md` 工作流自动完成：建模 → 论文 → 图表 → Word 转换 → 后处理。

### 4. 手动生成

```bash
# 从项目根目录运行
scripts\convert.bat
```

## 复用到新题目

1. 清空 `output/`，把新题目写入 `input/question.md`
2. 把 Agent 指令写入 `input/todo.md`
3. 编写 `output/model.py`（建模求解 + 生成图表）
4. Agent 按工作流将论文写入 `output/paper.md`
5. 运行 `scripts\convert.bat` 生成 `output/paper.docx`

## 论文格式（默认）

| 元素 | 字号 | CJK | EN | 加粗 | 对齐 | 行距 |
|:---|:---|:---|:---|:---|:---|:---|
| 标题 | 16pt | 黑体 | Times New Roman | 是 | 居中 | 1.5x |
| 一级标题 | 14pt | 黑体 | Times New Roman | 是 | 居中 | 1.5x |
| 二级标题 | 13pt | 黑体 | Times New Roman | 是 | 左 | 1.5x |
| 正文 | 12pt | 宋体 | Times New Roman | 否 | 两端 | 1.25x |
| 图表标题 | 10.5pt | 宋体 | Times New Roman | 是 | 居中 | 1.25x |

A4 纸，上下左右 ≥2.5cm。格式可在 `scripts/fix_reference.py` 中调整。

## License

MIT
