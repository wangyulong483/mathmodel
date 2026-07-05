# Agent 通用工作流：数学建模题目 → Word 论文（v2.0 优化版）

> **用途**：给定任意数学建模题目（`question.md` + `todo.md` + 可选竞赛模板 `.docx`），按此工作流自动生成符合竞赛规范的 Word 论文。
>
> **适用范围**：全国大学生数学建模竞赛（CUMCM）、校赛、暑期培训作业等各类数学建模论文。
>
> **v2.0 更新**：集成 Word MCP + Word Skill + EXA MCP，关键优化——Pandoc "Table" 样式消除三线表后处理、Word MCP 工具简化表格操作、MCP 审查工具增强质量保证。

---

## 〇、可用工具与能力速查

### Word MCP Server（`word-document-server`）

| 类别 | 工具 | 用途 |
|:---|:---|:---|
| **样式创建** | `create_custom_style` | 创建简单样式（单字体，无需 CJK/Latin 分离） |
| **表格格式** | `format_table` | 表格边框、表头行、底纹 |
| | `set_table_column_widths` | 精确列宽 |
| | `highlight_table_header` | 表头行高亮 |
| | `set_table_alignment_all` | 全体单元格对齐 |
| | `apply_table_alternating_rows` | 交替行底色 |
| **内容插入** | `add_picture` | 插入代码图片 |
| | `add_heading`, `add_paragraph` | 如需直接构建文档 |
| **检查审查** | `get_document_outline` | 验证标题层级结构 |
| | `get_document_text` | 提取全文做内容审查 |
| | `get_document_xml` | 深入检查 OOXML |
| | `find_text_in_document` | 定位特定内容 |
| | `validate_document_footnotes` | 脚注完整性 |
| | `get_document_info` | 页数/字数 |

### Word Skill（`word-docx-1.0.2`）

关键规则：
- **样式 > 直接格式**：优先用命名样式，不堆叠行内格式
- **节级布局**：页边距/页眉/页脚/页码是节级行为
- **三线表用样式**：表边框应通过 table style 定义，不靠后处理 XML
- **CJK/Latin 字体分离**：中文论文需要 `w:rFonts w:ascii="TNR" w:eastAsia="SimSun"`
- **keepNext 陷阱**：标题 keepNext 会导致跨页大片空白

### EXA MCP（`web_search_exa` / `web_fetch_exa`）

用于搜索最佳实践、Pandoc 问题、OOXML 规范、竞赛格式要求。

---

## 一、工作流总览

```
input/question.md + input/todo.md + templates/PAPER_SPEC.md（格式规范）
        │
        ├── [1] 理解需求 ── 读 input/ + EXA MCP 搜索
        ├── [2] 建模求解 ── 写 output/model.py → 运行验证 → 生成图表
        ├── [3] 撰写论文 ── Markdown + LaTeX 公式 → output/paper.md
        ├── [4] 构建模板 ── XML（CJK/Latin 样式）+ MCP（简单样式）+ "Table" 三线表样式
        ├── [5] Pandoc ── Markdown → DOCX（OMML 公式 + "Table" 样式自动应用）
        ├── [6] 后处理 ── 仅：列宽 + keepNext 清除 + 代码图片（三线表边框由样式自动处理）
        └── [7] 审查迭代 ── 3 Agent 并行 + Word MCP 检查工具
```

### 关键变化（v1.0 → v2.0）

| 步骤 | v1.0 | v2.0 |
|:---|:---|:---|
| Step 4 | 160 行 XML 改 styles.xml | XML（CJK/Latin）+ MCP（简单样式）+ "Table" 样式 |
| Step 5 | `-s` 标志 | 移除 `-s`（与 reference.docx 冲突） |
| Step 6 | 70 行 lxml 写三线表边框 | **零代码**——"Table" 样式自动处理 |
| Step 6 | python-docx cell.width | MCP `set_table_column_widths` |
| Step 7 | 建议手动检查 XML | MCP `get_document_outline` + `get_document_xml` + `validate` |

---

## 二、Step 1：理解需求 & 搜索方案

### 2.1 读输入

