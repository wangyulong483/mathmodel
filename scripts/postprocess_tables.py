# -*- coding: utf-8 -*-
"""Legacy wrapper for old table post-processing entry point."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path


if __name__ == "__main__":
    print("[INFO] postprocess_tables.py 已合并到 postprocess_appendix.py")
    script = Path(__file__).with_name("postprocess_appendix.py")
    raise SystemExit(subprocess.run([sys.executable, str(script), *sys.argv[1:]]).returncode)
