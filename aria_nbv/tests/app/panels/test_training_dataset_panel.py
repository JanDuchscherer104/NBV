"""App-level contracts for the training-dataset composition hub."""

# ruff: noqa: S101

from __future__ import annotations

import json
from collections.abc import Generator, Iterable
from pathlib import Path
from types import SimpleNamespace
from typing import Any, cast

import numpy as np
import pytest
import streamlit as st
from streamlit.testing.v1 import AppTest

from aria_nbv.app.panels.training_dataset import (
    _artifact_identity,
    _clear_qh_results_for_control_change,
    _deep_metric_value,
    _download_payload,
    _qh_preview_for_identity,
    _qh_preview_identity,
    _qh_readiness_for_identity,
    _qh_readiness_identity,
    _target_inventory_explanation,
    _target_inventory_frames,
)
from aria_nbv.configs import PathConfig
from aria_nbv.data_handling.vin_store.format import (
    VinOfflineIndexRecord,
    VinOfflineManifest,
    VinOfflineMaterializedBlocks,
)
from aria_nbv.data_handling.vin_store.store import OFFLINE_DATASET_VERSION
from aria_nbv.dataset_bundle import (
    DatasetBundleSelection,
    QhCorpusReadiness,
    build_dataset_bundle_summary,
)
from aria_nbv.rollouts.zarr_store import ROLLOUT_ZARR_SCHEMA_VERSION
from aria_nbv.utils.fingerprints import stable_msgspec_hash

_PATH_CONFIG_FIELDS = (
    "root",
    "data_root",
    "data_root_massive",
    "checkpoints",
    "external_checkpoints",
    "wandb",
    "optuna",
    "configs_dir",
    "url_dir",
    "metadata_cache",
    "offline_cache_dir",
    "ase_meshes",
    "processed_meshes",
    "external_dir",
)


def _element_labels(elements: Iterable[Any]) -> list[str]:
    return [str(element.label) for element in elements]


@pytest.fixture
def isolated_path_config(tmp_path: Path) -> Generator[PathConfig, None, None]:
    """Point the singleton path owner at one isolated app workspace."""

    original = PathConfig()
    original_values = {field: getattr(original, field) for field in _PATH_CONFIG_FIELDS}
    cfg = PathConfig(
        root=tmp_path,
        data_root=tmp_path / ".data",
        offline_cache_dir=Path("offline_cache"),
    )
    try:
        yield cfg
    finally:
        PathConfig(**original_values)


def _write_root_store(cache: Path) -> tuple[Path, str]:
    store = cache / "vin-root"
    store.mkdir(parents=True)
    manifest = VinOfflineManifest(
        version=OFFLINE_DATASET_VERSION,
        created_at="2026-07-21T00:00:00Z",
        source={},
        oracle={},
        vin={},
        materialized_blocks=VinOfflineMaterializedBlocks(
            backbone=False,
            depths=False,
            candidate_pcs=False,
            gt_obbs=False,
        ),
        stats={"num_samples": 2, "num_train": 1, "num_val": 1},
        provenance={},
        shards=[],
    )
    manifest.write(store / "manifest.json")
    records = [
        VinOfflineIndexRecord(0, "scene-a::snippet-a", "scene-a", "snippet-a", "train", "a", 0),
        VinOfflineIndexRecord(1, "scene-b::snippet-b", "scene-b", "snippet-b", "val", "b", 0),
    ]
    VinOfflineIndexRecord.write_many(store / "sample_index.jsonl", records)
    (store / "splits").mkdir()
    np.save(store / "splits" / "train.npy", np.asarray([0], dtype=np.int64))
    np.save(store / "splits" / "val.npy", np.asarray([1], dtype=np.int64))
    return store, stable_msgspec_hash(manifest)


def _write_rollout_store(cache: Path, source_hash: str, *, compatible: bool = True) -> Path:
    store = cache / ("compatible.zarr" if compatible else "blocked.zarr")
    store.mkdir()
    payload = {
        "manifest_version": "rollout-store-manifest-v1",
        "schema_id": "aria_nbv.rollout_zarr_q_invalidity",
        "schema_version": ROLLOUT_ZARR_SCHEMA_VERSION,
        "root_attrs": {"schema_version": ROLLOUT_ZARR_SCHEMA_VERSION, "q_h_horizon": 2},
        "counts": {"sources": 1, "targets": 2, "rollouts": 3, "steps": 6, "candidates": 24},
        "config_hashes": {
            "source_manifest": [source_hash if compatible else "wrong-root"],
            "split_manifest": ["split-a"],
        },
        "generation": {"writer_config": {"profile": "pilot"}},
        "source_coverage": {
            "split_counts": {"train": 1},
            "sources": [
                {
                    "source_row_id": 0,
                    "source_sample_index": 0,
                    "source_sample_key": "scene-a::snippet-a",
                    "scene_id": "scene-a",
                    "snippet_id": "snippet-a",
                    "split": "train",
                    "source_shard_id": "a",
                    "source_shard_row": 0,
                }
            ],
        },
    }
    (store / "manifest.json").write_text(json.dumps(payload), encoding="utf-8")
    return store


