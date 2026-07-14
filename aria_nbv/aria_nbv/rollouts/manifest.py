"""Top-level manifest helpers for standalone rollout Zarr stores.

The rollout store keeps large replay facts in Zarr arrays, while this module
owns the small JSON sidecar that should be inspectable with normal shell tools.
The manifest is intentionally outside the Zarr payload so users can understand
how a store was generated without loading candidate, step, or target arrays.
"""

from __future__ import annotations

import hashlib
import json
import platform
import subprocess
import sys
from dataclasses import dataclass, field
from datetime import UTC, datetime
from importlib import metadata
from pathlib import Path
from typing import Any, Literal

from ..utils import BaseConfig

ROLLOUT_MANIFEST_FILENAME = "manifest.json"
"""Filename of the human-readable rollout-store sidecar manifest."""

ROLLOUT_MANIFEST_VERSION = "rollout-store-manifest-v1"
"""Version tag for the top-level rollout-store manifest payload."""


@dataclass(frozen=True, slots=True)
class RolloutStoreInvocation:
    """How a rollout store generation run was invoked."""

    mode: Literal["programmatic", "cli"] = "programmatic"
    """Invocation mode used to produce the store."""

    argv: tuple[str, ...] = ()
    """Command arguments for CLI runs."""

    config_path: str | None = None
    """Resolved TOML path for CLI runs."""

    raw_toml_text: str | None = None
    """Raw TOML text supplied to the writer CLI."""

    raw_toml_sha256: str | None = None
    """SHA-256 of `raw_toml_text`."""

    @classmethod
    def programmatic(cls) -> "RolloutStoreInvocation":
        """Return the default invocation for non-CLI calls."""

        return cls(mode="programmatic")

    @classmethod
    def from_cli(cls, *, argv: list[str], config_path: Path) -> "RolloutStoreInvocation":
        """Build CLI invocation metadata from parsed arguments and TOML source."""

        resolved = config_path.expanduser().resolve()
        raw_toml = resolved.read_text(encoding="utf-8")
        return cls(
            mode="cli",
            argv=tuple(argv),
            config_path=resolved.as_posix(),
            raw_toml_text=raw_toml,
            raw_toml_sha256=hashlib.sha256(raw_toml.encode("utf-8")).hexdigest(),
        )

    def to_jsonable(self) -> dict[str, Any]:
        """Return JSON-friendly invocation metadata."""

        return {
            "mode": self.mode,
            "argv": list(self.argv),
            "config_path": self.config_path,
            "raw_toml_sha256": self.raw_toml_sha256,
            "raw_toml_text": self.raw_toml_text,
        }


@dataclass(frozen=True, slots=True)
class RolloutStoreManifestContext:
    """Optional rich context attached by higher-level rollout writers."""

    writer_config: dict[str, Any] | None = None
    """Resolved writer configuration, if available."""

    invocation: RolloutStoreInvocation = field(default_factory=RolloutStoreInvocation.programmatic)
    """How generation was invoked."""

    runtime: dict[str, Any] = field(default_factory=dict)
    """Runtime provenance such as git and package versions."""

    shard: dict[str, Any] | None = None
    """Optional rollout shard manifest entry for cluster generation runs."""

    @classmethod
    def programmatic(cls, *, writer_config: BaseConfig | None = None) -> "RolloutStoreManifestContext":
        """Build provenance context for a non-CLI rollout-store invocation.

        The optional resolved writer configuration is serialized into the
        sidecar together with current runtime provenance. No source payloads or
        mutable runtime objects are retained.
        """

        return cls(
            writer_config=None if writer_config is None else writer_config.model_dump_jsonable(),
            invocation=RolloutStoreInvocation.programmatic(),
            runtime=collect_runtime_provenance(),
            shard=None,
        )

    @classmethod
    def from_cli(
        cls,
        *,
        writer_config: BaseConfig,
        argv: list[str],
        config_path: Path,
    ) -> "RolloutStoreManifestContext":
        """Build context for `nbv-build-rollouts` CLI runs."""

        return cls(
            writer_config=writer_config.model_dump_jsonable(),
            invocation=RolloutStoreInvocation.from_cli(argv=argv, config_path=config_path),
            runtime=collect_runtime_provenance(),
            shard=None,
        )

    def to_jsonable(self) -> dict[str, Any]:
        """Return the resolved writer, invocation, runtime, and shard metadata.

        The returned mapping is suitable for stable JSON serialization and
        intentionally contains provenance only; heavy rollout facts remain in
        normalized Zarr arrays.
        """

        return {
            "writer_config": self.writer_config,
            "invocation": self.invocation.to_jsonable(),
            "runtime": self.runtime,
            "shard": self.shard,
        }