```
Read input/question.md  → 题目背景、数据、具体问题列表
Read input/todo.md      → Agent 专属指令
Read templates/PAPER_SPEC.md → 通用论文格式规范
Glob input/*.xlsx       → 发现附件数据文件
```

### 2.2 调用 Word Skill 确定样式策略

在搜索前，先咨询 Word Skill 确定样式策略：
- 确认哪些格式走样式、哪些走直接格式
- 确认节级布局设置（页边距/页眉/页脚）
- 确认三线表通过 table style 定义，不在后处理中手写 XML

### 2.3 EXA MCP 搜索清单

| 搜索类别 | 触发条件 | 典型搜索词 |
|:---|:---|:---|
| **格式转换方案** | 任何题目 | `pandoc 3.x markdown to docx preserve equations reference docx` |
| **竞赛格式规范** | 任何题目 | `全国大学生数学建模竞赛 论文格式规范 字号 字体 页边距 CUMCM` |
| **Pandoc Table 样式** | 任何题目（新增） | `pandoc reference docx Table style custom borders OOXML` |
| **数学模型参考** | 特定模型 | `SIR model parameter estimation python scipy` |
| **三线表 OOXML** | 表格问题 | `OOXML tblBorders three-line table Chinese academic paper` |
| **公式渲染问题** | 转换后 | `pandoc mathml omml sum subscript not rendering` |
| **代码图片问题** | 附录含代码 | `PIL render code to image monospace CJK font` |

---

## 三、Step 2：建模与求解

（与 v1.0 相同——纯数学/代码，无 MCP 工具影响）

### 3.1 代码结构模板

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
# ===== 1. 模型定义 =====
# ===== 2. 求解/拟合 =====
# ===== 3. 结果计算 =====
# ===== 4. 情景分析 =====
# ===== 5. 守恒/正确性验证 =====
# ===== 6. 绘图 =====
```

### 3.2 参数估计通用经验

- ✅ 使用有约束优化（`L-BFGS-B` + `bounds`）
- ✅ 目标函数纯净，不混入惩罚项
- ✅ 多起点策略避免局部最优
- ✅ 参数落在约束边界时论文中诚实说明
- ✅ 每次修改代码后立即运行验证

### 3.3 图表规范

```
fig1_model_diagram.png     # 图1 模型结构/流程
fig2_data_or_result.png    # 图2 数据展示/中间结果
fig3_fitting.png           # 图3 拟合/求解结果
fig4_solution.png          # 图4 模型数值解
fig5_prediction.png        # 图5 预测结果
fig6_comparison.png        # 图6 情景/参数对比
```

---

## 四、Step 3：撰写论文 Markdown

（与 v1.0 相同——内容创作）

### 4.1 YAML

```yaml
---
title: "{论文标题}"
---
```

### 4.2 通用论文结构

```markdown
# 摘要（300-500字）
**关键词：** KW1；KW2；KW3；KW4；KW5

# 1 问题重述
## 1.1 问题背景
## 1.2 问题重述

# 2 问题分析

# 3 模型假设（编号列表，≥6条）

# 4 符号说明（三线表：符号 | 含义 | 单位）

# 5 模型建立与求解
## 5.1 模型建立（含图1）
## 5.2 数据处理（含表1、图2）
## 5.3 参数求解（含表2、图3）
## 5.4 数值求解（含图4）
## 5.5 结果与预测（含表3、图5）
## 5.6 对比分析（含表4、图6）

# 6 模型评价
## 6.1 优点
## 6.2 缺点
## 6.3 改进方向
## 6.4 模型推广

# 参考文献（≥3条，全部在正文引用）

# 附录
## 附录A 支撑材料文件列表
## 附录B 核心代码（图片嵌入）
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

**禁止项**：`\tag{...}`、`\bigl`/`\bigr`、`\left[...\right]`、自定义宏、空 `$$`

### 4.4 图文规则

- 图号从 1 开始连续，表题注在表上方
- 论文口吻客观冷静，不出现"课堂上学习了""参考PPT"

---

## 五、Step 4：构建 reference.docx（优化重点）

