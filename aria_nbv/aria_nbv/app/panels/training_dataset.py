"""Training-dataset composition hub for VIN roots and rollout supervision.

The page composes one immutable VIN observation store with an explicit set of
rollout stores through :mod:`aria_nbv.dataset_bundle`. It owns session-local
selection, cached read-only inspection, readiness presentation, and evidence
export; it never repairs stores or persists a training-bundle configuration.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pandas as pd
import streamlit as st

from ...configs import PathConfig
from ...dataset_bundle import (
    DatasetBundleEvidence,
    DatasetBundleSelection,
    QhBatchPreview,
    QhCorpusReadiness,
    build_dataset_bundle_summary,
    build_qh_corpus_readiness,
    compute_dataset_bundle_deep_statistics,
    preview_qh_batch,
)
from ...dataset_topology import discover_vin_store_dirs
from ...rollouts.inspection import discover_rollout_store_paths

_VALIDATED_STATE_KEY = "training_dataset_validated_evidence"
_DEEP_STATE_KEY = "training_dataset_deep_statistics"
_QH_READINESS_STATE_KEY = "training_dataset_qh_readiness"
_QH_PREVIEW_STATE_KEY = "training_dataset_qh_preview"
_QH_BATCH_SIZE_KEY = "training_dataset_qh_batch_size"
_QH_SEED_KEY = "training_dataset_qh_seed"

QhReadinessIdentity = tuple[tuple[Any, ...], int, int]
QhPreviewIdentity = tuple[tuple[Any, ...], str, int, int, int]


def _artifact_identity(path: Path) -> tuple[tuple[str, int, int], ...]:
    """Return a bounded cache key for persisted artifact metadata.

    Immutable payload chunks are intentionally excluded: the lightweight page
    keys manifests, root Zarr metadata, and split indexes without recursively
    statting every store file. Metadata that disappears during this cache-key
    snapshot is omitted; the subsequent evidence read still reports an
    unreadable or incomplete store explicitly.
    """

    resolved = path.expanduser().resolve()
    if resolved.is_file():
        candidates = (resolved,)
    elif resolved.exists():
        metadata_names = ("manifest.json", "sample_index.jsonl", ".zattrs", ".zgroup", ".zarray", "zarr.json")
        direct = [resolved / name for name in metadata_names]
        split_metadata = list((resolved / "splits").glob("*.npy"))
        candidates = tuple(child for child in (*direct, *split_metadata) if child.is_file())
    else:
        candidates = ()
    rows: list[tuple[str, int, int]] = []
    for child in sorted(candidates, key=lambda item: item.as_posix()):
        try:
            stat = child.stat()
        except OSError:
            continue
        rows.append((child.as_posix(), stat.st_mtime_ns, stat.st_size))
    return tuple(rows)


def _selection_cache_key(selection: DatasetBundleSelection) -> tuple[Any, ...]:
    """Return the session-result key for one immutable bundle snapshot."""

    return (
        selection.root_store.as_posix(),
        tuple(path.as_posix() for path in selection.rollout_stores),
        _artifact_identity(selection.root_store),
        tuple(_artifact_identity(path) for path in selection.rollout_stores),
    )


def _qh_preview_identity(
    selection_identity: tuple[Any, ...],
    *,
    stage: str,
    chain_index: int,
    batch_size: int,
    seed: int,
) -> QhPreviewIdentity:
    """Return the exact selection and controls that produced one preview."""

    return (selection_identity, stage, chain_index, batch_size, seed)


def _qh_readiness_identity(
    selection_identity: tuple[Any, ...],
    *,
    batch_size: int,
    seed: int,
) -> QhReadinessIdentity:
    """Return the exact selection and loader controls that produced readiness."""

    return (selection_identity, batch_size, seed)


def _qh_readiness_for_identity(
    readiness_state: tuple[QhReadinessIdentity, QhCorpusReadiness] | None,
    identity: QhReadinessIdentity,
) -> QhCorpusReadiness | None:
    """Return readiness evidence only when its selection and loader controls match."""

    return readiness_state[1] if readiness_state is not None and readiness_state[0] == identity else None


def _qh_preview_for_identity(
    preview_state: tuple[QhPreviewIdentity, QhBatchPreview] | None,
    identity: QhPreviewIdentity,
) -> QhBatchPreview | None:
    """Return preview evidence only when its selection and controls still match."""

    return preview_state[1] if preview_state is not None and preview_state[0] == identity else None


@st.cache_data(show_spinner="Inspecting manifests and indexes…", max_entries=32)
def _cached_bundle_summary(
    root_store: str,
    rollout_stores: tuple[str, ...],
    artifact_identity: tuple[Any, ...],
    *,
    validate_rollouts: bool,
) -> DatasetBundleEvidence:
    """Build lightweight or validated evidence for one artifact identity."""

    del artifact_identity
    selection = DatasetBundleSelection(
        Path(root_store),
        tuple(Path(path) for path in rollout_stores),
    )
    return build_dataset_bundle_summary(
        selection,
        validate_rollouts=validate_rollouts,
    )


@st.cache_data(show_spinner="Scanning rollout arrays and target identities…", max_entries=16)
def _cached_deep_statistics(
    root_store: str,
    rollout_stores: tuple[str, ...],
    artifact_identity: tuple[Any, ...],
) -> dict[str, Any]:
    """Return deep rollout statistics cached by immutable artifact identity."""

    del artifact_identity
    selection = DatasetBundleSelection(
        Path(root_store),
        tuple(Path(path) for path in rollout_stores),
    )
    return compute_dataset_bundle_deep_statistics(selection)


@st.cache_data(show_spinner="Constructing Q_H datasets and DataModule…", max_entries=8)
def _cached_qh_readiness(
    root_store: str,
    rollout_stores: tuple[str, ...],
    artifact_identity: tuple[Any, ...],
    batch_size: int,
    seed: int,
) -> QhCorpusReadiness:
    """Cross the real Q_H dataset/DataModule seam after explicit request."""

    del artifact_identity
    return build_qh_corpus_readiness(
        DatasetBundleSelection(Path(root_store), tuple(Path(path) for path in rollout_stores)),
        batch_size=batch_size,
        seed=seed,
    )


@st.cache_data(show_spinner="Reading one Q_H chain and collating one batch…", max_entries=8)
def _cached_qh_preview(
    root_store: str,
    rollout_stores: tuple[str, ...],
    artifact_identity: tuple[Any, ...],
    stage: str,
    chain_index: int,
    batch_size: int,
    seed: int,
) -> QhBatchPreview:
    """Materialize one bounded chain and DataLoader batch after explicit request."""

    del artifact_identity
    return preview_qh_batch(
        DatasetBundleSelection(Path(root_store), tuple(Path(path) for path in rollout_stores)),
        stage=stage,
        chain_index=chain_index,
        batch_size=batch_size,
        seed=seed,
    )


def _clear_training_dataset_caches() -> None:
    """Clear this page's cached read models and selection-bound session results."""

    _cached_bundle_summary.clear()
    _cached_deep_statistics.clear()
    _cached_qh_readiness.clear()
    _cached_qh_preview.clear()
    for key in (
        _VALIDATED_STATE_KEY,
        _DEEP_STATE_KEY,
        _QH_READINESS_STATE_KEY,
        _QH_PREVIEW_STATE_KEY,
    ):
        st.session_state.pop(key, None)