def utc_timestamp() -> str:
    """Return an ISO-8601 UTC timestamp for metadata payloads."""

    return datetime.now(UTC).isoformat(timespec="seconds").replace("+00:00", "Z")


def manifest_json_bytes(payload: dict[str, Any]) -> bytes:
    """Serialize manifest JSON with stable key order."""

    return json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=True).encode("utf-8")


def manifest_sha256(payload: dict[str, Any]) -> str:
    """Return the SHA-256 for the canonical manifest JSON bytes."""

    return hashlib.sha256(manifest_json_bytes(payload)).hexdigest()


def write_rollout_store_manifest(store_dir: Path, payload: dict[str, Any]) -> str:
    """Write `manifest.json` next to `zarr.json` and return its SHA-256."""

    store_dir.mkdir(parents=True, exist_ok=True)
    data = manifest_json_bytes(payload)
    digest = hashlib.sha256(data).hexdigest()
    tmp_path = store_dir / f".{ROLLOUT_MANIFEST_FILENAME}.tmp"
    final_path = store_dir / ROLLOUT_MANIFEST_FILENAME
    tmp_path.write_bytes(data)
    tmp_path.replace(final_path)
    return digest


def read_rollout_store_manifest(store_dir: Path | str) -> dict[str, Any]:
    """Read the human-inspectable manifest beside a rollout Zarr payload.

    Args:
        store_dir: Standalone rollout-store directory containing
            ``manifest.json``.

    Returns:
        Parsed provenance and schema metadata. The function performs no Zarr
        reads and does not mutate the completed store.
    """

    path = Path(store_dir).expanduser().resolve() / ROLLOUT_MANIFEST_FILENAME
    return json.loads(path.read_text(encoding="utf-8"))


def collect_runtime_provenance(*, cwd: Path | None = None) -> dict[str, Any]:
    """Collect compact runtime provenance for a rollout store manifest."""

    root = _git_root(cwd or Path.cwd())
    return {
        "python": sys.version.split()[0],
        "platform": platform.platform(),
        "git": _git_summary(root),
        "packages": _package_versions(
            (
                "aria-nbv",
                "numpy",
                "pydantic",
                "rerun-sdk",
                "torch",
                "zarr",
            )
        ),
    }


def _git_root(start: Path) -> Path | None:
    result = _run_git(start, "rev-parse", "--show-toplevel")
    if result is None:
        return None
    path = Path(result.strip())
    return path if path.exists() else None


def _git_summary(root: Path | None) -> dict[str, Any]:
    if root is None:
        return {"available": False}
    sha = _run_git(root, "rev-parse", "HEAD")
    branch = _run_git(root, "rev-parse", "--abbrev-ref", "HEAD")
    status = _run_git(root, "status", "--porcelain")
    dirty_paths = [] if status is None else [line for line in status.splitlines() if line.strip()]
    return {
        "available": True,
        "root": root.as_posix(),
        "commit": None if sha is None else sha.strip(),
        "branch": None if branch is None else branch.strip(),
        "dirty": bool(dirty_paths),
        "dirty_path_count": len(dirty_paths),
    }


def _run_git(cwd: Path, *args: str) -> str | None:
    try:
        result = subprocess.run(
            ("git", "-C", cwd.as_posix(), *args),
            check=False,
            capture_output=True,
            text=True,
            timeout=5.0,
        )
    except (OSError, subprocess.TimeoutExpired):
        return None
    if result.returncode != 0:
        return None
    return result.stdout


def _package_versions(names: tuple[str, ...]) -> dict[str, str | None]:
    versions: dict[str, str | None] = {}
    for name in names:
        try:
            versions[name] = metadata.version(name)
        except metadata.PackageNotFoundError:
            versions[name] = None
    return versions


__all__ = [
    "ROLLOUT_MANIFEST_FILENAME",
    "ROLLOUT_MANIFEST_VERSION",
    "RolloutStoreInvocation",
    "RolloutStoreManifestContext",
    "collect_runtime_provenance",
    "manifest_sha256",
    "read_rollout_store_manifest",
    "utc_timestamp",
    "write_rollout_store_manifest",
]
