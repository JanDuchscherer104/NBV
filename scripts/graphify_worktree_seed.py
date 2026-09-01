#!/usr/bin/env python3
"""Fail-closed Graphify artifact seed for a linked ARIA-NBV worktree."""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path, PurePosixPath
from typing import Any, NoReturn

CORE = (
    Path("graphify-out/graph.json"),
    Path("graphify-out/manifest.json"),
    Path("graphify-out/.graphify_python"),
)
ROOT = Path("graphify-out/.graphify_root")
SENTINEL = Path("graphify-out/.aria-worktree-seed.json")
CACHE = Path("graphify-out/cache")
CACHE_NAMES = ("semantic", "semantic-deep")
GRAPHIFY_DISTRIBUTION = "graphifyy"
PINNED_GRAPHIFY_VERSION = "0.9.48"
OID = re.compile(r"^[0-9a-f]+$")


def fail(message: str) -> NoReturn:
    raise ValueError(message)


def regular(path: Path, label: str) -> None:
    if path.is_symlink() or not path.is_file():
        fail(f"{label} must be a regular local file: {path}")


def validate_parent_chain(
    root: Path, relative: Path, label: str, *, require_existing: bool
) -> None:
    """Reject symlinked or non-directory parents below an already-resolved root."""
    current = root
    for part in relative.parent.parts:
        current /= part
        if current.is_symlink() or (current.exists() and not current.is_dir()):
            fail(f"unsafe {label} parent: {current}")
        if require_existing and not current.exists():
            fail(f"unsafe {label} parent: {current}")


def safe_path(value: Any, label: str) -> Path:
    if not isinstance(value, str) or not value or "\\" in value or "\x00" in value:
        fail(f"unsafe {label} path: {value!r}")
    path = PurePosixPath(value)
    if path.is_absolute() or "." in path.parts or ".." in path.parts:
        fail(f"unsafe {label} path: {value!r}")
    return Path(*path.parts)


def json_object(path: Path, label: str) -> dict[str, Any]:
    regular(path, label)
    try:
        result = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as error:
        fail(f"invalid {label}: {error}")
    if not isinstance(result, dict):
        fail(f"invalid {label}: expected a JSON object")
    return result


def git(root: Path, git_dir: Path | None, *args: str) -> str:
    command = ["git"]
    command.extend(
        (f"--git-dir={git_dir}", f"--work-tree={root}")
        if git_dir
        else ("-C", str(root))
    )
    result = subprocess.run(
        [*command, *args], capture_output=True, text=True, check=False
    )
    if result.returncode:
        fail(f"Git metadata unavailable for {root}: {result.stderr.strip()}")
    return result.stdout.strip()


def common_dir(root: Path, git_dir: Path | None) -> Path:
    value = Path(git(root, git_dir, "rev-parse", "--git-common-dir"))
    return value.resolve() if value.is_absolute() else (root / value).resolve()


def validate_topology(
    source: Path,
    destination: Path,
    source_git_dir: Path | None,
    destination_git_dir: Path | None,
) -> Path:
    if source == destination:
        fail("source and destination worktrees must differ")
    common = common_dir(source, source_git_dir)
    if common != common_dir(destination, destination_git_dir):
        fail("source and destination must belong to the same Git common directory")
    worktrees = {
        Path(line[9:]).resolve()
        for line in git(
            source, source_git_dir, "worktree", "list", "--porcelain"
        ).splitlines()
        if line.startswith("worktree ")
    }
    if source not in worktrees or destination not in worktrees:
        fail("source and destination must both be registered Git worktrees")
    return common


def manifest_markdown(
    root: Path, *, allow_missing_generated: bool = False
) -> list[Path]:
    manifest = json_object(root / CORE[1], "source manifest")
    entries: Any = manifest.get("files", manifest)
    if not isinstance(entries, dict) or not entries:
        fail("invalid source manifest: files must be a non-empty object")
    result: list[Path] = []
    for raw, entry in entries.items():
        path = safe_path(raw, "manifest")
        if not isinstance(entry, dict):
            fail(f"invalid source manifest entry: {path}")
        if path.parts[0] == "graphify-input" and path.suffix.lower() == ".md":
            candidate = root / path
            if allow_missing_generated and not candidate.exists() and not candidate.is_symlink():
                continue
            validate_parent_chain(root, path, "source", require_existing=True)
            regular(candidate, "manifest source")
            result.append(path)
    index = Path("graphify-input/index.md")
    if index not in result:
        fail("source manifest must include graphify-input/index.md")
    return sorted(set(result))