def _manual_paths(value: str) -> tuple[Path, ...]:
    """Parse newline-separated manual paths without fabricating artifacts."""

    return tuple(Path(line.strip()).expanduser() for line in value.splitlines() if line.strip())


def _select_root_store(discovered: list[Path]) -> Path | None:
    """Render exactly-one root-store selection with a manual-path escape hatch."""

    manual_label = "Enter a path manually…"
    options = [path.as_posix() for path in discovered]
    choice = st.selectbox(
        "VIN root observation store",
        options=[*options, manual_label],
        index=0 if options else len(options),
        help="Select exactly one immutable VIN store. Discovery reads filenames only.",
    )
    if choice != manual_label:
        return Path(choice)
    manual = st.text_input(
        "Manual VIN root path",
        placeholder="/path/to/vin_offline_store",
    ).strip()
    return Path(manual).expanduser() if manual else None


def _select_rollout_stores(discovered: list[Path]) -> tuple[Path, ...]:
    """Render explicit multi-store rollout selection and manual additions."""

    options = [path.as_posix() for path in discovered]
    selected = st.multiselect(
        "Rollout supervision stores",
        options=options,
        default=[],
        help="Only explicitly selected stores participate in the bundle.",
    )
    manual = st.text_area(
        "Additional rollout paths",
        placeholder="One .zarr directory per line",
        height=80,
    )
    return tuple(Path(path) for path in selected) + _manual_paths(manual)