### 5.1 核心洞察：Pandoc "Table" 样式机制

**Pandoc 对每个表格写入 `<w:tblStyle w:val="Table"/>`**，即在 reference.docx 中定义 `w:styleId="Table"` 的表格样式，Pandoc 会自动应用到所有表格。

**Pandoc 3.x（我们使用 3.10）已移除硬编码的表头单元格边框**，因此样式中定义的三线表边框会被完整保留，无需后处理。

### 5.2 构建流程

```
[1] pandoc -o reference.docx --print-default-data-file reference.docx
        │
[2] build_reference.py（XML 层：CJK/Latin 字体分离样式）
        │   └── 处理 Normal/Title/Heading1-3/Caption/Bibliography/Source Code
        │   └── 处理 "Table" 表格样式（三线表边框定义）
        │
[3] Word MCP create_custom_style（简单单字体样式）
        │   └── Author, Date, Subtitle, TOC Heading, Block Text
        │
[4] Word MCP get_document_xml（验证 styles.xml）
```

### 5.3 "Table" 样式：三线表 OOXML 定义

将此样式添加到 reference.docx 的 `word/styles.xml` 中（`build_reference.py` 自动完成）：

```xml
<w:style w:type="table" w:styleId="Table">
  <w:name w:val="Table"/>
  <w:basedOn w:val="7"/>  <!-- 继承 Normal Table -->
  <w:pPr><w:jc w:val="center"/></w:pPr>
  <w:tblPr>
    <w:jc w:val="center"/>
    <w:tblBorders>
      <w:top    w:val="single" w:sz="12" w:space="0" w:color="000000"/>
      <w:left   w:val="none"   w:sz="0"  w:space="0" w:color="auto"/>
      <w:bottom w:val="single" w:sz="12" w:space="0" w:color="000000"/>
      <w:right  w:val="none"   w:sz="0"  w:space="0" w:color="auto"/>
      <w:insideH w:val="none"  w:sz="0"  w:space="0" w:color="auto"/>
      <w:insideV w:val="none"  w:sz="0"  w:space="0" w:color="auto"/>
    </w:tblBorders>
  </w:tblPr>
  <w:tcPr><w:vAlign w:val="center"/></w:tcPr>
  <w:tblStylePr w:type="firstRow">
    <w:tcPr>
      <w:tcBorders>
        <w:bottom w:val="single" w:sz="6" w:space="0" w:color="000000"/>
      </w:tcBorders>
    </w:tcPr>
  </w:tblStylePr>
</w:style>
```

**边框宽度对照**：OOXML 中 `sz` 的单位是 1/8 点 → 1.5pt = sz="12"，0.75pt = sz="6"

### 5.4 通用样式参数

| 样式 | 字号(pt) | CJK字体 | EN字体 | 加粗 | 对齐 | 行距 | 缩进 | keepNext |
|:---|:---|:---|:---|:---|:---|:---|:---|:---|
| Normal | 12 | SimSun | Times New Roman | 否 | both | 1.25x | 0.74cm | — |
| Title | 16 | SimHei | Times New Roman | 是 | center | 1.5x | 0 | **否** |
| Heading 1 | 14 | SimHei | Times New Roman | 是 | center | 1.5x | 0 | **否** |
| Heading 2 | 12 | SimHei | Times New Roman | 是 | left | 1.5x | 0 | **否** |
| Heading 3 | 12 | SimHei | Times New Roman | 是 | left | 1.25x | 0 | **否** |
| Caption | 10.5 | SimSun | Times New Roman | 是 | center | 1.25x | 0 | — |
| Bibliography | 10.5 | SimSun | Times New Roman | 否 | both | 1.25x | 0 | — |
| Source Code | 9 | SimSun | Consolas | 否 | left | 1.0x | 0 | — |

- **所有字体颜色 `#000000`**（Pandoc 默认给 Heading 加蓝色主题色）
- **`keepNext` 全部禁用**（否则标题强制绑定下文，跨页产生大段空白）

### 5.5 分工原则

