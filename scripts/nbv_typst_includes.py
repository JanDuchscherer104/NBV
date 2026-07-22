#!/usr/bin/env python3
"""Run the retained Typst outline/include inspector from its skill owner."""

from __future__ import annotations

import runpy
from pathlib import Path

OWNER = (
    Path(__file__).resolve().parents[1]
    / ".agents/skills/aria-nbv-context/scripts/nbv_typst_includes.py"
)
runpy.run_path(str(OWNER), run_name="__main__")
