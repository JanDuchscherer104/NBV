"""Resolve config and cache paths at CLI and persistence boundaries.

These helpers delegate project-root policy to :class:`PathConfig` so command
entrypoints and Pydantic validators interpret relative paths consistently.
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from ..configs import PathConfig

if TYPE_CHECKING:
    from pydantic import ValidationInfo


def resolve_config_toml_path(path: str | Path, *, paths: PathConfig | None = None) -> Path:
    """Resolve a TOML config path from an absolute path, shell path, or config name."""

    path_config = paths or PathConfig()
    expanded = Path(path).expanduser()
    if expanded.is_absolute():
        resolved = expanded.resolve()
    elif expanded.exists():
        resolved = expanded.resolve()
    else:
        resolved = path_config.resolve_config_toml_path(expanded, must_exist=True)
    if resolved.suffix != ".toml":
        raise ValueError(f"Config path must be a .toml file, got {resolved}.")
    if not resolved.exists():
        raise FileNotFoundError(f"Config file not found: {resolved}")
    return resolved


def resolve_cache_artifact_dir(value: str | Path, info: "ValidationInfo") -> Path:
    """Resolve cache/store directories against the configured project cache roots."""

    paths: PathConfig = info.data.get("paths") or PathConfig()
    return paths.resolve_cache_artifact_dir(value)


__all__ = ["resolve_cache_artifact_dir", "resolve_config_toml_path"]
