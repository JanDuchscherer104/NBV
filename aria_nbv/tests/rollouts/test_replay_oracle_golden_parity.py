"""Frozen functional parity for replay, oracle labels, and stored Q_H rows."""

# ruff: noqa: S101

from __future__ import annotations

import subprocess
import sys
from pathlib import Path


def test_replay_oracle_cpu_golden_parity() -> None:
    root = Path(__file__).resolve().parents[3]
    subprocess.run(
        [sys.executable, str(root / "scripts" / "check_replay_oracle_golden.py")],
        cwd=root / "aria_nbv",
        check=True,
    )
