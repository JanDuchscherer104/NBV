"""Overview, corpus summary, and topology presentation for stored rollouts."""

from __future__ import annotations

import html
from pathlib import Path
from typing import Any

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from ....configs import PathConfig
from ....dataset_topology import discover_vin_store_dirs
from ....rollouts import RolloutZarrStoreReader
from ....rollouts.reporting import RolloutCorpusSummary
from .session import _cached_header, _cached_invariants, _cached_topology, _clear_stored_rollout_caches
from .shared import _ROLE_COLORS, ScientificExplanation
from .shared import download_frame as _download_frame
from .shared import download_json as _download_json
from .shared import render_plot as _render_plot


def _render_store_selector(
    paths: PathConfig,
    inventory: list[dict[str, object]],
) -> tuple[tuple[Path, ...], Path | None]:
    """Select an explicit corpus and one active drill-down store."""

    col_store, col_status = st.columns([4, 1])
    selected: Path | None = None
    if inventory:
        options = [Path(str(item["path"])).expanduser().resolve() for item in inventory]
        corpus = tuple(
            col_store.multiselect(
                "Corpus stores",
                options=options,
                default=options[:1],
                format_func=lambda path: path.name,
                help="Only selected stores enter the explicit aggregate summary.",
            )
        )
        row = col_store.selectbox(
            "Active drill-down store",
            options=inventory,
            format_func=lambda item: (
                f"{Path(str(item['path'])).name} · {item.get('schema_status', 'unknown')} · "
                f"R/S/C={item.get('observed_rollouts', '?')}/{item.get('observed_steps', '?')}/"
                f"{item.get('observed_candidates', '?')}"
            ),
            key="rollout_store_selector",
        )
        selected = Path(str(row["path"])).expanduser().resolve()
        col_status.metric("Schema", str(row.get("schema_status", "unknown")).upper())
    else:
        corpus = ()
        col_store.info(f"No `*.zarr` rollout stores found below `{paths.offline_cache_dir}`.")

    with st.expander("Store path override", expanded=not inventory):
        manual = st.text_input("Manual rollouts.zarr path", value="", key="rollout_store_manual_path")
        if manual.strip():
            candidate = Path(manual).expanduser()
            if not candidate.is_absolute():
                candidate = paths.resolve_cache_artifact_dir(manual)
            selected = candidate.resolve()
            if selected not in corpus:
                corpus = (*corpus, selected)
    if col_status.button("Refresh stores", help="Clear inspector caches after creating or replacing a store."):
        _clear_stored_rollout_caches()
        st.rerun()
    if selected is not None and selected not in corpus:
        corpus = (*corpus, selected)
    return tuple(dict.fromkeys(corpus)), selected


def _render_corpus_overview(summary: RolloutCorpusSummary | None, *, selected_count: int) -> None:
    """Render only additive corpus counts after explicit aggregation."""

    st.subheader("Corpus overview")
    if summary is None:
        st.info(f"{selected_count} store(s) selected. Build the summary to validate and aggregate them.")
        return
    totals = summary.totals
    cols = st.columns(6)
    cols[0].metric("Included stores", totals["included_store_count"])
    cols[1].metric("Excluded stores", totals["excluded_store_count"])
    cols[2].metric("Q_H chains", _format_count(totals["q_h_chain_count"]))
    cols[3].metric("Q_H states", _format_count(totals["q_h_state_count"]))
    cols[4].metric("Trainable candidates", _format_count(totals["q_h_trainable_count"]))
    cols[5].metric("Storage", _format_bytes(totals["storage_bytes"]))
    st.caption(f"Corpus verdict: {summary.verdict}. Counts are additive; scientific macro estimates are not pooled.")
    if summary.excluded_stores:
        st.dataframe(pd.DataFrame(summary.excluded_stores), hide_index=True, width="stretch")


