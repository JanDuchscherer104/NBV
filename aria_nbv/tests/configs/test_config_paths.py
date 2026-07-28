"""Nested repository config discovery and resolution contracts."""

# ruff: noqa: S101

from __future__ import annotations

from pathlib import Path

import pytest

from aria_nbv.configs import PathConfig
from aria_nbv.utils.config_paths import discover_config_toml_paths, resolve_config_toml_path


@pytest.fixture
def isolated_paths(tmp_path: Path):
    original = PathConfig()
    original_values = {field: getattr(original, field) for field in type(original).model_fields}
    configs_dir = tmp_path / ".configs"
    configs_dir.mkdir()
    paths = PathConfig(root=tmp_path, configs_dir=configs_dir)
    try:
        yield paths
    finally:
        PathConfig(**original_values)


def test_discover_config_tomls_returns_recursive_absolute_paths(isolated_paths: PathConfig) -> None:
    shallow = isolated_paths.configs_dir / "inspection" / "rerun.toml"
    deep = isolated_paths.configs_dir / "generation" / "rollouts" / "smoke.toml"
    ignored = isolated_paths.configs_dir / "generation" / "notes.md"
    for path in (shallow, deep, ignored):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("", encoding="utf-8")

    assert discover_config_toml_paths(isolated_paths.configs_dir) == tuple(
        sorted((shallow.resolve(), deep.resolve()), key=lambda path: path.as_posix())
    )


def test_bare_config_name_resolves_unique_nested_match(isolated_paths: PathConfig) -> None:
    nested = isolated_paths.configs_dir / "training" / "qh" / "train_qh_v0_smoke.toml"
    nested.parent.mkdir(parents=True)
    nested.write_text("", encoding="utf-8")

    assert resolve_config_toml_path("train_qh_v0_smoke.toml", paths=isolated_paths) == nested.resolve()


def test_bare_config_name_rejects_ambiguous_nested_matches(isolated_paths: PathConfig) -> None:
    for folder in ("one", "two"):
        path = isolated_paths.configs_dir / folder / "smoke.toml"
        path.parent.mkdir()
        path.write_text("", encoding="utf-8")

    with pytest.raises(ValueError, match="ambiguous"):
        resolve_config_toml_path("smoke.toml", paths=isolated_paths)


def test_repository_tomls_have_no_flat_root_entries() -> None:
    config_root = Path(__file__).resolve().parents[3] / ".configs"

    assert tuple(config_root.glob("*.toml")) == ()
