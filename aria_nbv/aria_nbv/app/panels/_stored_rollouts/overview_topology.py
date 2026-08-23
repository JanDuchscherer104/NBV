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
from .session import _clear_stored_rollout_caches
from .shared import _ROLE_COLORS, ExplanationSection, ScientificExplanation
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
    cols = st.columns(3)
    cols[0].metric("Selected stores (operational)", totals["selected_store_count"])
    cols[1].metric("Included stores (operational)", totals["included_store_count"])
    cols[2].metric("Excluded stores (operational)", totals["excluded_store_count"])
    st.caption(
        f"Corpus verdict: {summary.verdict}. Operational selection counts span the request; scientific totals below stay separated by exact persisted contract."
    )
    contract_totals = getattr(summary, "contract_totals", pd.DataFrame())
    if contract_totals.empty:
        st.info("No compatible contract facet has validated scientific totals yet.")
    else:
        st.markdown("#### Validated scientific totals by exact contract")
        for row in contract_totals.to_dict("records"):
            label = f"{row['contract']} · {row['profile']} · {row['contract_id']}"
            st.caption(label)
            facet = st.columns(5)
            facet[0].metric("Stores", row["store_count"])
            facet[1].metric("Rollouts / steps", f"{row['rollout_count']} / {row['step_count']}")
            facet[2].metric("Candidates", _format_count(row["candidate_count"]))
            facet[3].metric(
                "Q_H states / trainable",
                f"{_format_count(row['q_h_state_count'])} / {_format_count(row['q_h_trainable_count'])}",
            )
            facet[4].metric("Storage", _format_bytes(row["storage_bytes"]))
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
    """Render the corpus reward/reconstruction surface, plot first."""

    st.subheader("Corpus reward and reconstruction")
    if summary is None:
        st.info("Build the corpus summary in Overview to render reward and reconstruction evidence.")
        return
    from .reconstruction_return import _render_corpus_temporal_evidence

    _render_corpus_temporal_evidence(summary)

    if summary.endpoints.empty:
        st.info("No validated endpoint rows are available.")
    else:
        metric = next(
            (
                name
                for name in ("endpoint_gain", "target_rri", "cumulative_target_root_gain")
                if name in summary.endpoints
            ),
            None,
        )
        if metric is not None:
            endpoint_rows = summary.endpoints.copy()
            if {"contract", "contract_id"}.issubset(endpoint_rows.columns):
                endpoint_rows["contract_facet"] = (
                    endpoint_rows["contract"].astype(str) + " · id=" + endpoint_rows["contract_id"].astype(str)
                )
            else:
                endpoint_rows["contract_facet"] = endpoint_rows.get("contract", "corpus")
            fig = px.box(
                endpoint_rows,
                x="contract_facet",
                y=metric,
                color="policy",
                facet_col="horizon",
                hover_data=[name for name in ("store_id", "profile", "contract_id") if name in endpoint_rows],
                title="Store-qualified factual endpoint distributions",
            )
            _render_plot(
                fig,
                ScientificExplanation(
                    question="How are factual rollout endpoints distributed across the selected compatible shards?",
                    answer="This plot answers the question using the persisted evidence rows and preserves the denominator and comparison caveats below.",
                    sections=(
                        ExplanationSection(
                            "population",
                            "One store-qualified factual terminal endpoint, separated by persisted contract, policy, and horizon.",
                        ),
                        ExplanationSection("metric", f"{metric}; units follow the persisted endpoint metric contract."),
                        ExplanationSection(
                            "denominator masks",
                            "Validated included stores and finite factual endpoints only; excluded stores contribute no values.",
                        ),
                        ExplanationSection(
                            "comparability",
                            "Compare only within the same persisted contract, policy, and horizon; store identity remains visible.",
                        ),
                        ExplanationSection(
                            "expected pattern",
                            "Endpoint distributions remain supported across shards rather than being driven by one store.",
                        ),
                        ExplanationSection(
                            "failure interpretation",
                            "Separated or heavy-tailed distributions indicate coverage, profile, or rollout-quality issues for drill-down.",
                        ),
                    ),
                    evidence_role="oracle/evaluation",
                    source_fields=("reporting.RolloutCorpusSummary.endpoints", "rollouts", "steps"),
                ),
            )
        with st.expander("Endpoint rows and CSV", expanded=False):
            st.dataframe(summary.endpoints, hide_index=True, width="stretch")
            _download_frame("Download endpoint rows CSV", "corpus-endpoints.csv", summary.endpoints)