def _render_corpus_details(summary: RolloutCorpusSummary | None) -> None:
    """Render store-qualified corpus evidence outside the essential overview."""

    st.subheader("Corpus store details")
    if summary is None:
        st.info("Build the corpus summary in Overview to inspect store-qualified inclusion and Q_H evidence.")
        return
    if summary.included_stores:
        st.dataframe(pd.DataFrame(summary.included_stores), hide_index=True, width="stretch")
    if summary.excluded_stores:
        st.dataframe(pd.DataFrame(summary.excluded_stores), hide_index=True, width="stretch")
    if not summary.q_h_stores.empty:
        st.dataframe(summary.q_h_stores, hide_index=True, width="stretch")


def _render_corpus_evidence(summary: RolloutCorpusSummary | None) -> None:
    """Render cohort-separated additive support and raw endpoint distributions."""

    st.subheader("Corpus evidence")
    if summary is None:
        st.info("Build the corpus summary in Overview before viewing aggregate evidence.")
        return
    if summary.candidate_support.empty:
        st.info("No validated candidate-support rows are available.")
    else:
        st.dataframe(summary.candidate_support, hide_index=True, width="stretch")
    if summary.endpoints.empty:
        st.info("No validated endpoint rows are available.")
    else:
        st.dataframe(summary.endpoints, hide_index=True, width="stretch")
        metric = next(
            (
                name
                for name in ("endpoint_gain", "target_rri", "cumulative_target_root_gain")
                if name in summary.endpoints
            ),
            None,
        )
        if metric is not None:
            fig = px.box(
                summary.endpoints,
                x="profile",
                y=metric,
                color="policy",
                facet_col="horizon",
                hover_data=["store_id"],
                title="Store-qualified endpoint distributions",
            )
            _render_plot(
                fig,
                ScientificExplanation(
                    question="How are diagnostic rollout endpoints distributed across validated stores?",
                    population="One store-qualified factual rollout endpoint, faceted by persisted horizon.",
                    metric=f"{metric}; units follow the persisted endpoint metric contract.",
                    denominator_masks="Validated included stores and finite factual endpoints only; excluded stores contribute no values.",
                    comparability="Compare within profile, policy, horizon, and compatible generation contracts; store identity remains visible.",
                    expected_pattern="Distributions remain stable across stores of the same profile rather than being driven by one shard.",
                    failure_interpretation="Separated or heavy-tailed store distributions suggest a source, profile, or rollout-quality issue requiring drill-down.",
                    evidence_role="oracle/evaluation",
                    source_fields=("reporting.RolloutCorpusSummary.endpoints", "rollouts", "steps"),
                ),
            )


def _render_corpus_failures(summary: RolloutCorpusSummary | None) -> None:
    """Render aggregate failure counts before active-store triage."""

    st.subheader("Corpus failures")
    if summary is None:
        st.info("Build the corpus summary in Overview before viewing aggregate failures.")
        return
    if summary.failure_counts.empty:
        st.success("No validated aggregate failure rows were reported.")
        return
    st.dataframe(summary.failure_counts, hide_index=True, width="stretch")
    _render_plot(
        px.bar(summary.failure_counts, x="kind", y="count", color="severity", title="Failures across included stores"),
        ScientificExplanation(
            question="Which validation and data-quality failure classes dominate the selected corpus?",
            population="Additive failure findings from validated included stores, grouped by exact kind and severity.",
            metric="Finding count; counts prioritize debugging and are not independent scientific samples.",
            denominator_masks="Only findings emitted by included validated stores; excluded-store reasons remain in Overview.",
            comparability="Compare counts only for the same selected corpus and failure rules.",
            expected_pattern="Hard contract failures are absent or sparse and every count is traceable to a store.",
            failure_interpretation="Large counts identify debugging priorities, not policy-performance effects.",
            evidence_role="provenance",
            source_fields=("reporting.RolloutCorpusSummary.failure_counts", "inspection.suspicious_rollout_rows"),
        ),
    )


