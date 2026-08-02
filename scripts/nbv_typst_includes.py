#!/usr/bin/env python3
"""Run the aria-nbv-context Typst include helper from the repository root."""

import runpy
from pathlib import Path


SKILL_SCRIPT = (
    Path(__file__).resolve().parents[1]
    / ".agents"
    / "skills"
    / "aria-nbv-context"
    / "scripts"
    / "nbv_typst_includes.py"
)


def main() -> None:
    """Execute the skill-owned helper with the original command-line arguments."""
    runpy.run_path(str(SKILL_SCRIPT), run_name="__main__")


if __name__ == "__main__":
    main()
