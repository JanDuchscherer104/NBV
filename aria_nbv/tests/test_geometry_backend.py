"""Tests for ARIA-NBV's single PyTorch3D backend preflight surface."""

from __future__ import annotations

import importlib.metadata

import pytest
import torch

from aria_nbv import geometry_backend


def test_backend_env_parser_accepts_provider_values(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(geometry_backend.BACKEND_ENV_VAR, "MoJo")

    assert geometry_backend.requested_backend_from_env() == "mojo"


def test_backend_env_parser_rejects_unknown_value() -> None:
    with pytest.raises(RuntimeError, match="PYTORCH3D_BACKEND must be one of"):
        geometry_backend.requested_backend_from_env("metal")


def test_forced_cuda_fails_without_cuda(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(torch.cuda, "is_available", lambda: False)

    with pytest.raises(RuntimeError, match="requires available CUDA"):
        geometry_backend.resolve_geometry_backend("cuda")


def test_auto_prefers_cuda_before_mojo(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(torch.cuda, "is_available", lambda: True)
    monkeypatch.setattr(geometry_backend, "_pytorch3d_cuda_probe", lambda: (True, None))
    monkeypatch.setattr(geometry_backend, "_mojo_available", lambda: True)

    assert geometry_backend.resolve_geometry_backend("auto") == "cuda"


def test_forced_cuda_rejects_cpu_only_pytorch3d(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(torch.cuda, "is_available", lambda: True)
    monkeypatch.setattr(
        geometry_backend,
        "_pytorch3d_cuda_probe",
        lambda: (False, "RuntimeError: Not compiled with GPU support"),
    )

    with pytest.raises(RuntimeError, match="working PyTorch3D CUDA rasterization"):
        geometry_backend.resolve_geometry_backend("cuda")


def test_auto_cuda_device_rejects_cpu_only_pytorch3d(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(geometry_backend.BACKEND_ENV_VAR, "auto")
    monkeypatch.setattr(torch.cuda, "is_available", lambda: True)
    monkeypatch.setattr(
        geometry_backend,
        "_pytorch3d_cuda_probe",
        lambda: (False, "RuntimeError: Not compiled with GPU support"),
    )

    with pytest.raises(ValueError, match="FORCE_CUDA=1"):
        geometry_backend.resolve_geometry_device("auto")


def test_auto_uses_mojo_on_non_cuda_provider(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(torch.cuda, "is_available", lambda: False)
    monkeypatch.setattr(geometry_backend, "_mojo_available", lambda: True)

    assert geometry_backend.resolve_geometry_backend("auto") == "mojo"


def test_mojo_forces_geometry_tensors_to_cpu(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(geometry_backend.BACKEND_ENV_VAR, "mojo")
    monkeypatch.setattr(geometry_backend, "_mojo_available", lambda: True)

    assert geometry_backend.resolve_geometry_device("auto").type == "cpu"


def test_forced_mojo_device_fails_without_provider(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(geometry_backend.BACKEND_ENV_VAR, "mojo")
    monkeypatch.setattr(geometry_backend, "_mojo_available", lambda: False)

    with pytest.raises(ValueError, match="requires a Mojo-enabled PyTorch3D provider"):
        geometry_backend.resolve_geometry_device("auto")


def test_auto_keeps_explicit_geometry_device(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(geometry_backend.BACKEND_ENV_VAR, "auto")

    assert geometry_backend.resolve_geometry_device("cpu").type == "cpu"


def test_provenance_reads_direct_url_and_provider_counters(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(torch.cuda, "is_available", lambda: False)
    monkeypatch.setattr(
        geometry_backend,
        "_pytorch3d_cuda_probe",
        lambda: (False, "Torch CUDA is unavailable"),
    )
    monkeypatch.setattr(geometry_backend, "_mojo_available", lambda: True)
    monkeypatch.setattr(
        geometry_backend,
        "expected_pytorch3d_identity",
        lambda: geometry_backend._APPLE_SILICON_PYTORCH3D,
    )
    monkeypatch.setattr(
        geometry_backend,
        "_provider_status",
        lambda: {
            "mojo_available": True,
            "mojo_import_error": None,
            "mojo_operations": ["point_face_dist_forward"],
            "dispatch_policy": "eligible_cpu_contract_else_native",
            "counters": {"point_face_calls": 2},
        },
    )
    monkeypatch.setattr(geometry_backend, "_package_version", lambda _package: "0.7.9")
    monkeypatch.setattr(
        geometry_backend,
        "_pytorch3d_direct_url",
        lambda: {
            "url": "https://github.com/JanDuchscherer104/pytorch3d.git",
            "vcs_info": {
                "vcs": "git",
                "commit_id": "0b213747a5610e56e8be5c0c7a11fca67a883018",
            },
        },
    )

    provenance = geometry_backend.collect_geometry_backend_provenance("mojo").to_dict()

    assert provenance["requested_backend"] == "mojo"
    assert provenance["resolved_backend"] == "mojo"
    assert provenance["pytorch3d_version"] == "0.7.9"
    assert provenance["pytorch3d_commit"] == "0b213747a5610e56e8be5c0c7a11fca67a883018"
    assert provenance["torch_device"] == "cpu"
    assert provenance["pytorch3d_cuda_available"] is False
    assert provenance["pytorch3d_cuda_error"] == "Torch CUDA is unavailable"
    assert provenance["mojo_operations"] == ("point_face_dist_forward",)
    assert provenance["counters"] == {"point_face_calls": 2}


def test_provenance_rejects_unpinned_provider(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        geometry_backend,
        "_pytorch3d_direct_url",
        lambda: {
            "url": "https://github.com/JanDuchscherer104/pytorch3d.git",
            "vcs_info": {"vcs": "git", "commit_id": "moving-branch"},
        },
    )

    with pytest.raises(RuntimeError, match="exact project pin"):
        geometry_backend.collect_geometry_backend_provenance("cpu")


def test_missing_pytorch3d_distribution_has_empty_direct_url(monkeypatch: pytest.MonkeyPatch) -> None:
    def missing_distribution(_package: str) -> object:
        raise importlib.metadata.PackageNotFoundError

    monkeypatch.setattr(importlib.metadata, "distribution", missing_distribution)

    assert geometry_backend._pytorch3d_direct_url() == {}
