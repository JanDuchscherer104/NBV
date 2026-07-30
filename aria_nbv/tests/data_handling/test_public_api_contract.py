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


def test_snippet_views_are_owned_by_their_domain_leaves() -> None:
    """Keep ASE/EFM and immutable VIN view ownership separate."""

    data_root = importlib.import_module("aria_nbv.data_handling")
    ase_root = importlib.import_module("aria_nbv.data_handling.ase_efm")
    ase_views = importlib.import_module("aria_nbv.data_handling.ase_efm.views")
    vin_views = importlib.import_module("aria_nbv.data_handling.vin_store.views")

    assert tuple(vin_views.__all__) == ("VinSnippetView", "is_vin_snippet_view_instance")  # noqa: S101
    assert data_root.VinSnippetView is vin_views.VinSnippetView  # noqa: S101
    assert not hasattr(ase_root, "VinSnippetView")  # noqa: S101
    assert not hasattr(ase_views, "VinSnippetView")  # noqa: S101
    assert not hasattr(ase_views, "is_vin_snippet_view_instance")  # noqa: S101


def test_compact_repr_support_is_representation_only_and_excludes_qh_dtos() -> None:
    """Share view formatting without creating a generic data-object contract."""

    support = importlib.import_module("aria_nbv.data_handling._repr_support")
    ase_views = importlib.import_module("aria_nbv.data_handling.ase_efm.views")
    vin_views = importlib.import_module("aria_nbv.data_handling.vin_store.views")
    qh_batching = importlib.import_module("aria_nbv.data_handling.qh_data.batching")
    qh_views = importlib.import_module("aria_nbv.data_handling.qh_data.views")
    mixin = support._CompactReprMixin

    assert support.__all__ == []  # noqa: S101
    assert issubclass(ase_views.EfmGtTimestampView, mixin)  # noqa: S101
    assert issubclass(vin_views.VinSnippetView, mixin)  # noqa: S101
    assert {name for name, value in vars(mixin).items() if callable(value)} == {  # noqa: S101
        "__repr__",
        "repr_with_docstrings",
    }
    qh_dtos = (
        qh_views.QhActorTensors,
        qh_views.QhSupervision,
        qh_views.QhChainKey,
        qh_views.QhChain,
        qh_batching.QhBatch,
    )
    assert all(not issubclass(dto, mixin) for dto in qh_dtos)  # noqa: S101
    assert "to" in qh_batching.QhBatch.__dict__  # noqa: S101
    assert "to" not in mixin.__dict__  # noqa: S101

    efm_view = ase_views.EfmGtTimestampView(time_id="7", cameras={})
    assert repr(efm_view) == "EfmGtTimestampView(time_id='7', cameras={})"  # noqa: S101
    assert "Timestamp identifier for this GT slice." in efm_view.repr_with_docstrings()  # noqa: S101


def test_qh_surfaces_remain_importable_from_owner_leaves() -> None:
    """Keep Q_H data and training APIs leaf-owned without widening package roots."""

    data_root = importlib.import_module("aria_nbv.data_handling")
    qh_data = importlib.import_module("aria_nbv.data_handling.qh_data")
    lightning_root = importlib.import_module("aria_nbv.lightning")
    qh_datamodule = importlib.import_module("aria_nbv.lightning.qh_datamodule")
    qh_module = importlib.import_module("aria_nbv.lightning.qh_module")

    data_names = (
        "QhActorTensors",
        "QhBatch",
        "QhChain",
        "QhDataset",
        "QhDatasetConfig",
        "collate_qh_chains",
    )
    assert tuple(qh_data.__all__) == data_names  # noqa: S101
    assert all(hasattr(qh_data, name) and not hasattr(data_root, name) for name in data_names)  # noqa: S101
    assert not hasattr(qh_data, "QhSupervision")  # noqa: S101
    assert not hasattr(qh_data, "QhChainKey")  # noqa: S101
    lightning_symbols = ((qh_datamodule, "QhDataModule"), (qh_module, "QhLightningModule"))
    assert all(hasattr(module, name) and not hasattr(lightning_root, name) for module, name in lightning_symbols)  # noqa: S101


def test_obsolete_qh_module_path_is_unavailable() -> None:
    """Keep the package move honest instead of retaining a compatibility facade."""

    with pytest.raises(ModuleNotFoundError):
        importlib.import_module("aria_nbv.data_handling.qh")


@pytest.mark.parametrize("module_name", ["raw", "offline"])
def test_obsolete_data_handling_package_paths_are_unavailable(module_name: str) -> None:
    """Keep ownership renames honest instead of retaining compatibility packages."""

    with pytest.raises(ModuleNotFoundError):
        importlib.import_module(f"aria_nbv.data_handling.{module_name}")


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

    batch_module = importlib.import_module("aria_nbv.data_handling.vin_store.batch")
    dataset_module = importlib.import_module("aria_nbv.data_handling.vin_store.dataset")
    assert "from_label" not in batch_module.VinOracleBatch.__dict__  # noqa: S101
    assert "to_vin_oracle_batch" not in dataset_module.VinOfflineSample.__dict__  # noqa: S101


def test_offline_configs_omit_premature_counterfactual_knobs() -> None:
    """Rollout storage should stay out of the immutable VIN offline-store schema."""

    data_module = importlib.import_module("aria_nbv.data_handling")
    pipeline_module = importlib.import_module("aria_nbv.oracle.pipelines.offline_vin")
    source_module = importlib.import_module("aria_nbv.data_handling.vin_store.source")
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