| 方法 | 适用场景 | 原因 |
|:---|:---|:---|
| **XML（build_reference.py）** | 需要 CJK/Latin 字体分离的样式 | MCP `create_custom_style` 只接受单一 `font_name` |
| **Word MCP `create_custom_style`** | 单字体简单样式 | 避免 XML 操作，快速可靠 |

### 5.6 页边距与页脚

- A4 (21×29.7cm)，上下 ≥2.5cm，左右 ≥2.5cm
- **页脚页码已预置在 reference.docx 模板中**（居中 PAGE 字段，TNR 10.5pt）
- Pandoc `--reference-doc` 自动保留页脚 → 无需后处理创建

---

## 六、Step 5：Pandoc 转换

```bash
pandoc output/paper.md -o output/paper.docx \
    --reference-doc=templates/reference.docx \
    --mathml \
    --syntax-highlighting=pygments
```

**与 v1.0 的关键变化**：
- ❌ **移除 `-s`**：wiki 说不用但 convert.bat 用了，会导致与 reference.docx 的 `<w:sectPr>` 冲突
- ❌ **不用 `--toc`**：国赛禁止目录

### Pandoc 不可替代的核心能力

- Markdown 段落/标题/列表 → OOXML 结构
- LaTeX 公式 → OMML（`--mathml`）——**这是整个流程的核心**
- 代码块语法高亮（`--syntax-highlighting=pygments`）
- `--reference-doc` 自动应用 "Table" 样式到所有表格

---

## 七、Step 6：后处理（大幅简化）

### 7.1 变化总览

| 任务 | v1.0 方法 | v2.0 方法 | 节省代码 |
|:---|:---|:---|:---|
| **三线表边框** | 50 行 lxml 手写 `<w:tblBorders>` | **零代码**——"Table" 样式自动处理 | ~50 行 |
| **表头底线 0.75pt** | 20 行 lxml 手写 `<w:tcBorders>` | **零代码**——`tblStylePr firstRow` | ~20 行 |
| **表格列宽** | 10 行 python-docx `cell.width` | MCP `set_table_column_widths` | 保留或简化 |
| **keepNext 清除** | 15 行 lxml | 15 行 lxml（无 MCP 替代） | 0 |
| **页脚页码** | 已验证模板存在 | 已验证模板存在（无变化） | 0 |
| **代码图片** | PIL 渲染 | PIL 渲染 + MCP `add_picture` | 0（但更可靠） |

### 7.2 后处理清单

#### 7.2.1 表格列宽（Word MCP）

```python
# 对每个表格调用 MCP：
# 符号表（表1，3列）：
set_table_column_widths(paper.docx, table_index=0,
    widths=[3.0, 9.6, 3.0], width_type="cm")

# 其余表格（均分）：
set_table_column_widths(paper.docx, table_index=i,
    widths=[15.6/ncols]*ncols, width_type="cm")
```

**注意**：如果表有合并单元格，`set_table_column_widths` 可能失败。此时回退到 python-docx `cell.width`。

#### 7.2.2 keepNext 清除（Python/lxml，保留）

```python
# 从 styles.xml 和 document.xml 移除所有 keepNext/keepLines
# 约 15 行，无 MCP 工具可替代
for p in doc.paragraphs:
    pPr = p._element.find(qn('w:pPr'))
    if pPr is not None:
        for tag in ['keepNext', 'keepLines']:
            for el in list(pPr):
                if el.tag == qn(f'w:{tag}'):
                    pPr.remove(el)
```

#### 7.2.3 代码图片（PIL + MCP add_picture）

```python
from PIL import Image, ImageDraw, ImageFont

# 渲染代码为 PNG
font = ImageFont.truetype('consola.ttf', 13)
for i, line in enumerate(code.split('\n')):
    draw.text((pad, pad + i * line_h), line, font=font, fill='#1a1a2e')
img.save('code_appendix.png')

# MCP 插入
add_picture(paper.docx, 'code_appendix.png', width=15.6, width_type="cm")
```

### 7.3 三线表验证

由于 "Table" 样式已处理边框，Pandoc 3.x 不再注入硬编码 `w:tcBorders`，转换后直接检查即可：

