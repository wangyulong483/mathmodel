# -*- coding: utf-8 -*-
"""Initialize a clean task workspace without touching reusable templates."""

from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
import time
from pathlib import Path

from project_utils import PROJECT_ROOT, configured_path, load_config, print_header


def check_dependencies() -> bool:
    packages = {
        "docx": "python-docx",
        "PIL": "Pillow",
        "numpy": "numpy",
        "scipy": "scipy",
        "pandas": "pandas",
        "matplotlib": "matplotlib",
        "sklearn": "scikit-learn",
        "lxml": "lxml",
    }
    ok = True
    for import_name, package_name in packages.items():
        try:
            __import__(import_name)
            print(f"  [OK] {package_name}")
        except ImportError:
            ok = False
            print(f"  [WARN] {package_name} 未安装")
    try:
        result = subprocess.run(["pandoc", "--version"], capture_output=True, text=True, check=False)
        if result.returncode == 0:
            print(f"  [OK] {result.stdout.splitlines()[0]}")
        else:
            ok = False
            print("  [WARN] pandoc 不可用")
    except FileNotFoundError:
        ok = False
        print("  [WARN] pandoc 未找到，请安装 Pandoc 3.x")
    return ok


def check_workspace_contract() -> None:
    """检查 DSH 协作契约与技能目录；缺失只告警，不阻断初始化。"""
    agents_md = PROJECT_ROOT / "AGENTS.md"
    if agents_md.is_file():
        print("  [OK] AGENTS.md")
    else:
        print("  [WARN] 缺少 AGENTS.md：DSH 会话不会自动加载协作契约")
    # AGENTS.md：.dsh/skills 优先，.agents/skills 兼容
    found = []
    for skill_dir in (PROJECT_ROOT / ".dsh" / "skills", PROJECT_ROOT / ".agents" / "skills"):
        if not skill_dir.is_dir():
            continue
        names = [item.name for item in sorted(skill_dir.iterdir())]
        if names:
            found.append((skill_dir, names))
    if found:
        for skill_dir, names in found:
            relative = skill_dir.relative_to(PROJECT_ROOT).as_posix()
            print(f"  [OK] {relative}/（{'、'.join(names)}）")
    else:
        print("  [WARN] 缺少 .dsh/skills/ 与 .agents/skills/：技能无法按需加载")


def main() -> int:
    parser = argparse.ArgumentParser(description="初始化数学建模任务目录")
    parser.add_argument("--force", "-f", action="store_true", help="跳过确认并清空 output")
    parser.add_argument("--keep-output", action="store_true", help="保留 output 中已有生成物")
    parser.add_argument("--keep-reference", action="store_true", help="保留现有 reference.docx")
    parser.add_argument("--skip-deps", action="store_true", help="跳过依赖检查")
    parser.add_argument("--no-build", action="store_true", help="不构建 reference.docx")
    args = parser.parse_args()

    config = load_config()
    output = configured_path(config, "output_dir", "output")
    figures = output / "figures"
    tables = output / "tables"
    reference = PROJECT_ROOT / "templates" / "reference.docx"

    print_header("MathModel 任务初始化")
    if not args.skip_deps:
        print("[1/5] 检查依赖")
        check_dependencies()
    else:
        print("[1/5] 跳过依赖检查")

    print("[2/5] 检查工作区契约")
    check_workspace_contract()

    print("[3/5] 准备 output")
    output.mkdir(parents=True, exist_ok=True)
    generated = [item for item in output.iterdir() if item.name != ".gitignore"]
    if generated and not args.keep_output:
        should_clear = args.force
        if not should_clear:
            should_clear = input("output/ 中已有生成物，清空并重建？[y/N] ").strip().lower() == "y"
        if should_clear:
            for item in generated:
                if item.is_dir():
                    shutil.rmtree(item)
                else:
                    item.unlink()
            print("  已清空生成物")
        else:
            print("  保留现有生成物")
    figures.mkdir(exist_ok=True)
    tables.mkdir(exist_ok=True)
    gitignore = output / ".gitignore"
    if not gitignore.exists():
        gitignore.write_text("# Generated task outputs\n*\n!.gitignore\n", encoding="utf-8")

    print("[4/5] 准备 reference.docx")
    build_script = Path(__file__).with_name("build_reference.py")
    if args.keep_reference and reference.exists():
        print(f"  保留：{reference}")
    elif args.no_build:
        print("  跳过模板构建")
    elif not reference.exists() or time.time() - reference.stat().st_mtime > 7 * 24 * 3600:
        subprocess.run([sys.executable, str(build_script)], cwd=str(PROJECT_ROOT), check=True)
    else:
        print(f"  模板较新，保留：{reference}")

    print("[5/5] 初始化完成")
    print(f"  input/: {len(list((PROJECT_ROOT / 'input').iterdir()))} 个文件")
    print(f"  output/: {output}")
    print("  下一步：阅读 `AGENTS.md`（协作契约）与 `wiki.md`（完整工作流）")
    print("  生成计划提示词：`python scripts/ai_assistant.py plan --print-prompt`")
    print("  审计与构建：`python scripts/audit_project.py` → `python scripts/build_paper.py`")
    return 0


if __name__ == "__main__":
    sys.exit(main())
