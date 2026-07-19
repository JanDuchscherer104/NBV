#!/usr/bin/env python3
"""Check ARIA-NBV's Graphify corpus and tracked integration contracts."""

from __future__ import annotations

import json
from pathlib import Path
import re
import shutil
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
FORBIDDEN_PREFIXES = (
    "docs/_extensions/",
    "docs/_inv/",
    "graphify-out/",
)


def _graphify_python() -> Path:
    launcher = shutil.which("graphify")
    if launcher is None:
        raise RuntimeError("graphify is required; install or upgrade graphifyy")
    first_line = (
        Path(launcher).read_text(encoding="utf-8", errors="ignore").splitlines()[0]
    )
    if not first_line.startswith("#!"):
        raise RuntimeError(f"cannot resolve Graphify interpreter from {launcher}")
    return Path(first_line[2:])


def _detect() -> dict[str, object]:
    code = (
        "import json; from pathlib import Path; from graphify.detect import detect; "
        "print(json.dumps(detect(Path('.'))))"
    )
    result = subprocess.run(
        [_graphify_python(), "-c", code],
        cwd=ROOT,
        check=True,
        text=True,
        capture_output=True,
    )
    return json.loads(result.stdout)


def main() -> int:
    version_text = subprocess.check_output(["graphify", "--version"], text=True).strip()
    match = re.search(r"(\d+)\.(\d+)\.(\d+)", version_text)
    if match is None or tuple(map(int, match.groups())) < (0, 9, 19):
        print(
            f"Graphify 0.9.19 or newer is required; found {version_text}",
            file=sys.stderr,
        )
        return 1

    detected = _detect()
    files = detected["files"]
    relative: list[str] = []
    for category in ("code", "document", "paper", "image", "video"):
        for raw_path in files.get(category, []):
            relative.append(Path(raw_path).resolve().relative_to(ROOT).as_posix())

    forbidden = [
        path
        for path in relative
        if path.startswith(FORBIDDEN_PREFIXES) or "/_files/" in path
    ]
    if forbidden:
        print(
            "forbidden Graphify sources detected:",
            *forbidden,
            sep="\n- ",
            file=sys.stderr,
        )
        return 1

    required = {
        "package code": any(path.startswith("aria_nbv/aria_nbv/") for path in relative),
        "Quarto or thesis docs": any(
            path.startswith("docs/") and path.endswith((".qmd", ".typ"))
            for path in relative
        ),
        "literature papers": bool(files.get("paper")),
        "diagrams": any(
            path.startswith("docs/") and path.endswith(".svg") for path in relative
        ),
        "agent routing context": any(
            path.startswith(".agents/references/") for path in relative
        ),
    }
    missing = [name for name, present in required.items() if not present]
    if missing:
        print(
            "missing Graphify source families:", *missing, sep="\n- ", file=sys.stderr
        )
        return 1

    hook = (ROOT / "scripts/git_hooks/post-commit").read_text(encoding="utf-8")
    if "exec scripts/kg/auto_refresh.sh" in hook or "/home/" in hook:
        print(
            "post-commit contains terminal dispatch or a host-specific path",
            file=sys.stderr,
        )
        return 1
    if "scripts/graphify_refresh.py" not in hook:
        print(
            "post-commit does not dispatch the Graphify refresh module", file=sys.stderr
        )
        return 1
    if "nohup" in hook or "python3 scripts/graphify_refresh.py" in hook:
        print("post-commit uses a non-portable Graphify launcher", file=sys.stderr)
        return 1
    makefile = (ROOT / "Makefile").read_text(encoding="utf-8")
    if "git rev-parse --git-path hooks" not in makefile:
        print(
            "hook installation does not resolve Git's effective hooks path",
            file=sys.stderr,
        )
        return 1

    print(
        f"Graphify integration OK: {detected['total_files']} policy-conformant sources"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
