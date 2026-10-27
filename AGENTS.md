# AGENTS.md — DeepSeek Harness 协作契约

本文件在每次 DSH 会话中自动加载。完整的建模流程见 `wiki.md`，多代理/长任务协作细则见 `docs/agent-workflow.md`，论文格式约束见 `templates/PAPER_SPEC.md`。本文件只写硬规则与入口，不重复细节。

## 项目是什么

MathModel 4.1：面向全国大学生数学建模竞赛（`cumcm-2026` 档案）的可复现建模与论文生成工具链。

```text
input/ 题目与数据  ->  output/model.py 计算  ->  output/paper.md 写作
                  ->  Pandoc + templates/reference.docx  ->  output/paper.docx
                  ->  output/support_materials.zip
```

AI 负责拆题、候选模型、验证设计、论文审稿和格式审计；数据、运行结果、引用与最终结论必须由代码产出或由人确认。

## 硬规则

1. **不编造**：不虚构数据、参数、实验结果、参考文献；没运行过的模型不得写成已验证结果。
2. **可复现**：论文中每个数字必须能追溯到 `output/model.py`、`output/tables/*.json` 或 `output/logs/*`；禁止手填数字。
3. **引用可核实**：搜索摘要不能当证据；必须用 `web_fetch` 打开原文核对标题、作者、年份、链接；无法核实就删除或标为待查。
4. **边界干净**：`input/` 只读；`templates/reference.docx` 由脚本生成，不手工编辑；`output/` 不进 Git；不提交 API Key 与队伍/学校身份信息。

## 唯一入口命令

| 目的 | 命令 |
|:---|:---|
| 初始化任务 | `python scripts/init_project.py --keep-reference` |
| 开新题目（清空 output） | `python scripts/init_project.py --force` |
| 离线审计（Markdown + 已有 DOCX） | `python scripts/audit_project.py` |
| 完整构建（模型→审计→Pandoc→后处理） | `python scripts/build_paper.py` |
| 只转换已有论文源稿 | `python scripts/build_paper.py --skip-model` |
| 重建 Word 模板 | `python scripts/build_reference.py` |
| 生成代码附录图片 | `python scripts/gen_code_images.py --input output/model.py --output output/figures/model_code.png` |
| 打包支撑材料 | `python scripts/package_support.py` |
| 导出计划/审稿提示词（离线可用） | `python scripts/ai_assistant.py plan --print-prompt` |

- **不要手工调用 pandoc**，也不要在项目根目录运行 pandoc（相对图片路径会失效）。`build_paper.py` 是唯一交付路径。
- 交互式命令（`input()`、vim、less、等待 stdin 的 REPL）会让会话挂起，禁止使用；需要长时间运行时用后台 job。

## 阶段与退出条件（摘要）

| 阶段 | 执行方式 | 退出条件 |
|:---|:---|:---|
| 初始化 | `init_project.py` | 依赖与 pandoc 检查通过，`output/` 只有 `.gitignore`/空目录 |
| 题目理解与研究 | `web_search` + `web_fetch`；必要时 subagent | 事实表完成，引用可打开核对 |
| 计划 | plan mode（复杂任务）/ `ai_assistant.py --print-prompt` | 每个小问有模型候选、数据需求、验证方法 |
| 数据审计 | 代码 + 记录 | 字段、单位、缺失、异常、划分方式明确 |
| 建模与求解 | `output/model.py` | 固定随机种子，结果落盘到 `output/tables`、`output/logs` |
| 论文写作 | `output/paper.md` | 图表编号连续、正文引用齐全、数字来自结果文件 |
| 审计与构建 | `audit_project.py` / `build_paper.py` | 审计无阻断项，DOCX 可打开，页脚/表格/图片正常 |
| 审稿 | 离线审计 + subagent 审查 + 人工核验 | 阻断项清零，数学与数据风险有结论 |
| 提交 | `package_support.py` | 论文与支撑材料是两个可打开文件，无身份信息 |

## Harness 使用约定

- **计划先行**：跨文件、跨阶段或多个子问题的改动，先用 plan mode 给出计划再动手。
- **分工并行**：独立研究、代码审查、格式排查用 `subagent`；多角色并行用 Agent Teams + `team_task`（写作用域不重叠才可并行）。细则见 `docs/agent-workflow.md`。
- **长任务后台化**：仿真/训练/批量试算用后台 job（`run_in_background`），用 `job_output` 收集，不要空转轮询。
- **上下文纪律**：大输出先落盘再读；已消费的探索用 `compress` 折叠；不要把整篇论文、整份日志塞进对话。
- **记忆**：关键决策、踩坑纠错用 `hindsight_ingest_document` 记录；发现旧结论过期时写 "Correction: …" 文档。
- **技能**：`.dsh/skills`（优先）与 `.agents/skills` 下的技能按需加载（`paper-formatter`、`mathmodel-pipeline`），不要凭记忆复述其中的流程。
- **本文件有预算**：会话指令预算 64 KB，且改动要等下一次注入才生效；新增内容优先写进 `wiki.md`/`docs/`，本文件只留硬规则与入口。

## 文档地图

| 文档 | 内容 |
|:---|:---|
| `README.md` | 快速开始、目录结构、命令表、版本说明 |
| `wiki.md` | 从题目到提交的完整工作流（权威流程） |
| `docs/agent-workflow.md` | DSH 多代理、目标、后台任务、记忆与提示词模板 |
| `templates/PAPER_SPEC.md` | 可执行格式约束与定稿检查清单 |
| `templates/paper_skeleton.md` | 论文 Markdown 骨架 |

## 提交前自检

```powershell
python scripts/audit_project.py
python scripts/build_paper.py
python scripts/package_support.py
```

- [ ] 审计报告无阻断项，`output/audit_report.json` 已生成
- [ ] 论文数字来自结果文件，图表编号连续且被正文引用
- [ ] 参考文献全部可核实并与正文对应
- [ ] 论文无目录、身份信息、聊天记录或"本题答案"类措辞
- [ ] `git status` 中没有 `output/`、`.env`、`AGENTS.local.md`
