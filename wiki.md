# Agent 通用工作流：数学建模题目 → Word 论文

> **用途**：给定任意数学建模题目（`README.md` + `todo.md` + 可选竞赛模板 `.docx`），按此工作流自动生成符合竞赛规范的 Word 论文。
>
> **适用范围**：全国大学生数学建模竞赛（CUMCM）、校赛、暑期培训作业等各类数学建模论文。
>
> **案例参考**：本文档以"SIR 传染病建模"为例贯穿说明，但核心流程适用于任何数学模型（优化、微分方程、统计回归、图论等）。

---

## 一、工作流总览

```
题目(README.md) + 格式规范(todo.md) + [竞赛模板.docx]
        │
        ├── [1] 理解需求 ── 读输入 + EXA MCP 搜索最优方案
        ├── [2] 建模求解 ── 写 Python 代码 → 运行验证 → 生成图表
        ├── [3] 撰写论文 ── Markdown + LaTeX 公式 → paper.md
        ├── [4] 构建模板 ── 分析竞赛模板 → 生成 reference.docx
        ├── [5] Pandoc ── Markdown → DOCX（含公式 OMML 转换）
        ├── [6] 后处理 ── 三线表/页码/样式修复/代码图片
        └── [7] 审查迭代 ── 多 Agent 并行检查 + EXA MCP 修正
```

---

## 二、Step 1：理解需求 & 搜索方案

### 2.1 读输入

```
Read README.md    → 题目背景、数据、具体问题列表
Read todo.md      → 论文结构要求、格式规范、修改清单
Glob **/*.docx    → 发现竞赛模板文件
```

### 2.2 EXA MCP 搜索清单

**每类问题对应一套搜索策略。Agent 应根据题目的数学方法选择相关搜索。**

| 搜索类别 | 触发条件 | 典型搜索词 |
|:---|:---|:---|
| **格式转换方案** | 任何题目 | `pandoc markdown to docx preserve equations reference docx` |
| **竞赛格式规范** | 任何题目 | `全国大学生数学建模竞赛 论文格式规范 字号 字体 页边距` |
| **数学模型参考** | 题目涉及特定模型 | `SIR model parameter estimation least squares python` / `linear programming simplex method` |
| **算法实现** | 题目要求特定方法 | `cubic spline interpolation scipy` / `genetic algorithm python optimization` |
| **参数范围** | 需要经验值 | `respiratory infection beta gamma typical range SIR` |
| **三线表实现** | 任何题目 | `pandoc docx table border three-line style` |
| **公式渲染问题** | 转换后出现 | `pandoc math formula sum subscript not rendering OMML` |
| **表格宽度问题** | 转换后出现 | `python-docx set table column width cell tcW` |
| **代码图片问题** | 附录含代码 | `pygments ImageFormatter CJK overlap bug` |
| **页面空白问题** | 转换后出现 | `Word keep with next blank page fix` |

### 2.3 信息源优先级

1. **官方文档**：pandoc.org/MANUAL.html, mcm.edu.cn, scipy docs
2. **GitHub Issues**：jgm/pandoc issues（如已关闭的 bug）
3. **StackOverflow**：具体代码实现
4. **中文社区**：竞赛格式惯例

---

## 三、Step 2：建模与求解

### 3.1 代码结构模板（无论什么模型）

```python
# -*- coding: utf-8 -*-
"""{模型名称} —— {题目简称}"""
import numpy as np
from scipy.integrate import solve_ivp      # 如有 ODE
from scipy.optimize import minimize         # 如有优化
from scipy.interpolate import CubicSpline   # 如有插值
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

# ===== 全局设置 =====
matplotlib.rcParams['font.sans-serif'] = ['Microsoft YaHei', 'SimHei']
matplotlib.rcParams['axes.unicode_minus'] = False
plt.rcParams['figure.dpi'] = 150
plt.rcParams['savefig.dpi'] = 150
plt.rcParams['savefig.bbox'] = 'tight'

# ===== 0. 数据加载 =====
# 从 README.md 提取，硬编码为 NumPy 数组

# ===== 1. 模型定义 =====
# 根据题目的数学方法：ODE / 优化目标函数 / 统计模型 / ...

# ===== 2. 求解/拟合 =====
# 使用有约束优化（如有参数估计）：
# bounds = [(low, high), ...]
# minimize(objective, x0, method='L-BFGS-B', bounds=bounds)

# ===== 3. 结果计算 =====
# 预测 / 评估 / 敏感性分析

# ===== 4. 情景分析 =====
# 改变关键参数，对比不同情景

# ===== 5. 守恒/正确性验证 =====
# 如：S+I+R=N, 插值过点检查, 残差分析

# ===== 6. 绘图 =====
# fig, ax = plt.subplots(...)
# ax.plot(...)
# fig.savefig('figX_desc.png', dpi=150)
# plt.close()
```

