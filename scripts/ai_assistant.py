# -*- coding: utf-8 -*-
"""Structured AI assistant for problem planning and paper review.

The client uses the standard library so the project can still run offline.
It supports OpenAI Responses API and OpenAI-compatible Chat Completions APIs,
including DeepSeek-compatible endpoints.

Use --print-prompt to export the complete prompt and JSON Schema to
output/ai_prompt_<command>.md without an API key, so a harness Agent (or a
human) can produce the structured JSON offline.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

from project_utils import (
    configured_path,
    json_dump,
    load_config,
    print_header,
    project_path,
    read_text,
)


PLAN_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "properties": {
        "problem_summary": {"type": "string"},
        "subproblems": {
            "type": "array",
            "items": {
                "type": "object",
                "additionalProperties": False,
                "properties": {
                    "id": {"type": "string"},
                    "goal": {"type": "string"},
                    "data_needed": {"type": "array", "items": {"type": "string"}},
                    "candidate_models": {"type": "array", "items": {"type": "string"}},
                    "validation": {"type": "array", "items": {"type": "string"}},
                    "risks": {"type": "array", "items": {"type": "string"}},
                },
                "required": ["id", "goal", "data_needed", "candidate_models", "validation", "risks"],
            },
        },
        "data_inventory": {"type": "array", "items": {"type": "string"}},
        "paper_outline": {"type": "array", "items": {"type": "string"}},
        "research_tasks": {"type": "array", "items": {"type": "string"}},
        "must_not_claim": {"type": "array", "items": {"type": "string"}},
    },
    "required": [
        "problem_summary",
        "subproblems",
        "data_inventory",
        "paper_outline",
        "research_tasks",
        "must_not_claim",
    ],
}


REVIEW_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "properties": {
        "overall": {"type": "string"},
        "blocking_issues": {"type": "array", "items": {"type": "string"}},
        "mathematical_risks": {"type": "array", "items": {"type": "string"}},
        "data_consistency_checks": {"type": "array", "items": {"type": "string"}},
        "writing_issues": {"type": "array", "items": {"type": "string"}},
        "formatting_issues": {"type": "array", "items": {"type": "string"}},
        "next_actions": {"type": "array", "items": {"type": "string"}},
    },
    "required": [
        "overall",
        "blocking_issues",
        "mathematical_risks",
        "data_consistency_checks",
        "writing_issues",
        "formatting_issues",
        "next_actions",
    ],
}


def api_url(base_url: str, style: str) -> str:
    base = base_url.rstrip("/")
    if base.endswith("/v1"):
        return f"{base}/{ 'responses' if style == 'responses' else 'chat/completions' }"
    return f"{base}/v1/{ 'responses' if style == 'responses' else 'chat/completions' }"


def extract_text(payload: dict[str, Any], style: str) -> str:
    if style == "responses":
        if isinstance(payload.get("output_text"), str):
            return payload["output_text"]
        chunks: list[str] = []
        for item in payload.get("output", []):
            for content in item.get("content", []):
                if isinstance(content, dict) and isinstance(content.get("text"), str):
                    chunks.append(content["text"])
        return "".join(chunks)
    choices = payload.get("choices", [])
    if choices:
        message = choices[0].get("message", {})
        content = message.get("content", "")
        if isinstance(content, list):
            return "".join(part.get("text", "") for part in content if isinstance(part, dict))
        return str(content)
    return ""


def call_model(prompt: str, schema: dict[str, Any], config: dict[str, Any]) -> dict[str, Any]:
    api_key = os.getenv("MM_AI_API_KEY", "")
    if not api_key:
        raise RuntimeError(
            "未设置 MM_AI_API_KEY。离线导出提示词请加 --print-prompt（写入 output/ai_prompt_<command>.md），"
            "联网规划时再设置 API Key。"
        )

    ai = config.get("ai", {})
    style = str(ai.get("api_style", "chat")).lower()
    url = api_url(str(ai.get("base_url", "")), style)
    model = str(ai.get("model", ""))
    temperature = ai.get("temperature", 0.2)

    if style == "responses":
        body = {
            "model": model,
            "input": prompt,
            "temperature": temperature,
            "text": {
                "format": {
                    "type": "json_schema",
                    "name": "mathmodel_result",
                    "strict": True,
                    "schema": schema,
                }
            },
        }
    else:
        body = {
            "model": model,
            "temperature": temperature,
            "messages": [
                {
                    "role": "system",
                    "content": "你是严谨的数学建模竞赛助手。只输出符合给定 JSON Schema 的 JSON，不得编造数据、文献、实验结果或已经运行过的代码。",
                },
                {"role": "user", "content": prompt},
            ],
            "response_format": {
                "type": "json_schema",
                "json_schema": {
                    "name": "mathmodel_result",
                    "strict": True,
                    "schema": schema,
                },
            },
        }

    request = urllib.request.Request(
        url,
        data=json.dumps(body, ensure_ascii=False).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
            "User-Agent": "mathmodel-toolchain/4.1",
        },
        method="POST",
    )
    timeout = int(ai.get("timeout_seconds", 120))
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"AI API 返回 HTTP {exc.code}: {detail[:1000]}") from exc
    except urllib.error.URLError as exc:
        raise RuntimeError(f"AI API 网络请求失败：{exc.reason}") from exc

    content = extract_text(payload, style)
    if not content:
        raise RuntimeError("AI API 返回中没有可解析的文本。")
    try:
        return json.loads(content)
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"AI 返回不是合法 JSON：{content[:500]}") from exc


def build_plan_prompt(question: str, todo: str, paper_spec: str) -> str:
    return f"""请为全国大学生数学建模竞赛建立一个可执行、可复现的研究计划。

