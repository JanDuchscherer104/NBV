#!/usr/bin/env python3
"""Check ARIA-NBV's Graphify corpus and tracked integration contracts."""

from __future__ import annotations

import json
from pathlib import Path
import re
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
GRAPHIFY_VERSION_FILE = ROOT / ".codex/skills/graphify/.graphify_version"
FORBIDDEN_PREFIXES = (
    "docs/_extensions/",
    "docs/_inv/",
    "graphify-out/",
)
FORBIDDEN_FRAGMENTS = ("_files/",)
ALLOWED_STRUCTURAL_PATHS = ("Makefile",)
ALLOWED_STRUCTURAL_PREFIXES = (
    ".agents/",
    "aria_nbv/",
    "docs/",
)
REQUIRED_SEMANTIC_FAMILIES = {
    "Quarto docs": ("docs/**/*.qmd",),
    "thesis Typst docs": ("docs/typst/thesis/**/*.typ",),
    "literature sources": (
        "docs/literature/*.md",
        "docs/literature/*.qmd",
        "docs/literature/*.jsonl",
    ),
    "diagrams": ("docs/figures/diagrams/**/*.svg",),
    "agent routing context": (".agents/references/*.md",),
}
REQUIRED_SEMANTIC_REINCLUDE_RULES = {
    "Quarto docs": (
        "!docs/",
        "!docs/index.qmd",
        "!docs/contents/",
        "!docs/contents/**",
    ),
    "thesis Typst docs": (
        "!docs/typst/",
        "!docs/typst/thesis/",
        "!docs/typst/thesis/**",
    ),
    "literature sources": (
        "!docs/literature/",
        "!docs/literature/*.md",
        "!docs/literature/*.qmd",
        "!docs/literature/*.jsonl",
    ),
    "diagrams": (
        "!docs/figures/",
        "!docs/figures/diagrams/",
        "!docs/figures/diagrams/**/*.svg",
    ),
    "agent routing context": (
        "!.agents/",
        "!.agents/references/",
        "!.agents/references/*.md",
    ),
}
REQUIRED_GENERATED_IGNORE_RULES = (
    "graphify-out/",
    "graphify-out/**",
    "docs/_build/",
    "docs/_extensions/",
    "docs/_inv/",
    "docs/_generated/",
    "docs/_site/",
    "docs/*_files/",
    "docs/**/*_files/",
)


def _expected_version() -> str:
    try:
        return GRAPHIFY_VERSION_FILE.read_text(encoding="utf-8").strip()
    except OSError as exc:
        raise RuntimeError(f"cannot read {GRAPHIFY_VERSION_FILE}: {exc}") from exc


def _graphify_version() -> str:
    try:
        version_text = subprocess.check_output(
            ["graphify", "--version"], text=True, stderr=subprocess.STDOUT
        ).strip()
    except (OSError, subprocess.CalledProcessError) as exc:
        raise RuntimeError(
            "graphify is required; install the graphifyy version declared in "
            ".codex/skills/graphify/.graphify_version"
        ) from exc
    match = re.search(r"(\d+\.\d+\.\d+)", version_text)
    if match is None:
        raise RuntimeError(f"cannot parse graphify --version output: {version_text}")
    return match.group(1)


def _load_manifest(path: Path) -> dict[str, object]:
    try:
        raw = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise RuntimeError(
            f"Graphify manifest is unavailable at {path}: {exc}"
        ) from exc
    try:
        manifest = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise RuntimeError(
            f"Graphify manifest is malformed JSON at {path}: {exc}"
        ) from exc
    if not isinstance(manifest, dict):
        raise RuntimeError(f"Graphify manifest must be a JSON object at {path}")
    return manifest


def _extract_structural_manifest(out_dir: Path) -> dict[str, object]:
    command = [
        "graphify",
        "extract",
        ".",
        "--code-only",
        "--no-cluster",
        "--out",
        str(out_dir),
    ]
    try:
        subprocess.run(
            command,
            cwd=ROOT,
            check=True,
            text=True,
            capture_output=True,
        )
    except (OSError, subprocess.CalledProcessError) as exc:
        stderr = getattr(exc, "stderr", "") or str(exc)
        raise RuntimeError(
            f"Graphify code-only extraction failed: {stderr.strip()}"
        ) from exc
    return _load_manifest(out_dir / "graphify-out/manifest.json")


def _has_repo_file(patterns: tuple[str, ...]) -> bool:
    for pattern in patterns:
        if any(path.is_file() for path in ROOT.glob(pattern)):
            return True
    return False


def _is_canonical_repo_path(path: str) -> bool:
    parts = path.split("/")
    return (
        path not in {"", ".", ".."}
        and not Path(path).is_absolute()
        and not path.startswith("./")
        and "\\" not in path
        and all(part not in {"", ".", ".."} for part in parts)
    )