### 3.2 参数估计通用经验

**无论什么模型，只要有参数估计：**
- ✅ 使用有约束优化（`L-BFGS-B` + `bounds`），不用无约束 + 惩罚项
- ✅ 目标函数中不混入惩罚项——RSS 必须是纯净的
- ✅ 多起点策略避免局部最优
- ✅ 若参数落在约束边界，论文中诚实说明数据局限性
- ✅ 每次修改代码后立即运行验证数值结果

### 3.3 图表规范

```
fig1_model_diagram.png     # 图1 模型结构/流程（始终从图1开始）
fig2_data_or_result.png    # 图2 数据展示/中间结果
fig3_fitting.png           # 图3 拟合/求解结果
fig4_solution.png          # 图4 模型数值解
fig5_prediction.png        # 图5 预测结果
fig6_comparison.png        # 图6 情景/参数对比
```

---

## 四、Step 3：撰写论文 Markdown

### 4.1 YAML（国赛匿名 + 无英文摘要）

```yaml
---
title: "{论文标题}"
# 不放 author / date / abstract
---
```

### 4.2 通用论文结构

```markdown
# 摘要（300-500字：背景+方法+结果+优点）
**关键词：** KW1；KW2；KW3；KW4；KW5

# 1 问题重述
## 1.1 问题背景
## 1.2 问题重述（列出所有子问题）

# 2 问题分析（为什么选择这些方法，每个子问题一段）

# 3 模型假设（编号列表，≥6条，含参数取值依据）

# 4 符号说明（三线表：符号 | 含义 | 单位）

# 5 模型建立与求解
## 5.1 模型建立（含图1：模型结构/流程）
## 5.2 数据处理/插值/预处理（含图2）
## 5.3 参数求解（含目标函数公式、拟合结果表、图3）
## 5.4 数值求解（含图4）
## 5.5 结果/预测（含数据表、图5）
## 5.6 对比分析（含对比表、图6）

# 6 模型评价
## 6.1 优点
## 6.2 缺点
## 6.3 改进方向
## 6.4 模型推广

# 参考文献（至少3条，全部在正文引用）

# 附录
## 附录A 支撑材料文件列表
## 附录B 核心代码（每段前有说明文字）
```

### 4.3 LaTeX 公式规则

```markdown
行内：$\beta$、$x_i$、$R^2$

显示+编号：
$$
f(x) = \frac{1}{\sqrt{2\pi}} e^{-x^2/2} \qquad (1)
$$

多行：
$$
\begin{aligned}
x &= a + b \\
y &= c + d
\end{aligned}
$$
```

**禁止项：**
- `\tag{...}`、`\bigl`/`\bigr`、`\left[...\right]`、自定义宏（`\abs`、`\norm`）
- 复杂宏包（tikz、minted、amscd）

**踩坑：多余的空白 `$$` 会导致后续公式变为纯文本。** 确保每个 `$$...$$` 对内都有数学内容。

### 4.4 图文规则

- **图号从 1 开始连续**，不跳号。每个图有题注且在正文被引用
- **表题注**在表上方，**图题注**在图片下方
- 数据表包含验证列（如守恒检查）
- 正文语言：客观冷静的论文口吻，不出现"课堂上学习了""参考PPT""通过不断调整参数"等

---

## 五、Step 4：构建 reference.docx

### 5.1 流程

```bash
# 1. 生成 pandoc 默认参考模板
pandoc -o reference.docx --print-default-data-file reference.docx

# 2. 分析竞赛模板（如有），提取字体/字号/页边距
python extract_template_format.py

# 3. 直接编辑 reference.docx 的 styles.xml
# 必须用 XML 而非 python-docx 高级 API（后者不能分离 CJK/Latin 字体）
python fix_reference.py
```

### 5.2 通用样式参数