def _render_corpus_admission(summary: RolloutCorpusSummary | None) -> None:
    """Render corpus admission and feasibility without reward plots."""

    st.subheader("Corpus admission and feasibility")
    if summary is None:
        st.info("Build the corpus summary in Overview before viewing admission evidence.")
        return
    if summary.target_admission.empty:
        st.info("No validated target-admission rows are available.")
    else:
        target_rows = _select_contract_facet(summary.target_admission, "Target admission")
        target_rows["outcome"] = target_rows.apply(
            lambda row: (
                f"actor={bool(row['target_valid'])} · gt={bool(row['gt_label_valid'])} · {row['gt_match_status']}"
            ),
            axis=1,
        )
        figure = px.bar(target_rows, x="outcome", y="count", color="gt_label_valid", title="Target admission outcomes")
        _render_plot(
            figure,
            ScientificExplanation(
                question="Which observed targets are actor-admissible and which also receive an unambiguous GT label?",
                answer="This plot answers the question using the persisted evidence rows and preserves the denominator and comparison caveats below.",
                sections=(
                    ExplanationSection("population", "One persisted target row across validated selected stores."),
                    ExplanationSection(
                        "metric",
                        "Additive target count; categories preserve actor validity, GT-label validity, and match status.",
                    ),
                    ExplanationSection(
                        "denominator masks",
                        "All target rows remain visible, including ambiguous, unmatched, invalid, and below-threshold outcomes.",
                    ),
                    ExplanationSection(
                        "comparability", "Compare only when target-selection and GT-matching contracts agree."
                    ),
                    ExplanationSection(
                        "expected pattern",
                        "Exactly one same-class oriented-IoU match strictly above 0.20 is required for privileged label admission.",
                    ),
                    ExplanationSection(
                        "failure interpretation",
                        "Ambiguous or unmatched outcomes are coverage/debugging signals, not low reward examples.",
                    ),
                ),
                evidence_role="oracle/evaluation",
                source_fields=("reporting.RolloutCorpusSummary.target_admission", "targets", "GT match audit"),
            ),
        )
        with st.expander("Target-admission rows and CSV", expanded=False):
            st.dataframe(target_rows.drop(columns="outcome"), hide_index=True, width="stretch")
            _download_frame(
                "Download target-admission rows CSV", "corpus-target-admission.csv", target_rows.drop(columns="outcome")
            )
    if summary.candidate_support.empty:
        st.info("No validated candidate-family support rows are available.")
    else:
        support = _select_contract_facet(summary.candidate_support, "Candidate support")
        count_fields = (
            "allocated_count",
            "actor_valid_count",
            "oracle_valid_count",
            "trainable_count",
            "selected_count",
        )
        count_totals = {
            field: int(pd.to_numeric(support.get(field), errors="coerce").fillna(0).sum())
            for field in count_fields
            if field in support
        }
        cards = st.columns(5)
        for card, (field, value) in zip(cards, count_totals.items(), strict=False):
            card.metric(field.removesuffix("_count").replace("_", " ").title(), _format_count(value))
        rate_fields = [
            field
            for field in ("actor_valid_rate", "oracle_valid_rate", "trainable_rate", "selected_rate")
            if field in support
        ]
        if rate_fields:
            rate_rows = support.melt(
                id_vars=[field for field in ("family", "generation_cohort") if field in support],
                value_vars=rate_fields,
                var_name="support_rate",
                value_name="rate",
            )
            figure = px.bar(
                rate_rows,
                x="family",
                y="rate",
                color="support_rate",
                facet_col="generation_cohort" if "generation_cohort" in rate_rows else None,
                barmode="group",
                title="Candidate-family support within the selected contract facet",
                labels={"rate": "fraction of allocated candidates"},
            )
            _render_plot(
                figure,
                ScientificExplanation(
                    question="Are candidate families available, actor-valid, oracle-valid, trainable, and selected across the corpus?",
                    answer="The plot preserves additive family support from the validated shards. Absent families remain visible as zero rows when the typed projection provides them.",
                    sections=(
                        ExplanationSection(
                            "population", "One exact contract/profile facet, retaining generation cohort and family."
                        ),
                        ExplanationSection(
                            "metric / units",
                            "Bars are dimensionless rates; cards above show the corresponding additive candidate counts.",
                        ),
                        ExplanationSection(
                            "denominator / masks",
                            "Every rate uses allocated_count within its cohort/family; zero allocation is unavailable, not silently zero.",
                        ),
                        ExplanationSection(
                            "evidence role",
                            "Actor-valid support and privileged oracle/trainable masks are displayed separately.",
                        ),
                        ExplanationSection(
                            "interpretation",
                            "A family can be absent or available but non-trainable; these are distinct coverage outcomes.",
                        ),
                        ExplanationSection(
                            "warning",
                            "Different contract IDs are never pooled, even when their human-readable labels match.",
                        ),
                    ),
                    evidence_role="provenance",
                    source_fields=(
                        "reporting.RolloutCorpusSummary.candidate_support",
                        "candidate composition",
                        "validated stores",
                    ),
                ),
            )
        with st.expander("Candidate-family support rows and CSV", expanded=False):
            st.dataframe(support, hide_index=True, width="stretch")
            _download_frame("Download candidate-family support CSV", "corpus-candidate-support.csv", support)
    if summary.feasibility.empty:
        st.info("No validated clearance/collision evidence is available.")
    else:
        feasibility = _select_contract_facet(summary.feasibility, "Feasibility")
        metrics = st.columns(4)
        # Cards summarize the selected corpus, not the first generation
        # cohort. Rates are recomputed from additive denominators.
        candidates = pd.to_numeric(feasibility.get("candidate_count"), errors="coerce").sum()
        collision_evaluated = pd.to_numeric(feasibility.get("collision_evaluated_count"), errors="coerce").sum()
        collisions = pd.to_numeric(feasibility.get("collision_count"), errors="coerce").sum()
        clearance_finite = pd.to_numeric(feasibility.get("clearance_finite_count"), errors="coerce").sum()
        clearance_denominator = pd.to_numeric(feasibility.get("clearance_denominator"), errors="coerce").sum()
        metrics[0].metric("Candidates", _format_count(candidates))
        metrics[1].metric(
            "Collision rate", _format_fraction(collisions / collision_evaluated if collision_evaluated else None)
        )
        metrics[2].metric(
            "Clearance coverage",
            _format_fraction(clearance_finite / clearance_denominator if clearance_denominator else None),
        )
        metrics[3].metric("Cohorts", _format_count(len(feasibility)))
        figure = px.bar(
            feasibility,
            x="generation_cohort",
            y=["collision_rate", "clearance_coverage"],
            barmode="group",
            title="Candidate feasibility by generation cohort",
        )
        _render_plot(
            figure,
            ScientificExplanation(
                question="Are candidate collision and clearance checks sufficiently observed across generation cohorts?",
                answer="This plot answers the question using the persisted evidence rows and preserves the denominator and comparison caveats below.",
                sections=(
                    ExplanationSection(
                        "population", "Additive candidate feasibility denominators grouped by exact generation cohort."
                    ),
                    ExplanationSection(
                        "metric",
                        "Collision rate and clearance coverage are dimensionless fractions recomputed from additive counts.",
                    ),
                    ExplanationSection(
                        "denominator masks",
                        "Only finite persisted collision and clearance evidence enters each corresponding denominator.",
                    ),
                    ExplanationSection(
                        "comparability",
                        "Cohorts remain separate; do not interpret missing clearance as a successful clearance.",
                    ),
                    ExplanationSection(
                        "expected pattern",
                        "High clearance coverage and low collision rate support usable candidate geometry.",
                    ),
                    ExplanationSection(
                        "failure interpretation",
                        "Low coverage or high collision rate points to generator, rendering, or validity issues.",
                    ),
                ),
                evidence_role="actor-visible",
                source_fields=("reporting.RolloutCorpusSummary.feasibility", "candidate_collision_support"),
            ),
        )
        with st.expander("Feasibility rows and CSV", expanded=False):
            st.dataframe(feasibility, hide_index=True, width="stretch")
            _download_frame("Download feasibility rows CSV", "corpus-feasibility.csv", feasibility)


