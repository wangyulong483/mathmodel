# -*- coding: utf-8 -*-
"""Create a clean ZIP archive of the supporting materials."""

from __future__ import annotations

import argparse
import zipfile
from pathlib import Path

from project_utils import configured_path, load_config, project_path


def main() -> int:
    parser = argparse.ArgumentParser(description="打包数学建模支撑材料")
    parser.add_argument("--output", default="output/support_materials.zip")
    args = parser.parse_args()

    config = load_config()
    root = project_path(".")
    output_dir = configured_path(config, "output_dir", "output")
    archive = (root / args.output).resolve()
    archive.parent.mkdir(parents=True, exist_ok=True)

    candidates = [
        output_dir / "model.py",
        output_dir / "figures",
        output_dir / "tables",
        output_dir / "audit_report.json",
        output_dir / "audit_report.md",
        root / "input",
    ]
    files: list[tuple[Path, str]] = []
    for candidate in candidates:
        if candidate.is_file():
            files.append((candidate, candidate.relative_to(root).as_posix()))
        elif candidate.is_dir():
            for path in candidate.rglob("*"):
                if path.is_file() and path.name != "support_materials.zip":
                    files.append((path, path.relative_to(root).as_posix()))

    if not files:
        print("没有找到可打包的支撑材料。")
        return 1

    with zipfile.ZipFile(archive, "w", compression=zipfile.ZIP_DEFLATED) as bundle:
        for path, arcname in files:
            bundle.write(path, arcname)

    print(f"[DONE] {archive}")
    print(f"[INFO] 文件数：{len(files)}，大小：{archive.stat().st_size / 1024 / 1024:.2f} MB")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
