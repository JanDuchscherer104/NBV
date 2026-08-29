"""Tests for the cross-host artifact allowlist."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "scripts"))

import sync_ubuntu_artifacts as sync  # noqa: E402


def test_graphify_cache_uses_canonical_primary(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    primary = tmp_path / "primary"
    monkeypatch.setattr(sync, "canonical_primary", lambda _root: primary)

    transfers = sync.build_transfers(
        root=tmp_path / "child",
        remote="ubuntu",
        remote_root="/home/jd/repos/ARIA-NBV",
        family="graphify-cache",
        direction="pull",
    )

    assert transfers == [
        sync.Transfer(
            "ubuntu:/home/jd/repos/ARIA-NBV/.data/graphify-semantic-cache/",
            f"{primary}/.data/graphify-semantic-cache/",
        )
    ]


def test_research_snapshot_is_host_and_revision_namespaced(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    monkeypatch.setattr(sync, "_remote_head", lambda _remote, _root: "0123456789ab")

    transfers = sync.build_transfers(
        root=tmp_path,
        remote="ubuntu",
        remote_root="/home/jd/repos/ARIA-NBV",
        family="research-snapshot",
        direction="pull",
    )

    assert all("/.agents/work/remote/ubuntu/0123456789ab/" in transfer.destination for transfer in transfers)
    assert any(transfer.source.endswith("/.omx/plans/") for transfer in transfers)
    assert any(transfer.source.endswith("/docs/literature/pdf/") for transfer in transfers)
    assert not any("graphify-input" in transfer.source for transfer in transfers)
    assert not any("graphify-out" in transfer.source for transfer in transfers)


def test_non_cache_families_reject_push(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="pull-only"):
        sync.build_transfers(
            root=tmp_path,
            remote="ubuntu",
            remote_root="/home/jd/repos/ARIA-NBV",
            family="real-data-smoke",
            direction="push",
        )


def test_dry_run_never_requests_delete_or_inplace(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    commands: list[tuple[str, ...]] = []

    def capture(command: tuple[str, ...] | list[str], *, capture: bool = False) -> str:
        del capture
        commands.append(tuple(command))
        return ""

    monkeypatch.setattr(sync, "_run", capture)
    sync.execute([sync.Transfer("source", "destination")], apply=False)

    command = commands[0]
    assert "--dry-run" in command
    assert "--ignore-existing" in command
    assert "--delete" not in command
    assert "--inplace" not in command