def _render_corpus_failures(summary: RolloutCorpusSummary | None) -> None:
    """Render aggregate failure counts before active-store triage."""

    st.subheader("Corpus failures")
    if summary is None:
        st.info("Build the corpus summary in Overview before viewing aggregate failures.")
        return
    if summary.failure_counts.empty:
        st.success("No validated aggregate failure rows were reported.")
        return
    failures = _select_contract_facet(summary.failure_counts, "Corpus failures")
    _render_plot(
        px.bar(failures, x="kind", y="count", color="severity", title="Failures across the selected contract facet"),
        ScientificExplanation(
            question="Which validation and data-quality failure classes dominate the selected corpus?",
            answer="This plot answers the question using the persisted evidence rows and preserves the denominator and comparison caveats below.",
            sections=(
                ExplanationSection(
                    "population",
                    "Additive failure findings from validated included stores, grouped by exact kind and severity.",
                ),
                ExplanationSection(
                    "metric", "Finding count; counts prioritize debugging and are not independent scientific samples."
                ),
                ExplanationSection(
                    "denominator masks",
                    "Only findings emitted by included validated stores; excluded-store reasons remain in Overview.",
                ),
                ExplanationSection(
                    "comparability", "Compare counts only for the same selected corpus and failure rules."
                ),
                ExplanationSection(
                    "expected pattern",
                    "Hard contract failures are absent or sparse and every count is traceable to a store.",
                ),
                ExplanationSection(
                    "failure interpretation",
                    "Large counts identify debugging priorities, not policy-performance effects.",
                ),
            ),
            evidence_role="provenance",
            source_fields=("reporting.RolloutCorpusSummary.failure_counts", "inspection.suspicious_rollout_rows"),
        ),
    )
    with st.expander("Failure rows and CSV"):
        st.dataframe(failures, hide_index=True, width="stretch")
        _download_frame("Download corpus failures CSV", "corpus-failures.csv", failures)


