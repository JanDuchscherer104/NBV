#!/usr/bin/env python3
"""Safely exchange allowlisted ARIA-NBV artifacts with the Ubuntu host."""

from __future__ import annotations

import argparse
import json
import shlex
import shutil
import subprocess
import sys
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True, slots=True)
class Transfer:
    """One rsync source/destination pair with immutable safety policy."""

    source: str
    destination: str
    ignore_existing: bool = True
    delete_extra: bool = False
    exclude: tuple[str, ...] = ()


def _run(command: Sequence[str], *, capture: bool = False) -> str:
    result = subprocess.run(command, check=True, capture_output=capture, text=True)
    return result.stdout.strip() if capture else ""


def canonical_primary(root: Path) -> Path:
    """Return the primary checkout that owns this worktree's common Git dir."""

    common = _run(
        (
            "git",
            "-C",
            str(root),
            "rev-parse",
            "--path-format=absolute",
            "--git-common-dir",
        ),
        capture=True,
    )
    common_path = Path(common).resolve()
    if common_path.name != ".git" or not common_path.is_dir():
        raise ValueError("repository common Git directory is unavailable")
    return common_path.parent


def _remote_head(remote: str, remote_root: str) -> str:
    head = _run(
        (
            "ssh",
            "-o",
            "ClearAllForwardings=yes",
            remote,
            "git",
            "-C",
            remote_root,
            "rev-parse",
            "--short=12",
            "HEAD",
        ),
        capture=True,
    )
    if len(head) != 12 or any(character not in "0123456789abcdef" for character in head):
        raise ValueError("remote Git HEAD is not a canonical abbreviated object ID")
    return head


def _full_oid(value: str, label: str) -> str:
    if len(value) not in {40, 64} or any(character not in "0123456789abcdef" for character in value):
        raise ValueError(f"{label} is not a canonical object ID")
    return value


def _local_head(root: Path) -> str:
    return _full_oid(
        _run(
            ("git", "-C", str(root), "rev-parse", "--verify", "HEAD^{commit}"),
            capture=True,
        ),
        "local Git HEAD",
    )


def _remote_head_full(remote: str, remote_root: str) -> str:
    return _full_oid(
        _run(
            (
                "ssh",
                "-o",
                "ClearAllForwardings=yes",
                remote,
                "git",
                "-C",
                remote_root,
                "rev-parse",
                "--verify",
                "HEAD^{commit}",
            ),
            capture=True,
        ),
        "remote Git HEAD",
    )