```
get_document_xml(paper.docx) → 确认 <w:tblStyle w:val="Table"/> 存在
get_document_xml(paper.docx) → 确认无残留 <w:tcBorders> 在表头单元格
```

---

## 八、Step 7：多 Agent 审查（增强）

### 8.1 三 Agent 并行

| Agent | 职责 | v2.0 新增工具 |
|:---|:---|:---|
| **格式审查** | EXA MCP 搜索最新规范 + MCP 检查 styles.xml | `get_document_outline` 验证标题层级；`get_document_xml` 检查字体/字号/颜色/行距 |
| **内容审查** | 阅读 question.md/todo.md/paper.md | `get_document_text` 提取全文供审查；`find_text_in_document` 验证参考文献引用 |
| **渲染检查** | MCP 检查 DOCX XML + 结构完整性 | `validate_document_footnotes`；`get_document_info` 验证页数/字数；`get_document_xml` 检查表格 tcW/OMML/图片嵌入 |

### 8.2 Word Skill 格式审查清单

格式审查 Agent 调用 Word Skill 规则：
- ✅ 样式是主要格式机制（非直接格式堆叠）
- ✅ 页布局是节级设置（非手动空行/分页符）
- ✅ 无空段落做间距（间距应在段落设置中）
- ✅ 表宽是显式值（非 auto-fit 百分比）
- ✅ 三线表边框由 "Table" 样式定义（非直接格式）

### 8.3 Word MCP 审查工作流

```
[格式审查 Agent]
  get_document_outline(paper.docx)     → 验证 H1→H2→H3 嵌套
  get_document_xml(paper.docx)          → 检查 styles.xml 字体颜色（Heading 不应是蓝色）
  find_text_in_document(paper.docx, "参考文献") → 确认参考文献节存在

[内容审查 Agent]
  get_document_text(paper.docx)         → 提取全文
  find_text_in_document(paper.docx, "[1]") → 验证参考文献引用标记存在

[渲染检查 Agent]
  get_document_info(paper.docx)         → 验证页数 ≥10、字数 ≥5000
  get_document_xml(paper.docx)          → 检查 <w:tblStyle w:val="Table"/> 存在于所有表格
  get_document_xml(paper.docx)          → 检查无残留 <w:keepNext/>
  validate_document_footnotes(paper.docx) → 验证脚注完整性
```

### 8.4 常见问题速查

| 发现 | 根因 | 修复 |
|:---|:---|:---|
| 标题是蓝色 | Pandoc 默认主题色 | styles.xml 显式设 `w:color w:val="000000"` |
| 三线表边框缺失 | reference.docx 无 "Table" 样式 | 确保 `build_reference.py` 注入了 "Table" 样式 |
| 三线表有竖线 | Pandoc 2.x 残留硬编码边框 | 确认 Pandoc 版本 ≥3.0 |
| 页面大段空白 | 标题 keepNext 强制绑定 | 从 styles.xml 全部移除 keepNext/keepLines |
| 表格列宽不均 | gridCol 无宽度/WPS 渲染差异 | MCP `set_table_column_widths` 设 cell 级宽度 |
| 公式显示为纯文本 | 空 `$$` 或复杂语法 | 检查 `$$` 配对，简化 `\left[...\right]` |
| 代码图片文字叠加 | Pygments CJK bug | 改用 PIL + Consolas 字体渲染 |

---

## 九、多 Agent 并行执行策略

### 9.1 阶段与并行度

```
Phase 1: [Agent: 研究]  Step 1（搜索 + 理解需求）
Phase 2: [2 Agent 并行]  Agent A: Step 2（建模求解）
                         Agent B: Step 4（构建 reference.docx）
Phase 3: [Agent: 写作]  Step 3（撰写 paper.md）← 依赖 Phase 2 Agent A
Phase 4: [Agent: 转换]  Step 5（Pandoc）
Phase 5: [Agent: 后处理] Step 6（MCP + 脚本）
Phase 6: [3 Agent 并行]  Step 7（格式 + 内容 + 渲染审查）
```

### 9.2 各阶段 MCP/Skill 工具使用

