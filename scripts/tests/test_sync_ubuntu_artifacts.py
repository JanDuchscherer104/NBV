"""Tests for the cross-host artifact allowlist."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "scripts"))

import sync_ubuntu_artifacts as sync  # noqa: E402


def _write_graph(root: Path, revision: str) -> None:
    output = root / "graphify-out"
    output.mkdir()
    (output / "graph.json").write_text(
        f'{{"built_at_commit": "{revision}"}}\n', encoding="utf-8"
    )


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


def test_graphify_state_push_is_revision_checked_and_updates_existing(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    revision = "a" * 40
    _write_graph(tmp_path, revision)
    monkeypatch.setattr(sync, "canonical_primary", lambda _root: tmp_path)
    monkeypatch.setattr(sync, "_local_head", lambda _root: revision)
    monkeypatch.setattr(sync, "_remote_head_full", lambda _remote, _root: revision)

    transfers = sync.build_transfers(
        root=tmp_path,
        remote="ubuntu",
        remote_root="/home/jd/.codex/worktrees/aria-pr193-cuda-verify",
        family="graphify-state",
        direction="push",
    )

    assert transfers[0] == sync.Transfer(
        f"{tmp_path}/graphify-input/",
        "ubuntu:/home/jd/.codex/worktrees/aria-pr193-cuda-verify/graphify-input/",
        ignore_existing=False,
        delete_extra=True,
    )
    assert transfers[1] == sync.Transfer(
        f"{tmp_path}/graphify-out/",
        "ubuntu:/home/jd/.codex/worktrees/aria-pr193-cuda-verify/graphify-out/",
        ignore_existing=False,
        delete_extra=True,
        exclude=(
            ".aria-worktree-seed.json",
            ".graphify_python",
            ".graphify_root",
            "cache/semantic",
            "cache/semantic-deep",
        ),
    )
    assert transfers[2] == sync.Transfer(
        f"{tmp_path}/.data/graphify-semantic-cache/",
        "ubuntu:/home/jd/.codex/worktrees/aria-pr193-cuda-verify/.data/graphify-semantic-cache/",
    )


def test_graphify_state_rejects_remote_checkout_mismatch(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    revision = "a" * 40
    _write_graph(tmp_path, revision)
    monkeypatch.setattr(sync, "canonical_primary", lambda _root: tmp_path)
    monkeypatch.setattr(sync, "_local_head", lambda _root: revision)
    monkeypatch.setattr(sync, "_remote_head_full", lambda _remote, _root: "b" * 40)

    with pytest.raises(ValueError, match="remote checkout HEAD does not match"):
        sync.build_transfers(
            root=tmp_path,
            remote="ubuntu",
            remote_root="/home/jd/repos/ARIA-NBV",
            family="graphify-state",
            direction="push",
        )


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


def test_graphify_state_sync_can_reconcile_generated_directories(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    commands: list[tuple[str, ...]] = []

    def capture(command: tuple[str, ...] | list[str], *, capture: bool = False) -> str:
        del capture
        commands.append(tuple(command))
        return ""

    monkeypatch.setattr(sync, "_run", capture)
    sync.execute(
        [
            sync.Transfer(
                "source/",
                "destination/",
                ignore_existing=False,
                delete_extra=True,
                exclude=("marker",),
            )
        ],
        apply=False,
    )

    command = commands[0]
    assert "--dry-run" in command
    assert "--delete" in command
    assert "--ignore-existing" not in command
    assert command[command.index("--exclude") + 1] == "marker"
    assert "--inplace" not in command


def test_graphify_state_activation_rebinds_remote_markers_after_apply(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    commands: list[tuple[str, ...]] = []
    monkeypatch.setattr(
        sync,
        "_remote_graphify_interpreter",
        lambda _remote, _root: "/opt/graphify/bin/python",
    )

    def capture(command: tuple[str, ...] | list[str], *, capture: bool = False) -> str:
        del capture
        commands.append(tuple(command))
        return ""

    monkeypatch.setattr(sync, "_run", capture)
    sync.activate_graphify_state(
        root=tmp_path,
        remote="ubuntu",
        remote_root="/home/jd/repos/ARIA-NBV",
        direction="push",
        apply=True,
    )

    assert commands
    command = commands[0]
    assert command[:3] == ("ssh", "-o", "ClearAllForwardings=yes")
    assert "/home/jd/repos/ARIA-NBV" in command[-1]
    assert ".graphify_root" in command[-1]
    assert ".graphify_python" in command[-1]
    assert "/opt/graphify/bin/python" in command[-1]
