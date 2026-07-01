# MathModel — 数学建模论文自动生成工具

> **给定一道数学建模题，自动生成符合国赛/CUMCM 规范的 Word 论文（.docx）。**

## 核心思路

```
数学建模题目 → Python 建模求解 → Markdown + LaTeX 写论文 → Pandoc 转 Word → 后处理格式化
```

- **内容与格式分离**：用 Markdown + LaTeX 写论文内容，用 `reference.docx` + 后处理脚本管格式
- **全自动后处理**：三线表、页脚页码、样式修复、代码图片全部自动完成
- **Agent 友好**：完整工作流文档（[wiki.md](wiki.md)），可供 AI Agent 学习复用

## 快速开始

### 1. 准备

```bash
# 安装 Pandoc（Windows）
winget install JohnMacFarlane.Pandoc

# 安装 Python 依赖
pip install python-docx Pillow numpy scipy matplotlib scikit-learn pygments
```

### 2. 填入题目

- `README.md`（本文件）— 项目简介
- `PAPER_SPEC.md` — 论文格式规范与修改清单
- 编写 `model.py` — 建模求解 + 出图

### 3. 写论文

编辑 `paper.md`，按模板填充内容。

### 4. 生成

```bash
# 一键生成
convert.bat

# 或手动
pandoc paper.md -o paper.docx --reference-doc=reference.docx --mathml --syntax-highlighting=pygments
python postprocess_tables.py
```

## 文件说明

| 文件 | 说明 |
|:---|:---|
| `paper.md` | 论文源文件（Markdown + LaTeX），编辑此文件写论文 |
| `reference.docx` | Pandoc 样式模板（字体/字号/行距/页边距） |
| `convert.bat` | 一键转换 + 后处理 |
| `model.py` | 建模求解代码（需自行编写） |
| `wiki.md` | Agent 通用工作流完整文档 |
| `PAPER_SPEC.md` | 论文格式规范模板 |
| `fix_reference.py` | 样式模板构建脚本 |
| `fix_table_style.py` | 三线表样式定义 |
| `fix_code_style.py` | 代码块样式定义 |
| `gen_code_images.py` | 代码渲染为 PNG 图片 |
| `postprocess_tables.py` | 表格后处理（备用） |

## 特性

- **三线表**：自动生成顶线(1.5pt)+表头下线(0.75pt)+底线(1.5pt)，无竖线
- **LaTeX 公式**：`$...$` / `$$...$$` → Word 原生 OMML 可编辑公式
- **代码图片**：附录代码以清晰 PNG 嵌入，避免 Word 中字母分裂
- **页码**：自动添加页脚居中页码
- **样式修复**：自动修复无样式段落、标题蓝色、页面空白等问题
- **中英文字体分离**：正文宋体+Times New Roman，标题黑体+Times New Roman

## 论文格式（默认）

| 元素 | 字号 | CJK | EN | 加粗 | 对齐 | 行距 |
|:---|:---|:---|:---|:---|:---|:---|
| 标题 | 16pt | 黑体 | Times New Roman | 是 | 居中 | 1.5x |
| 一级标题 | 14pt | 黑体 | Times New Roman | 是 | 居中 | 1.5x |
| 二级标题 | 13pt | 黑体 | Times New Roman | 是 | 左 | 1.5x |
| 正文 | 12pt | 宋体 | Times New Roman | 否 | 两端 | 1.25x |
| 图表标题 | 10.5pt | 宋体 | Times New Roman | 是 | 居中 | 1.25x |

A4 纸，上下左右 ≥2.5cm，左侧装订。格式可按需在 `fix_reference.py` 中调整。

## 复用到新题目

1. 将题目数据写入 `PAPER_SPEC.md`
2. 编写 `model.py`（建模 + 出图）
3. 编辑 `paper.md`（论文内容）
4. 运行 `convert.bat` 生成 `paper.docx`

## License

MIT