def _app(tmp_path: Path) -> AppTest:
    script = tmp_path / "render_training_dataset.py"
    script.write_text(
        "from aria_nbv.app.panels.training_dataset import render_training_dataset_page\n"
        "render_training_dataset_page()\n",
        encoding="utf-8",
    )
    return AppTest.from_file(str(script), default_timeout=15)


def _metrics(app: AppTest) -> dict[str, str]:
    return {metric.label: metric.value for metric in app.metric}


def test_hub_discovers_composes_and_scans_explicit_stores(
    isolated_path_config: PathConfig,
    tmp_path: Path,
) -> None:
    root, source_hash = _write_root_store(isolated_path_config.offline_cache_dir)
    rollout = _write_rollout_store(isolated_path_config.offline_cache_dir, source_hash)
    app = _app(tmp_path).run()

    assert not app.exception
    assert app.title[0].value == "Training Dataset"
    assert _metrics(app)["Root samples"] == "2"
    assert _metrics(app)["Compatible rollout stores"] == "0 / 0"
    assert {button.label for button in app.button} >= {
        "Validate bundle",
        "Deep statistics / target scan",
    }
    assert "Download resolved bundle evidence JSON" in set(_element_labels(app.get("download_button")))
    assert "Run full single-step pipeline" not in {button.label for button in app.button}
    assert "Deep statistics / target scan" in {button.label for button in app.button}
    assert "Deep target and candidate evidence" not in {item.label for item in app.expander}

    app.multiselect[0].set_value([rollout.as_posix()])
    app = app.run()
    assert not app.exception
    metrics = _metrics(app)
    assert metrics["Compatible rollout stores"] == "1 / 1"
    assert metrics["Rollouts"] == "3"
    assert metrics["Rollout steps"] == "6"
    assert metrics["Candidates"] == "24"

    next(button for button in app.button if button.label == "Deep statistics / target scan").click()
    app = app.run()
    assert not app.exception
    metrics = _metrics(app)
    assert metrics["Root target opportunities"] == "Unavailable"
    assert metrics["Unique persisted target tasks"] == "Unavailable"
    assert metrics["Q_H trainable candidates"] == "Unavailable"
    assert root.as_posix() in str(app.session_state)


def test_blocked_store_remains_selected_but_is_excluded_from_totals(
    isolated_path_config: PathConfig,
    tmp_path: Path,
) -> None:
    _root, source_hash = _write_root_store(isolated_path_config.offline_cache_dir)
    blocked = _write_rollout_store(
        isolated_path_config.offline_cache_dir,
        source_hash,
        compatible=False,
    )
    app = _app(tmp_path).run()
    app.multiselect[0].set_value([blocked.as_posix()])
    app = app.run()

    assert not app.exception
    assert _metrics(app)["Compatible rollout stores"] == "0 / 1"
    assert _metrics(app)["Rollouts"] == "0"
    assert any("Blocked" in error.value for error in app.error)
    visible = "\n".join(item.value for item in [*app.markdown, *app.caption, *app.error, *app.success])
    assert f"{blocked.name}" in visible
    assert "Store compatibility matrix" in visible
    assert "Excluded" in visible
    assert "Root/source binding hashes, paths, and raw findings" in "\n".join(item.label for item in app.expander)
    assert "Root/source binding identifiers are available" in visible
    assert "source_manifest_hash_mismatch" in visible


def test_compatible_store_attribution_shows_root_and_source_bindings(
    isolated_path_config: PathConfig,
    tmp_path: Path,
) -> None:
    root, source_hash = _write_root_store(isolated_path_config.offline_cache_dir)
    compatible = _write_rollout_store(isolated_path_config.offline_cache_dir, source_hash)
    app = _app(tmp_path).run()
    app.multiselect[0].set_value([compatible.as_posix()])
    app = app.run()

    assert not app.exception
    visible = "\n".join(item.value for item in [*app.markdown, *app.caption, *app.error, *app.success])
    assert "Store compatibility matrix" in visible
    assert "Store compatibility matrix" in visible
    assert "Root/source binding hashes, paths, and raw findings" in "\n".join(item.label for item in app.expander)
    assert "Root/source binding identifiers are available" in visible