| 阶段 | Word MCP | Word Skill | EXA MCP |
|:---|:---|:---|:---|
| Phase 1 | — | 样式策略咨询 | 搜索最佳实践/规范 |
| Phase 2 | `create_custom_style`（简单样式） | — | 搜索模型/算法参考 |
| Phase 3 | — | — | — |
| Phase 4 | — | — | — |
| Phase 5 | `set_table_column_widths`, `add_picture` | — | — |
| Phase 6 | `get_document_outline`, `get_document_xml`, `validate_document_footnotes` | 格式合规检查 | 搜索疑难问题解决方案 |

---

## 十、复用到新题目

1. **清空 `output/`**，删除上次任务的所有生成物
2. **替换 `input/question.md`**：新题目 + 新数据（附件 .xlsx 放入 `input/`）
3. **替换 `input/todo.md`**：新题目的 Agent 专属指令
4. **`templates/` 通常不变**：reference.docx（含 "Table" 样式）和 PAPER_SPEC.md 跨任务复用
5. **重写 `output/model.py`**：新题目的数学方法（建模 + 出图 + 代码图片生成）
6. **重写 `output/paper.md`**：从骨架复制，填入新内容
7. **运行**：`python output/model.py && scripts/convert.bat`

### 目录职责一览

| 目录 | 职责 | 是否跨任务复用 |
|:---|:---|:---|
| `input/` | 题目、数据、Agent 指令 | 否（每次替换） |
| `output/` | 论文、图表、模型代码 | 否（.gitignore） |
| `templates/` | reference.docx（含 "Table" 样式）、PAPER_SPEC.md、paper_skeleton.md | **是** |
| `scripts/` | convert.bat、build_reference.py、postprocess 脚本 | **是** |

---

## 十一、核心经验速查

### 建模代码
- ✅ 使用有约束优化 (`L-BFGS-B` + `bounds`)
- ✅ 目标函数不混入惩罚项
- ✅ 多起点策略避免局部最优
- ✅ 每步修改后运行代码验证

### 论文写作
- ✅ 论文口吻客观、冷静
- ✅ 所有公式 `\qquad (N)` 编号
- ✅ 图号从 1 开始连续
- ✅ 每条参考文献至少引用一次

### Pandoc 转换
- ✅ Pandoc ≥3.0（我们使用 3.10）——"Table" 样式方案可行
- ✅ 不用 `-s` + `--reference-doc` 同时
- ✅ 不用 `--toc`
- ✅ 确保 `$$` 配对正确，无空 `$$`

### DOCX 后处理（大幅简化）
- ✅ **三线表边框零代码**——"Table" 样式自动处理
- ✅ MCP `set_table_column_widths` 设列宽
- ✅ 移除所有 keepNext/keepLines（保留 Python/lxml）
- ✅ PIL 渲染代码图片（非 Pygments ImageFormatter）
- ✅ 页脚页码已预置在 reference.docx 中

### 样式构建
- ✅ XML 处理需要 CJK/Latin 字体分离的样式（MCP 无法做到）
- ✅ MCP `create_custom_style` 处理简单单字体样式
- ✅ "Table" 样式一次定义，所有表格自动应用

### EXA MCP 搜索
- ✅ 先泛搜方案，后精准搜索具体问题
- ✅ 查 GitHub Issues（pandoc/pygments）
- ✅ 中文搜竞赛规范，英文搜技术方案

### Word MCP 审查
- ✅ `get_document_outline` 验证标题结构
- ✅ `get_document_xml` 深入检查 OOXML
- ✅ `validate_document_footnotes` 检查完整性

---

## 十二、实战经验总结（来自 2022 CUMCM C 题全流程实战）

### 12.1 样式与排版踩坑