def validate_commit_oid(
    root: Path, git_dir: Path | None, value: Any, label: str
) -> str:
    object_format = git(root, git_dir, "rev-parse", "--show-object-format")
    if object_format not in {"sha1", "sha256"}:
        fail(f"{label} Git object format is unavailable")
    length = 40 if object_format == "sha1" else 64
    if not isinstance(value, str) or len(value) != length or not OID.fullmatch(value):
        fail(f"{label} must be a canonical full commit OID")
    object_type = git(root, git_dir, "cat-file", "-t", "--end-of-options", value)
    if object_type != "commit":
        fail(f"{label} must resolve as a commit object")
    return value


def validate_graph(root: Path, git_dir: Path | None, label: str) -> str:
    graph = json_object(root / CORE[0], f"{label} graph")
    if not isinstance(graph.get("nodes"), list) or any(
        not isinstance(node, dict) for node in graph["nodes"]
    ):
        fail(f"invalid {label} graph: nodes must be a list of objects")
    revision = validate_commit_oid(
        root, git_dir, graph.get("built_at_commit"), f"{label} graph built_at_commit"
    )
    if not any(
        node.get("source_file") == "graphify-input/index.md" for node in graph["nodes"]
    ):
        fail(f"invalid {label} graph: missing graphify-input/index.md node")
    return revision


def trusted_interpreter(root: Path) -> Path:
    graphify = shutil.which("graphify")
    if graphify is None:
        fail("trusted Graphify CLI is unavailable")
    root = root.resolve()
    cli_path = Path(graphify).absolute()
    if cli_path.is_relative_to(root):
        fail("trusted Graphify CLI is inside repository")
    cli = cli_path.resolve(strict=True)
    if not cli.is_file() or not os.access(cli, os.X_OK):
        fail("trusted Graphify CLI is unsafe")
    try:
        shebang = cli.read_text(encoding="utf-8").splitlines()[0]
    except (OSError, UnicodeDecodeError, IndexError) as error:
        fail(f"trusted Graphify CLI shebang is unavailable: {error}")
    if not shebang.startswith("#!"):
        fail("trusted Graphify CLI has no interpreter shebang")
    interpreter = Path(shebang[2:].strip())
    if not interpreter.is_absolute():
        fail("trusted Graphify CLI interpreter is not absolute")
    if interpreter.is_relative_to(root):
        fail("trusted Graphify CLI interpreter is inside repository")
    canonical = interpreter.resolve(strict=True)
    if (
        canonical.is_relative_to(root)
        or not interpreter.is_file()
        or not os.access(interpreter, os.X_OK)
    ):
        fail("trusted Graphify CLI interpreter is unsafe")
    return interpreter


def validate_interpreter(root: Path) -> None:
    marker = root / CORE[2]
    regular(marker, "source Graphify interpreter marker")
    try:
        configured = Path(marker.read_text(encoding="utf-8").strip())
    except (OSError, UnicodeDecodeError) as error:
        fail(f"invalid source Graphify interpreter marker: {error}")
    if not configured.is_absolute():
        fail("invalid source Graphify interpreter marker")
    trusted = trusted_interpreter(root)
    try:
        configured = configured.resolve(strict=True)
    except (OSError, RuntimeError) as error:
        fail(f"invalid source Graphify interpreter marker: {error}")
    if configured != trusted.resolve(strict=True):
        fail("source Graphify interpreter marker does not match trusted CLI")
    with tempfile.TemporaryDirectory(prefix="aria-graphify-seed-trust-") as neutral:
        child_env = {
            key: value
            for key, value in os.environ.items()
            if key not in {"PYTHONPATH", "PYTHONHOME"}
        }
        result = subprocess.run(
            [
                str(trusted),
                "-c",
                "import graphify; from importlib.metadata import version; print(version('graphifyy'))",
            ],
            check=False,
            capture_output=True,
            text=True,
            cwd=neutral,
            env=child_env,
        )
    if result.returncode:
        fail("source Graphify interpreter cannot import graphify")
    if result.stdout.strip() != PINNED_GRAPHIFY_VERSION:
        fail(
            f"source Graphify interpreter has {GRAPHIFY_DISTRIBUTION} {result.stdout.strip()!r}; "
            f"expected {PINNED_GRAPHIFY_VERSION}"
        )