硬性规则：
1. 只根据输入中已有的信息作判断，不得补造数据、参数、实验结果或参考文献。
2. 为每个子问题给出候选模型、所需数据、验证方法和风险。
3. 候选模型可以有多个，但必须说明选择依据和可证伪的验证方式。
4. 计划必须区分“已知事实”“待计算结果”“需要联网核实的资料”。
5. 论文结构服务于解题，不得为了凑章节而声称没有实现的方法。

题目：
---BEGIN QUESTION---
{question}
---END QUESTION---

队伍/Agent要求：
---BEGIN TODO---
{todo}
---END TODO---

格式与提交约束：
---BEGIN PAPER SPEC---
{paper_spec}
---END PAPER SPEC---

请严格按 JSON Schema 输出。"""


def build_review_prompt(question: str, paper: str, audit: str) -> str:
    return f"""请审查一篇数学建模竞赛论文草稿。审查重点是可复现性、数学诚实性、数据一致性和国赛提交风险。

禁止事项：
- 不得把没有运行过的模型当成已验证结果。
- 不得把论文中出现的数字默认为正确；应把需要复现的数字列为检查项。
- 不得凭空判断参考文献真实存在；把需要用 web_fetch 打开原文核实的内容列出（搜索摘要不算证据）。

题目：
---BEGIN QUESTION---
{question}
---END QUESTION---

论文草稿：
---BEGIN PAPER---
{paper}
---END PAPER---

离线审计结果：
---BEGIN AUDIT---
{audit}
---END AUDIT---

