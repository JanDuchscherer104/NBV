#!/usr/bin/env python3
"""Safely exchange allowlisted ARIA-NBV artifacts with the Ubuntu host."""

from __future__ import annotations

import argparse
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


def _graphify_transfers(root: Path, remote: str, remote_root: str, direction: str) -> list[Transfer]:
    local = canonical_primary(root) / ".data/graphify-semantic-cache/"
    remote_path = f"{remote}:{remote_root}/.data/graphify-semantic-cache/"
    if direction == "pull":
        return [Transfer(remote_path, f"{local}/")]
    return [Transfer(f"{local}/", remote_path)]


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
    if direction != "pull":
        raise ValueError(f"{family} is pull-only; Ubuntu's working checkout is not a push target")
    if family == "real-data-smoke":
        return _real_data_transfers(root, remote, remote_root)
    if family == "research-snapshot":
        return _snapshot_transfers(root, remote, remote_root)
    raise ValueError(f"unknown artifact family: {family}")


def execute(transfers: Sequence[Transfer], *, apply: bool) -> None:
    """Execute or dry-run an allowlisted transfer plan without deletion."""

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
        if not apply:
            command.append("--dry-run")
        command.extend((transfer.source, transfer.destination))
        _run(command)


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("family", choices=("graphify-cache", "real-data-smoke", "research-snapshot"))
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
    except (OSError, ValueError, subprocess.CalledProcessError) as error:
        print(f"error: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