def validate_source(
    source: Path,
    source_git_dir: Path | None,
    canonical_cache_root: Path,
) -> tuple[list[Path], str, dict[str, str]]:
    for path in (*CORE, Path("graphify-out/needs_update")):
        validate_parent_chain(source, path, "source", require_existing=True)
    pending = source / "graphify-out/needs_update"
    if pending.exists() or pending.is_symlink():
        regular(pending, "source Graphify semantic refresh marker")
    graph_revision = validate_graph(source, source_git_dir, "source")
    markdown = manifest_markdown(source)
    validate_interpreter(source)
    cache_targets = validate_cache_root(canonical_cache_root)
    return markdown, graph_revision, cache_targets


def validate_cache_root(root: Path) -> dict[str, str]:
    """Validate the independently authenticated canonical semantic cache."""
    if root.is_symlink() or not root.is_dir():
        fail(f"canonical Graphify cache root must be a regular directory: {root}")
    root = root.resolve()
    targets: dict[str, str] = {}
    for name in CACHE_NAMES:
        leaf = root / name
        if leaf.is_symlink() or not leaf.is_dir():
            fail(f"canonical Graphify {name} cache must be a regular directory: {leaf}")
        targets[name] = str(leaf)
    return targets


def owned_files(payload: dict[str, Any]) -> list[Path]:
    if payload.get("schema_version") != 2:
        fail("invalid worktree seed sentinel schema")
    raw = payload.get("files")
    if not isinstance(raw, list) or not raw:
        fail("invalid worktree seed sentinel files")
    files = [safe_path(item, "worktree seed") for item in raw]
    if len(files) != len(set(files)):
        fail("invalid worktree seed sentinel: duplicate files")
    return files


def validate_owned(
    destination: Path, common: Path, destination_git_dir: Path | None
) -> None:
    validate_parent_chain(destination, SENTINEL, "destination", require_existing=True)
    payload = json_object(destination / SENTINEL, "worktree seed sentinel")
    if payload.get("target_root") != str(destination) or payload.get(
        "git_common_dir"
    ) != str(common):
        fail("worktree seed sentinel is bound to another worktree")
    files = owned_files(payload)
    if not set((*CORE, ROOT)).issubset(files):
        fail("partial owned Graphify seed install")
    # The manifest-backed projection is legitimately replaced and pruned by
    # upstream extraction after seeding. Its historical allowlist therefore
    # authenticates seed ownership, while current manifest validation below
    # authenticates the live local projection.
    for path in (*CORE, ROOT):
        validate_parent_chain(destination, path, "destination", require_existing=True)
        regular(destination / path, "seeded artifact")
    try:
        root_marker = (destination / ROOT).read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as error:
        fail(f"invalid child .graphify_root: {error}")
    if root_marker not in {str(destination), f"{destination}\n"}:
        fail("child .graphify_root is not bound to this worktree")
    validate_graph(destination, destination_git_dir, "destination")
    manifest_markdown(destination, allow_missing_generated=True)
    cache_targets = payload.get("source_cache_targets")
    if not isinstance(cache_targets, dict) or set(cache_targets) != set(CACHE_NAMES):
        fail("invalid worktree seed sentinel source cache targets")
    for name in CACHE_NAMES:
        expected = cache_targets.get(name)
        if not isinstance(expected, str) or not Path(expected).is_absolute():
            fail(f"invalid worktree seed sentinel {name} cache target")
        cache = destination / CACHE / name
        validate_parent_chain(destination, CACHE / name, "destination", require_existing=True)
        if not cache.is_symlink():
            fail(f"destination Graphify {name} cache is not linked")
        try:
            actual = cache.resolve(strict=True)
        except (OSError, RuntimeError) as error:
            fail(f"destination Graphify {name} cache target is unavailable: {error}")
        if str(actual) != expected or not actual.is_dir():
            fail(f"destination Graphify {name} cache points somewhere else")