def _select_contract_facet(frame: pd.DataFrame, label: str) -> pd.DataFrame:
    """Gate corpus plots/cards to one exact persisted contract and profile."""

    selected = frame.copy()
    for field in ("contract_id", "contract", "profile"):
        if field not in selected.columns:
            continue
        values = sorted(selected[field].dropna().astype(str).unique())
        if len(values) <= 1:
            continue
        choice = st.selectbox(
            f"{label}: {field}",
            values,
            index=0,
            key=f"corpus-{label.lower().replace(' ', '-')}-{field}",
        )
        selected = selected.loc[selected[field].astype(str).eq(str(choice))]
    return selected


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
    session_handle: Any,
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

    _render_validated_store_header(session_handle, validation_ok=validation_ok)

    if not st.toggle(
        "Show advanced validation, topology, and raw metadata",
        value=False,
        help="Keeps topology discovery and invariant projections off the essential overview until requested.",
    ):
        return

    try:
        invariants = session_handle.invariants()
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
        topology = session_handle.topology(tuple(path.as_posix() for path in vin_dirs), paths)
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
                    answer="This plot answers the question using the persisted evidence rows and preserves the denominator and comparison caveats below.",
                    sections=(
                        ExplanationSection(
                            "population",
                            "Aggregate artifact nodes and typed edges; source rows are collapsed by default.",
                        ),
                        ExplanationSection(
                            "metric", "Edge width is relationship count, not bytes or scientific effect size."
                        ),
                        ExplanationSection(
                            "denominator masks",
                            "All recorded topology links for the selected rollout store and discovered VIN stores.",
                        ),
                        ExplanationSection(
                            "comparability", "Compare resolution classes only; node width does not imply data quality."
                        ),
                        ExplanationSection(
                            "expected pattern",
                            "Manifest hashes resolve uniquely and required actor/oracle modalities have one owner.",
                        ),
                        ExplanationSection(
                            "failure interpretation",
                            "Missing or ambiguous links indicate incomplete local provenance, not invalid scientific values by themselves.",
                        ),
                    ),
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
                topology = session_handle.topology(tuple(path.as_posix() for path in vin_dirs), paths, int(source_id))
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


def _render_store_header_summary(session_handle: Any) -> None:
    """Render reference coverage and physical cost without candidate projection."""

    header = session_handle.header()
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
    cost_cols = st.columns(4)
    cost_cols[0].metric("Bytes / rollout", _format_bytes(header.get("physical_bytes_per_rollout")))
    cost_cols[1].metric("Bytes / candidate", _format_bytes(header.get("physical_bytes_per_candidate")))
    cost_cols[2].metric("Return semantics", str(header.get("return_semantics") or "n/a"))
    discount_gamma = header.get("discount_gamma")
    cost_cols[3].metric("Discount gamma", "n/a" if discount_gamma is None else f"{float(discount_gamma):g}")
    _download_json("Download coverage and cost JSON", "rollout-coverage-cost.json", header)


def _render_validated_store_header(session_handle: Any, *, validation_ok: bool) -> None:
    """Render scientific coverage only for a store that passed validation."""

    if not validation_ok:
        st.info("Coverage and physical-cost projections are withheld until store validation succeeds.")
        return
    _render_store_header_summary(session_handle)


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
