# MathModel 4.0

面向全国大学生数学建模竞赛的可复现建模与论文生成工具链。项目以 Python + Pandoc + `reference.docx` 为稳定主链路，同时提供可切换的 GPT、DeepSeek 和其他 OpenAI-compatible 模型助手。

这个项目不会替队伍“编造一个答案”。AI 负责题目拆解、模型候选、验证计划、论文审稿和格式审计；数据、代码运行结果、引用来源和最终结论必须由队伍确认。

## 目录

```text
mathmodel/
├── input/
│   ├── question.md          # 题目、数据说明、具体问题
│   └── todo.md              # 队伍约束、分工、待办
├── output/                  # 当前任务生成物，默认不进 Git
│   ├── model.py             # 可复现建模代码
│   ├── paper.md             # 论文源稿
│   ├── paper.docx           # 生成的 Word 论文
│   ├── figures/             # 图片
│   └── tables/              # 表格或中间数据
├── templates/
│   ├── reference.docx       # Pandoc 样式模板
│   ├── PAPER_SPEC.md        # 国赛格式与写作约束
│   └── paper_skeleton.md    # 论文骨架
├── scripts/
│   ├── init_project.py      # 初始化任务
│   ├── ai_assistant.py      # GPT/DeepSeek 结构化计划与审稿
│   ├── audit_project.py     # 离线 Markdown/DOCX 审计
│   ├── build_paper.py       # 统一构建入口
│   ├── package_support.py   # 支撑材料 ZIP
│   ├── build_reference.py   # 构建 Word 模板
│   └── postprocess_appendix.py
├── mathmodel.config.json    # 路径、比赛档案、AI 默认配置
├── requirements.txt
└── wiki.md                  # 完整工作流
```

## 快速开始

### 1. 安装依赖

```powershell
winget install JohnMacFarlane.Pandoc
python -m pip install -r requirements.txt
```

### 2. 初始化任务

```powershell
python scripts/init_project.py --keep-reference
```

初始化只清理 `output/` 生成物，不会覆盖 `input/`、`templates/` 或 `.claude/`。需要彻底开启新题目时使用：

```powershell
python scripts/init_project.py --force
```

### 3. 准备输入

把题目和数据说明写入 `input/question.md`，把分工、限制、必须回答的内容写入 `input/todo.md`，原始数据文件放在 `input/`。

### 4. 生成 AI 研究计划（可选）

默认配置保留 DeepSeek 兼容入口。切换到 GPT 时，复制 `.env.example` 中的配置到当前终端环境，并设置 API Key：

```powershell
$env:MM_AI_PROVIDER="openai"
$env:MM_AI_API_STYLE="responses"
$env:MM_AI_BASE_URL="https://api.openai.com/v1"
$env:MM_AI_MODEL="gpt-5.6-terra"
$env:MM_AI_API_KEY="YOUR_KEY"
python scripts/ai_assistant.py plan --force
```

DeepSeek 或其他兼容服务使用 `chat` API 风格：

```powershell
$env:MM_AI_PROVIDER="deepseek"
$env:MM_AI_API_STYLE="chat"
$env:MM_AI_BASE_URL="https://api.deepseek.com/v1"
$env:MM_AI_MODEL="deepseek-chat"
python scripts/ai_assistant.py plan --force
```

计划写入 `output/ai_plan.json`。没有 API Key 时不影响离线建模、审计和文档构建。

### 5. 运行模型与生成论文

队伍在 `output/model.py` 中实现模型，在 `output/paper.md` 中写论文。完成后执行：

```powershell
python scripts/audit_project.py
python scripts/build_paper.py
python scripts/package_support.py
```

Windows 也可以执行：

```powershell
scripts\convert.bat
```

`build_paper.py` 的顺序是：

1. 运行 `output/model.py`
2. 审计论文 Markdown
3. 在 `output/` 目录运行 Pandoc，保证相对图片路径正确
4. 运行 DOCX 后处理和结构检查
5. 写入 `output/audit_report.json` 与 `output/audit_report.md`

## 国赛写作底线

项目内的 `cumcm-2026` 档案依据官方 2026 修订稿整理，正式提交前仍应重新打开官方通知核对当年要求：

- 论文结构应包含摘要、问题重述、问题分析、模型假设、符号说明、模型建立与求解、模型评价、参考文献和附录。
- 不默认生成目录；正文不泄露队伍、学校等身份信息。
- 摘要控制在摘要专用页内，关键词使用空格分隔。
- 图题位于图下方，表题位于表上方；图号、表号分别从 1 开始连续。
- 表格优先拆成窄表，单表建议不超过 6 列；表内尽量使用 Unicode 数学符号，段落公式再使用 LaTeX。
- 论文中的数字必须能从模型代码、数据文件或审计报告复现。
- 参考文献只能使用真实、可核实的来源，正文必须有对应引用。
- 论文文件和支撑材料按当年官方报名/提交通知分别准备，不把支撑材料误当作论文正文。

## 联网研究协议

联网研究由 Agent 使用 Brave MCP 和 GitHub MCP 完成，脚本本身保持离线可运行：

1. Brave MCP：优先查官方竞赛通知、论文格式、标准、论文原文和算法原始资料。
2. GitHub MCP：查找成熟实现、Pandoc 模板和测试方式，只借鉴公开工程结构，不把仓库代码当作论文结论。
3. 搜索结果摘要不能直接作为引用；必须打开原文并记录标题、作者、年份、链接和使用位置。
4. AI 不得自行生成文献条目。无法核实的资料标记为待查，不进入最终参考文献。

## 主要命令

| 命令 | 用途 |
|:---|:---|
| `python scripts/init_project.py --keep-reference` | 初始化任务 |
| `python scripts/ai_assistant.py plan --force` | 生成结构化解题计划 |
| `python scripts/ai_assistant.py review --force` | 审阅论文草稿 |
| `python scripts/audit_project.py` | 离线审计源稿和已有 DOCX |
| `python scripts/build_paper.py` | 运行模型、转换、后处理、审计 |
| `python scripts/build_paper.py --skip-model` | 只转换已有论文源稿 |
| `python scripts/gen_code_images.py --input output/model.py --output output/figures/model_code.png` | 生成代码附录图片 |
| `python scripts/package_support.py` | 打包支撑材料 |

## 资料来源

- [全国大学生数学建模竞赛 2026 论文格式规范](https://www.mcm.edu.cn/html_cn/node/4cd596519c9eb9fbd866398f6df0caa3.html)
- [全国大学生数学建模竞赛官网](https://www.mcm.edu.cn/)
- [CUMCMThesis：2026 LaTeX 模板](https://github.com/latexstudio/CUMCMThesis)
- [math-modeling-skill：三阶段数学建模工作流](https://github.com/XiaoMaColtAI/math-modeling-skill)
- [Pandoc DOCX 模板实践](https://github.com/Achuan-2/pandoc_docx_template)

## License

MIT
