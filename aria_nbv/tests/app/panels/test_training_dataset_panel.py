"""App-level contracts for the training-dataset composition hub."""

# ruff: noqa: S101

from __future__ import annotations

import inspect
import json
from collections.abc import Callable, Generator, Iterable
from pathlib import Path
from types import SimpleNamespace
from typing import Any, cast, get_type_hints

import numpy as np
import pytest
import streamlit as st
from streamlit.testing.v1 import AppTest

import aria_nbv.app.panels.training_dataset as training_dataset
import aria_nbv.dataset_bundle as dataset_bundle
from aria_nbv.app.panels._stored_rollouts import session as stored_rollout_session
from aria_nbv.app.panels.training_dataset import (
    _cached_deep_statistics,
    _cached_qh_preview,
    _cached_qh_readiness,
    _clear_qh_results_for_control_change,
    _deep_metric_value,
    _download_payload,
    _qh_preview_for_identity,
    _qh_preview_identity,
    _qh_readiness_for_identity,
    _qh_readiness_identity,
    _retained_bundle_evidence,
    _retained_deep_statistics,
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
    DatasetBundleGenerationChangedError,
    DatasetBundleSelection,
    DatasetBundleSummaryRequest,
    QhBatchPreview,
    QhCorpusReadiness,
    QhStageReadiness,
    build_dataset_bundle_summary,
    capture_dataset_bundle_generation,
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


def _element_labels(elements: Iterable[Any]) -> list[str]:
    return [str(element.label) for element in elements]


@pytest.fixture  # type: ignore[untyped-decorator]
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


def _ready_qh_evidence(root: Path) -> QhCorpusReadiness:
    return QhCorpusReadiness(
        selection=DatasetBundleSelection(root, ()),
        verdict="Ready",
        blockers=(),
        stages=(QhStageReadiness(Stage.TRAIN, True, 1, 1, 1, ("scene-a",), 1, {}),),
        contract={},
        actor_contract={},
        loader_settings={"batch_size": 1, "seed": 0},
        scene_disjoint=True,
        storage=(),
    )


def _qh_preview_evidence() -> QhBatchPreview:
    return QhBatchPreview(Stage.TRAIN, 0, {}, 1, ({},), (1,), {}, {}, 0, 0, 1, 1)


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


def test_unavailable_root_sample_count_is_never_rendered_as_zero(
    isolated_path_config: PathConfig,
    tmp_path: Path,
) -> None:
    root, _source_hash = _write_root_store(isolated_path_config.offline_cache_dir)
    (root / "sample_index.jsonl").write_text("not-json\n", encoding="utf-8")

    app = _app(tmp_path).run()

    assert not app.exception
    assert _metrics(app)["Root samples"] == "Unavailable"
    assert any("Blocked" in error.value for error in app.error)


def test_initial_render_never_dispatches_deep_or_qh_acquisition(
    monkeypatch: pytest.MonkeyPatch,
    isolated_path_config: PathConfig,
    tmp_path: Path,
) -> None:
    _write_root_store(isolated_path_config.offline_cache_dir)
    calls = {"deep": 0, "qh": 0, "preview": 0}

    def _unexpected(name: str) -> None:
        calls[name] += 1
        raise AssertionError(f"unexpected initial-render {name} acquisition")

    monkeypatch.setattr(
        training_dataset, "compute_dataset_bundle_deep_statistics", lambda _selection: _unexpected("deep")
    )
    monkeypatch.setattr(training_dataset, "build_qh_corpus_readiness", lambda *_args, **_kwargs: _unexpected("qh"))
    monkeypatch.setattr(training_dataset, "preview_qh_batch", lambda *_args, **_kwargs: _unexpected("preview"))

    app = _app(tmp_path).run()

    assert not app.exception
    assert calls == {"deep": 0, "qh": 0, "preview": 0}


def test_initial_summary_never_opens_deep_vin_or_rollout_readers(
    monkeypatch: pytest.MonkeyPatch,
    isolated_path_config: PathConfig,
    tmp_path: Path,
) -> None:
    _root, source_hash = _write_root_store(isolated_path_config.offline_cache_dir)
    rollout = _write_rollout_store(isolated_path_config.offline_cache_dir, source_hash)

    def _unexpected_reader(*_args: object, **_kwargs: object) -> Any:
        pytest.fail("initial summary opened a deep array reader")

    monkeypatch.setattr(dataset_bundle, "VinOfflineStoreReader", _unexpected_reader)
    monkeypatch.setattr(dataset_bundle, "RolloutZarrStoreReader", _unexpected_reader)

    app = _app(tmp_path).run()
    app.multiselect[0].set_value([rollout.as_posix()])
    app = app.run()

    assert not app.exception
    assert _metrics(app)["Root samples"] == "2"
    assert _metrics(app)["Compatible rollout stores"] == "1 / 1"


def test_cached_bundle_summary_accepts_one_complete_request() -> None:
    signature = inspect.signature(training_dataset._cached_bundle_summary)

    assert tuple(signature.parameters) == ("request",)
    assert get_type_hints(training_dataset._cached_bundle_summary)["request"] is DatasetBundleSummaryRequest


def test_initial_summary_failure_is_contained_and_actionable(
    monkeypatch: pytest.MonkeyPatch,
    isolated_path_config: PathConfig,
    tmp_path: Path,
) -> None:
    _write_root_store(isolated_path_config.offline_cache_dir)
    app = _app(tmp_path)
    for key in (
        training_dataset._VALIDATED_STATE_KEY,
        training_dataset._DEEP_STATE_KEY,
        training_dataset._QH_READINESS_STATE_KEY,
        training_dataset._QH_PREVIEW_STATE_KEY,
    ):
        app.session_state[key] = ("stale-generation", "stale-sentinel")

    def _fail(_request: DatasetBundleSummaryRequest) -> Any:
        raise ValueError("summary-sentinel")

    monkeypatch.setattr(training_dataset, "_cached_bundle_summary", _fail)

    app = app.run()

    assert not app.exception
    assert any("Bundle summary failed" in error.value for error in app.error)
    assert any("summary-sentinel" in error.value for error in app.error)
    assert "stale-sentinel" not in str(app.session_state)


def test_validation_failure_is_section_local_and_drops_retained_evidence(
    monkeypatch: pytest.MonkeyPatch,
    isolated_path_config: PathConfig,
    tmp_path: Path,
) -> None:
    _write_root_store(isolated_path_config.offline_cache_dir)
    app = _app(tmp_path).run()
    validate = next(button for button in app.button if button.label == "Validate bundle")
    app = validate.click().run()
    assert training_dataset._VALIDATED_STATE_KEY in str(app.session_state)

    cached_summary = training_dataset._cached_bundle_summary

    def _fail_validation(request: DatasetBundleSummaryRequest) -> Any:
        if request.validate_rollouts:
            raise ValueError("validation-sentinel")
        return cached_summary(request)

    monkeypatch.setattr(training_dataset, "_cached_bundle_summary", _fail_validation)
    validate = next(button for button in app.button if button.label == "Validate bundle")
    app = validate.click().run()

    assert not app.exception
    assert any("Bundle validation failed" in error.value for error in app.error)
    assert any("validation-sentinel" in error.value for error in app.error)
    assert training_dataset._VALIDATED_STATE_KEY not in str(app.session_state)


@pytest.mark.parametrize(
    ("button_label", "cached_name", "state_key", "diagnostic"),
    [
        (
            "Preflight Q_H corpus",
            "_cached_qh_readiness",
            training_dataset._QH_READINESS_STATE_KEY,
            "Q_H corpus preflight failed",
        ),
        (
            "Deep statistics / target scan",
            "_cached_deep_statistics",
            training_dataset._DEEP_STATE_KEY,
            "Deep statistics scan failed",
        ),
    ],
)  # type: ignore[untyped-decorator]
def test_dispatched_section_failure_drops_stale_evidence(
    button_label: str,
    cached_name: str,
    state_key: str,
    diagnostic: str,
    monkeypatch: pytest.MonkeyPatch,
    isolated_path_config: PathConfig,
    tmp_path: Path,
) -> None:
    _write_root_store(isolated_path_config.offline_cache_dir)
    app = _app(tmp_path).run()
    app.session_state[state_key] = ("stale-generation", "stale-sentinel")
    if button_label == "Preflight Q_H corpus":
        app.session_state[training_dataset._QH_PREVIEW_STATE_KEY] = ("stale-generation", "stale-preview")

    def _fail(*_args: object, **_kwargs: object) -> Any:
        raise ValueError("section-sentinel")

    monkeypatch.setattr(training_dataset, cached_name, _fail)
    button = next(element for element in app.button if element.label == button_label)
    app = button.click().run()

    assert not app.exception
    assert any(diagnostic in error.value for error in app.error)
    assert any("section-sentinel" in error.value for error in app.error)
    assert state_key not in str(app.session_state)
    if button_label == "Preflight Q_H corpus":
        assert training_dataset._QH_PREVIEW_STATE_KEY not in str(app.session_state)


def test_qh_preview_failure_drops_stale_preview(
    monkeypatch: pytest.MonkeyPatch,
    isolated_path_config: PathConfig,
    tmp_path: Path,
) -> None:
    root, _source_hash = _write_root_store(isolated_path_config.offline_cache_dir)
    readiness = QhCorpusReadiness(
        selection=DatasetBundleSelection(root, ()),
        verdict="Ready",
        blockers=(),
        stages=(QhStageReadiness(Stage.TRAIN, True, 1, 1, 1, ("scene-a",), 1, {}),),
        contract={},
        actor_contract={},
        loader_settings={"batch_size": 1, "seed": 0},
        scene_disjoint=True,
        storage=(),
    )
    monkeypatch.setattr(training_dataset, "_cached_qh_readiness", lambda *_args, **_kwargs: readiness)
    app = _app(tmp_path).run()
    preflight = next(button for button in app.button if button.label == "Preflight Q_H corpus")
    app = preflight.click().run()
    app.session_state[training_dataset._QH_PREVIEW_STATE_KEY] = ("stale-generation", "stale-preview")

    def _fail_preview(*_args: object, **_kwargs: object) -> Any:
        raise ValueError("preview-sentinel")

    monkeypatch.setattr(training_dataset, "_cached_qh_preview", _fail_preview)
    preview = next(button for button in app.button if button.label == "Preview one chain and batch")
    app = preview.click().run()

    assert not app.exception
    assert any("Q_H preview failed" in error.value for error in app.error)
    assert any("preview-sentinel" in error.value for error in app.error)
    assert training_dataset._QH_PREVIEW_STATE_KEY not in str(app.session_state)


def test_unexpected_acquisition_failure_retains_exception_type_in_app_diagnostics(
    monkeypatch: pytest.MonkeyPatch,
    isolated_path_config: PathConfig,
    tmp_path: Path,
) -> None:
    _write_root_store(isolated_path_config.offline_cache_dir)

    def _fail(_request: DatasetBundleSummaryRequest) -> Any:
        raise RuntimeError("unexpected-summary-sentinel")

    monkeypatch.setattr(training_dataset, "_cached_bundle_summary", _fail)
    app = _app(tmp_path).run()

    assert len(app.exception) == 1
    assert app.exception[0].value == "unexpected-summary-sentinel"
    assert "RuntimeError" in "\n".join(app.exception[0].stack_trace)


@pytest.mark.parametrize("acquisition", ["summary", "validation", "deep", "readiness", "preview"])  # type: ignore[untyped-decorator]
def test_warmed_cache_hits_remain_guarded_before_and_after_acquisition(
    acquisition: str,
    monkeypatch: pytest.MonkeyPatch,
    isolated_path_config: PathConfig,
) -> None:
    root, _source_hash = _write_root_store(isolated_path_config.offline_cache_dir)
    selection, generation = capture_dataset_bundle_generation(root, ())
    root_arg = root.as_posix()
    domain_calls = 0
    acquire: Callable[[], Any]

    if acquisition in {"summary", "validation"}:
        cache_owner = training_dataset._cached_bundle_summary_inner
        validate_rollouts = acquisition == "validation"
        expected = build_dataset_bundle_summary(selection, validate_rollouts=validate_rollouts)

        def counted_summary(_request: DatasetBundleSummaryRequest) -> Any:
            nonlocal domain_calls
            domain_calls += 1
            return expected

        monkeypatch.setattr(training_dataset, "inspect_dataset_bundle", counted_summary)

        def acquire_summary() -> Any:
            return training_dataset._cached_bundle_summary(
                DatasetBundleSummaryRequest(
                    selection=selection,
                    generation=generation,
                    validate_rollouts=validate_rollouts,
                )
            )

        acquire = acquire_summary
    elif acquisition == "deep":
        cache_owner = training_dataset._cached_deep_statistics_inner

        def counted_deep(_selection: DatasetBundleSelection) -> dict[str, Any]:
            nonlocal domain_calls
            domain_calls += 1
            return {"aggregate": {}}

        monkeypatch.setattr(training_dataset, "compute_dataset_bundle_deep_statistics", counted_deep)

        def acquire_deep() -> Any:
            return training_dataset._cached_deep_statistics(root_arg, (), generation)

        acquire = acquire_deep
    elif acquisition == "readiness":
        cache_owner = training_dataset._cached_qh_readiness_inner
        expected_readiness = QhCorpusReadiness(selection, "Blocked", ("fixture",), (), None, None, {}, None, ())

        def counted_readiness(*_args: Any, **_kwargs: Any) -> QhCorpusReadiness:
            nonlocal domain_calls
            domain_calls += 1
            return expected_readiness

        monkeypatch.setattr(training_dataset, "build_qh_corpus_readiness", counted_readiness)

        def acquire_readiness() -> Any:
            return training_dataset._cached_qh_readiness(
                root_arg, (), generation, 1, 0, training_dataset._QH_READINESS_CONTRACT
            )

        acquire = acquire_readiness
    else:
        cache_owner = training_dataset._cached_qh_preview_inner
        preview = QhBatchPreview(Stage.TRAIN, 0, {}, 1, ({},), (1,), {}, {}, 0, 0, 1, 1)

        def counted_preview(*_args: Any, **_kwargs: Any) -> QhBatchPreview:
            nonlocal domain_calls
            domain_calls += 1
            return preview

        monkeypatch.setattr(training_dataset, "preview_qh_batch", counted_preview)

        def acquire_preview() -> Any:
            return training_dataset._cached_qh_preview(
                root_arg, (), generation, "train", 0, 1, 0, training_dataset._QH_READINESS_CONTRACT
            )

        acquire = acquire_preview

    cache_owner.clear()
    acquire()
    assert domain_calls == 1
    guard_calls = 0

    def counted_guard(_generation: Any) -> None:
        nonlocal guard_calls
        guard_calls += 1

    monkeypatch.setattr(training_dataset, "assert_dataset_bundle_generation_current", counted_guard)
    acquire()
    assert guard_calls == 2
    assert domain_calls == 1

    monkeypatch.undo()
    manifest = root / "manifest.json"
    manifest.write_bytes(manifest.read_bytes() + b"\n")
    with pytest.raises(DatasetBundleGenerationChangedError):
        acquire()
    assert domain_calls == 1
    cache_owner.clear()


@pytest.mark.parametrize("acquisition", ["deep", "readiness", "preview"])  # type: ignore[untyped-decorator]
def test_explicit_acquisition_rejects_replacement_under_stale_generation(
    acquisition: str,
    monkeypatch: pytest.MonkeyPatch,
    isolated_path_config: PathConfig,
) -> None:
    root, _source_hash = _write_root_store(isolated_path_config.offline_cache_dir)
    _selection, generation = capture_dataset_bundle_generation(root, ())

    def _replace_manifest(*_args: object, **_kwargs: object) -> Any:
        manifest_path = root / "manifest.json"
        payload = json.loads(manifest_path.read_text(encoding="utf-8"))
        payload["replacement_during_acquisition"] = acquisition
        manifest_path.write_text(json.dumps(payload), encoding="utf-8")
        return object()

    root_arg = root.as_posix()
    with pytest.raises(DatasetBundleGenerationChangedError):
        if acquisition == "deep":
            monkeypatch.setattr(training_dataset, "compute_dataset_bundle_deep_statistics", _replace_manifest)
            _cached_deep_statistics(root_arg, (), generation)
        elif acquisition == "readiness":
            monkeypatch.setattr(training_dataset, "build_qh_corpus_readiness", _replace_manifest)
            _cached_qh_readiness(root_arg, (), generation, 1, 0, training_dataset._QH_READINESS_CONTRACT)
        else:
            monkeypatch.setattr(training_dataset, "preview_qh_batch", _replace_manifest)
            _cached_qh_preview(root_arg, (), generation, "train", 0, 1, 0, training_dataset._QH_READINESS_CONTRACT)


@pytest.mark.parametrize("acquisition", ["deep", "readiness", "preview"])  # type: ignore[untyped-decorator]
def test_cached_acquisition_rejects_stale_generation_before_domain_call(
    acquisition: str,
    monkeypatch: pytest.MonkeyPatch,
    isolated_path_config: PathConfig,
) -> None:
    root, _source_hash = _write_root_store(isolated_path_config.offline_cache_dir)
    _selection, generation = capture_dataset_bundle_generation(root, ())
    manifest = root / "manifest.json"
    manifest.write_bytes(manifest.read_bytes() + b"\n")

    def _unexpected(*_args: object, **_kwargs: object) -> Any:
        pytest.fail(f"{acquisition} domain function ran for a stale generation")

    root_arg = root.as_posix()
    with pytest.raises(DatasetBundleGenerationChangedError):
        if acquisition == "deep":
            monkeypatch.setattr(training_dataset, "compute_dataset_bundle_deep_statistics", _unexpected)
            _cached_deep_statistics(root_arg, (), generation)
        elif acquisition == "readiness":
            monkeypatch.setattr(training_dataset, "build_qh_corpus_readiness", _unexpected)
            _cached_qh_readiness(root_arg, (), generation, 1, 0, training_dataset._QH_READINESS_CONTRACT)
        else:
            monkeypatch.setattr(training_dataset, "preview_qh_batch", _unexpected)
            _cached_qh_preview(root_arg, (), generation, "train", 0, 1, 0, training_dataset._QH_READINESS_CONTRACT)


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


def test_malformed_promotion_marker_remains_visible_and_contributes_no_totals(
    isolated_path_config: PathConfig,
    tmp_path: Path,
) -> None:
    _root, source_hash = _write_root_store(isolated_path_config.offline_cache_dir)
    rollout = _write_rollout_store(isolated_path_config.offline_cache_dir, source_hash)
    for name in ("_SUCCESS.json", "_owner.json"):
        (rollout / name).write_text("{}", encoding="utf-8")
    app = _app(tmp_path).run()
    app.multiselect[0].set_value([rollout.as_posix()])
    app = app.run()

    assert not app.exception
    metrics = _metrics(app)
    assert metrics["Compatible rollout stores"] == "0 / 1"
    assert metrics["Rollouts"] == "0"
    assert metrics["Rollout steps"] == "0"
    assert metrics["Candidates"] == "0"
    visible = "\n".join(item.value for item in [*app.markdown, *app.caption, *app.error, *app.success])
    assert rollout.name in visible
    assert "rollout_promotion_invalid" in visible


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
    selection_a = "generation-a"
    baseline = _qh_preview_identity(
        selection_a,
        stage="train",
        chain_index=0,
        batch_size=4,
        seed=7,
    )
    evidence = _qh_preview_evidence()
    state = (baseline, evidence)

    assert _qh_preview_for_identity(state, baseline) is evidence
    for changed in (
        _qh_preview_identity("generation-b", stage="train", chain_index=0, batch_size=4, seed=7),
        _qh_preview_identity(selection_a, stage="val", chain_index=0, batch_size=4, seed=7),
        _qh_preview_identity(selection_a, stage="train", chain_index=1, batch_size=4, seed=7),
        _qh_preview_identity(selection_a, stage="train", chain_index=0, batch_size=8, seed=7),
        _qh_preview_identity(selection_a, stage="train", chain_index=0, batch_size=4, seed=8),
    ):
        assert _qh_preview_for_identity(state, changed) is None


def test_qh_readiness_hides_stale_preflight_after_loader_control_changes() -> None:
    selection = "generation"
    baseline = _qh_readiness_identity(selection, batch_size=4, seed=7)
    evidence = QhCorpusReadiness(DatasetBundleSelection(Path("/root"), ()), "Blocked", (), (), None, None, {}, None, ())
    state = (baseline, evidence)

    assert _qh_readiness_for_identity(state, baseline) is evidence
    assert _qh_readiness_for_identity(state, _qh_readiness_identity(selection, batch_size=8, seed=7)) is None
    assert _qh_readiness_for_identity(state, _qh_readiness_identity(selection, batch_size=4, seed=8)) is None


@pytest.mark.parametrize(
    ("helper", "identity", "wrong_payload"),
    [
        (_qh_readiness_for_identity, _qh_readiness_identity("generation", batch_size=1, seed=0), object()),
        (
            _qh_preview_for_identity,
            _qh_preview_identity("generation", stage="train", chain_index=0, batch_size=1, seed=0),
            object(),
        ),
    ],
)
def test_qh_retained_helpers_reject_untrusted_state(
    helper: Callable[[Any, Any], Any],
    identity: Any,
    wrong_payload: object,
) -> None:
    for state in (object(), {}, (), (identity,), (identity, wrong_payload, None), [identity, wrong_payload]):
        assert helper(state, identity) is None
    assert helper((identity, wrong_payload), identity) is None


def test_exact_key_malformed_qh_state_is_removed_page_locally(
    isolated_path_config: PathConfig,
    tmp_path: Path,
) -> None:
    root, _source_hash = _write_root_store(isolated_path_config.offline_cache_dir)
    _selection, generation = capture_dataset_bundle_generation(root, ())
    readiness_identity = _qh_readiness_identity(generation.generation_digest, batch_size=1, seed=0)
    app = _app(tmp_path).run()
    app.session_state[training_dataset._QH_READINESS_STATE_KEY] = (readiness_identity, object())
    app.session_state[training_dataset._QH_PREVIEW_STATE_KEY] = ("stale", object())

    app = app.run()

    assert not app.exception
    assert training_dataset._QH_READINESS_STATE_KEY not in str(app.session_state)
    assert training_dataset._QH_PREVIEW_STATE_KEY not in str(app.session_state)


def test_exact_key_malformed_qh_preview_is_removed_page_locally(
    isolated_path_config: PathConfig,
    tmp_path: Path,
) -> None:
    root, _source_hash = _write_root_store(isolated_path_config.offline_cache_dir)
    _selection, generation = capture_dataset_bundle_generation(root, ())
    readiness_identity = _qh_readiness_identity(generation.generation_digest, batch_size=1, seed=0)
    preview_identity = _qh_preview_identity(
        generation.generation_digest,
        stage="train",
        chain_index=0,
        batch_size=1,
        seed=0,
    )
    app = _app(tmp_path).run()
    app.session_state[training_dataset._QH_READINESS_STATE_KEY] = (readiness_identity, _ready_qh_evidence(root))
    app.session_state[training_dataset._QH_PREVIEW_STATE_KEY] = (preview_identity, object())

    app = app.run()

    assert not app.exception
    assert training_dataset._QH_READINESS_STATE_KEY in str(app.session_state)
    assert training_dataset._QH_PREVIEW_STATE_KEY not in str(app.session_state)


def test_qh_control_change_clears_displayed_readiness_and_preview(monkeypatch: pytest.MonkeyPatch) -> None:
    state = {
        "training_dataset_qh_readiness": ("old-controls", object()),
        "training_dataset_qh_preview": ("old-controls", object()),
    }
    monkeypatch.setattr(st, "session_state", state)

    _clear_qh_results_for_control_change()

    assert state == {}


def test_training_dataset_refresh_is_page_local_to_stored_rollouts(monkeypatch: pytest.MonkeyPatch) -> None:
    state = {
        training_dataset._VALIDATED_STATE_KEY: object(),
        training_dataset._DEEP_STATE_KEY: object(),
        training_dataset._QH_READINESS_STATE_KEY: object(),
        training_dataset._QH_PREVIEW_STATE_KEY: object(),
        stored_rollout_session.CORPUS_SUMMARY_STATE_KEY: object(),
        "unrelated:test-sentinel": object(),
    }
    monkeypatch.setattr(st, "session_state", state)
    monkeypatch.setattr(
        stored_rollout_session,
        "clear_rollout_page_caches",
        lambda: pytest.fail("Training Dataset refresh cleared Stored Rollouts"),
    )

    training_dataset._clear_training_dataset_caches()

    assert stored_rollout_session.CORPUS_SUMMARY_STATE_KEY in state
    assert "unrelated:test-sentinel" in state
    assert not any(key.startswith("training_dataset_") for key in state)
    assert "_stored_rollouts" not in inspect.getsource(training_dataset._clear_training_dataset_caches)


def test_page_retained_slots_reject_invalid_or_stale_values() -> None:
    evidence = cast(Any, SimpleNamespace())
    assert _retained_bundle_evidence(("digest", evidence), "digest") is None
    assert _retained_bundle_evidence({"digest": evidence}, "digest") is None
    assert _retained_deep_statistics(("other", {"aggregate": {}}), "digest") is None
    assert _retained_deep_statistics(("digest", {"aggregate": {}}), "digest") == {"aggregate": {}}


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
    expected = evidence.to_jsonable()
    expected["deep_statistics"] = deep
    expected["q_h_readiness"] = None
    expected["q_h_batch_preview"] = None
    assert first == (json.dumps(expected, indent=2, sort_keys=True) + "\n").encode()
    assert payload["aggregate"]["persisted_rollout_target_rows"] == 2
    assert payload["deep_statistics"]["aggregate"] == deep["aggregate"]


def test_download_payload_uses_displayed_evidence_without_reacquisition(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    root, source_hash = _write_root_store(tmp_path)
    rollout = _write_rollout_store(tmp_path, source_hash)
    evidence = build_dataset_bundle_summary(DatasetBundleSelection(root, (rollout,)))
    monkeypatch.setattr(
        training_dataset,
        "inspect_dataset_bundle",
        lambda _request: pytest.fail("download must not reacquire evidence"),
    )

    payload = json.loads(_download_payload(evidence, None))

    assert payload["generation"]["generation_digest"] == evidence.generation.generation_digest


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