| 样式 | 字号(pt) | CJK字体 | EN字体 | 加粗 | 对齐 | 行距 | 缩进 | keepNext |
|:---|:---|:---|:---|:---|:---|:---|:---|:---|
| Normal | 12 | SimSun | Times New Roman | 否 | both | 1.25x | 0.74cm | — |
| Title | 16~18 | SimHei | Times New Roman | 是 | center | 1.5x | 0 | — |
| Heading 1 | 14 | SimHei | Times New Roman | 是 | center | 1.5x | 0 | **否** |
| Heading 2 | 13 | SimHei | Times New Roman | 是 | left | 1.5x | 0 | **否** |
| Heading 3 | 12 | SimHei | Times New Roman | 是 | left | 1.25x | 0 | **否** |
| Caption | 10.5 | SimSun | Times New Roman | 是 | center | 1.25x | 0 | — |
| Bibliography | 10.5 | SimSun | Times New Roman | 否 | both | 1.25x | 0 | — |

- **所有字体颜色设为 `#000000`**（Pandoc 默认给 Heading 加蓝色主题色）
- **`keepNext` 全部禁用**（否则标题+下文强制绑定，跨页产生大段空白）

### 5.3 页边距

```
A4 (21×29.7cm)，上下 ≥2.5cm，左右 ≥2.5cm
```

---

## 六、Step 5：Pandoc 转换

```bash
pandoc paper.md -o paper.docx \
    --reference-doc=reference.docx \
    --mathml \
    --syntax-highlighting=pygments
```

- **不用 `-s`**：与 reference.docx 可能冲突
- **不用 `-M columns=30`**：破坏表格列宽
- **不用 `--toc`**：国赛禁止目录

---

## 七、Step 6：后处理（最关键步骤）

### 7.1 后处理清单

| # | 任务 | 工具/方法 |
|:---:|:---|:---|
| 1 | **表格宽度** | python-docx `cell.width` + `tblLayout fixed` + `tblW pct` |
| 2 | **三线表边框** | 直接写 `<w:tblBorders>`（顶1.5pt/中0.75pt/底1.5pt/竖none） |
| 3 | **页脚页码** | 创建 `footer1.xml` + 更新 `[Content_Types].xml` 和 rels |
| 4 | **无样式段落** | 检测无 `pStyle` 的段落，分配 `Compact` 样式 |
| 5 | **移除 keepNext** | 从 styles.xml 和 document.xml 全部移除 |
| 6 | **代码图片** | PIL 直接渲染（不用 Pygments ImageFormatter，CJK 有 bug） |

### 7.2 表格宽度修复（核心经验）

```python
from docx import Document
from docx.shared import Cm
from docx.oxml.ns import qn
from lxml import etree

doc = Document('paper.docx')

for i, table in enumerate(doc.tables):
    table.autofit = False
    tbl = table._tbl
    tblPr = tbl.find(qn('w:tblPr'))
    
    # 全宽
    tw = etree.SubElement(tblPr, qn('w:tblW'))
    tw.set(qn('w:w'), '5000'); tw.set(qn('w:type'), 'pct')
    
    # 固定布局
    tl = etree.SubElement(tblPr, qn('w:tblLayout'))
    tl.set(qn('w:type'), 'fixed')
    
    # 列宽（表1特殊处理，其余均分）
    ncols = len(table.columns)
    if i == 0:
        widths = [Cm(3.0), Cm(9.6), Cm(3.0)]  # 符号表：含义列最宽
    else:
        w = Cm(15.6 / ncols)
        widths = [w] * ncols
    
    # 单元格级别设置宽度（Word 真正尊重的层级）
    for row in table.rows:
        for ci, cell in enumerate(row.cells):
            if ci < len(widths):
                cell.width = widths[ci]
```

**为什么必须是 `cell.width`？** OOXML 中 `tcW` 优先级最高。`gridCol` 只是备选。

### 7.3 三线表边框 XML

```
顶线：single sz=12 (1.5pt)   —— 写在 <w:tblBorders><w:top>
表头下线：single sz=6 (0.75pt) —— 写在表头行每个 <w:tc><w:tcPr><w:tcBorders><w:bottom>
底线：single sz=12 (1.5pt)   —— 写在 <w:tblBorders><w:bottom>
左/右/行间/列间：val=none     —— 全部无
```

### 7.4 页脚页码 XML

```xml
<w:ftr xmlns:w="...">
  <w:p><w:pPr><w:jc w:val="center"/></w:pPr>
    <w:r><w:rPr><w:rFonts w:ascii="Times New Roman"/><w:sz w:val="21"/></w:rPr>
      <w:fldChar w:fldCharType="begin"/></w:r>
    <w:r><w:rPr><w:rFonts w:ascii="Times New Roman"/><w:sz w:val="21"/></w:rPr>
      <w:instrText xml:space="preserve"> PAGE </w:instrText></w:r>
    <w:r><w:rPr><w:rFonts w:ascii="Times New Roman"/><w:sz w:val="21"/></w:rPr>
      <w:fldChar w:fldCharType="end"/></w:r>
  </w:p>
</w:ftr>
```

