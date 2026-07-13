"""Contract tests for the public ``aria_nbv.data_handling`` root API."""

from __future__ import annotations

import ast
import importlib
import tomllib
from pathlib import Path

import pytest


def test_public_api_has_exact_stable_allowlist() -> None:
    """Keep the package root limited to cross-family stable entrypoints."""

    module = importlib.import_module("aria_nbv.data_handling")
    expected = (
        "AseEfmDataset",
        "AseEfmDatasetConfig",
        "EfmSnippetView",
        "VinSnippetView",
        "VinOracleBatch",
        "VinOfflineDataset",
        "VinOfflineDatasetConfig",
        "VinOfflineStoreConfig",
    )
    assert tuple(module.__all__) == expected  # noqa: S101
    assert all(hasattr(module, name) for name in expected)  # noqa: S101


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
        "VinOfflineWriter",
        "VinOfflineWriterConfig",
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
    assert not hasattr(module, "VinDatasetSourceConfig")  # noqa: S101
    assert not hasattr(module, "VinOfflineSourceConfig")  # noqa: S101
    assert not hasattr(module, "VinOracleOnlineDataset")  # noqa: S101
    assert not hasattr(module, "VinOracleOnlineDatasetConfig")  # noqa: S101


def test_data_contracts_omit_pipeline_conversion_conveniences() -> None:
    """Keep online adaptation in pipelines and offline conversion in the dataset."""

    batch_module = importlib.import_module("aria_nbv.data_handling.offline.batch")
    dataset_module = importlib.import_module("aria_nbv.data_handling.offline.dataset")
    assert "from_label" not in batch_module.VinOracleBatch.__dict__  # noqa: S101
    assert "to_vin_oracle_batch" not in dataset_module.VinOfflineSample.__dict__  # noqa: S101


def test_offline_configs_omit_premature_counterfactual_knobs() -> None:
    """Rollout storage should stay out of the immutable VIN offline-store schema."""

    data_module = importlib.import_module("aria_nbv.data_handling")
    pipeline_module = importlib.import_module("aria_nbv.oracle.pipelines.offline_vin")
    source_module = importlib.import_module("aria_nbv.data_handling.offline.source")
    assert "include_counterfactuals" not in pipeline_module.VinOfflineWriterConfig.model_fields  # noqa: S101
    assert "load_counterfactuals" not in data_module.VinOfflineDatasetConfig.model_fields  # noqa: S101
    assert "load_counterfactuals_for_batch" not in source_module.VinOfflineSourceConfig.model_fields  # noqa: S101


def test_offline_generation_config_fields_are_frozen() -> None:
    """Keep canonical offline-generation TOMLs valid across the ownership move."""

    pipeline_module = importlib.import_module("aria_nbv.oracle.pipelines.offline_vin")
    assert tuple(pipeline_module.VinOfflineWriterConfig.model_fields) == (  # noqa: S101
        "paths",
        "store",
        "dataset",
        "labeler",
        "backbone",
        "include_backbone",
        "include_depths",
        "include_pointclouds",
        "include_diagnostic_payloads",
        "include_gt_obbs",
        "include_detected_obbs",
        "include_trajectory_metadata",
        "backbone_numeric_keep_fields",
        "backbone_payload_keep_fields",
        "vin_pad_points",
        "semidense_max_points",
        "semidense_include_obs_count",
        "max_candidates",
        "samples_per_shard",
        "max_samples",
        "train_val_split",
        "overwrite",
        "num_failures_allowed",
        "verbosity",
    )


def test_pyproject_omits_legacy_cache_entrypoints() -> None:
    """Removed cache CLIs should stay out of project scripts."""

    pyproject_path = Path(__file__).resolve().parents[2] / "pyproject.toml"
    pyproject_text = pyproject_path.read_text(encoding="utf-8")
    project_scripts = tomllib.loads(pyproject_text)["project"]["scripts"]
    assert "nbv-cache-samples" not in pyproject_text  # noqa: S101
    assert "nbv-cache-vin-snippets" not in pyproject_text  # noqa: S101
    assert project_scripts["nbv-build-offline"] == "aria_nbv.oracle.pipelines.cli:offline_main"  # noqa: S101


def test_runtime_root_imports_use_only_stable_entrypoints() -> None:
    """Require specialized data contracts to be imported from owner leaves."""

    package_root = Path(__file__).resolve().parents[2] / "aria_nbv"
    stable = {
        "AseEfmDataset",
        "AseEfmDatasetConfig",
        "EfmSnippetView",
        "VinSnippetView",
        "VinOracleBatch",
        "VinOfflineDataset",
        "VinOfflineDatasetConfig",
        "VinOfflineStoreConfig",
    }
    offenders: list[str] = []
    for path in package_root.rglob("*.py"):
        if "data_handling" in path.parts:
            continue
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if not isinstance(node, ast.ImportFrom):
                continue
            module = node.module or ""
            if module != "aria_nbv.data_handling" and not (node.level > 0 and module == "data_handling"):
                continue
            unexpected = sorted(alias.name for alias in node.names if alias.name not in stable)
            if unexpected:
                rel_path = path.relative_to(package_root).as_posix()
                offenders.append(f"{rel_path}:{node.lineno}: {', '.join(unexpected)}")
    assert not offenders  # noqa: S101


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
        "aria_nbv.data_handling._target_selection",
        "aria_nbv.data_handling.efm_dataset_utils",
        "aria_nbv.data_handling.efm_views",
    ]

    for module_name in removed_modules:
        with pytest.raises(ModuleNotFoundError):
            importlib.import_module(module_name)