def _is_allowed_structural_path(path: str) -> bool:
    return path in ALLOWED_STRUCTURAL_PATHS or path.startswith(
        ALLOWED_STRUCTURAL_PREFIXES
    )


def _validate_structural_manifest(manifest: dict[str, object]) -> int:
    paths = sorted(manifest)
    noncanonical = [path for path in paths if not _is_canonical_repo_path(path)]
    if noncanonical:
        raise RuntimeError(
            "Graphify manifest contains non-canonical repo-relative paths:\n- "
            + "\n- ".join(noncanonical[:10])
        )

    forbidden = [
        path
        for path in paths
        if path.startswith(FORBIDDEN_PREFIXES)
        or any(fragment in path for fragment in FORBIDDEN_FRAGMENTS)
    ]
    if forbidden:
        raise RuntimeError(
            "forbidden Graphify structural sources detected:\n- "
            + "\n- ".join(forbidden[:20])
        )

    outside_allowed = [path for path in paths if not _is_allowed_structural_path(path)]
    if outside_allowed:
        raise RuntimeError(
            "Graphify manifest contains paths outside allowed structural surfaces:\n- "
            + "\n- ".join(outside_allowed[:20])
        )

    missing = [path for path in paths if not (ROOT / path).is_file()]
    if missing:
        raise RuntimeError(
            "Graphify manifest contains nonexistent repo paths:\n- "
            + "\n- ".join(missing[:20])
        )

    package_code = [
        path
        for path in paths
        if path.startswith("aria_nbv/aria_nbv/") and path.endswith(".py")
    ]
    if not package_code:
        raise RuntimeError(
            "missing required Graphify structural source: aria_nbv/aria_nbv/*.py"
        )

    return len(paths)


def _validate_semantic_policy() -> None:
    policy_path = ROOT / ".graphifyignore"
    try:
        policy_rules = {
            line.strip()
            for line in policy_path.read_text(encoding="utf-8").splitlines()
            if line.strip() and not line.lstrip().startswith("#")
        }
    except OSError as exc:
        raise RuntimeError(f"cannot read {policy_path}: {exc}") from exc

    missing_rules = [
        rule for rule in REQUIRED_GENERATED_IGNORE_RULES if rule not in policy_rules
    ]
    if missing_rules:
        raise RuntimeError(
            "missing generated-source Graphify ignore rules:\n- "
            + "\n- ".join(missing_rules)
        )

    missing_reincludes = [
        f"{family}: {rule}"
        for family, rules in REQUIRED_SEMANTIC_REINCLUDE_RULES.items()
        for rule in rules
        if rule not in policy_rules
    ]
    if missing_reincludes:
        raise RuntimeError(
            "missing semantic-source Graphify reinclude rules:\n- "
            + "\n- ".join(missing_reincludes)
        )

    missing_families = [
        name
        for name, patterns in REQUIRED_SEMANTIC_FAMILIES.items()
        if not _has_repo_file(patterns)
    ]
    if missing_families:
        raise RuntimeError(
            "missing Graphify semantic source families:\n- "
            + "\n- ".join(missing_families)
        )


def _validate_hook_contracts() -> None:
    hook = (ROOT / "scripts/git_hooks/post-commit").read_text(encoding="utf-8")
    if "exec scripts/kg/auto_refresh.sh" in hook or "/home/" in hook:
        raise RuntimeError(
            "post-commit contains terminal dispatch or a host-specific path"
        )
    if "scripts/graphify_refresh.py" not in hook:
        raise RuntimeError("post-commit does not dispatch the Graphify refresh module")
    if "nohup" in hook or "python3 scripts/graphify_refresh.py" in hook:
        raise RuntimeError("post-commit uses a non-portable Graphify launcher")
    makefile = (ROOT / "Makefile").read_text(encoding="utf-8")
    if "git rev-parse --git-path hooks" not in makefile:
        raise RuntimeError(
            "hook installation does not resolve Git's effective hooks path"
        )


def _check_graphify_version() -> None:
    expected = _expected_version()
    found = _graphify_version()
    if found != expected:
        raise RuntimeError(
            f"Graphify {expected} is required by .graphify_version; found {found}"
        )


def run_check() -> int:
    _check_graphify_version()
    with tempfile.TemporaryDirectory() as directory:
        source_count = _validate_structural_manifest(
            _extract_structural_manifest(Path(directory))
        )
    _validate_semantic_policy()
    _validate_hook_contracts()
    return source_count


def main() -> int:
    try:
        source_count = run_check()
    except RuntimeError as exc:
        print(str(exc), file=sys.stderr)
        return 1

    print(
        f"Graphify integration OK: {source_count} policy-conformant structural sources"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
