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
import plotly.express as px
import streamlit as st

from ...configs import PathConfig
from ...dataset_bundle import (
    DatasetBundleEvidence,
    DatasetBundleSelection,
    build_dataset_bundle_summary,
    compute_dataset_bundle_deep_statistics,
)
from ...dataset_topology import discover_vin_store_dirs
from ...rollouts.inspection import discover_rollout_store_paths

_VALIDATED_STATE_KEY = "training_dataset_validated_evidence"
_DEEP_STATE_KEY = "training_dataset_deep_statistics"


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


def _coral_artifact_identity(root: Path) -> tuple[tuple[str, int, int], ...]:
    """Return identities for narrowly matched CORAL artifacts outside stores."""

    resolved = root.expanduser().resolve()
    if not resolved.exists():
        return ()
    rows: list[tuple[str, int, int]] = []
    for child in sorted(resolved.glob("**/rri_binner*.json"), key=lambda item: item.as_posix()):
        try:
            stat = child.stat()
        except OSError:
            continue
        rows.append((child.as_posix(), stat.st_mtime_ns, stat.st_size))
    return tuple(rows)


def _selection_cache_key(
    selection: DatasetBundleSelection,
    *,
    coral_root: Path,
) -> tuple[Any, ...]:
    """Return the session-result key for one immutable bundle snapshot."""

    return (
        selection.root_store.as_posix(),
        tuple(path.as_posix() for path in selection.rollout_stores),
        _artifact_identity(selection.root_store),
        tuple(_artifact_identity(path) for path in selection.rollout_stores),
        _coral_artifact_identity(coral_root),
    )


