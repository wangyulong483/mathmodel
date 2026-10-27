---
name: mathmodel-pipeline
description: Run the CUMCM modeling pipeline in this repo end to end. Use when initializing a modeling task, auditing or building the paper DOCX, packaging support materials, or checking stage gates from initialization through submission.
---

# MathModel Pipeline

本仓库是"可复现建模 + 论文生成"工具链，入口全部在 `scripts/`。加载本技能后按下面的 gate 推进；完整解释见项目根 `wiki.md`，硬规则见 `AGENTS.md`。

## 唯一合法入口

```powershell
python scripts/init_project.py --keep-reference   # 初始化（--force 换题）
python scripts/audit_project.py                   # 离线审计
python scripts/build_paper.py                     # 模型 -> 审计 -> pandoc -> 后处理
python scripts/build_paper.py --skip-model        # 只重转论文
python scripts/build_reference.py --force         # 重建 Word 模板
python scripts/gen_code_images.py --input output/model.py --output output/figures/model_code.png
python scripts/package_support.py                 # 打包支撑材料
python scripts/ai_assistant.py plan  --print-prompt
python scripts/ai_assistant.py review --print-prompt
```

禁止：手工 pandoc（尤其在项目根）、手工编辑 `templates/reference.docx`、在 `input/` 写代码、交互式命令。

## 阶段 gate

| 阶段 | 通过条件 |
|:---|:---|
| 初始化 | pandoc 3.x + 依赖齐全；`output/` 只剩 `.gitignore`/空目录 |
| 理解与研究 | 事实表完成；每条外部事实有 `web_fetch` 核验过的 URL |
| 计划 | 每小问：目标量、2-3 个候选模型、数据需求、验证指标 |
| 数据审计 | `output/logs/data_profile.json` 覆盖字段/缺失/异常/量纲/划分 |
| 建模 | 种子固定；数字写入 `output/tables/*.json`；日志写入 `output/logs/` |
| 论文 | `output/paper.md` 含摘要/1-6 章/参考文献/附录；图表连续且被引用 |
| 审计 | `audit_project.py` 无 error |
| 构建 | `output/paper.docx` 可打开；页码/A4/三线表/公式/图正常 |
| 审稿 | 独立审稿阻断项清零；数字与引用逐条核验 |
| 提交 | `output/support_materials.zip` 可解压；无身份信息 |

## 数字与引用纪律

- 论文任何数字必须来自 `output/tables/`、`output/logs/` 或代码常量；**禁止手填、禁止从对话里抄**。
- 外部事实必须 `web_fetch` 打开原文核对标题/作者/年份/数值；搜索摘要和模型记忆不算证据。
- 参考文献只列核实过的条目；查不到就删或标"待查"。

## 常见故障

| 症状 | 处理 |
|:---|:---|
| 审计 error `missing-heading` | 按 `templates/paper_skeleton.md` 补齐章节 |
| `missing-image` | 图片相对 `output/paper.md` 的路径写错 |
| DOCX 无页码/非 A4 | `build_reference.py --force` 后重建 |
| 构建中止"审计未通过" | 先单独跑 `audit_project.py` 定位 code |
| AI 接口失败 | 用 `--print-prompt` 离线完成 |

## 交接给 harness

- 长仿真/网格搜索：后台 job 提交，`job_output` 收集。
- 并行研究/审稿：`subagent`；多工序写文件：`team_task` 登记 `write_scopes`。
- 跨多轮的建模目标：`create_goal`，完成后标记 complete。
