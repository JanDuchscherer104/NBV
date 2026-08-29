"""PyTorch3D geometry backend preflight and provenance.

ARIA-NBV keeps geometry calls on PyTorch3D's public API. This module owns only
the user-facing backend request, provider capability check, and provenance
record used by smoke tests and experiment artifacts.
"""

from __future__ import annotations

import importlib.metadata
import json
import os
import platform
from dataclasses import asdict, dataclass
from typing import Any, Literal, cast

import torch

GeometryBackend = Literal["auto", "cpu", "cuda", "mojo"]
BACKEND_ENV_VAR = "PYTORCH3D_BACKEND"
_VALID_BACKENDS: set[str] = {"auto", "cpu", "cuda", "mojo"}
_UPSTREAM_PYTORCH3D = (
    "https://github.com/facebookresearch/pytorch3d.git",
    "b6a77ad7aaf41ed90fca80ce6a2bac3c462a7881",
)
_APPLE_SILICON_PYTORCH3D = (
    "https://github.com/JanDuchscherer104/pytorch3d.git",
    "0b213747a5610e56e8be5c0c7a11fca67a883018",
)


@dataclass(frozen=True)
class GeometryBackendProvenance:
    """Serializable geometry backend provenance for run artifacts."""

    requested_backend: GeometryBackend
    resolved_backend: str
    torch_version: str
    torch_device: str
    platform_system: str
    platform_machine: str
    pytorch3d_version: str | None
    pytorch3d_url: str | None
    pytorch3d_commit: str | None
    mojo_available: bool
    mojo_import_error: str | None
    mojo_operations: tuple[str, ...]
    dispatch_policy: str | None
    counters: dict[str, int]

    def to_dict(self) -> dict[str, Any]:
        """Return a plain JSON-serializable mapping."""

        return asdict(self)


def requested_backend_from_env(value: str | None = None) -> GeometryBackend:
    """Parse ``PYTORCH3D_BACKEND`` using the provider's supported values."""

    raw = (os.getenv(BACKEND_ENV_VAR) if value is None else value) or "auto"
    backend = raw.lower()
    if backend not in _VALID_BACKENDS:
        raise RuntimeError(f"{BACKEND_ENV_VAR} must be one of: auto, cpu, cuda, mojo")
    return cast(GeometryBackend, backend)


def resolve_geometry_backend(requested: GeometryBackend | None = None) -> str:
    """Resolve a requested backend without mutating PyTorch3D dispatch policy."""

    backend = requested or requested_backend_from_env()
    if backend == "cuda":
        if not torch.cuda.is_available():
            raise RuntimeError(f"{BACKEND_ENV_VAR}=cuda requires available CUDA")
        return "cuda"
    if backend == "mojo":
        if not _mojo_available():
            raise RuntimeError(f"{BACKEND_ENV_VAR}=mojo requires a Mojo-enabled PyTorch3D provider")
        return "mojo"
    if backend == "cpu":
        return "cpu"
    if torch.cuda.is_available():
        return "cuda"
    if _mojo_available():
        return "mojo"
    return "cpu"


def resolve_geometry_device(value: str | torch.device | None) -> torch.device:
    """Resolve tensors at ARIA-NBV's public PyTorch3D boundary.

    Mojo kernels in the Apple Silicon provider consume CPU tensors. The
    provider owns dispatch; this function is the sole ARIA-NBV translation
    from backend policy to the public PyTorch3D tensor contract.
    """

    if isinstance(value, torch.device):
        configured = value
    elif value is None or str(value).lower() == "auto":
        configured = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    else:
        configured = torch.device(value)

    requested = requested_backend_from_env()
    if requested == "cuda":
        if not torch.cuda.is_available():
            raise ValueError(f"{BACKEND_ENV_VAR}=cuda requires available CUDA")
        return torch.device("cuda")
    if requested == "mojo":
        if not _mojo_available():
            raise ValueError(f"{BACKEND_ENV_VAR}=mojo requires a Mojo-enabled PyTorch3D provider")
        return torch.device("cpu")
    if requested == "cpu":
        return torch.device("cpu")
    return configured


def expected_pytorch3d_identity() -> tuple[str, str]:
    """Return the exact provider source selected for this host platform."""

    if platform.system() == "Darwin" and platform.machine() == "arm64":
        return _APPLE_SILICON_PYTORCH3D
    return _UPSTREAM_PYTORCH3D