def _format_bytes(value: Any) -> str:
    """Format a byte count for compact metric cards."""

    if not isinstance(value, int | float):
        return "Unavailable"
    size = float(value)
    for unit in ("B", "KiB", "MiB", "GiB", "TiB"):
        if abs(size) < 1024.0 or unit == "TiB":
            return f"{size:.1f} {unit}"
        size /= 1024.0
    return f"{size:.1f} TiB"


def _metric_value(value: Any, *, pending: str = "Unavailable") -> str:
    """Render optional counts without silently converting missing evidence to zero."""

    return pending if value is None else f"{int(value):,}"


def _deep_metric_value(aggregate: dict[str, Any], key: str, *, deep_available: bool) -> str:
    """Format one deep denominator together with its completeness status."""

    if not deep_available:
        return "Deep scan required"
    value = aggregate.get(key)
    status = aggregate.get(f"{key}_status", "unavailable")
    if value is None or status == "unavailable":
        return "Unavailable"
    rendered = f"{int(value):,}"
    return f"{rendered} (partial)" if status == "partial" else rendered


def _render_verdict(evidence: DatasetBundleEvidence) -> None:
    """Render the strict bundle verdict with its operational meaning."""

    messages = {
        "Ready": "All selected rollout stores passed compatibility and read-only validation.",
        "Incomplete": "The selected bundle is structurally inspectable, but required validation or optional evidence is pending.",
        "Blocked": "At least one selected store has a training-critical incompatibility. Blocked stores remain visible and are excluded from totals.",
    }
    renderer = {
        "Ready": st.success,
        "Incomplete": st.warning,
        "Blocked": st.error,
    }[evidence.verdict]
    renderer(f"**{evidence.verdict}** — {messages[evidence.verdict]}")


def _render_summary_metrics(
    readiness: QhCorpusReadiness | None,
) -> None:
    """Render only admission quantities established by the real Q_H preflight."""

    pending = "Preflight required"
    train_scenes: str = pending
    chain_count: str = pending
    state_count: str = pending
    trainable_count: str = pending
    storage_per_trainable: str = pending
    if readiness is not None and readiness.verdict == "Ready":
        train = next((row for row in readiness.stages if row.stage.value == "train"), None)
        train_scenes = _metric_value(None if train is None else len(train.scene_ids))
        chain_count = _metric_value(sum(row.chain_count for row in readiness.stages))
        state_count = _metric_value(sum(row.state_count for row in readiness.stages))
        trainable_count = _metric_value(sum(row.trainable_candidate_count for row in readiness.stages))
        storage = next(
            (metric for metric in readiness.storage if metric.name == "rollout_bytes_per_trainable_candidate"),
            None,
        )
        storage_per_trainable = (
            "Unavailable" if storage is None or storage.value is None else _format_bytes(storage.value)
        )
    elif readiness is not None:
        train_scenes = chain_count = state_count = trainable_count = storage_per_trainable = "Blocked"

    columns = st.columns(5)
    columns[0].metric("Train scenes", train_scenes)
    columns[1].metric("Q_H chains", chain_count)
    columns[2].metric("Q_H states", state_count)
    columns[3].metric("Trainable candidates", trainable_count)
    columns[4].metric("Storage / trainable", storage_per_trainable)


