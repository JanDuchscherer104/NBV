"""Contract tests for the public ``aria_nbv.data_handling`` root API."""

from __future__ import annotations

import ast
import importlib
import tomllib
from pathlib import Path

import pytest


def test_public_api_smoke_imports_all_exports() -> None:
    """Ensure every root-exported symbol resolves from the package root."""

    module = importlib.import_module("aria_nbv.data_handling")
    missing = [name for name in module.__all__ if not hasattr(module, name)]
    assert not missing  # noqa: S101


def test_public_api_omits_internal_helper_exports() -> None:
    """Keep low-level storage and migration plumbing off the root contract."""

    module = importlib.import_module("aria_nbv.data_handling")
    unexpected = {
        "OpenedShard",
        "VinOfflineStoreReader",
        "OracleRriCacheEntry",
        "OracleRriCacheMetadata",
        "OracleRriCacheSample",
        "VinSnippetCacheEntry",
        "VinSnippetCacheMetadata",
        "collapse_vin_points",
        "pad_vin_points",
        "vin_snippet_cache_config_hash",
        "LegacyOfflinePlan",
        "LegacyOfflineRecord",
        "OracleRriCacheConfig",
        "OracleRriCacheDataset",
        "OracleRriCacheDatasetConfig",
        "OracleRriCacheVinDataset",
        "OracleRriCacheWriter",
        "OracleRriCacheWriterConfig",
        "VinOracleDatasetConfig",
        "prepare_legacy_records",
        "finalize_migrated_store",
        "VinOracleCacheDatasetConfig",
        "VIN_SNIPPET_CACHE_VERSION",
        "VIN_SNIPPET_PAD_POINTS",
        "VinSnippetCacheConfig",
        "VinSnippetCacheDataset",
        "VinSnippetCacheDatasetConfig",
        "VinSnippetCacheWriter",
        "VinSnippetCacheWriterConfig",
        "compute_cache_coverage",
        "expand_tar_urls",
        "extract_snippet_token",
        "read_cache_index_entries",
        "read_oracle_cache_metadata",
        "read_vin_snippet_cache_metadata",
        "rebuild_cache_index",
        "rebuild_oracle_cache_index",
        "rebuild_vin_snippet_cache_index",
        "repair_oracle_cache_indices",
        "repair_vin_snippet_cache_index",
        "scan_dataset_snippets",
        "scan_tar_sample_keys",
        "snippets_by_scene",
        "RolloutDatasetWriter",
        "RolloutDatasetWriterConfig",
        "RolloutDatasetWriterStats",
        "RolloutRecipeConfig",
        "RolloutZarrStoreConfig",
        "RolloutZarrStoreReader",
        "RolloutZarrStoreWriter",
        "RolloutZarrValidationResult",
        "RolloutZarrWriteResult",
        "validate_rollout_zarr_store",
        "write_rollout_zarr_store",
    }
    assert not (unexpected & set(module.__all__))  # noqa: S101


def test_public_api_omits_legacy_vin_oracle_dataset_alias() -> None:
    """Keep the ambiguous legacy source alias off the canonical package root."""

    module = importlib.import_module("aria_nbv.data_handling")
    assert not hasattr(module, "VinOracleDatasetConfig")  # noqa: S101
    assert not hasattr(module, "VinOnlineDatasetConfig")  # noqa: S101


def test_offline_configs_omit_premature_counterfactual_knobs() -> None:
    """Rollout storage should stay out of the immutable VIN offline-store schema."""

    module = importlib.import_module("aria_nbv.data_handling")
    assert "include_counterfactuals" not in module.VinOfflineWriterConfig.model_fields  # noqa: S101
    assert "load_counterfactuals" not in module.VinOfflineDatasetConfig.model_fields  # noqa: S101
    assert "load_counterfactuals_for_batch" not in module.VinOfflineSourceConfig.model_fields  # noqa: S101


def test_pyproject_omits_legacy_cache_entrypoints() -> None:
    """Removed cache CLIs should stay out of project scripts."""

    pyproject_path = Path(__file__).resolve().parents[2] / "pyproject.toml"
    pyproject_text = pyproject_path.read_text(encoding="utf-8")
    project_scripts = tomllib.loads(pyproject_text)["project"]["scripts"]
    assert "nbv-cache-samples" not in pyproject_text  # noqa: S101
    assert "nbv-cache-vin-snippets" not in pyproject_text  # noqa: S101
    assert project_scripts["nbv-build-offline"] == "aria_nbv.data_handling.offline.cli:main"  # noqa: S101