def _render_role_legend() -> None:
    badges = " ".join(
        f'<span style="display:inline-block;padding:.15rem .45rem;margin:.1rem;border-radius:.35rem;'
        f'background:{color};color:white;font-size:.78rem">{html.escape(role)}</span>'
        for role, color in _ROLE_COLORS.items()
    )
    st.markdown(
        "**Evidence roles:** "
        + badges
        + "<br><span style='font-size:.85rem'>Actor-visible inputs, privileged evaluation, derived training caches, "
        "and provenance are never interchangeable.</span>",
        unsafe_allow_html=True,
    )


def _render_trust_and_topology(
    *,
    reader: RolloutZarrStoreReader,
    store_path: Path,
    inventory_row: dict[str, object] | None,
    manifest_payload: dict[str, Any],
    paths: PathConfig,
    validation_ok: bool,
) -> None:
    st.subheader("Active-store validation")
    counts = inventory_row or {}
    cols = st.columns(5)
    cols[0].metric("Schema", str(counts.get("schema_status", "unknown")))
    cols[1].metric("Validation", "OK" if validation_ok else "BLOCKED")
    cols[2].metric("Rollouts", str(counts.get("observed_rollouts", "?")))
    cols[3].metric("Steps", str(counts.get("observed_steps", "?")))
    cols[4].metric("Candidates", str(counts.get("observed_candidates", "?")))

    _render_validated_store_header(reader.store_dir.as_posix(), validation_ok=validation_ok)

    if not st.toggle(
        "Show advanced validation, topology, and raw metadata",
        value=False,
        help="Keeps topology discovery and invariant projections off the essential overview until requested.",
    ):
        return

    try:
        invariants = _cached_invariants(reader.store_dir.as_posix())
    except Exception as exc:
        invariants = [{"status": "FAIL", "invariant": "invariant projection", "evidence": str(exc)}]
    inv_df = pd.DataFrame(invariants)
    st.markdown("#### Invariant matrix")
    st.caption(
        "PASS is established evidence; WARN is incomplete comparability; FAIL blocks scientific and Rerun claims."
    )
    st.dataframe(inv_df, hide_index=True, width="stretch")
    _download_frame("Download invariant CSV", "rollout-invariants.csv", inv_df)
    _download_json("Download invariant JSON", "rollout-invariants.json", invariants)

    vin_dirs = discover_vin_store_dirs(paths.offline_cache_dir)
    try:
        topology = _cached_topology(
            store_path.as_posix(),
            tuple(path.as_posix() for path in vin_dirs),
            paths,
        )
    except Exception as exc:
        st.warning(f"Topology could not be fully resolved: {type(exc).__name__}: {exc}")
        topology = None
    if topology is not None:
        st.markdown("#### Cross-store topology")
        sankey = topology.sankey_data()
        if sankey.get("link", {}).get("source"):
            fig = go.Figure(go.Sankey(node=sankey["node"], link=sankey["link"]))
            fig.update_layout(title="Persisted payloads and cross-store pointers", height=480)
            _render_plot(
                fig,
                ScientificExplanation(
                    question="Which persisted artifacts are embedded, resolved, inferred, or missing?",
                    population="Aggregate artifact nodes and typed edges; source rows are collapsed by default.",
                    metric="Edge width is relationship count, not bytes or scientific effect size.",
                    denominator_masks="All recorded topology links for the selected rollout store and discovered VIN stores.",
                    comparability="Compare resolution classes only; node width does not imply data quality.",
                    expected_pattern="Manifest hashes resolve uniquely and required actor/oracle modalities have one owner.",
                    failure_interpretation="Missing or ambiguous links indicate incomplete local provenance, not invalid scientific values by themselves.",
                    evidence_role="provenance",
                    source_fields=("rollout manifest source lineage", "VIN manifest", "PathConfig", "mesh paths"),
                ),
            )
        modality_df = pd.DataFrame(topology.modality_rows())
        if not modality_df.empty:
            st.dataframe(modality_df, hide_index=True, width="stretch")
            _download_frame("Download modality matrix CSV", "dataset-modalities.csv", modality_df)
        with st.expander("Selected-source drill-down and plain-text tree"):
            source_rows = topology.source_rows()
            if source_rows:
                source_id = st.selectbox(
                    "Source row",
                    options=[int(row["source_row_id"]) for row in source_rows],
                    format_func=lambda value: next(
                        (
                            f"{value} · {row.get('scene_id', '?')} / {row.get('snippet_id', '?')}"
                            for row in source_rows
                            if int(row["source_row_id"]) == value
                        ),
                        str(value),
                    ),
                    key="stored_topology_source_row",
                )
                topology = _cached_topology(
                    store_path.as_posix(),
                    tuple(path.as_posix() for path in vin_dirs),
                    paths,
                    int(source_id),
                )
                st.dataframe(
                    [row for row in source_rows if int(row["source_row_id"]) == int(source_id)],
                    hide_index=True,
                    width="stretch",
                )
            st.code(topology.plain_text_tree(), language="text")
        _download_json("Download topology JSON", "dataset-topology.json", topology.to_jsonable())

    with st.expander("Raw store metadata"):
        st.json({"inventory": inventory_row, **manifest_payload}, expanded=False)
    _download_json(
        "Download store metadata JSON", "rollout-store-metadata.json", {"inventory": inventory_row, **manifest_payload}
    )