@st.cache_data(show_spinner="Inspecting manifests and indexes…", max_entries=32)
def _cached_bundle_summary(
    root_store: str,
    rollout_stores: tuple[str, ...],
    artifact_identity: tuple[Any, ...],
    coral_root: str,
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
        coral_artifact_roots=(Path(coral_root),),
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


def _target_inventory_frames(
    inventory: dict[str, Any],
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """Return sample, class, and geometry frames from typed target evidence."""

    sample_rows: list[dict[str, Any]] = []
    target_rows: list[dict[str, Any]] = []
    for population in ("detected", "gt"):
        evidence = inventory.get(population, {})
        if not bool(evidence.get("available")):
            continue
        sample_rows.extend({**row, "population": population} for row in evidence.get("sample_rows", ()))
        target_rows.extend(evidence.get("rows", ()))
    sample_frame = pd.DataFrame(sample_rows)
    target_frame = pd.DataFrame(target_rows)
    if target_frame.empty:
        return sample_frame, pd.DataFrame(), target_frame
    class_frame = (
        target_frame.groupby(["population", "class_name"], dropna=False)
        .agg(target_count=("source_row", "size"), scene_count=("scene_id", "nunique"))
        .reset_index()
        .sort_values(["population", "target_count", "class_name"], ascending=[True, False, True])
        .reset_index(drop=True)
    )
    return sample_frame, class_frame, target_frame


def _render_target_context(*, question: str, interpretation: str, caveat: str) -> None:
    """Provide concise scientific context beside a target-inventory plot."""

    with st.popover("Interpret this plot", icon=":material/info:"):
        st.markdown(f"**Question.** {question}")
        st.markdown(interpretation)
        st.markdown(f"**Important limitation.** {caveat}")


def _zero_target_summary(sample_frame: pd.DataFrame, population: str) -> str:
    rows = sample_frame.loc[sample_frame["population"] == population] if not sample_frame.empty else sample_frame
    if rows.empty:
        return "Unavailable"
    zero_count = int((rows["count"] == 0).sum())
    return f"{zero_count:,} / {len(rows):,} ({zero_count / len(rows):.1%})"


def _render_target_inventory(inventory: dict[str, Any]) -> None:
    """Render complete detected/GT availability before campaign selection."""

    sample_frame, class_frame, target_frame = _target_inventory_frames(inventory)
    detected = inventory.get("detected", {})
    gt = inventory.get("gt", {})
    metric_cols = st.columns(4)
    metric_cols[0].metric("Detected targets", _metric_value(detected.get("row_count")))
    metric_cols[1].metric("GT targets", _metric_value(gt.get("row_count")))
    metric_cols[2].metric("Samples without detections", _zero_target_summary(sample_frame, "detected"))
    metric_cols[3].metric("Samples without GT targets", _zero_target_summary(sample_frame, "gt"))

    unavailable = [
        f"{population}: {evidence.get('reason', 'unavailable')}"
        for population, evidence in (("detected", detected), ("gt", gt))
        if not bool(evidence.get("available"))
    ]
    if unavailable:
        st.warning("Target populations unavailable — " + "; ".join(unavailable))

    exclusion_rows = [
        {"population": population, "reason": reason, "count": int(evidence.get(field, 0))}
        for population, evidence in (("detected", detected), ("gt", gt))
        for reason, field in (
            ("padding", "excluded_padding_count"),
            ("non-finite", "excluded_nonfinite_count"),
            ("invalid geometry", "excluded_invalid_geometry_count"),
        )
        if int(evidence.get(field, 0)) > 0
    ]
    if exclusion_rows:
        exclusion_figure = px.bar(
            pd.DataFrame(exclusion_rows),
            x="reason",
            y="count",
            color="population",
            barmode="group",
            title="Target rows excluded from statistical summaries",
            labels={"reason": "exclusion reason", "count": "excluded OBB rows", "population": "population"},
        )
        st.plotly_chart(exclusion_figure, width="stretch")
        _render_target_context(
            question="How much target evidence was withheld before computing the population summaries?",
            interpretation=(
                "These rows are counted but excluded from every downstream distribution. Padding is expected fixed-width "
                "storage; non-finite values and non-positive extents indicate unusable geometry."
            ),
            caveat="A clean plot has no bars. Padding is not a detector error and should be interpreted separately.",
        )

    if not sample_frame.empty:
        sample_figure = px.histogram(
            sample_frame,
            x="count",
            color="population",
            barmode="overlay",
            opacity=0.65,
            marginal="box",
            title="Detected and GT targets per physical sample",
            labels={"count": "finite valid OBB rows per sample", "population": "target population"},
        )
        st.plotly_chart(sample_figure, width="stretch")
        _render_target_context(
            question="How consistently are actor-visible detections and privileged GT targets available across samples?",
            interpretation=(
                "Every physical sample contributes once, including samples with zero targets. The histogram shows the "
                "distribution while the marginal box summarizes its median and interquartile range."
            ),
            caveat=(
                "Detected and GT counts are two different evidence populations. Their ratio is descriptive and is not "
                "object-detection recall because no global one-to-one assignment is performed here."
            ),
        )

    if not class_frame.empty:
        class_figure = px.bar(
            class_frame,
            x="class_name",
            y="target_count",
            color="population",
            barmode="group",
            hover_data=["scene_count"],
            title="Target support by semantic class",
            labels={"class_name": "semantic class", "target_count": "target rows", "population": "population"},
        )
        st.plotly_chart(class_figure, width="stretch")
        _render_target_context(
            question="Which semantic classes dominate or disappear from detected and GT target pools?",
            interpretation=(
                "Bars count finite valid OBB rows. Hovered scene support helps distinguish a broadly represented class "
                "from many repeated targets in only a few scenes."
            ),
            caveat=(
                "Counts are inventory evidence, not class accuracy. Unknown semantic names retain their numeric ID rather "
                "than being merged into a guessed class."
            ),
        )

    if not target_frame.empty:
        geometry_frame = target_frame.loc[(target_frame["volume"] > 0) & target_frame["volume"].notna()]
        if not geometry_frame.empty:
            volume_figure = px.histogram(
                geometry_frame,
                x="volume",
                color="population",
                barmode="overlay",
                opacity=0.65,
                log_x=True,
                title="Target OBB volume distribution",
                labels={"volume": "oriented-box volume (m³)", "population": "target population"},
            )
            st.plotly_chart(volume_figure, width="stretch")
            _render_target_context(
                question="Does the dataset overrepresent very small or very large target geometry?",
                interpretation=(
                    "Volume is the product of the three positive OBB extents. The logarithmic x-axis makes multiplicative "
                    "scale differences visible across detected and GT populations."
                ),
                caveat="Non-finite, padded, and non-positive geometry is excluded and reported separately in the evidence.",
            )
            aspect_figure = px.histogram(
                geometry_frame,
                x="aspect_ratio",
                color="population",
                barmode="overlay",
                opacity=0.65,
                log_x=True,
                title="Target OBB aspect-ratio distribution",
                labels={"aspect_ratio": "largest / smallest OBB extent", "population": "target population"},
            )
            st.plotly_chart(aspect_figure, width="stretch")
            _render_target_context(
                question="Are detected or GT boxes dominated by unusually elongated geometry?",
                interpretation=(
                    "An aspect ratio of 1 is isotropic; larger values indicate increasing elongation. The logarithmic "
                    "axis separates ordinary variation from extreme geometric tails."
                ),
                caveat=(
                    "Aspect ratio diagnoses box shape, not semantic correctness. Compare populations and inspect raw rows "
                    "before treating an extreme value as an annotation or detector defect."
                ),
            )
        detected_confidence = target_frame.loc[
            (target_frame["population"] == "detected") & target_frame["confidence"].notna()
        ]
        if not detected_confidence.empty:
            confidence_figure = px.histogram(
                detected_confidence,
                x="confidence",
                color="class_name",
                nbins=20,
                title="Actor-visible detection confidence",
                labels={"confidence": "persisted detection confidence", "class_name": "semantic class"},
            )
            st.plotly_chart(confidence_figure, width="stretch")
            st.caption(
                "Confidence describes the detector output only. Calibration against campaign admission belongs to the "
                "Campaign Generation admission audit."
            )
            _render_target_context(
                question="How concentrated are the detector's persisted confidence scores across semantic classes?",
                interpretation=(
                    "The histogram exposes low-confidence mass, class-dependent score ranges, and saturation near the "
                    "bounds before any campaign matching is applied."
                ),
                caveat=(
                    "Confidence is not accuracy or calibration. Relating it to matching success requires a joined, "
                    "identity-validated admission view and is intentionally not inferred here."
                ),
            )

    with st.expander("Target inventory rows and export", expanded=False):
        st.dataframe(target_frame, hide_index=True, width="stretch")
        st.download_button(
            "Download target inventory JSON",
            data=(json.dumps(inventory, indent=2, sort_keys=True) + "\n").encode("utf-8"),
            file_name="target_inventory.json",
            mime="application/json",
            on_click="ignore",
        )


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
) -> bytes:
    """Serialize deterministic, complete bundle evidence for download."""

    payload = evidence.to_jsonable()
    payload["deep_statistics"] = deep
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
    coral_root = paths.root / ".logs" / "vin"

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
    identity = _selection_cache_key(selection, coral_root=coral_root)
    root_text = selection.root_store.as_posix()
    rollout_texts = tuple(path.as_posix() for path in selection.rollout_stores)
    light = _cached_bundle_summary(
        root_text,
        rollout_texts,
        identity,
        coral_root.as_posix(),
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
                coral_root.as_posix(),
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

    _render_verdict(evidence)
    _render_summary_metrics(evidence, deep)

    overview_tab, stores_tab, topology_tab, targets_tab, coral_tab, findings_tab = st.tabs(
        ["Overview", "Stores & splits", "Topology", "Target inventory", "CORAL artifacts", "Findings"]
    )
    with overview_tab:
        st.subheader("Bundle overview")
        st.write(
            {
                "root_store": evidence.root.get("path"),
                "root_splits": evidence.root.get("split_counts", {}),
                "materialized_blocks": evidence.root.get("materialized_blocks", {}),
                "selected_rollout_stores": evidence.aggregate.get("selected_rollout_store_count", 0),
                "compatible_rollout_stores": evidence.aggregate.get("compatible_rollout_store_count", 0),
                "combined_compatible_storage": _format_bytes(evidence.aggregate.get("storage_bytes")),
            }
        )
        st.info(
            "For detailed inspection, use **Training Data → Root Observation Store** or "
            "**Training Data → Rollout Supervision** in the top navigation."
        )
    with stores_tab:
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
    with topology_tab:
        st.subheader("Root-store → rollout-store → Q_H dependency")
        _render_topology(evidence)
    with targets_tab:
        st.subheader("Detected and GT target inventory")
        st.caption(
            "This view describes the complete VIN root-store populations before campaign matching or rollout selection."
        )
        if deep is None:
            st.info("Run **Deep statistics / target scan** to load target availability and geometry distributions.")
        else:
            inventory = deep.get("root_target_inventory", {})
            if inventory:
                _render_target_inventory(inventory)
        root_target_scan = deep.get("root_gt_obb_target_opportunities", {}) if deep is not None else {}
        if not bool(root_target_scan.get("available")):
            reason = root_target_scan.get("reason", "deep scan not run")
            st.warning(
                "Root target opportunities are counted only from persisted GT-OBB labels and are never inferred "
                f"from rollout rows. Current status: {reason}."
            )
    with coral_tab:
        st.subheader("Available CORAL binner artifacts")
        st.caption(f"Catalog is intentionally scoped to {coral_root}.")
        if evidence.coral_artifacts:
            st.dataframe(pd.DataFrame(evidence.coral_artifacts), hide_index=True, width="stretch")
        else:
            st.info("No rri_binner*.json artifacts were found. Their absence does not block bundle readiness.")
    with findings_tab:
        st.subheader("Readiness findings")
        finding_rows = [finding.to_jsonable() for finding in evidence.findings]
        if finding_rows:
            st.dataframe(pd.DataFrame(finding_rows), hide_index=True, width="stretch")
        else:
            st.success("No readiness findings.")

    st.download_button(
        "Download resolved bundle evidence JSON",
        data=lambda: _download_payload(evidence, deep),
        file_name="training_dataset_bundle_evidence.json",
        mime="application/json",
        on_click="ignore",
        width="stretch",
        help="Exports the current session selection and resolved evidence; it does not persist a bundle config.",
    )


__all__ = ["render_training_dataset_page"]