def collect_geometry_backend_provenance(requested: GeometryBackend | None = None) -> GeometryBackendProvenance:
    """Collect backend provenance for run metadata and diagnostics."""

    selected = requested or requested_backend_from_env()
    resolved = resolve_geometry_backend(selected)
    direct_url = _pytorch3d_direct_url()
    _validate_pytorch3d_identity(direct_url)
    provider = _provider_status()
    operations = provider.get("mojo_operations", ())
    if not isinstance(operations, (list, tuple)) or not all(isinstance(operation, str) for operation in operations):
        operations = ()
    import_error = provider.get("mojo_import_error")
    dispatch_policy = provider.get("dispatch_policy")
    return GeometryBackendProvenance(
        requested_backend=selected,
        resolved_backend=resolved,
        torch_version=torch.__version__,
        torch_device="cuda" if resolved == "cuda" else "cpu",
        platform_system=platform.system(),
        platform_machine=platform.machine(),
        pytorch3d_version=_package_version("pytorch3d"),
        pytorch3d_url=_pytorch3d_url(direct_url),
        pytorch3d_commit=_pytorch3d_commit(direct_url),
        mojo_available=bool(provider.get("mojo_available", False)),
        mojo_import_error=import_error if isinstance(import_error, str) else None,
        mojo_operations=tuple(operations),
        dispatch_policy=dispatch_policy if isinstance(dispatch_policy, str) else None,
        counters=_provider_counters(provider),
    )


def main() -> None:
    """Print backend provenance as stable JSON."""

    print(json.dumps(collect_geometry_backend_provenance().to_dict(), sort_keys=True))


def _package_version(package: str) -> str | None:
    try:
        return importlib.metadata.version(package)
    except importlib.metadata.PackageNotFoundError:
        return None


def _pytorch3d_direct_url() -> dict[str, Any]:
    try:
        dist = importlib.metadata.distribution("pytorch3d")
    except importlib.metadata.PackageNotFoundError:
        return {}
    content = dist.read_text("direct_url.json")
    if not content:
        return {}
    try:
        loaded = json.loads(content)
    except json.JSONDecodeError:
        return {}
    return loaded if isinstance(loaded, dict) else {}


def _pytorch3d_url(direct_url: dict[str, Any]) -> str | None:
    url = direct_url.get("url")
    return url if isinstance(url, str) else None


def _pytorch3d_commit(direct_url: dict[str, Any]) -> str | None:
    vcs_info = direct_url.get("vcs_info")
    if not isinstance(vcs_info, dict):
        return None
    commit = vcs_info.get("commit_id")
    return commit if isinstance(commit, str) else None


def _validate_pytorch3d_identity(direct_url: dict[str, Any]) -> None:
    expected_url, expected_commit = expected_pytorch3d_identity()
    vcs_info = direct_url.get("vcs_info")
    vcs = vcs_info.get("vcs") if isinstance(vcs_info, dict) else None
    installed = (_pytorch3d_url(direct_url), vcs, _pytorch3d_commit(direct_url))
    if installed != (expected_url, "git", expected_commit):
        raise RuntimeError("installed PyTorch3D VCS identity does not match the exact project pin")


def _provider_status() -> dict[str, Any]:
    try:
        from pytorch3d import _mojo_ops
    except ImportError:
        return {}
    status = getattr(_mojo_ops, "backend_status", None)
    if callable(status):
        value = status()
        return value if isinstance(value, dict) else {}
    has_mojo = getattr(_mojo_ops, "has_mojo", None)
    return {
        "mojo_available": bool(callable(has_mojo) and has_mojo()),
        "counters": _legacy_provider_counters(_mojo_ops),
    }


def _mojo_available() -> bool:
    return bool(_provider_status().get("mojo_available", False))


def _legacy_provider_counters(provider: Any) -> dict[str, int]:
    counters: dict[str, int] = {}
    for public_name, provider_name in (
        ("point_face_calls", "point_face_calls"),
        ("face_point_calls", "face_point_calls"),
        ("rasterize_calls", "rasterize_calls"),
    ):
        value = getattr(provider, provider_name, None)
        if callable(value):
            counters[public_name] = int(value())
    return counters


def _provider_counters(provider: dict[str, Any] | None = None) -> dict[str, int]:
    status = _provider_status() if provider is None else provider
    raw = status.get("counters")
    if not isinstance(raw, dict):
        return {}
    counters: dict[str, int] = {}
    for name, value in raw.items():
        if isinstance(name, str) and isinstance(value, int):
            counters[name] = value
    return counters