def test_mixed_store_selection_keeps_compatible_and_excluded_attribution(
    isolated_path_config: PathConfig,
    tmp_path: Path,
) -> None:
    root, source_hash = _write_root_store(isolated_path_config.offline_cache_dir)
    compatible = _write_rollout_store(isolated_path_config.offline_cache_dir, source_hash, compatible=True)
    blocked = _write_rollout_store(isolated_path_config.offline_cache_dir, source_hash, compatible=False)
    app = _app(tmp_path).run()
    app.multiselect[0].set_value([compatible.as_posix(), blocked.as_posix()])
    app = app.run()

    assert not app.exception
    assert _metrics(app)["Compatible rollout stores"] == "1 / 2"
    assert _metrics(app)["Rollouts"] == "3"
    visible = "\n".join(item.value for item in [*app.markdown, *app.caption, *app.error, *app.success])
    assert "Store compatibility matrix: 2 selected, 1 excluded" in visible
    assert "source_manifest_hash_mismatch" in visible
    assert "Rollout lineage does not resolve uniquely" in visible
    assert root.as_posix() in str(app.session_state)
    assert "Root/source binding hashes, paths, and raw findings" in "\n".join(item.label for item in app.expander)


def test_selected_root_blocker_is_not_mislabeled_as_rollout_finding(
    isolated_path_config: PathConfig,
    tmp_path: Path,
) -> None:
    root, source_hash = _write_root_store(isolated_path_config.offline_cache_dir)
    blocked = _write_rollout_store(isolated_path_config.offline_cache_dir, source_hash, compatible=False)
    (root / "manifest.json").write_text("{not valid json", encoding="utf-8")
    app = _app(tmp_path).run()
    app.multiselect[0].set_value([blocked.as_posix()])
    app = app.run()

    assert not app.exception
    visible = "\n".join(item.value for item in [*app.markdown, *app.caption, *app.error, *app.success])
    assert "Selected VIN root blocker(s)" in visible
    assert "root_store_unreadable" in visible
    excluded_section = visible.split("Selected VIN root blocker(s)", 1)[0]
    assert "root_store_unreadable" not in excluded_section


def test_qh_preview_reuses_only_exact_selection_and_controls() -> None:
    selection_a = ("selection-a",)
    baseline = _qh_preview_identity(
        selection_a,
        stage="train",
        chain_index=0,
        batch_size=4,
        seed=7,
        include_stats=False,
    )
    evidence = ("item", "batch")
    state = (baseline, evidence)

    assert _qh_preview_for_identity(state, baseline) is evidence
    for changed in (
        _qh_preview_identity(
            ("selection-b",), stage="train", chain_index=0, batch_size=4, seed=7, include_stats=False
        ),
        _qh_preview_identity(
            selection_a, stage="val", chain_index=0, batch_size=4, seed=7, include_stats=False
        ),
        _qh_preview_identity(
            selection_a, stage="train", chain_index=1, batch_size=4, seed=7, include_stats=False
        ),
        _qh_preview_identity(
            selection_a, stage="train", chain_index=0, batch_size=8, seed=7, include_stats=False
        ),
        _qh_preview_identity(
            selection_a, stage="train", chain_index=0, batch_size=4, seed=8, include_stats=False
        ),
        _qh_preview_identity(
            selection_a, stage="train", chain_index=0, batch_size=4, seed=7, include_stats=True
        ),
    ):
        assert _qh_preview_for_identity(state, changed) is None


def test_qh_readiness_hides_stale_preflight_after_loader_control_changes() -> None:
    selection = ("selection",)
    baseline = _qh_readiness_identity(selection, batch_size=4, seed=7)
    evidence = cast(QhCorpusReadiness, SimpleNamespace())
    state = (baseline, evidence)

    assert _qh_readiness_for_identity(state, baseline) is evidence
    assert _qh_readiness_for_identity(state, _qh_readiness_identity(selection, batch_size=8, seed=7)) is None
    assert _qh_readiness_for_identity(state, _qh_readiness_identity(selection, batch_size=4, seed=8)) is None


def test_qh_control_change_clears_displayed_readiness_and_preview(monkeypatch: pytest.MonkeyPatch) -> None:
    state = {
        "training_dataset_qh_readiness": ("old-controls", object()),
        "training_dataset_qh_preview": ("old-controls", object()),
    }
    monkeypatch.setattr(st, "session_state", state)

    _clear_qh_results_for_control_change()

    assert state == {}