def _rollout_rows(evidence: DatasetBundleEvidence) -> list[dict[str, Any]]:
    """Project compatibility, schema, profile, split, and count evidence."""

    rows: list[dict[str, Any]] = []
    for row in evidence.rollouts:
        counts = row.get("counts", {})
        rows.append(
            {
                "store": Path(str(row["path"])).name,
                "path": row["path"],
                "included": bool(row.get("included_in_training_totals")),
                "validation": row.get("validation_status"),
                "profile": row.get("profile"),
                "schema": row.get("schema_version"),
                "horizon": row.get("horizon"),
                "source_splits": json.dumps(row.get("source_splits", {}), sort_keys=True),
                "rollouts": counts.get("rollouts"),
                "steps": counts.get("steps"),
                "candidates": counts.get("candidates"),
                "target_rows": counts.get("targets"),
                "storage": _format_bytes(row.get("storage_bytes")),
                "storage_status": row.get("storage_status"),
            }
        )
    return rows


def _download_payload(
    evidence: DatasetBundleEvidence,
    deep: dict[str, Any] | None,
    qh_readiness: QhCorpusReadiness | None = None,
    qh_preview: QhBatchPreview | None = None,
) -> bytes:
    """Serialize deterministic, complete bundle evidence for download."""

    payload = evidence.to_jsonable()
    payload["deep_statistics"] = deep
    payload["q_h_readiness"] = None if qh_readiness is None else qh_readiness.to_jsonable()
    payload["q_h_batch_preview"] = None if qh_preview is None else qh_preview.to_jsonable()
    return (json.dumps(payload, indent=2, sort_keys=True) + "\n").encode("utf-8")