def _graphify_revision(root: Path) -> str:
    graph = root / "graphify-out/graph.json"
    if graph.is_symlink() or not graph.is_file():
        raise ValueError("local Graphify state is missing graphify-out/graph.json")
    try:
        payload = json.loads(graph.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as error:
        raise ValueError(f"local Graphify graph is invalid: {error}") from error
    revision = payload.get("built_at_commit")
    if not isinstance(revision, str):
        raise ValueError("local Graphify graph has no canonical built_at_commit")
    return _full_oid(revision, "local Graphify graph built_at_commit")


def _remote_graphify_interpreter(remote: str, remote_root: str) -> str:
    program = (
        "set -eu; "
        f"root={shlex.quote(remote_root)}; "
        "bin=$(command -v graphify); "
        'case "$bin" in "$root"/*) exit 11;; esac; '
        'shebang=$(head -n 1 "$bin"); '
        "case \"$shebang\" in '#!'*) interpreter=${shebang#'#!'};; *) exit 12;; esac; "
        'case "$interpreter" in /*) ;; *) exit 13;; esac; '
        'case "$interpreter" in "$root"/*) exit 14;; esac; '
        '"$interpreter" -I -c '
        + shlex.quote(
            "import graphify; from importlib.metadata import version; "
            "raise SystemExit(0 if version('graphifyy') == '0.9.48' else 15)"
        )
        + "; "
        "printf '%s\n' \"$interpreter\""
    )
    interpreter = _run(("ssh", "-o", "ClearAllForwardings=yes", remote, program), capture=True)
    if not interpreter.startswith("/") or "\n" in interpreter:
        raise ValueError("remote Graphify interpreter is unavailable")
    return interpreter


def _local_graphify_interpreter(root: Path) -> str:
    graphify = shutil.which("graphify")
    if not graphify:
        raise ValueError("trusted local Graphify CLI is unavailable")
    root = root.resolve()
    graphify_path = Path(graphify)
    if graphify_path.resolve(strict=True).is_relative_to(root):
        raise ValueError("trusted local Graphify CLI is inside repository")
    try:
        shebang = graphify_path.read_text(encoding="utf-8").splitlines()[0]
    except (OSError, UnicodeDecodeError, IndexError) as error:
        raise ValueError("trusted local Graphify CLI shebang is unavailable") from error
    if not shebang.startswith("#!"):
        raise ValueError("trusted local Graphify CLI has no interpreter shebang")
    interpreter = shebang[2:].strip()
    if not interpreter.startswith("/"):
        raise ValueError("trusted local Graphify CLI interpreter is not absolute")
    return interpreter


def _graphify_transfers(root: Path, remote: str, remote_root: str, direction: str) -> list[Transfer]:
    local = canonical_primary(root) / ".data/graphify-semantic-cache/"
    remote_path = f"{remote}:{remote_root}/.data/graphify-semantic-cache/"
    if direction == "pull":
        return [Transfer(remote_path, f"{local}/")]
    return [Transfer(f"{local}/", remote_path)]


def _graphify_state_transfers(
    root: Path, remote: str, remote_root: str, direction: str
) -> list[Transfer]:
    local_root = root.resolve()
    graph_revision = _graphify_revision(local_root)
    if graph_revision != _local_head(local_root):
        raise ValueError(
            "local Graphify state does not match this checkout; run "
            "scripts/check_graphify_freshness.py --usable before syncing"
        )
    if graph_revision != _remote_head_full(remote, remote_root):
        raise ValueError(
            "remote checkout HEAD does not match the local Graphify state; "
            "target a matching worktree with --remote-root"
        )
    output_excludes = (
        ".aria-worktree-seed.json",
        ".graphify_python",
        ".graphify_root",
        "cache/semantic",
        "cache/semantic-deep",
    )
    if direction == "pull":
        return [
            Transfer(
                f"{remote}:{remote_root}/graphify-input/",
                f"{local_root}/graphify-input/",
                ignore_existing=False,
                delete_extra=True,
            ),
            Transfer(
                f"{remote}:{remote_root}/graphify-out/",
                f"{local_root}/graphify-out/",
                ignore_existing=False,
                delete_extra=True,
                exclude=output_excludes,
            ),
            *_graphify_transfers(root, remote, remote_root, direction),
        ]
    return [
        Transfer(
            f"{local_root}/graphify-input/",
            f"{remote}:{remote_root}/graphify-input/",
            ignore_existing=False,
            delete_extra=True,
        ),
        Transfer(
            f"{local_root}/graphify-out/",
            f"{remote}:{remote_root}/graphify-out/",
            ignore_existing=False,
            delete_extra=True,
            exclude=output_excludes,
        ),
        *_graphify_transfers(root, remote, remote_root, direction),
    ]


def activate_graphify_state(
    *,
    root: Path,
    remote: str,
    remote_root: str,
    direction: str,
    apply: bool,
) -> None:
    """Bind synced Graphify state to the receiving host's trusted paths."""

    if not apply:
        return
    if direction == "pull":
        local_root = root.resolve()
        interpreter = _local_graphify_interpreter(local_root)
        (local_root / "graphify-out/.graphify_root").write_text(
            f"{local_root}\n", encoding="utf-8"
        )
        (local_root / "graphify-out/.graphify_python").write_text(
            f"{interpreter}\n", encoding="utf-8"
        )
        return

    interpreter = _remote_graphify_interpreter(remote, remote_root)
    program = (
        "set -eu; "
        f"root={shlex.quote(remote_root)}; "
        'mkdir -p "$root/graphify-out"; '
        f"printf '%s\\n' {shlex.quote(remote_root)} > \"$root/graphify-out/.graphify_root\"; "
        f"printf '%s\\n' {shlex.quote(interpreter)} > \"$root/graphify-out/.graphify_python\""
    )
    _run(("ssh", "-o", "ClearAllForwardings=yes", remote, program))


def _real_data_transfers(root: Path, remote: str, remote_root: str) -> list[Transfer]:
    relative_paths = (
        ".data/ase_efm/81283/shards-0001.tar",
        ".data/ase_meshes/scene_ply_81283.ply",
        ".data/ase_meshes_processed/scene_81283_0.02_nocrop_2cc7a9f350d4.ply",
    )
    return [Transfer(f"{remote}:{remote_root}/{relative}", str(root / relative)) for relative in relative_paths]


def _snapshot_transfers(root: Path, remote: str, remote_root: str) -> list[Transfer]:
    head = _remote_head(remote, remote_root)
    destination = root / ".agents/work/remote/ubuntu" / head
    relative_paths = (
        ".agents/work/",
        ".omx/context/",
        ".omx/interviews/",
        ".omx/plans/",
        ".omx/specs/",
        "docs/literature/pdf/",
        "docs/literature/tex-src/",
    )
    return [
        Transfer(
            f"{remote}:{remote_root}/{relative}",
            str(destination / relative.rstrip("/")),
        )
        for relative in relative_paths
    ]


def build_transfers(
    *,
    root: Path,
    remote: str,
    remote_root: str,
    family: str,
    direction: str,
) -> list[Transfer]:
    """Build the closed transfer plan for one artifact family."""

    if family == "graphify-cache":
        return _graphify_transfers(root, remote, remote_root, direction)
    if family in {"graphify-projection", "graphify-state"}:
        return _graphify_state_transfers(root, remote, remote_root, direction)
    if direction != "pull":
        raise ValueError(f"{family} is pull-only; Ubuntu's working checkout is not a push target")
    if family == "real-data-smoke":
        return _real_data_transfers(root, remote, remote_root)
    if family == "research-snapshot":
        return _snapshot_transfers(root, remote, remote_root)
    raise ValueError(f"unknown artifact family: {family}")


def execute(transfers: Sequence[Transfer], *, apply: bool) -> None:
    """Execute or dry-run an allowlisted transfer plan."""

    for transfer in transfers:
        if apply and ":" not in transfer.destination:
            Path(transfer.destination).parent.mkdir(parents=True, exist_ok=True)
        command = [
            "rsync",
            "-az",
            "-e",
            "ssh -o ClearAllForwardings=yes",
            "--partial",
            "--safe-links",
            "--itemize-changes",
        ]
        if transfer.ignore_existing:
            command.append("--ignore-existing")
        if transfer.delete_extra:
            command.append("--delete")
        for pattern in transfer.exclude:
            command.extend(("--exclude", pattern))
        if not apply:
            command.append("--dry-run")
        command.extend((transfer.source, transfer.destination))
        _run(command)


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "family",
        choices=(
            "graphify-cache",
            "graphify-projection",
            "graphify-state",
            "real-data-smoke",
            "research-snapshot",
        ),
    )
    parser.add_argument("direction", nargs="?", choices=("pull", "push"), default="pull")
    parser.add_argument(
        "--apply",
        action="store_true",
        help="perform the transfer; otherwise show an rsync dry-run",
    )
    parser.add_argument("--remote", default="ubuntu")
    parser.add_argument("--remote-root", default="/home/jd/repos/ARIA-NBV")
    parser.add_argument("--local-root", type=Path, default=Path(__file__).resolve().parents[1])
    args = parser.parse_args(argv)
    try:
        transfers = build_transfers(
            root=args.local_root.resolve(),
            remote=args.remote,
            remote_root=args.remote_root,
            family=args.family,
            direction=args.direction,
        )
        execute(transfers, apply=args.apply)
        if args.family in {"graphify-projection", "graphify-state"}:
            activate_graphify_state(
                root=args.local_root.resolve(),
                remote=args.remote,
                remote_root=args.remote_root,
                direction=args.direction,
                apply=args.apply,
            )
    except (OSError, ValueError, subprocess.CalledProcessError) as error:
        print(f"error: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