| 踩坑 | 根因 | 正确做法 |
|:---|:---|:---|
| 标题显示为等线而非黑体 | `eastAsiaTheme="majorEastAsia"` 覆盖了显式的 `SimHei` | `set_fonts()` 中清除所有 `*Theme` 属性 |
| WPS 模板的 reference.docx 与 Pandoc 不兼容 | WPS 使用非标准 styleId | **必须从 Pandoc 默认生成**：`pandoc --print-default-data-file reference.docx` |
| CJK/Latin 字体无法分离 | MCP `create_custom_style` 只接受单一 `font_name` | XML 层处理：`w:rFonts w:ascii="TNR" w:eastAsia="SimSun"` |
| 正文大量段落无首行缩进 | Markdown 空行分隔 → Pandoc 映射到 Compact 样式 | 段落间不加空行，或用 Lua filter 重映射到 Normal |

### 12.2 图表规范

| 规范 | 做法 |
|:---|:---|
| **图号必须连续** | 33 张图从 图1→图33，按正文出场顺序，不跳号不倒序 |
| **图尺寸统一** | model.py 定义 `SINGLE`/`TWO_PANEL`/`BOXPLOT` 等常量，所有 `figsize` 使用常量 |
| **表题在表上方** | paper.md 中 `**表N 标题**` 置于表格前，`postprocess_appendix.py` 自动应用 Table Caption 样式 |
| **三线表零代码** | reference.docx 中定义 `styleId="Table"` 样式 → Pandoc 3.x 自动应用 |
| **表号连续无重复** | 插入新表后检查全文 `**表N` 无冲突，正文引用 `见表 N` 与之对应 |

### 12.3 数据一致性自检清单

论文定稿前必须逐项检查：

- [ ] 表5（敏感性）的"修正后"列 = 表10（预测结果）的数值
- [ ] 表中化学成分描述 = 原始数据（表单1/2/3）
- [ ] 摘要的预测结论 = 正文表10 的最终结论
- [ ] 配对数 = 全文统一（4 对，非 5 对）
- [ ] 所有正文引用 `见表 N` = 实际表格编号
- [ ] 参考文献全部在正文引用过
- [ ] 未实现的代码功能不在论文中声称（如 SHAP）

### 12.4 学术诚实性原则

| 原则 | 做法 |
|:---|:---|
| **有局限就承认** | 高钾无配对 → 明确声明，用敏感性分析检验 |
| **Silhouette 非最优就说** | K=2 的 0.247 > K=3 的 0.229，坦诚讨论后选择 K=3 的理由 |
| **网络分析是探索性** | 14 节点 10 边分 8 社区 → 主动说明解释力有限 |
| **化学先验知识可纠偏模型** | A6/A7 无 PbO + 高 SiO₂ → 即使模型判铅钡，综合判定为高钾 |
| **不声称未实现的方法** | 查到 SHAP 未在代码中 → 立即删除论文中所有 SHAP 引用 |

### 12.5 多 Agent 协作模式

| 模式 | 适用场景 | 示例 |
|:---|:---|:---|
| **并行研究** | 需要多个独立方向的调研 | Agent1=Pandoc Table 样式, Agent2=docx-plus 页码, Agent3=工作流设计 |
| **并行实现** | 多个独立模块同步开发 | Agent1=高钾敏感性, Agent2=K=2 聚类对比, Agent3=Soft Voting 权重 |
| **串行审查** | 需要层层把关的评审 | human → Agent 格式审查 → Agent 内容审查 → human 最终定稿 |
| **注意** | Agent 修改后必须检查数据一致性 | Agent 修复 VotingClassifier 权重 → A6/A7 预测翻转 → 全文表9/10/5 不一致 |

### 12.6 附录与提交

| 要点 | 规范 |
|:---|:---|
| **附录A** | 只列实际提交/引用的支撑文件（`model.py`） |
| **附录B** | 一段文字概述代码结构，不嵌代码图片 |
| **提交文件** | 只交 `paper.docx` 一个文件 |
| **model.py** | docstring 标题 + `# ---- Step X: ----` 分隔 + 按四问组织 |

---

> **核心原则：Markdown+LaTeX 写论文，Pandoc+reference.docx（含 "Table" 样式）管格式，Word MCP 后处理表格 + 审查，python-docx/XML 兜底，EXA MCP 搜方案，多 Agent 并行 + 人工审查保证质量，化学先验知识优于模型盲信。**