同时更新 `word/_rels/document.xml.rels`（添加 footer 关系）和 `[Content_Types].xml`（注册 footer 类型）。

### 7.5 代码图片（含中文）

**不用 Pygments ImageFormatter**（GitHub issue #1213：CJK 字符会叠加）。

```python
from PIL import Image, ImageDraw, ImageFont

font = ImageFont.truetype('consola.ttf', 13)
for i, line in enumerate(code.split('\n')):
    clean = ''.join(c if ord(c) < 128 else '  ' for c in line)
    draw.text((pad, pad + i * line_h), clean, font=font, fill='#1a1a2e')
```

---

## 八、Step 7：多 Agent 审查

### 8.1 三 Agent 并行

| Agent | 职责 | 关键检查项 |
|:---|:---|:---|
| **格式审查** | EXA MCP 搜索最新规范 + 对比 DOCX styles.xml | 字号/字体/颜色/行距/页边距/页码 |
| **内容审查** | 阅读 README/todo/paper.md | 数据正确性、模型逻辑、参数可靠性、参考文献 |
| **渲染检查** | 解压 DOCX 检查 XML | 表格宽度/tcW、公式 OMML、无样式段落、图片嵌入 |

### 8.2 常见问题速查

| 发现 | 根因 | 修复 |
|:---|:---|:---|
| 标题是蓝色 | Pandoc 默认主题色 | styles.xml 显式设 `w:color w:val="000000"` |
| 无页码 | Pandoc 不生成 | 后处理创建 footer1.xml |
| 三线表极窄 | `tcW` 缺失 | python-docx `cell.width` 设单元格宽度 |
| 公式显示为纯文本 | 多余空白 `$$` 或复杂语法 | 检查 `$$` 配对，简化 `\left[...\right]` |
| 页面大段空白 | 标题 keepNext 强制绑定 | 从 styles.xml 全部移除 keepNext/keepLines |
| 代码图片文字叠加 | Pygments CJK bug | 改用 PIL + 过滤非 ASCII |
| 表格列宽不均 | gridCol 无宽度 | 保留 pandoc 生成的 gridCol 宽度值 |
| 参考文献只列未引 | 正文无引用标记 | 删除未引用文献或添加 `[N]` 引用 |

---

## 九、核心经验速查

### 建模代码

- ✅ 使用有约束优化 (`L-BFGS-B` + `bounds`)
- ✅ 目标函数不混入惩罚项
- ✅ 多起点策略避免局部最优
- ✅ 每步修改后运行代码验证
- ✅ 预测初始值确保从正确时间点获取

### 论文写作

- ✅ 论文口吻客观、冷静、不提及学习过程
- ✅ 所有公式 `\qquad (N)` 编号
- ✅ 图号从1开始连续
- ✅ 每条参考文献至少引用一次
- ✅ 数据表包含验证列

### Pandoc 转换

- ✅ 不用 `-s` + `--reference-doc` 同时
- ✅ 不用 `-M columns=30`
- ✅ 不用 `--toc`
- ✅ 确保 `$$` 配对正确，无空 `$$`

### DOCX 后处理

- ✅ `cell.width` 设表格宽度（非 gridCol）
- ✅ 直接写 XML 设三线表边框（非靠样式）
- ✅ 手动创建 footer1.xml 加页码
- ✅ 移除所有 keepNext/keepLines
- ✅ PIL 渲染代码图片（非 Pygments ImageFormatter）

### EXA MCP 搜索

- ✅ 先泛搜方案，后精准搜索具体问题
- ✅ 查 GitHub Issues（pandoc/pygments）
- ✅ 中文搜竞赛规范，英文搜技术方案

---

## 十、复用到新题目

1. **替换 README.md**：新题目 + 新数据
2. **替换 todo.md**：新格式要求 + 修改清单
3. **重写 model.py**：新题目的数学方法
4. **重写 paper.md**：新题目的解题思路和结果
5. **替换竞赛模板**：放入新的 `.docx` 模板
6. **调整 fix_reference.py**：从新模板提取字号/字体
7. **运行**：`python model.py && python gen_code_images.py && convert.bat`

> **核心原则：Markdown+LaTeX 写论文，Pandoc+reference.docx 管格式，python-docx 后处理兜底，EXA MCP 搜方案，多 Agent 审查质量。**