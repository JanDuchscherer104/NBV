"""App-level contracts for the training-dataset composition hub."""

# ruff: noqa: S101

from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pytest
from streamlit.testing.v1 import AppTest

from aria_nbv.app.panels import training_dataset as panel
from aria_nbv.app.panels._stored_rollouts import session
from aria_nbv.app.panels.training_dataset import _artifact_identity, _download_payload
from aria_nbv.configs import PathConfig
from aria_nbv.data_handling.vin_store.format import (
    VinOfflineIndexRecord,
    VinOfflineManifest,
    VinOfflineMaterializedBlocks,
)
from aria_nbv.data_handling.vin_store.store import OFFLINE_DATASET_VERSION
from aria_nbv.dataset_bundle import (
    DatasetBundleSelection,
    NormalizedStorageMetric,
    QhCorpusReadiness,
    QhStageReadiness,
    build_dataset_bundle_summary,
)
from aria_nbv.rollouts.zarr_store import ROLLOUT_ZARR_SCHEMA_VERSION
from aria_nbv.utils import Stage
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


def test_qh_ui_dispatchers_cross_real_owners_only_when_called(monkeypatch: pytest.MonkeyPatch) -> None:
    """Initial rendering owns buttons; explicit dispatch owns Q_H construction and preview."""

    readiness = object()
    preview = object()
    calls: list[tuple[str, object]] = []
    monkeypatch.setattr(
        panel,
        "build_qh_corpus_readiness",
        lambda selection, **kwargs: calls.append(("readiness", (selection, kwargs))) or readiness,
    )
    monkeypatch.setattr(
        panel,
        "preview_qh_batch",
        lambda selection, **kwargs: calls.append(("preview", (selection, kwargs))) or preview,
    )

    assert calls == []
    assert panel._cached_qh_readiness.__wrapped__("/root", ("/rollout",), (), 2, 7) is readiness
    assert panel._cached_qh_preview.__wrapped__("/root", ("/rollout",), (), "train", 0, 2, 7) is preview
    assert [name for name, _payload in calls] == ["readiness", "preview"]


def test_refresh_rollout_caches_clears_each_page_family(monkeypatch: pytest.MonkeyPatch) -> None:
    """One refresh control invalidates all native read-model caches."""

    cleared: list[str] = []
    for name in (
        "_cached_bundle_summary",
        "_cached_deep_statistics",
        "_cached_qh_readiness",
        "_cached_qh_preview",
    ):
        monkeypatch.setattr(panel, name, SimpleNamespace(clear=lambda name=name: cleared.append(name)))
    monkeypatch.setattr(session, "_clear_stored_rollout_caches", lambda: cleared.append("supervision"))

    session.clear_rollout_page_caches()

    assert set(cleared) == {
        "_cached_bundle_summary",
        "_cached_deep_statistics",
        "_cached_qh_readiness",
        "_cached_qh_preview",
        "supervision",
    }


@pytest.fixture
def isolated_path_config(tmp_path: Path):
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


def test_admission_metrics_use_only_real_qh_readiness(monkeypatch: pytest.MonkeyPatch) -> None:
    """The compact header derives every admitted value from the Q_H preflight."""

    metrics: dict[str, str] = {}

    class Column:
        def metric(self, label: str, value: str) -> None:
            metrics[label] = value

    monkeypatch.setattr(panel.st, "columns", lambda count: [Column() for _ in range(count)])
    readiness = QhCorpusReadiness(
        selection=DatasetBundleSelection(Path("/root"), (Path("/rollout.zarr"),)),
        verdict="Ready",
        blockers=(),
        stages=(
            QhStageReadiness(Stage.TRAIN, True, 3, 12, 40, ("scene-a", "scene-b"), 8, {}),
            QhStageReadiness(Stage.VAL, True, 1, 4, 9, ("scene-c",), 4, {}),
        ),
        contract={},
        loader_settings={},
        scene_disjoint=True,
        storage=(
            NormalizedStorageMetric(
                "rollout_bytes_per_trainable_candidate",
                2048.0,
                100352,
                49,
                "bytes / trainable Q_H candidate",
                None,
            ),
        ),
    )

    panel._render_summary_metrics(readiness)

    assert metrics == {
        "Train scenes": "2",
        "Q_H chains": "4",
        "Q_H states": "16",
        "Trainable candidates": "49",
        "Storage / trainable": "2.0 KiB",
    }


def test_hub_discovers_composes_and_scans_explicit_stores(
    isolated_path_config: PathConfig,
    tmp_path: Path,
) -> None:
    root, source_hash = _write_root_store(isolated_path_config.offline_cache_dir)
    rollout = _write_rollout_store(isolated_path_config.offline_cache_dir, source_hash)
    app = _app(tmp_path).run()

    assert not app.exception
    assert app.title[0].value == "Training Dataset"
    assert [tab.label for tab in app.tabs] == ["Readiness", "Q_H corpus", "Details"]
    assert _metrics(app) == {
        "Train scenes": "Preflight required",
        "Q_H chains": "Preflight required",
        "Q_H states": "Preflight required",
        "Trainable candidates": "Preflight required",
        "Storage / trainable": "Preflight required",
    }
    assert {button.label for button in app.button} >= {
        "Validate bundle",
        "Run deep target and candidate scan",
        "Preflight Q_H corpus",
    }
    assert "training_dataset_qh_readiness" not in app.session_state
    assert not any("CORAL" in tab.label for tab in app.tabs)
    assert "Download resolved bundle evidence JSON" in {button.label for button in app.get("download_button")}
    assert "Run full single-step pipeline" not in {button.label for button in app.button}

    app.multiselect[0].set_value([rollout.as_posix()])
    app = app.run()
    assert not app.exception
    assert "Root samples" not in _metrics(app)
    assert "Rollouts" not in _metrics(app)
    assert "Candidates" not in _metrics(app)

    next(button for button in app.button if button.label == "Run deep target and candidate scan").click()
    app = app.run()
    assert not app.exception
    assert "Root target opportunities" not in _metrics(app)
    assert "Unique persisted target tasks" not in _metrics(app)
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
    assert "Compatible rollout stores" not in _metrics(app)
    assert "Rollouts" not in _metrics(app)
    assert any("Blocked" in error.value for error in app.error)


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

    assert identity == ((manifest.as_posix(), manifest.stat().st_mtime_ns, manifest.stat().st_size),)


def test_artifact_identity_tolerates_metadata_disappearing_during_stat(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    store = tmp_path / "store.zarr"
    store.mkdir()
    manifest = store / "manifest.json"
    manifest.write_text("{}", encoding="utf-8")
    original_stat = Path.stat
    manifest_stat_calls = 0

    def _stat(path: Path, *args: object, **kwargs: object):
        nonlocal manifest_stat_calls
        if path == manifest:
            manifest_stat_calls += 1
            if manifest_stat_calls > 1:
                raise FileNotFoundError(path)
        return original_stat(path, *args, **kwargs)

    monkeypatch.setattr(Path, "stat", _stat)

    assert _artifact_identity(store) == ()