def test_runtime_modules_do_not_import_data_handling_submodules() -> None:
    """Keep direct ``data_handling`` submodule imports tightly constrained."""

    package_root = Path(__file__).resolve().parents[2] / "aria_nbv"
    allowlist = {"vin/models/scene_myopic.py"}
    allowed_direct_imports = {
        "rollouts/target_counterfactuals.py": {
            "data_handling.offline.dataset",
            "data_handling._target_selection",
            "data_handling.efm_views",
        },
        "oracle/pipelines/rollout_dataset.py": {
            "data_handling.offline.dataset",
            "data_handling._target_selection",
        },
        "rollouts/info_cli.py": {"data_handling.efm_dataset_utils"},
        "rollouts/zarr_store.py": {"data_handling.efm_dataset_utils"},
        "rerun_inspector/_cli.py": {"data_handling.efm_dataset_utils"},
        "rerun_inspector/_metadata.py": {"data_handling.efm_dataset_utils"},
        "rerun_inspector/_rollout_zarr.py": {"data_handling.efm_dataset_utils"},
        "rerun_inspector/_sample.py": {"data_handling.efm_dataset_utils"},
    }
    offenders: list[str] = []
    for path in package_root.rglob("*.py"):
        if "data_handling" in path.parts:
            continue
        rel_path = path.relative_to(package_root)
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                if any(alias.name.startswith("aria_nbv.data_handling.") for alias in node.names):
                    rel = rel_path.as_posix()
                    bad = [
                        alias.name
                        for alias in node.names
                        if alias.name.startswith("aria_nbv.data_handling.")
                        and not _allowed_data_handling_import(rel, alias.name, allowed_direct_imports)
                    ]
                    if rel not in allowlist and bad:
                        offenders.append(f"{rel}: {', '.join(bad)}")
                    break
            if isinstance(node, ast.ImportFrom):
                module = node.module or ""
                if (
                    module.startswith("aria_nbv.data_handling.")
                    or ".data_handling." in module
                    or (node.level > 0 and module.startswith("data_handling."))
                ):
                    rel = rel_path.as_posix()
                    if rel not in allowlist and not _allowed_data_handling_import(rel, module, allowed_direct_imports):
                        offenders.append(f"{rel}: {module}")
                    break
    assert not offenders  # noqa: S101


def _allowed_data_handling_import(rel_path: str, module: str, allowed_by_file: dict[str, set[str]]) -> bool:
    """Return whether a file has an explicit canonical data-handling dependency."""

    allowed = allowed_by_file.get(rel_path, set())
    normalized = module.removeprefix("aria_nbv.")
    return normalized in allowed


def test_data_handling_has_no_legacy_data_imports() -> None:
    """Ensure the new core stays independent from ``aria_nbv.data``."""

    data_handling_root = Path(__file__).resolve().parents[2] / "aria_nbv" / "data_handling"
    offenders: list[str] = []
    for path in data_handling_root.rglob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                if any(alias.name.startswith("aria_nbv.data") for alias in node.names):
                    offenders.append(path.relative_to(data_handling_root).as_posix())
                    break
            if isinstance(node, ast.ImportFrom):
                module = node.module or ""
                if (
                    module.startswith("aria_nbv.data")
                    or module == "data"
                    or (node.level > 0 and module.startswith("data."))
                ):
                    offenders.append(path.relative_to(data_handling_root).as_posix())
                    break
    assert not offenders  # noqa: S101


def test_removed_legacy_data_modules_raise_import_error() -> None:
    """The mirrored legacy ``aria_nbv.data`` modules should no longer exist."""

    removed_modules = [
        "aria_nbv.data.efm_dataset",
        "aria_nbv.data.efm_snippet_loader",
        "aria_nbv.data.efm_views",
        "aria_nbv.data.mesh_cache",
        "aria_nbv.data.offline_cache",
        "aria_nbv.data.offline_cache_coverage",
        "aria_nbv.data.offline_cache_serialization",
        "aria_nbv.data.offline_cache_store",
        "aria_nbv.data.offline_cache_types",
        "aria_nbv.data.plotting",
        "aria_nbv.data.utils",
        "aria_nbv.data.vin_oracle_datasets",
        "aria_nbv.data.vin_oracle_types",
        "aria_nbv.data.vin_snippet_cache",
        "aria_nbv.data.vin_snippet_provider",
        "aria_nbv.data.vin_snippet_utils",
    ]

    for module_name in removed_modules:
        with pytest.raises(ModuleNotFoundError):
            importlib.import_module(module_name)


def test_removed_legacy_data_handling_modules_raise_import_error() -> None:
    """The data_handling legacy cache and migration modules should no longer exist."""

    removed_modules = [
        "aria_nbv.data_handling._legacy_cache_api",
        "aria_nbv.data_handling._legacy_dataset_mixins",
        "aria_nbv.data_handling._legacy_offline_cache_coverage",
        "aria_nbv.data_handling._legacy_offline_cache_serialization",
        "aria_nbv.data_handling._legacy_offline_cache_store",
        "aria_nbv.data_handling._legacy_oracle_cache",
        "aria_nbv.data_handling._legacy_vin_cache",
        "aria_nbv.data_handling._legacy_vin_provider",
        "aria_nbv.data_handling._legacy_vin_source",
        "aria_nbv.data_handling._migration",
        "aria_nbv.data_handling._config_utils",
        "aria_nbv.data_handling.cache_contracts",
        "aria_nbv.data_handling.cache_index",
        "aria_nbv.data_handling.offline_cache_coverage",
        "aria_nbv.data_handling.offline_cache_serialization",
        "aria_nbv.data_handling.offline_cache_store",
        "aria_nbv.data_handling.oracle_cache",
        "aria_nbv.data_handling.vin_cache",
        "aria_nbv.data_handling.vin_oracle_datasets",
        "aria_nbv.data_handling.vin_provider",
        "aria_nbv.data_handling._vin_runtime",
        "aria_nbv.data_handling._sample_keys",
    ]

    for module_name in removed_modules:
        with pytest.raises(ModuleNotFoundError):
            importlib.import_module(module_name)
