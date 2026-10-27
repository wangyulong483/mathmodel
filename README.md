# MathModel 4.1

面向全国大学生数学建模竞赛（CUMCM）的**可复现建模 + 论文生成**工作流，专为 [DeepSeek Harness](https://deepseek.com)（下称 DSH）会话设计。

它不是"一键生成论文"的工具：模型跑出的每个数字都有文件来源，论文的格式与提交检查由脚本执行，AI 负责拆题、候选方案、验证设计与审稿。一句话概括：

> **输入题目 -> 代码算出结果 -> 论文只引用结果 -> 脚本审计并生成 DOCX。**

## 环境要求

| 依赖 | 版本 | 说明 |
|:---|:---|:---|
| Python | 3.10+ | `python-docx` `Pillow` `numpy` `scipy` `pandas` `matplotlib` `scikit-learn` `lxml`（见 `requirements.txt`） |
| Pandoc | 3.x | `winget install JohnMacFarlane.Pandoc` / `brew install pandoc` / `apt install pandoc` |
| 编辑器 | 任意 | 推荐 VS Code；`output/paper.docx` 用 Word 或 LibreOffice 打开 |
| DSH | 当前版 | 在新会话中自动加载本仓库的 `AGENTS.md` |

## 目录结构

```text
mathmodel/
├─ AGENTS.md                  # DSH 会话契约：硬规则 + 入口命令 + 阶段 gate（自动加载）
├─ README.md                  # 本文件
├─ wiki.md                    # 完整工作流（权威流程）
├─ docs/
│  └─ agent-workflow.md       # DSH 多代理 / 目标 / 后台任务 / 记忆 / 提示词模板
├─ input/                     # 题目与数据（只读，不要在这里写代码）
│  ├─ question.md             # 题目原文
│  ├─ todo.md                 # 小问拆解与进度
│  └─ 附件*.md                # 数据说明、附件链接
├─ templates/
│  ├─ PAPER_SPEC.md           # 可执行格式约束 + 定稿检查清单
│  ├─ paper_skeleton.md       # 论文 Markdown 骨架
│  └─ reference.docx          # 由 scripts/build_reference.py 生成，勿手改
├─ scripts/                   # 工具链（唯一入口，见下表）
├─ .dsh/skills/ .agents/skills/  # DSH 技能：paper-formatter、mathmodel-pipeline
├─ output/                    # 全部生成物（不进 Git）
└─ mathmodel.config.json      # 赛事档案：页数、边距、AI 接口、路径
```

## 快速开始

```powershell
# 0) 检查环境
python --version
pandoc --version

# 1) 初始化（保留已有模板，只清生成物）
python scripts/init_project.py --keep-reference

# 2) 把题目写进 input/question.md，小问拆解写进 input/todo.md
#    附件与数据说明写进 input/附件*.md

# 3) （可选）导出结构化计划提示词；不配 API Key 也能用
python scripts/ai_assistant.py plan --print-prompt
#    -> output/ai_prompt_plan.md，粘给任意模型，把 JSON 存回 output/ai_plan.json

# 4) 建模：写 output/model.py，运行并落盘结果
python output/model.py

# 5) 写作：在 output/paper.md 按 templates/paper_skeleton.md 展开
#    所有数字引用 output/tables 或 output/logs 中的结果

# 6) 审计 -> 构建 -> 打包
python scripts/audit_project.py
python scripts/build_paper.py
python scripts/package_support.py
```

Windows 下也可双击 `scripts/convert.bat`（等价于 `build_paper.py`）。

## 在 DeepSeek Harness 里怎么用

DSH 会话打开本目录后，`AGENTS.md` 自动成为项目契约。推荐节奏：

1. **先计划，再动手**：让它读完 `input/` 并用 plan mode 给出小问拆解、模型候选与验证方案；确认后再写代码。
2. **研究用原生工具**：`web_search` 找线索，`web_fetch` 打开原文核对；搜索摘要不算证据。需要并行研究多个小问时，用 `subagent` 分头做，各自回传"事实 + 链接 + 置信度"。
3. **写作用域隔离**：论文、代码、模板由不同角色/子代理并行时，用 Agent Teams 的 `team_task` 登记写作用域，避免互相覆盖（见 `docs/agent-workflow.md`）。
4. **长任务后台跑**：仿真、网格搜索、批量训练用后台 job 提交，用 `job_output` 收集；不要在前台干等。
5. **交付走脚本**：`audit_project.py` -> `build_paper.py` -> `package_support.py`，不要手工 pandoc。

> 没有配置模型 API 也能完整使用：`ai_assistant.py` 的 `--print-prompt` 会把提示词和 JSON Schema 写到 `output/`，粘到任意聊天窗口即可；DSH 本身已内置模型。

## 命令表

| 命令 | 作用 |
|:---|:---|
| `python scripts/init_project.py [--force\|--keep-reference\|--keep-output\|--skip-deps\|--no-build]` | 初始化；`--force` 清空 output 重开题目 |
| `python scripts/audit_project.py` | 离线审计 Markdown 与已有 DOCX，写 `output/audit_report.json/.md` |
| `python scripts/build_paper.py [--skip-model\|--skip-audit\|--keep-docx]` | 模型 -> 审计 -> Pandoc -> 附录后处理 -> 复核 |
| `python scripts/build_reference.py` | 从 pandoc 默认模板生成 `templates/reference.docx`（A4/2.5cm/页脚/三线表）；无参数，重复执行幂等 |
| `python scripts/gen_code_images.py` | 把代码转成带行号的附录图片 |
| `python scripts/package_support.py` | 打包 `output/support_materials.zip` |
| `python scripts/ai_assistant.py plan [--print-prompt\|--force]` | 结构化建模计划（JSON） |
| `python scripts/ai_assistant.py review [--print-prompt\|--force]` | 论文审查报告（JSON） |
| `python scripts/convert.bat` | Windows 快捷方式，转调 `build_paper.py` |

## 工作流概览

| 阶段 | 产物 | 通过条件 |
|:---|:---|:---|
| 初始化 | 干净 `output/`、模板 | pandoc 3.x、依赖齐全 |
| 题目理解 | 事实表、约束、数据字段 | 引用可打开核对 |
| 计划 | `output/ai_plan.json` 或对话内计划 | 每问有候选模型 + 验证指标 |
| 数据审计 | `output/logs/` 记录 | 单位、缺失、异常、划分明确 |
| 建模求解 | `output/model.py`、`output/tables/*.json` | 随机种子固定，结果可复现 |
| 论文 | `output/paper.md` | 图表编号连续、正文引用齐全、数字有来源 |
| 审计构建 | `output/paper.docx`、审计报告 | 无阻断项，DOCX 打开正常 |
| 审稿 | 审查报告 | 数学/数据/格式风险清零 |
| 提交 | `support_materials.zip` | 两个文件可打开，无身份信息 |

完整的阶段说明、写作规则、公式约束与故障排查见 [wiki.md](wiki.md)；格式细则见 [templates/PAPER_SPEC.md](templates/PAPER_SPEC.md)。

## 常见问题

| 症状 | 处理 |
|:---|:---|
| `pandoc not found` | 安装 pandoc 3.x 并重开终端；`init_project.py` 会检查版本 |
| DOCX 打开空白/图片丢失 | 不要手工 pandoc；用 `build_paper.py`，它在 `output/` 内执行 |
| 页脚没有页码 / 不是 A4 | 重新生成模板：`python scripts/build_reference.py`（无参数），再构建 |
| AI 调用失败（401/超时） | 用 `--print-prompt` 导出提示词离线完成；或检查 `.env` 的 `MM_AI_*` |
| 审计报"数字无来源" | 把结果写进 `output/tables` 并在正文用表格/行内代码引用 |
| 页数超限 | 精简正文与图表，不要改页边距；见 `PAPER_SPEC.md` |

## 4.1 更新（从 Claude Code 版迁移）

- **新增 `AGENTS.md`**：作为 DSH 唯一会话契约，替代原先散落在对话里的约定。
- **研究协议原生**：Brave/GitHub MCP 两条硬依赖改为 `web_search` + `web_fetch`；要接 MCP 时，DSH 的入口是 profile 里 `cordis.patch.yml` 的 `dsh-mcp-client` 插件配置（不是 `mcpServers` 键），工具名形如 `mcp__<server>__<tool>`，默认不需要。
- **AI 步骤可分可合**：`ai_assistant.py` 新增 `--print-prompt`，无 API Key 也能产出计划/审稿提示词；修复了 `project_path` 未导入导致的崩溃。
- **模板自愈**：`build_reference.py` 现在把 A4 页面、2.5cm 页边距、页脚页码直接写进 `reference.docx`，并修复 rels 命名空间；重复执行幂等。
- **初始化自检**：`init_project.py` 检查 `AGENTS.md` 与技能目录（`.dsh/skills` 或 `.agents/skills`）是否就位。
- **清理 Claude 遗留**：删除 `.claude/`、`skills-lock.json`、`reference.docx.bak`；`paper-formatter` 技能脚本路径改为仓库内相对路径。
- **新增 `docs/agent-workflow.md`** 与 `mathmodel-pipeline` 技能，覆盖 DSH 的 plan mode、subagent、Agent Teams、后台 job 与记忆用法。

## 文档地图

| 文档 | 何时读 |
|:---|:---|
| [AGENTS.md](AGENTS.md) | 每次会话自动加载，先看它 |
| [wiki.md](wiki.md) | 想知道某阶段具体怎么做 |
| [docs/agent-workflow.md](docs/agent-workflow.md) | 想并行/分工/后台跑/让代理自我审查 |
| [templates/PAPER_SPEC.md](templates/PAPER_SPEC.md) | 写作与定稿前 |
| `.agents/skills/paper-formatter/SKILL.md` | 需要套用期刊/竞赛排版时 |

## 资料来源

- 全国大学生数学建模竞赛官网：<https://www.mcm.edu.cn/>
- CUMCMThesis LaTeX 模板与格式参考：<https://github.com/latexstudio/CUMCMThesis>
- Pandoc 文档：<https://pandoc.org/MANUAL.html>
- 参考模板来源：`pandoc_docx_template`

## License

MIT
