#!/usr/bin/env python3
"""Run Graphify's public merge driver and canonicalize stable array ordering."""

from __future__ import annotations

import json
from pathlib import Path
import shutil
import subprocess
import sys


def main() -> int:
    if len(sys.argv) != 4:
        print("usage: graphify_merge_driver.py BASE CURRENT OTHER", file=sys.stderr)
        return 2
    executable = shutil.which("graphify")
    if executable is None:
        print("graphify merge driver requires pinned graphifyy", file=sys.stderr)
        return 1
    result = subprocess.run([executable, "merge-driver", *sys.argv[1:]], check=False)
    if result.returncode:
        return result.returncode
    current = Path(sys.argv[2])
    try:
        graph = json.loads(current.read_text(encoding="utf-8"))
        graph["nodes"] = sorted(graph.get("nodes", []), key=lambda item: item["id"])
        graph["edges"] = sorted(graph.get("edges", []), key=lambda item: item["id"])
        current.write_text(
            json.dumps(graph, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n",
            encoding="utf-8",
        )
    except (OSError, ValueError, KeyError) as exc:
        print(f"merged Graphify output is invalid: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
