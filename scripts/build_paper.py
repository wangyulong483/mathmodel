# -*- coding: utf-8 -*-
"""Reproducible build pipeline: model -> audit -> Pandoc -> DOCX audit."""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

from project_utils import (
    command_exists,
    configured_path,
    load_config,
    print_header,
    project_path,
)


def run_python(script: Path) -> None:
    subprocess.run([sys.executable, str(script)], cwd=str(project_path(".")), check=True)


def main() -> int:
    parser = argparse.ArgumentParser(description="构建数学建模论文 DOCX")
    parser.add_argument("--skip-model", action="store_true", help="不运行 output/model.py")
    parser.add_argument("--skip-audit", action="store_true", help="不运行离线审计")
    parser.add_argument("--keep-docx", action="store_true", help="保留已有 DOCX，仍执行审计")
    args = parser.parse_args()

    config = load_config()
    output_dir = configured_path(config, "output_dir", "output")
    paper = configured_path(config, "paper_markdown", "output/paper.md")
    docx = configured_path(config, "paper_docx", "output/paper.docx")
    model = configured_path(config, "model_script", "output/model.py")
    reference = project_path("templates/reference.docx")

    print_header("MathModel 可复现构建")
    if not paper.exists():
        print(f"[ERROR] 找不到论文 Markdown：{paper}")
        return 1

    if not args.skip_model and model.exists():
        print(f"[1/5] 运行模型：{model}")
        run_python(model)
    else:
        print("[1/5] 跳过模型运行")

    if not args.skip_audit:
        print("[2/5] 执行 Markdown 离线审计")
        audit_script = Path(__file__).with_name("audit_project.py")
        result = subprocess.run(
            [sys.executable, str(audit_script)],
            cwd=str(project_path(".")),
            check=False,
        )
        if result.returncode != 0:
            print("[ERROR] Markdown 审计存在阻断问题，未继续转换 DOCX。")
            return result.returncode
    else:
        print("[2/5] 跳过 Markdown 审计")

    if not args.keep_docx:
        if not command_exists("pandoc"):
            print("[ERROR] 未找到 pandoc，请先安装 Pandoc 3.x。")
            return 1
        if not reference.exists():
            print(f"[ERROR] 找不到模板：{reference}")
            return 1
        print("[3/5] Pandoc 转换 Markdown -> DOCX")
        subprocess.run(
            [
                "pandoc",
                paper.name,
                "-o",
                docx.name,
                "--reference-doc=../templates/reference.docx",
                "--mathml",
                "--syntax-highlighting=pygments",
            ],
            cwd=str(output_dir),
            check=True,
        )
    else:
        print("[3/5] 保留已有 DOCX")

    print("[4/5] DOCX 后处理")
    postprocess = Path(__file__).with_name("postprocess_appendix.py")
    subprocess.run([sys.executable, str(postprocess), "--docx", str(docx)], check=True)
    if not args.skip_audit:
        print("[5/5] 复核 Markdown 与 DOCX")
        audit_script = Path(__file__).with_name("audit_project.py")
        final_audit = subprocess.run(
            [sys.executable, str(audit_script)],
            cwd=str(project_path(".")),
            check=False,
        )
        if final_audit.returncode != 0:
            print("[ERROR] 最终审计存在阻断问题。")
            return final_audit.returncode
    else:
        print("[5/5] 跳过最终审计")
    print(f"[DONE] {docx}")
    print(f"[INFO] 离线报告：{configured_path(config, 'audit_markdown', 'output/audit_report.md')}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
