"""Tests for the lock-sensitive PyTorch3D CUDA provider setup."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "scripts"))

import setup_pytorch3d_cuda as setup_cuda  # noqa: E402


def _write_lock(path: Path, *, revision: str, fragment: str | None = None) -> None:
    path.write_text(
        f"""version = 1
revision = 3

[[package]]
name = "pytorch3d"
version = "0.7.9"
source = {{ git = "https://github.com/facebookresearch/pytorch3d.git?rev={revision}#{fragment or revision}" }}
resolution-markers = ["python_full_version < '3.12' and platform_machine == 'x86_64' and sys_platform == 'linux'"]
""",
        encoding="utf-8",
    )


def test_locked_linux_pytorch3d_returns_exact_vcs_identity(tmp_path: Path) -> None:
    commit = "b6a77ad7aaf41ed90fca80ce6a2bac3c462a7881"
    lock_path = tmp_path / "uv.lock"
    _write_lock(lock_path, revision=commit)

    assert setup_cuda._locked_linux_pytorch3d(lock_path) == (
        "https://github.com/facebookresearch/pytorch3d.git",
        commit,
    )


def test_locked_linux_pytorch3d_rejects_moving_or_mismatched_source(tmp_path: Path) -> None:
    lock_path = tmp_path / "uv.lock"
    _write_lock(lock_path, revision="main", fragment="b" * 40)

    with pytest.raises(RuntimeError, match="exact Git commit"):
        setup_cuda._locked_linux_pytorch3d(lock_path)


def test_cuda_home_requires_nvcc(tmp_path: Path) -> None:
    with pytest.raises(RuntimeError, match="CUDA toolkit is missing"):
        setup_cuda._cuda_home(tmp_path)