def render_training_dataset_page() -> None:  # pragma: no cover - Streamlit UI
    """Render the read-only root-store and rollout-supervision composition hub."""

    st.title("Training Dataset")
    st.caption(
        "Compose one immutable VIN root observation store with explicit rollout supervision stores, "
        "then audit whether the resulting Q_H training bundle is usable."
    )
    from ._stored_rollouts.session import clear_rollout_page_caches

    if st.button(
        "Refresh rollout caches",
        help="Clear cached rollout and training-bundle read models after creating or replacing an artifact.",
    ):
        clear_rollout_page_caches()
        st.rerun()

    paths = PathConfig()
    discovered_roots = discover_vin_store_dirs(paths.offline_cache_dir)
    discovered_rollouts = discover_rollout_store_paths(paths.offline_cache_dir)
    with st.expander("Bundle selection", expanded=True):
        root_store = _select_root_store(discovered_roots)
        rollout_stores = _select_rollout_stores(discovered_rollouts)
        st.caption(
            f"Discovered {len(discovered_roots)} VIN root store(s) and "
            f"{len(discovered_rollouts)} rollout store candidate(s) below {paths.offline_cache_dir}."
        )

    if root_store is None:
        st.info("Select or enter exactly one VIN root observation store to inspect a training bundle.")
        st.markdown(
            "Use **Training Data → Root Observation Store** for shard-level VIN diagnostics and "
            "**Training Data → Rollout Supervision** for rollout-step and candidate-level inspection."
        )
        return

    try:
        selection = DatasetBundleSelection(root_store, rollout_stores)
    except ValueError as exc:
        st.error(str(exc))
        return
    identity = _selection_cache_key(selection)
    root_text = selection.root_store.as_posix()
    rollout_texts = tuple(path.as_posix() for path in selection.rollout_stores)
    light = _cached_bundle_summary(
        root_text,
        rollout_texts,
        identity,
        validate_rollouts=False,
    )

    validate = st.button("Validate bundle", type="primary", width="stretch")
    if validate:
        st.session_state[_VALIDATED_STATE_KEY] = (
            identity,
            _cached_bundle_summary(
                root_text,
                rollout_texts,
                identity,
                validate_rollouts=True,
            ),
        )
    validated_state = st.session_state.get(_VALIDATED_STATE_KEY)
    evidence = validated_state[1] if validated_state and validated_state[0] == identity else light
    deep_state = st.session_state.get(_DEEP_STATE_KEY)
    deep = deep_state[1] if deep_state and deep_state[0] == identity else None
    qh_readiness: QhCorpusReadiness | None = None
    qh_preview: QhBatchPreview | None = None

    _render_verdict(evidence)

    readiness_tab, qh_tab, details_tab = st.tabs(["Readiness", "Q_H corpus", "Details"])
    with readiness_tab:
        st.subheader("Bundle readiness")
        root_samples = sum(int(value) for value in evidence.root.get("split_counts", {}).values())
        included_rollouts = [row for row in evidence.rollouts if bool(row.get("included_in_training_totals"))]
        rollout_counts = [row.get("counts", {}) for row in included_rollouts]
        summary_columns = st.columns(5)
        summary_columns[0].metric("Root samples", f"{root_samples:,}")
        summary_columns[1].metric("Compatible rollout stores", f"{len(included_rollouts)} / {len(evidence.rollouts)}")
        summary_columns[2].metric(
            "Rollouts", _metric_value(sum(int(count.get("rollouts", 0)) for count in rollout_counts))
        )
        summary_columns[3].metric(
            "Rollout steps", _metric_value(sum(int(count.get("steps", 0)) for count in rollout_counts))
        )
        summary_columns[4].metric(
            "Candidates", _metric_value(sum(int(count.get("candidates", 0)) for count in rollout_counts))
        )
        st.subheader("Root splits")
        split_rows = [
            {"split": split, "samples": count} for split, count in sorted(evidence.root.get("split_counts", {}).items())
        ]
        st.dataframe(pd.DataFrame(split_rows), hide_index=True, width="stretch")
        st.subheader("Selected rollout stores")
        rollout_rows = _rollout_rows(evidence)
        if rollout_rows:
            st.dataframe(pd.DataFrame(rollout_rows), hide_index=True, width="stretch")
        else:
            st.info("No rollout supervision store is selected.")
        finding_rows = [finding.to_jsonable() for finding in evidence.findings]
        if finding_rows:
            st.subheader("Blockers and pending evidence")
            st.dataframe(pd.DataFrame(finding_rows), hide_index=True, width="stretch")
        else:
            st.success("No readiness findings.")
    with qh_tab:
        st.subheader("Q_H dataset and collation readiness")
        st.caption(
            "This action constructs the selected stage datasets and the production "
            "Q_H DataModule. "
            "It does not create a model or Trainer."
        )
        controls = st.columns(3)
        batch_size = int(
            controls[0].number_input(
                "Q_H batch size",
                min_value=1,
                value=1,
                step=1,
                key=_QH_BATCH_SIZE_KEY,
            )
        )
        seed = int(
            controls[1].number_input(
                "Q_H loader seed",
                min_value=0,
                value=0,
                step=1,
                key=_QH_SEED_KEY,
            )
        )
        readiness_identity = _qh_readiness_identity(identity, batch_size=batch_size, seed=seed)
        qh_state = st.session_state.get(_QH_READINESS_STATE_KEY)
        qh_readiness = _qh_readiness_for_identity(qh_state, readiness_identity)
        if controls[2].button("Preflight Q_H corpus", type="primary", width="stretch"):
            qh_readiness = _cached_qh_readiness(
                root_text,
                rollout_texts,
                identity,
                batch_size,
                seed,
            )
            st.session_state[_QH_READINESS_STATE_KEY] = (readiness_identity, qh_readiness)
            st.session_state.pop(_QH_PREVIEW_STATE_KEY, None)
            qh_preview = None
        if qh_readiness is None:
            st.info("Run the preflight to prove stage admission, joins, DataModule construction, and factual counts.")
        else:
            renderer = st.success if qh_readiness.verdict == "Ready" else st.error
            renderer(f"Q_H corpus: {qh_readiness.verdict}")
            if qh_readiness.blockers:
                st.dataframe(pd.DataFrame({"blocking_reason": qh_readiness.blockers}), hide_index=True, width="stretch")
            if qh_readiness.stages:
                stage_rows = [
                    {
                        "stage": row.stage.value,
                        "included": row.included,
                        "chains": row.chain_count,
                        "states": row.state_count,
                        "trainable_candidates": row.trainable_candidate_count,
                        "scenes": len(row.scene_ids),
                        "max_realized_horizon": row.max_horizon,
                    }
                    for row in qh_readiness.stages
                ]
                st.dataframe(pd.DataFrame(stage_rows), hide_index=True, width="stretch")
                storage_rows = [
                    {
                        "metric": metric.name,
                        "value": metric.value,
                        "unit": metric.unit,
                        "bytes": metric.numerator_bytes,
                        "denominator": metric.denominator,
                        "status": metric.reason or "available",
                    }
                    for metric in qh_readiness.storage
                ]
                st.dataframe(pd.DataFrame(storage_rows), hide_index=True, width="stretch")
            if qh_readiness.verdict == "Ready":
                included_stages = [row.stage.value for row in qh_readiness.stages if row.included]
                preview_controls = st.columns(3)
                preview_stage = preview_controls[0].selectbox("Preview stage", included_stages)
                preview_index = int(
                    preview_controls[1].number_input("Preview chain index", min_value=0, value=0, step=1)
                )
                preview_identity = _qh_preview_identity(
                    identity,
                    stage=preview_stage,
                    chain_index=preview_index,
                    batch_size=batch_size,
                    seed=seed,
                )
                preview_state = st.session_state.get(_QH_PREVIEW_STATE_KEY)
                qh_preview = _qh_preview_for_identity(preview_state, preview_identity)
                if preview_controls[2].button("Preview one chain and batch", width="stretch"):
                    try:
                        qh_preview = _cached_qh_preview(
                            root_text,
                            rollout_texts,
                            identity,
                            preview_stage,
                            preview_index,
                            batch_size,
                            seed,
                        )
                    except Exception as exc:
                        st.error(f"Q_H preview failed: {type(exc).__name__}: {exc}")
                    else:
                        st.session_state[_QH_PREVIEW_STATE_KEY] = (preview_identity, qh_preview)
            if qh_preview is not None:
                preview_cols = st.columns(4)
                preview_cols[0].metric("Selected chain steps", qh_preview.selected_chain_steps)
                preview_cols[1].metric("Batch trainable", qh_preview.trainable_candidate_count)
                preview_cols[2].metric("Step padding", qh_preview.step_padding_count)
                preview_cols[3].metric("Candidate padding", qh_preview.candidate_padding_count)
                st.dataframe(
                    pd.DataFrame(
                        [
                            {"tensor": name, "shape": list(shape), "dtype": qh_preview.dtypes[name]}
                            for name, shape in qh_preview.shapes.items()
                        ]
                    ),
                    hide_index=True,
                    width="stretch",
                )
    _render_summary_metrics(qh_readiness)
    with details_tab:
        with st.expander("Deep target and candidate evidence"):
            if st.button("Deep statistics / target scan", width="stretch"):
                deep = _cached_deep_statistics(root_text, rollout_texts, identity)
                st.session_state[_DEEP_STATE_KEY] = (identity, deep)
            if deep is None:
                st.info("Run the deep scan to materialize target and candidate denominators.")
            else:
                st.json(deep)
            root_target_scan = deep.get("root_gt_obb_target_opportunities", {}) if deep is not None else {}
            if deep is not None:
                deep_aggregate = deep.get("aggregate", {})
                deep_columns = st.columns(3)
                deep_columns[0].metric(
                    "Root target opportunities",
                    "Unavailable"
                    if not bool(root_target_scan.get("available"))
                    else _metric_value(root_target_scan.get("target_opportunity_count")),
                )
                deep_columns[1].metric(
                    "Unique persisted target tasks",
                    _deep_metric_value(deep_aggregate, "persisted_rollout_unique_target_tasks", deep_available=True),
                )
                deep_columns[2].metric(
                    "Q_H trainable candidates",
                    _deep_metric_value(deep_aggregate, "q_h_trainable_candidates", deep_available=True),
                )
            if not bool(root_target_scan.get("available")):
                reason = root_target_scan.get("reason", "deep scan not run")
                st.warning(
                    "Root target opportunities are counted only from persisted GT-OBB labels and are never inferred "
                    f"from rollout rows. Current status: {reason}."
                )
            st.caption(
                "Use Root Observation Store for source distributions and Rollout Supervision for scientific, "
                "failure, query, depth, and Rerun inspection."
            )

    st.download_button(
        "Download resolved bundle evidence JSON",
        data=lambda: _download_payload(evidence, deep, qh_readiness, qh_preview),
        file_name="training_dataset_bundle_evidence.json",
        mime="application/json",
        on_click="ignore",
        width="stretch",
        help="Exports the current session selection and resolved evidence; it does not persist a bundle config.",
    )


__all__ = ["render_training_dataset_page"]
