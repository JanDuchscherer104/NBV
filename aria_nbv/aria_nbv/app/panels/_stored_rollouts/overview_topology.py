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
from ...scientific_labels import TheoryReferences
from ..common import current_scientific_label, render_scientific_notation
from .session import _cached_projection, _cached_topology, clear_rollout_page_caches
from .shared import _ROLE_COLORS, ExplanationSection, ScientificExplanation
from .shared import download_frame as _download_frame
from .shared import download_json as _download_json
from .shared import render_plot as _render_plot

_EVIDENCE_REPORTING_REFERENCE = (
    "ARRIVE reporting guidance for individual data and summaries",
    "https://arriveguidelines.org/arrive-guidelines/results/10a/explanation",
)
_FAILURE_COUNT_REFERENCE = (
    "NIST Engineering Statistics Handbook: counts and nonconformities",
    "https://www.itl.nist.gov/div898/handbook/toolaids/pff/pmc.pdf",
)


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
    if col_status.button(
        "Refresh rollout caches",
        help="Clear cached rollout and training-bundle read models after creating or replacing an artifact.",
    ):
        clear_rollout_page_caches()
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


def _render_corpus_endpoint_distributions(summary: RolloutCorpusSummary | None) -> None:
    """Render corpus endpoint plots first; raw rows stay opt-in below them."""

    st.subheader("Corpus endpoint distributions")
    if summary is None:
        st.info("Build the corpus summary in Overview before viewing corpus endpoints.")
        return
    if summary.endpoints.empty:
        st.info("No validated endpoint rows are available.")
        return
    metric = next(
        (name for name in ("endpoint_gain", "target_rri", "cumulative_target_root_gain") if name in summary.endpoints),
        None,
    )
    if metric is None:
        st.info("The selected stores do not expose a supported endpoint metric.")
        return
    render_scientific_notation(metric)
    fig = px.box(
        summary.endpoints,
        x="profile",
        y=metric,
        color="policy",
        facet_col="horizon",
        hover_data=["store_id"],
        labels={metric: current_scientific_label(metric)},
        title=(f"Store-qualified factual endpoint distributions: {current_scientific_label(metric)}"),
    )
    _render_plot(
        fig,
        ScientificExplanation(
            question="How are factual rollout endpoints distributed across selected validated shards?",
            answer="The endpoint boxes show the observed store-to-store distribution for each matched profile, policy, and horizon.",
            sections=(
                ExplanationSection(
                    title="Following the population",
                    body=("One store-qualified factual rollout endpoint, faceted by persisted horizon.")
                    + "\n\n"
                    + (f"{metric}; units follow the persisted endpoint metric contract.")
                    + "\n\n"
                    + (
                        "Validated included stores and finite factual endpoints only; excluded stores contribute no values."
                    )
                    + "\n\n"
                    + (
                        "Each box summarizes finite endpoint values; color separates policy and facets preserve horizon while store_id remains available on hover."
                    ),
                ),
                ExplanationSection(
                    title="Reading the evidence",
                    body=(
                        "Compare within profile, policy, horizon, and the persisted contract; store identity remains visible."
                    )
                    + "\n\n"
                    + (
                        "Distributions remain stable across shards of one profile rather than being driven by one store."
                    )
                    + "\n\n"
                    + (
                        "Endpoint variability is a corpus-coverage diagnostic: it reveals whether the reported return is supported across shards rather than one pooled average."
                    )
                    + "\n\n"
                    + (
                        "Excluded stores contribute no values; compare medians and spread only within the same persisted endpoint contract and profile."
                    ),
                ),
                ExplanationSection(
                    title="What to investigate",
                    body=(
                        "Separated or heavy-tailed store distributions suggest a source, profile, or rollout-quality issue requiring drill-down."
                    )
                    + "\n\n"
                    + (
                        "An endpoint is the final factual selected step recorded for one rollout; early-terminated rollouts contribute their observed terminal value rather than an imputed horizon value."
                    ),
                ),
            ),
            evidence_role="oracle/evaluation",
            source_fields=("reporting.RolloutCorpusSummary.endpoints", "rollouts", "steps"),
            theory=TheoryReferences(equation_ids=("entity.endpoint_gain",)),
            external_references=(
                (
                    "Canonical ARIA-NBV RRI definition",
                    "https://github.com/JanDuchscherer104/ARIA-NBV/blob/main/docs/typst/shared/equations/rri.typ",
                ),
            ),
        ),
    )
    with st.expander("Endpoint rows and CSV", expanded=False):
        st.dataframe(summary.endpoints, hide_index=True, width="stretch")
        _download_frame("Download endpoint rows CSV", "corpus-endpoints.csv", summary.endpoints)


