#!/usr/bin/env python3
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

INCLUDE_RE = re.compile(r'^\s*#include\s+"([^"]+)"')
HEADING_RE = re.compile(r"^\s*(=+)\s+(.+)$")


def extract_includes(path: Path) -> list[str]:
    includes: list[str] = []
    try:
        text = path.read_text(encoding="utf-8")
    except OSError:
        return includes
    for line in text.splitlines():
        match = INCLUDE_RE.match(line)
        if match:
            includes.append(match.group(1))
    return includes


def _resolve_include(source: Path, root: Path, inc: str) -> Path | None:
    for candidate in ((source.parent / inc).resolve(), (root / inc).resolve()):
        if candidate.exists():
            return candidate
    return None


def _repo_relative(path: Path, repo_root: Path) -> str:
    return path.resolve().relative_to(repo_root.resolve()).as_posix()


def _walk_outline(
    path: Path, typst_root: Path, repo_root: Path, stack: list[Path]
) -> None:
    if path in stack:
        print(f"warning: include cycle detected: {path}", file=sys.stderr)
        return
    stack.append(path)
    try:
        text = path.read_text(encoding="utf-8")
    except OSError:
        print(f"warning: failed to read: {path}", file=sys.stderr)
        stack.pop()
        return

    print(f"# {_repo_relative(path, repo_root)}")
    for line in text.splitlines():
        include_match = INCLUDE_RE.match(line)
        if include_match:
            resolved = _resolve_include(path, typst_root, include_match.group(1))
            if resolved is None:
                print(
                    f"warning: include not found: {include_match.group(1)} (from {path})",
                    file=sys.stderr,
                )
            else:
                _walk_outline(resolved, typst_root, repo_root, stack)
            continue
        heading_match = HEADING_RE.match(line)
        if not heading_match or line.lstrip().startswith("//"):
            continue
        level = len(heading_match.group(1))
        title = heading_match.group(2).strip()
        indent = "  " * (level - 1)
        print(f"{indent}- {title}")
    print()
    stack.pop()


def _print_includes(path: Path, typst_root: Path, repo_root: Path) -> None:
    includes = extract_includes(path)
    if not includes:
        return
    print(f"# {_repo_relative(path, repo_root)}")
    for inc in includes:
        resolved = _resolve_include(path, typst_root, inc)
        if resolved is None:
            print(f"- {inc} -> (missing)")
        else:
            print(f"- {inc} -> {_repo_relative(resolved, repo_root)}")
    print()


def main() -> int:
    script_dir = Path(__file__).resolve().parent
    repo_root = (script_dir / "../../../../").resolve()
    default_typst_root = (repo_root / "docs" / "typst").resolve()
    default_thesis = default_typst_root / "thesis" / "main.typ"
    default_seminar = default_typst_root / "seminar_paper" / "main.typ"
    default_slides = default_typst_root / "seminar_slides"

    parser = argparse.ArgumentParser(
        description="Outline the active thesis by default; opt into historical seminar or slides when needed."
    )
    parser.add_argument(
        "--root", default=str(default_typst_root), help="Typst root directory"
    )
    parser.add_argument(
        "--thesis",
        nargs="?",
        const=str(default_thesis),
        default=None,
        help="Active thesis entrypoint. Defaults to docs/typst/thesis/main.typ.",
    )
    parser.add_argument(
        "--seminar",
        nargs="?",
        const=str(default_seminar),
        default=None,
        help="Historical seminar entrypoint. Defaults to docs/typst/seminar_paper/main.typ.",
    )
    parser.add_argument(
        "--paper",
        nargs="?",
        const=str(default_seminar),
        default=None,
        help="Compatibility alias for --seminar.",
    )
    parser.add_argument(
        "--with-slides",
        action="store_true",
        help="Include slide entrypoints in addition to the selected entrypoint.",
    )
    parser.add_argument(
        "--slides-root",
        default=str(default_slides),
        help="Slides directory used when --with-slides is set.",
    )
    parser.add_argument(
        "--mode",
        choices=["outline", "includes"],
        default="outline",
        help="outline: recursive include outline with headings; includes: include edges only",
    )
    args = parser.parse_args()

    typst_root = Path(args.root).resolve()
    slides_root = Path(args.slides_root).resolve()

    targets: list[Path] = []
    selected = [value for value in (args.thesis, args.seminar, args.paper) if value]
    if not selected:
        selected = [str(default_thesis)]
    for value in selected:
        target = Path(value).resolve()
        if target.exists() and target not in targets:
            targets.append(target)
    if args.with_slides and slides_root.exists():
        targets.extend(sorted(slides_root.glob("*.typ")))

    if args.mode == "includes":
        for target in targets:
            _print_includes(target, typst_root, repo_root)
        return 0

    for target in targets:
        _walk_outline(target, typst_root, repo_root, [])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