def _render_store_header_summary(store_path: str) -> None:
    """Render reference coverage and physical cost without candidate projection."""

    header = _cached_header(store_path)
    st.markdown("#### Coverage and physical cost")
    coverage_cols = st.columns(4)
    coverage_cols[0].metric("Scenes", _format_count(header.get("scenes")))
    coverage_cols[1].metric("Targets", _format_count(header.get("targets")))
    coverage_cols[2].metric("Source rows", _format_count(header.get("source_rows")))
    coverage_cols[3].metric("Store size", _format_bytes(header.get("physical_store_bytes")))
    if header.get("reference_scene_count") is None and header.get("reference_source_row_count") is None:
        st.caption(str(header.get("reference_coverage_reason") or "Reference coverage is unavailable."))
    else:
        st.caption(
            "Reference coverage: "
            f"scenes {_format_fraction(header.get('reference_scene_fraction'))}; "
            f"source rows {_format_fraction(header.get('reference_source_row_fraction'))}. "
            "Observed rows never define their own reference denominator."
        )
    cost = pd.DataFrame(
        [
            {
                "bytes_per_rollout": header.get("physical_bytes_per_rollout"),
                "bytes_per_candidate": header.get("physical_bytes_per_candidate"),
                "return_semantics": header.get("return_semantics"),
                "discount_gamma": header.get("discount_gamma"),
            }
        ]
    )
    st.dataframe(cost, hide_index=True, width="stretch")
    _download_json("Download coverage and cost JSON", "rollout-coverage-cost.json", header)


def _render_validated_store_header(store_path: str, *, validation_ok: bool) -> None:
    """Render scientific coverage only for a store that passed validation."""

    if not validation_ok:
        st.info("Coverage and physical-cost projections are withheld until store validation succeeds.")
        return
    _render_store_header_summary(store_path)


def _format_count(value: object) -> str:
    """Format an optional integral count without inventing a zero."""

    return "n/a" if value is None else f"{int(value):,}"


def _format_bytes(value: object) -> str:
    """Format an optional byte count using compact binary units."""

    if value is None:
        return "n/a"
    size = float(value)
    for unit in ("B", "KiB", "MiB", "GiB", "TiB"):
        if abs(size) < 1024.0 or unit == "TiB":
            return f"{size:.1f} {unit}"
        size /= 1024.0
    raise AssertionError("unreachable byte unit")


def _format_fraction(value: object) -> str:
    """Format an optional coverage fraction without deriving a denominator."""

    return "n/a" if value is None else f"{float(value):.1%}"