请严格按 JSON Schema 输出。"""


def prompt_export_path(command: str, config: dict[str, Any]) -> Path:
    output_dir = configured_path(config, "output_dir", "output")
    return output_dir / f"ai_prompt_{command}.md"


def render_prompt_export(
    command: str,
    prompt: str,
    schema: dict[str, Any],
    config: dict[str, Any],
) -> str:
    ai = config.get("ai", {})
    task = "解题计划（plan）" if command == "plan" else "论文审稿（review）"
    lines = [
        f"# MathModel AI 提示词：{task}",
        "",
        "> 离线导出的完整提示词与 JSON Schema，不调用 API、不需要 API Key。",
        "",
        "## 元信息",
        "",
        f"- 命令：`{command}`",
        f"- provider：`{ai.get('provider', '')}`",
        f"- api_style：`{ai.get('api_style', '')}`",
        f"- model：`{ai.get('model', '')}`",
        f"- base_url：`{ai.get('base_url', '')}`",
        "- 结果默认路径：`output/ai_plan.json`（plan）；review 结果请另存为 `output/ai_review.json` 作为审稿记录",
        "",
        "## 下一步",
        "",
        "1. 交给 DeepSeek Harness Agent：把下面「提示词」与「JSON Schema」一起发给它，要求只输出符合 Schema 的 JSON。",
        "2. 人工填写：按 Schema 写好 JSON，plan 保存为 `output/ai_plan.json`。",
        f"3. 直接调用 API：设置 `MM_AI_API_KEY` 后运行 `python scripts/ai_assistant.py {command} --force`。",
        "",
        "## 提示词",
        "",
        "~~~~text",
        prompt.rstrip(),
        "~~~~",
        "",
        "## JSON Schema",
        "",
        "```json",
        json.dumps(schema, ensure_ascii=False, indent=2),
        "```",
        "",
    ]
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description="生成数学建模结构化 AI 计划或论文审查")
    parser.add_argument("command", choices=["plan", "review"])
    parser.add_argument("--force", action="store_true", help="覆盖已有输出")
    parser.add_argument(
        "--print-prompt",
        action="store_true",
        help="只导出提示词与 JSON Schema 到 output/ai_prompt_<command>.md（离线可用，不调用 API）",
    )
    args = parser.parse_args()

    config = load_config()
    output_path = configured_path(config, "plan_json", "output/ai_plan.json")
    if not args.print_prompt and output_path.exists() and not args.force:
        print(f"已存在：{output_path}，如需覆盖请加 --force")
        return 2

    question = read_text(project_path("input/question.md"))
    todo = read_text(project_path("input/todo.md"))
    paper_spec = read_text(project_path("templates/PAPER_SPEC.md"))
    if args.command == "plan":
        if not question.strip():
            print("input/question.md 为空，无法生成计划。", file=sys.stderr)
            return 1
        prompt = build_plan_prompt(question, todo, paper_spec)
    else:
        paper = read_text(configured_path(config, "paper_markdown", "output/paper.md"))
        audit = read_text(configured_path(config, "audit_markdown", "output/audit_report.md"))
        if not paper.strip():
            print("output/paper.md 为空，无法审查。", file=sys.stderr)
            return 1
        prompt = build_review_prompt(question, paper, audit)

    schema = PLAN_SCHEMA if args.command == "plan" else REVIEW_SCHEMA

    if args.print_prompt:
        export_path = prompt_export_path(args.command, config)
        export_path.parent.mkdir(parents=True, exist_ok=True)
        export_path.write_text(
            render_prompt_export(args.command, prompt, schema, config),
            encoding="utf-8",
        )
        print_header(f"AI {args.command} 提示词已导出")
        print(f"provider={config.get('ai', {}).get('provider')}")
        print(f"model={config.get('ai', {}).get('model')}")
        print(f"提示词：{export_path}")
        target_hint = "output/ai_plan.json" if args.command == "plan" else "output/ai_review.json"
        print(f"下一步：交给 harness Agent 执行，或按 JSON Schema 人工填写后保存为 {target_hint}。")
        return 0

    try:
        result = call_model(prompt, schema, config)
    except RuntimeError as exc:
        print(f"[ERROR] {exc}", file=sys.stderr)
        return 1

    json_dump(output_path, result)
    print_header(f"AI {args.command} 完成")
    print(f"provider={config.get('ai', {}).get('provider')}")
    print(f"model={config.get('ai', {}).get('model')}")
    print(f"输出：{output_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