def _render_corpus_admission(summary: RolloutCorpusSummary | None) -> None:
    """Render additive admission and feasibility evidence without reward metrics."""

    st.subheader("Corpus admission and feasibility")
    if summary is None:
        st.info("Build the corpus summary in Overview before viewing admission evidence.")
        return
    if summary.target_admission.empty:
        st.info("No validated target-admission rows are available.")
    else:
        target_rows = summary.target_admission.copy()
        target_rows["admission"] = target_rows.apply(
            lambda row: (
                f"actor={bool(row['target_valid'])} · gt={bool(row['gt_label_valid'])} · {row['gt_match_status']}"
            ),
            axis=1,
        )
        _render_plot(
            px.bar(target_rows, x="admission", y="count", color="gt_label_valid", title="Target admission outcomes"),
            ScientificExplanation(
                question="Which actor-visible targets remain valid and receive an unambiguous GT label?",
                answer="The bars count every target outcome so that actor admission and privileged GT-label admission remain auditable separate decisions.",
                sections=(
                    ExplanationSection(
                        title="Following the population",
                        body=("One persisted target row across validated selected stores.")
                        + "\n\n"
                        + ("Target count by actor validity, GT-label validity, and exact match status.")
                        + "\n\n"
                        + (
                            "All persisted target rows; invalid, ambiguous, unmatched, and below-threshold rows remain explicit."
                        )
                        + "\n\n"
                        + (
                            "Each bar is the number of persisted targets in one combined actor-validity, GT-label-validity, and match-status category; color preserves label validity."
                        ),
                    ),
                    ExplanationSection(
                        title="Reading the evidence",
                        body=("Target-selection and GT-matching contracts must match before comparing counts.")
                        + "\n\n"
                        + (
                            "Admitted targets have actor and GT validity; non-admitted categories remain visible rather than becoming low-RRI examples."
                        )
                        + "\n\n"
                        + (
                            "An executable target is not automatically a trainable oracle-label target: exactly one same-class qualifying GT match is an independent requirement."
                        )
                        + "\n\n"
                        + (
                            "These are additive protocol counts, not effect estimates. Invalid, ambiguous, unmatched, and below-threshold targets stay visible instead of being converted to low-reward examples."
                        ),
                    ),
                    ExplanationSection(
                        title="What to investigate",
                        body=(
                            "A rise in ambiguous or unmatched rows indicates target or evidence coverage trouble, not an effect-size change."
                        )
                        + "\n\n"
                        + (
                            "A valid privileged label requires exactly one same-class GT match with strict oriented IoU greater than 0.20; equality and ambiguity are rejected."
                        ),
                    ),
                ),
                evidence_role="oracle/evaluation",
                source_fields=("reporting.RolloutCorpusSummary.target_admission", "targets/gt_match_status_id"),
                external_references=(
                    (
                        "Canonical observed-target admission",
                        "https://github.com/JanDuchscherer104/ARIA-NBV/blob/main/aria_nbv/aria_nbv/oracle/target_selection.py#L96-L169",
                    ),
                ),
            ),
        )
        with st.expander("Target-admission rows and CSV", expanded=False):
            st.dataframe(target_rows, hide_index=True, width="stretch")
            _download_frame("Download target-admission CSV", "corpus-target-admission.csv", target_rows)
    if summary.feasibility.empty:
        st.info("No validated collision or clearance availability rows are available.")
        return
    feasibility = summary.feasibility
    fig = px.bar(
        feasibility.melt(
            id_vars=["generation_cohort"],
            value_vars=["collision_rate", "clearance_coverage"],
            var_name="metric",
            value_name="fraction",
        ),
        x="generation_cohort",
        y="fraction",
        color="metric",
        barmode="group",
        title="Collision rate and clearance-evidence coverage by generation cohort",
    )
    _render_plot(
        fig,
        ScientificExplanation(
            question="Does each exact candidate-generation cohort retain collision and clearance evidence?",
            answer="The paired bars show whether each frozen generation cohort has enough collision and clearance evidence to assess action feasibility.",
            sections=(
                ExplanationSection(
                    title="Following the population",
                    body=("Additive candidate counts from validated stores, kept separate by generation cohort.")
                    + "\n\n"
                    + ("Collision rate among evaluated candidates and fraction with finite clearance evidence.")
                    + "\n\n"
                    + (
                        "Collision uses evaluated candidates; clearance uses its persisted finite-value denominator. Zero denominators remain unavailable, not zero."
                    )
                    + "\n\n"
                    + (
                        "For every exact generation cohort, grouped bars show collision rate and the fraction with finite clearance evidence on the common fractional scale."
                    ),
                ),
                ExplanationSection(
                    title="Reading the evidence",
                    body=(
                        "Compare exact generation cohorts only; no per-store macro or calibration estimate is averaged."
                    )
                    + "\n\n"
                    + (
                        "Clearance coverage is high where the geometry audit is available, while collision rates remain interpretable per cohort."
                    )
                    + "\n\n"
                    + (
                        "Collision frequency and clearance coverage diagnose different issues: a candidate can be non-colliding yet lack the geometric evidence required for a clearance conclusion."
                    )
                    + "\n\n"
                    + (
                        "Each rate is recomputed from additive persisted counts and zero denominators stay unavailable; cohorts are intentionally separated rather than averaged across incompatible candidate contracts."
                    ),
                ),
                ExplanationSection(
                    title="What to investigate",
                    body=(
                        "Missing coverage or elevated collision rates point to candidate geometry/support failures and warrant active-store drill-down."
                    )
                    + "\n\n"
                    + (
                        "Collision rate = collided evaluated candidates / evaluated candidates; clearance coverage = candidates with finite persisted clearance / its eligible persisted denominator."
                    ),
                ),
            ),
            evidence_role="actor-visible",
            source_fields=("reporting.RolloutCorpusSummary.feasibility", "candidate_diagnostics/path_collision_mask"),
            external_references=(_EVIDENCE_REPORTING_REFERENCE,),
        ),
    )
    with st.expander("Candidate support, feasibility rows, and CSV", expanded=False):
        st.dataframe(summary.candidate_support, hide_index=True, width="stretch")
        st.dataframe(feasibility, hide_index=True, width="stretch")
        _download_frame("Download candidate support CSV", "corpus-candidate-support.csv", summary.candidate_support)
        _download_frame("Download feasibility CSV", "corpus-feasibility.csv", feasibility)


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
            answer="The bars prioritize the failure predicates occurring most often among the selected validated stores so an investigator can choose an evidence trail to inspect.",
            sections=(
                ExplanationSection(
                    title="Following the population",
                    body=(
                        "Additive failure findings from validated included stores, grouped by exact kind and severity."
                    )
                    + "\n\n"
                    + ("Finding count; counts prioritize debugging and are not independent scientific samples.")
                    + "\n\n"
                    + ("Only findings emitted by included validated stores; excluded-store reasons remain in Overview.")
                    + "\n\n"
                    + (
                        "Bar height is the additive number of emitted findings, x is exact failure kind, and color separates the persisted severity category."
                    ),
                ),
                ExplanationSection(
                    title="Reading the evidence",
                    body=("Compare counts only for the same selected corpus and failure rules.")
                    + "\n\n"
                    + ("Hard contract failures are absent or sparse and every count is traceable to a store.")
                    + "\n\n"
                    + (
                        "Failure findings are operational signals at mixed rollout, step, candidate, target, and store grains; concentration identifies where to debug, not what policy is better."
                    )
                    + "\n\n"
                    + (
                        "Counts depend on the selected corpus and failure rules and are not independent scientific samples; excluded-store reasons remain separate from these values."
                    ),
                ),
                ExplanationSection(
                    title="What to investigate",
                    body=("Large counts identify debugging priorities, not policy-performance effects.")
                    + "\n\n"
                    + (
                        "A failure count is the number of emitted diagnostic predicates, not the number of independent rollouts or an estimated failure probability."
                    ),
                ),
            ),
            evidence_role="provenance",
            source_fields=("reporting.RolloutCorpusSummary.failure_counts", "inspection.suspicious_rollout_rows"),
            external_references=(_FAILURE_COUNT_REFERENCE,),
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
        invariants = _cached_projection(reader.store_dir.as_posix(), "invariants")
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
                    answer="The Sankey maps which rollout payloads and external artifacts the selected store declares, resolves, infers, or fails to locate.",
                    sections=(
                        ExplanationSection(
                            title="Following the population",
                            body=("Aggregate artifact nodes and typed edges; source rows are collapsed by default.")
                            + "\n\n"
                            + ("Edge width is relationship count, not bytes or scientific effect size.")
                            + "\n\n"
                            + ("All recorded topology links for the selected rollout store and discovered VIN stores.")
                            + "\n\n"
                            + (
                                "Nodes are artifact or modality classes and link width is the number of recorded relationships; it does not encode bytes, quality, or causal influence."
                            ),
                        ),
                        ExplanationSection(
                            title="Reading the evidence",
                            body=("Compare resolution classes only; node width does not imply data quality.")
                            + "\n\n"
                            + ("Manifest hashes resolve uniquely and required actor/oracle modalities have one owner.")
                            + "\n\n"
                            + (
                                "Scientific values can only be interpreted in context when their source, actor inputs, oracle material, and configuration references have one traceable owner."
                            )
                            + "\n\n"
                            + (
                                "Topology is a provenance inventory, not a validity proof: a resolved path still requires the store's schema and semantic validation before scientific use."
                            ),
                        ),
                        ExplanationSection(
                            title="What to investigate",
                            body=(
                                "Missing or ambiguous links indicate incomplete local provenance, not invalid scientific values by themselves."
                            )
                            + "\n\n"
                            + (
                                "A topology link records a persisted or resolved relationship between rollout and VIN/store artifacts; its class states whether the relation is embedded, resolved, inferred, or missing."
                            ),
                        ),
                    ),
                    evidence_role="provenance",
                    source_fields=("rollout manifest source lineage", "VIN manifest", "PathConfig", "mesh paths"),
                    external_references=(_EVIDENCE_REPORTING_REFERENCE,),
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

    header = _cached_projection(store_path, "header")
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
