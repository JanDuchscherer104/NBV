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
    evidence: DatasetBundleEvidence,
    deep: dict[str, Any] | None,
) -> None:
    """Render root, rollout, and target-supervision quantities separately."""

    root = evidence.root
    aggregate = evidence.aggregate
    root_cols = st.columns(5)
    root_cols[0].metric("Root samples", _metric_value(root.get("sample_count")))
    root_cols[1].metric("Root snippets", _metric_value(root.get("snippet_count")))
    root_cols[2].metric("Root scenes", _metric_value(root.get("scene_count")))
    root_cols[3].metric("Root storage", _format_bytes(root.get("storage_bytes")))
    root_cols[4].metric("Root schema", str(root.get("schema_version") or "Unavailable"))

    rollout_cols = st.columns(5)
    rollout_cols[0].metric(
        "Compatible rollout stores",
        f"{aggregate.get('compatible_rollout_store_count', 0)} / {aggregate.get('selected_rollout_store_count', 0)}",
    )
    rollout_cols[1].metric("Rollouts", _metric_value(aggregate.get("rollout_count")))
    rollout_cols[2].metric("Rollout steps", _metric_value(aggregate.get("step_count")))
    rollout_cols[3].metric("Candidates", _metric_value(aggregate.get("candidate_count")))
    rollout_cols[4].metric("Rollout storage", _format_bytes(aggregate.get("rollout_storage_bytes")))

    deep_aggregate = deep.get("aggregate", {}) if deep is not None else {}
    target_cols = st.columns(3)
    target_cols[0].metric(
        "Root target opportunities",
        _metric_value(
            deep_aggregate.get("root_gt_obb_target_opportunities"),
            pending="Deep scan required" if deep is None else "Unavailable",
        ),
    )
    target_cols[1].metric(
        "Unique persisted target tasks",
        _deep_metric_value(
            deep_aggregate,
            "persisted_rollout_unique_target_tasks",
            deep_available=deep is not None,
        ),
    )
    target_cols[2].metric(
        "Q_H trainable candidates",
        _deep_metric_value(deep_aggregate, "q_h_trainable_candidates", deep_available=deep is not None),
    )
    st.caption(
        f"Persisted rollout target rows: {int(aggregate.get('persisted_rollout_target_rows') or 0):,}. "
        "Root opportunities, unique persisted tasks, and candidate-level Q_H supervision are different denominators."
    )


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


def _render_topology(evidence: DatasetBundleEvidence) -> None:
    """Render a compact root-to-rollout-to-Q_H dependency graph."""

    lines = ["digraph bundle {", 'rankdir="LR";', 'node [shape="box", style="rounded"];']
    root_label = Path(str(evidence.root.get("path", "VIN root"))).name
    lines.append(f'root [label="VIN root\\n{root_label}"];')
    if not evidence.rollouts:
        lines.append('none [label="No rollout supervision selected", style="rounded,dashed"];')
        lines.append('root -> none [style="dashed"];')
    for index, row in enumerate(evidence.rollouts):
        name = Path(str(row["path"])).name.replace('"', "'")
        included = bool(row.get("included_in_training_totals"))
        color = "#2e7d32" if included else "#c62828"
        style = "solid" if included else "dashed"
        lines.append(f'rollout_{index} [label="Rollout store\\n{name}", color="{color}"];')
        lines.append(f'qh_{index} [label="Derived Q_H rows", color="{color}"];')
        lines.append(f'root -> rollout_{index} [color="{color}", style="{style}"];')
        lines.append(f'rollout_{index} -> qh_{index} [color="{color}", style="{style}"];')
    lines.append("}")
    st.graphviz_chart("\n".join(lines), width="stretch")
    st.caption("Green paths contribute to aggregate training totals; red dashed paths remain visible but are blocked.")


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

    action_cols = st.columns(2)
    validate = action_cols[0].button("Validate bundle", type="primary", width="stretch")
    scan = action_cols[1].button("Deep statistics / target scan", width="stretch")
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
    if scan:
        st.session_state[_DEEP_STATE_KEY] = (
            identity,
            _cached_deep_statistics(root_text, rollout_texts, identity),
        )

    validated_state = st.session_state.get(_VALIDATED_STATE_KEY)
    evidence = validated_state[1] if validated_state and validated_state[0] == identity else light
    deep_state = st.session_state.get(_DEEP_STATE_KEY)
    deep = deep_state[1] if deep_state and deep_state[0] == identity else None
    qh_state = st.session_state.get(_QH_READINESS_STATE_KEY)
    qh_readiness = qh_state[1] if qh_state and qh_state[0] == identity else None
    preview_state = st.session_state.get(_QH_PREVIEW_STATE_KEY)
    qh_preview = preview_state[1] if preview_state and preview_state[0] == identity else None

    _render_verdict(evidence)
    _render_summary_metrics(evidence, deep)

    readiness_tab, qh_tab, details_tab = st.tabs(["Readiness", "Q_H corpus", "Details"])
    with readiness_tab:
        st.subheader("Bundle readiness")
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
            "This action constructs the selected stage datasets and the production QhDataModule. "
            "It does not create a model or Trainer."
        )
        controls = st.columns(3)
        batch_size = int(controls[0].number_input("Q_H batch size", min_value=1, value=1, step=1))
        seed = int(controls[1].number_input("Q_H loader seed", min_value=0, value=0, step=1))
        if controls[2].button("Preflight Q_H corpus", type="primary", width="stretch"):
            qh_readiness = _cached_qh_readiness(
                root_text,
                rollout_texts,
                identity,
                batch_size,
                seed,
            )
            st.session_state[_QH_READINESS_STATE_KEY] = (identity, qh_readiness)
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
                        st.session_state[_QH_PREVIEW_STATE_KEY] = (identity, qh_preview)
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
    with details_tab:
        with st.expander("Topology and raw store evidence"):
            _render_topology(evidence)
        with st.expander("Deep target and candidate evidence"):
            if deep is None:
                st.info("Run **Deep statistics / target scan** to materialize target and candidate denominators.")
            else:
                st.json(deep)
            root_target_scan = deep.get("root_gt_obb_target_opportunities", {}) if deep is not None else {}
            if not bool(root_target_scan.get("available")):
                reason = root_target_scan.get("reason", "deep scan not run")
                st.warning(
                    "Root target opportunities are counted only from persisted GT-OBB labels and are never inferred "
                    f"from rollout rows. Current status: {reason}."
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