def validate_owned_seed(
    destination: Path, destination_git_dir: Path | None, canonical_cache_root: Path
) -> None:
    """Validate a linked worktree's complete local seed before maintenance."""
    destination = destination.resolve()
    common = common_dir(destination, destination_git_dir)
    validate_owned(destination, common, destination_git_dir)
    payload = json_object(destination / SENTINEL, "worktree seed sentinel")
    expected_targets = validate_cache_root(canonical_cache_root)
    if payload.get("source_cache_targets") != expected_targets:
        fail("worktree seed sentinel cache targets differ from the canonical primary")
    validate_interpreter(destination)


def rebind_owned_cache(
    destination: Path,
    common: Path,
    destination_git_dir: Path | None,
    canonical_cache_root: Path,
) -> None:
    """Move an already-owned child cache link to the authenticated primary."""
    validate_owned(destination, common, destination_git_dir)
    payload = json_object(destination / SENTINEL, "worktree seed sentinel")
    targets = validate_cache_root(canonical_cache_root)
    if payload.get("source_cache_targets") == targets:
        return
    for name, target in targets.items():
        cache = destination / CACHE / name
        if not cache.is_symlink():
            fail(f"destination Graphify {name} cache is not linked")
        cache.unlink()
        cache.symlink_to(target, target_is_directory=True)
    payload["source_cache_targets"] = targets
    (destination / SENTINEL).write_text(
        json.dumps(payload, sort_keys=True, indent=2) + "\n", encoding="utf-8"
    )


def seed(
    source: Path,
    destination: Path,
    *,
    check: bool,
    source_git_dir: Path | None,
    destination_git_dir: Path | None,
    canonical_cache_root: Path,
) -> None:
    source, destination = source.resolve(), destination.resolve()
    if not source.is_dir() or not destination.is_dir():
        fail("source and destination must be directories")
    common = validate_topology(source, destination, source_git_dir, destination_git_dir)
    for path in (*CORE, ROOT, SENTINEL, Path("graphify-input/index.md"), CACHE):
        validate_parent_chain(destination, path, "destination", require_existing=False)
    sentinel = destination / SENTINEL
    if sentinel.exists() or sentinel.is_symlink():
        validate_owned(destination, common, destination_git_dir)
        expected_targets = validate_cache_root(canonical_cache_root)
        payload = json_object(destination / SENTINEL, "worktree seed sentinel")
        if payload.get("source_cache_targets") != expected_targets:
            if check:
                fail("worktree seed sentinel cache targets differ from the canonical primary")
            rebind_owned_cache(
                destination, common, destination_git_dir, canonical_cache_root
            )
            validate_owned(destination, common, destination_git_dir)
        return
    markdown, graph_revision, cache_targets = validate_source(
        source, source_git_dir, canonical_cache_root
    )
    source_head = git(source, source_git_dir, "rev-parse", "HEAD")
    pending = Path("graphify-out/needs_update")
    pending_files = [pending] if (source / pending).exists() else []
    targets = [
        *CORE,
        *markdown,
        *pending_files,
        ROOT,
        SENTINEL,
        *(CACHE / name for name in CACHE_NAMES),
    ]
    for path in targets:
        validate_parent_chain(destination, path, "destination", require_existing=False)
    if any(
        (destination / path).exists() or (destination / path).is_symlink()
        for path in targets
    ):
        fail(
            "destination collision: Graphify seed paths exist without an ownership sentinel"
        )
    if check:
        fail("missing seeded Graphify artifacts")
    staged = Path(tempfile.mkdtemp(prefix=".graphify-seed-", dir=destination))
    try:
        files = [*CORE, *markdown, *pending_files]
        for path in files:
            target = staged / path
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(source / path, target)
        (staged / ROOT).write_text(f"{destination}\n", encoding="utf-8")
        provenance = {
            "files": [str(path) for path in [*files, ROOT]],
            "git_common_dir": str(common),
            "schema_version": 2,
            "source_graph_revision": graph_revision,
            "source_cache_targets": cache_targets,
            "source_worktree": str(source),
            "source_worktree_head": source_head,
            "target_root": str(destination),
        }
        (staged / SENTINEL).write_text(
            json.dumps(provenance, sort_keys=True, indent=2) + "\n",
            encoding="utf-8",
        )
        for path in [*files, ROOT, SENTINEL]:
            target = destination / path
            target.parent.mkdir(parents=True, exist_ok=True)
            os.replace(staged / path, target)
        for name, cache_target in cache_targets.items():
            cache = destination / CACHE / name
            if cache.exists() or cache.is_symlink():
                fail(f"destination Graphify {name} cache already exists")
            cache.parent.mkdir(parents=True, exist_ok=True)
            cache.symlink_to(cache_target, target_is_directory=True)
    finally:
        shutil.rmtree(staged, ignore_errors=True)


