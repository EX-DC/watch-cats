#!/usr/bin/env python3
"""Fail if VERSION, _version.py and the top CHANGELOG entry disagree."""
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def versions():
    file_v = (ROOT / "VERSION").read_text(encoding="utf-8").strip()
    py = (ROOT / "src/watchcats/_version.py").read_text(encoding="utf-8")
    py_v = re.search(r'__version__\s*=\s*"([^"]+)"', py).group(1)
    log = (ROOT / "CHANGELOG.md").read_text(encoding="utf-8")
    m = re.search(r"^## \[(\d+\.\d+\.\d+)\]", log, re.M)
    return file_v, py_v, m.group(1) if m else None


if __name__ == "__main__":
    f, p, c = versions()
    print(f"VERSION={f}  _version.py={p}  CHANGELOG={c}")
    sys.exit(0 if f == p == c else 1)
