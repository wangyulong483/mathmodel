# -*- coding: utf-8 -*-
"""Legacy wrapper. Use build_reference.py for current reference.docx styles."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path


if __name__ == "__main__":
    print("[INFO] fix_reference.py 已合并到 build_reference.py")
    script = Path(__file__).with_name("build_reference.py")
    raise SystemExit(subprocess.run([sys.executable, str(script)]).returncode)