def prepare_cache(
    destination: Path, canonical_cache_root: Path, *, check: bool
) -> None:
    """Prepare only the local parent directory for shared semantic cache leaves."""
    destination = destination.resolve()
    if not destination.is_dir():
        fail("destination must be a directory")
    canonical_cache_root = canonical_cache_root.resolve()
    guard = CACHE / "semantic"
    if check:
        validate_parent_chain(destination, guard, "destination", require_existing=True)
        validate_cache_root(canonical_cache_root)
        return
    for directory in (Path("graphify-out"), CACHE):
        validate_parent_chain(
            destination,
            directory / ".aria-cache-parent",
            "destination",
            require_existing=False,
        )
        path = destination / directory
        if not path.exists():
            path.mkdir()
    validate_parent_chain(destination, guard, "destination", require_existing=True)
    if canonical_cache_root.exists() and canonical_cache_root.is_symlink():
        fail(f"canonical Graphify cache root must not be a symlink: {canonical_cache_root}")
    canonical_cache_root.mkdir(parents=True, exist_ok=True)
    for name in CACHE_NAMES:
        leaf = canonical_cache_root / name
        if leaf.exists() or leaf.is_symlink():
            if leaf.is_symlink() or not leaf.is_dir():
                fail(f"canonical Graphify {name} cache must be a regular directory: {leaf}")
        else:
            leaf.mkdir()
    validate_cache_root(canonical_cache_root)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path)
    parser.add_argument("--destination", type=Path, required=True)
    parser.add_argument("--source-git-dir", type=Path)
    parser.add_argument("--destination-git-dir", type=Path)
    parser.add_argument("--canonical-cache-root", type=Path)
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--prepare-cache", action="store_true")
    parser.add_argument("--check-owned", action="store_true")
    args = parser.parse_args(argv)
    try:
        if args.prepare_cache:
            if args.check_owned:
                parser.error("--prepare-cache and --check-owned are mutually exclusive")
            if args.source or args.source_git_dir or args.destination_git_dir:
                parser.error("--prepare-cache accepts only --destination, --canonical-cache-root, and --check")
            if args.canonical_cache_root is None:
                parser.error("--canonical-cache-root is required with --prepare-cache")
            prepare_cache(args.destination, args.canonical_cache_root, check=args.check)
        elif args.check_owned:
            if args.source or args.source_git_dir or args.check:
                parser.error("--check-owned accepts only destination Git metadata and cache root")
            if args.canonical_cache_root is None:
                parser.error("--canonical-cache-root is required with --check-owned")
            validate_owned_seed(
                args.destination,
                args.destination_git_dir,
                args.canonical_cache_root,
            )
        else:
            if args.source is None:
                parser.error("--source is required unless --prepare-cache is used")
            if args.canonical_cache_root is None:
                parser.error("--canonical-cache-root is required")
            seed(
                args.source,
                args.destination,
                check=args.check,
                source_git_dir=args.source_git_dir,
                destination_git_dir=args.destination_git_dir,
                canonical_cache_root=args.canonical_cache_root,
            )
    except ValueError as error:
        print(f"error: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