def test_download_payload_is_deterministic_and_keeps_denominators_distinct(tmp_path: Path) -> None:
    root, source_hash = _write_root_store(tmp_path)
    rollout = _write_rollout_store(tmp_path, source_hash)
    evidence = build_dataset_bundle_summary(DatasetBundleSelection(root, (rollout,)))
    deep = {
        "aggregate": {
            "root_gt_obb_target_opportunities": 7,
            "persisted_rollout_unique_target_tasks": 2,
            "q_h_trainable_candidates": 19,
        }
    }

    first = _download_payload(evidence, deep)
    second = _download_payload(evidence, deep)
    payload = json.loads(first)

    assert first == second
    assert payload["aggregate"]["persisted_rollout_target_rows"] == 2
    assert payload["deep_statistics"]["aggregate"] == deep["aggregate"]


def test_artifact_identity_uses_bounded_metadata_and_ignores_payload_chunks(tmp_path: Path) -> None:
    store = tmp_path / "store.zarr"
    payload = store / "candidates" / "target_rri" / "c" / "0"
    payload.parent.mkdir(parents=True)
    payload.write_bytes(b"large-payload-chunk")
    manifest = store / "manifest.json"
    manifest.write_text("{}", encoding="utf-8")

    identity = _artifact_identity(store)

    assert [row[0] for row in identity] == [store.as_posix(), manifest.as_posix()]
    assert all(len(row) == 5 for row in identity)


def test_artifact_identity_includes_promotion_sidecars_and_detects_same_path_replacement(tmp_path: Path) -> None:
    store = tmp_path / "store.zarr"
    store.mkdir()
    for name in ("manifest.json", "_SUCCESS.json", "_owner.json"):
        (store / name).write_text("{}", encoding="utf-8")

    before = _artifact_identity(store)
    owner = store / "_owner.json"
    owner.unlink()
    owner.write_text("{}", encoding="utf-8")

    after = _artifact_identity(store)

    assert {Path(row[0]).name for row in before} == {"store.zarr", "manifest.json", "_SUCCESS.json", "_owner.json"}
    assert before != after


def test_artifact_identity_retains_broken_promotion_marker_membership(tmp_path: Path) -> None:
    store = tmp_path / "store.zarr"
    store.mkdir()
    (store / "manifest.json").write_text("{}", encoding="utf-8")
    (store / "_SUCCESS.json").symlink_to(tmp_path / "missing-success.json")

    identity = _artifact_identity(store)

    assert (store / "_SUCCESS.json").as_posix() in {row[0] for row in identity}


def test_artifact_identity_tolerates_metadata_disappearing_during_stat(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    store = tmp_path / "store.zarr"
    store.mkdir()
    manifest = store / "manifest.json"
    manifest.write_text("{}", encoding="utf-8")
    original_lstat = Path.lstat
    manifest_stat_calls = 0

    def _lstat(path: Path, *args: Any, **kwargs: Any) -> Any:
        nonlocal manifest_stat_calls
        if path == manifest:
            manifest_stat_calls += 1
            if manifest_stat_calls >= 1:
                raise FileNotFoundError(path)
        return original_lstat(path, *args, **kwargs)

    monkeypatch.setattr(Path, "lstat", _lstat)

    assert all(row[0] != manifest.as_posix() for row in _artifact_identity(store))


def test_deep_metric_value_marks_partial_counts_and_unavailable_failures() -> None:
    partial = {
        "q_h_trainable_candidates": 17,
        "q_h_trainable_candidates_status": "partial",
    }
    unavailable = {
        "q_h_trainable_candidates": None,
        "q_h_trainable_candidates_status": "unavailable",
    }

    assert _deep_metric_value(partial, "q_h_trainable_candidates", deep_available=True) == "17 (partial)"
    assert _deep_metric_value(unavailable, "q_h_trainable_candidates", deep_available=True) == "Unavailable"


def test_target_inventory_frames_preserve_zero_samples_and_class_scene_support() -> None:
    inventory = {
        "detected": {
            "available": True,
            "sample_rows": [{"sample_index": 0, "count": 0}, {"sample_index": 1, "count": 2}],
            "rows": [
                {"source_row": 0, "class_name": "chair", "scene_id": "scene-a"},
                {"source_row": 1, "class_name": "chair", "scene_id": "scene-b"},
            ],
        },
        "gt": {"available": True, "sample_rows": [{"sample_index": 0, "count": 1}], "rows": []},
    }

    samples, targets = _target_inventory_frames(inventory)

    assert len(samples) == 3
    assert int((samples["count"] == 0).sum()) == 1
    assert targets["class_name"].value_counts().to_dict() == {"chair": 2}
    assert targets["scene_id"].nunique() == 2
    assert (
        "aria_nbv/aria_nbv/data_handling/vin_store/target_inventory.py"
        in _target_inventory_explanation("detected").external_references[0][1]
    )
