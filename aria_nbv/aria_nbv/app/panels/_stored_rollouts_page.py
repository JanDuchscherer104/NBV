"""Science-first Streamlit workflow for persisted rollout inspection.

The page deliberately keeps data semantics in :mod:`aria_nbv.rollouts.inspection`
and lifecycle semantics in :mod:`aria_nbv.app.rerun_launch`.  This module owns
only interaction state, progressive disclosure, plotting, and download widgets.
"""

from __future__ import annotations

import hashlib
import html
import json
from collections import Counter
from collections.abc import MutableMapping
from dataclasses import asdict, dataclass
from itertools import pairwise
from pathlib import Path
from typing import Any, Literal

import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from ...configs import PathConfig
from ...dataset_topology import discover_vin_store_dirs
from ...rerun_inspector import RolloutLayerName, RolloutLayerPreset
from ...rollouts import RolloutZarrStoreReader
from ...rollouts.inspection import (
    CANDIDATE_GROUP_FIELDS,
    candidate_geometry_evidence_rows,
    rollout_endpoint_metric_summary,
    selected_depth_preview,
)
from ..rerun_launch import (
    RerunLaunchMode,
    build_rerun_rollout_command,
    format_command,
    poll_rerun_launch,
    rerun_web_url,
    resolve_rollout_launch_config,
    restart_rerun_launch,
    start_rerun_launch,
    stop_rerun_launch,
)
from . import _stored_rollout_session as session
from .common import _report_exception

_SECTIONS = (
    "Trust & Topology",
    "Scientific Evidence",
    "Targets & Action Support",
    "Failure Triage",
    "Inspect, Export & Rerun",
)
_ROLE_COLORS = {
    "actor-visible": "#1f77b4",
    "oracle/evaluation": "#d62728",
    "derived training data": "#9467bd",
    "provenance": "#6b7280",
}
_SECTION_KEY = "stored_rollouts_section"
_LAUNCH_HANDLE_KEY = "stored_rollouts_rerun_handle"
_ACTIVE_QUERY_STORE_KEY = "stored_rollouts_active_query_store"
_QUERY_SCOPES = ("Rollout summaries", "Factual steps", "Candidates")
_CANDIDATE_POPULATIONS = ("Selected step", "Selected rollout", "Explicit full store")
_TEMPORAL_METRIC_LABELS = {
    "Cumulative target root gain": "cumulative_target_root_gain",
    "Selected one-step target root gain": "selected_target_root_gain",
    "Selected target RRI": "selected_target_rri",
    "Marginal target RRI": "marginal_target_rri",
    "Valid candidate fanout": "valid_fanout",
    "Invalid candidate fraction": "invalid_fraction",
    "Selected-action probability": "selected_probability",
    "Selected-action entropy": "selected_entropy",
}
_TEMPORAL_GROUP_CLASSES = {
    "Upstream experiment dimensions": ("policy", "horizon", "budget_configuration"),
    "Selected-action provenance (descriptive, non-causal)": (
        "selected_position",
        "selected_strategy",
        "selected_mixture",
    ),
}
_TEMPORAL_SOURCE_FIELDS = {
    "valid_fanout": "num_valid_candidates",
}
_TEMPORAL_EVIDENCE_ROLES: dict[
    str,
    Literal["actor-visible", "oracle/evaluation", "derived training data", "provenance"],
] = {
    "cumulative_target_root_gain": "oracle/evaluation",
    "selected_target_root_gain": "oracle/evaluation",
    "selected_target_rri": "oracle/evaluation",
    "marginal_target_rri": "oracle/evaluation",
    "valid_fanout": "actor-visible",
    "invalid_fraction": "actor-visible",
    "selected_probability": "actor-visible",
    "selected_entropy": "actor-visible",
}


@dataclass(frozen=True, slots=True)
class ScientificExplanation:
    """Complete interpretation contract shown beside one primary visualization."""

    question: str
    """Scientific question answered by the visualization."""

    population: str
    """Row grain and population included in the view."""

    metric: str
    """Metric role and physical or dimensionless units."""

    denominator_masks: str
    """Denominator and active validity masks."""

    comparability: str
    """Conditions required before comparing marks."""

    expected_pattern: str
    """Expected pattern under a healthy data-generation process."""

    failure_interpretation: str
    """Warning patterns and plausible failure causes."""

    evidence_role: Literal["actor-visible", "oracle/evaluation", "derived training data", "provenance"]
    """Information boundary represented by the view."""

    source_fields: tuple[str, ...]
    """Persisted arrays or shared inspection helpers that own the evidence."""

    intuition: str | None = None
    """Plain-language intuition for exploring the visualization."""

    visual_encoding: str | None = None
    """How marks, colours, facets, and missingness are encoded."""

    uncertainty: str | None = None
    """What spread, missingness, or finite-sample limitation means here."""

    theory_references: tuple["TheoryReference", ...] = ()
    """Canonical project references for the equations and terms behind the view."""

    def __post_init__(self) -> None:
        """Reject incomplete explanation contracts before a plot can render."""

        required = (
            self.question,
            self.population,
            self.metric,
            self.denominator_masks,
            self.comparability,
            self.expected_pattern,
            self.failure_interpretation,
        )
        if any(not value.strip() for value in required) or not self.source_fields:
            raise ValueError("Scientific explanations require every interpretation field and at least one source.")


@dataclass(frozen=True, slots=True)
class TheoryReference:
    """One browser-addressable canonical notation or theory reference."""

    title: str
    url: str
    kind: Literal["equation", "symbol", "glossary", "source"]
    registry_key: str | None = None

    def __post_init__(self) -> None:
        if not self.title.strip() or not self.url.startswith("https://"):
            raise ValueError("Theory references require a title and HTTPS URL.")


TheoryKind = Literal[
    "geometry",
    "direction",
    "action",
    "target",
    "code",
    "validity",
    "endpoint_gain",
    "rri",
]


_THEORY: dict[TheoryKind, tuple[TheoryReference, ...]] = {
    "geometry": (
        TheoryReference(
            "Candidate reference-frame transform",
            "https://github.com/JanDuchscherer104/ARIA-NBV/blob/main/docs/typst/shared/equations/spatial.typ",
            "equation",
            "spatial.candidate_reference_transform",
        ),
        TheoryReference(
            "Spatial notation registry",
            "https://github.com/JanDuchscherer104/ARIA-NBV/blob/main/docs/notation.yml",
            "symbol",
            "spatial.candidate_reference_transform",
        ),
    ),
    "direction": (
        TheoryReference(
            "Candidate angles and shell",
            "https://github.com/JanDuchscherer104/ARIA-NBV/blob/main/docs/typst/shared/equations/action.typ",
            "equation",
            "action.angle_cap_transform",
        ),
        TheoryReference(
            "Finite candidate-view glossary",
            "https://github.com/JanDuchscherer104/ARIA-NBV/blob/main/docs/typst/shared/glossary.typ",
            "glossary",
            "finite-candidate-action-set",
        ),
    ),
    "action": (
        TheoryReference(
            "Candidate angle transform",
            "https://github.com/JanDuchscherer104/ARIA-NBV/blob/main/docs/typst/shared/equations/action.typ",
            "equation",
            "action.angle_cap_transform",
        ),
        TheoryReference(
            "Candidate shell and motion limits",
            "https://github.com/JanDuchscherer104/ARIA-NBV/blob/main/docs/typst/shared/equations/action.typ",
            "equation",
            "action.candidate_shell",
        ),
        TheoryReference(
            "Motion pruning limits",
            "https://github.com/JanDuchscherer104/ARIA-NBV/blob/main/docs/typst/shared/equations/action.typ",
            "equation",
            "action.motion_pruning_limits",
        ),
    ),
    "target": (
        TheoryReference(
            "Target-view glossary",
            "https://github.com/JanDuchscherer104/ARIA-NBV/blob/main/docs/typst/shared/glossary.typ",
            "glossary",
            "frustum",
        ),
    ),
    "code": (
        TheoryReference(
            "Inspection diagnostic implementation",
            "https://github.com/JanDuchscherer104/ARIA-NBV/blob/main/aria_nbv/aria_nbv/rollouts/inspection.py",
            "source",
            None,
        ),
    ),
    "validity": (
        TheoryReference(
            "Candidate validity equations",
            "https://github.com/JanDuchscherer104/ARIA-NBV/blob/main/docs/typst/shared/equations/metrics.typ",
            "equation",
            "metrics.candidate_validity",
        ),
    ),
    "endpoint_gain": (
        TheoryReference(
            "Endpoint gain equation",
            "https://github.com/JanDuchscherer104/ARIA-NBV/blob/main/docs/typst/shared/equations/entity.typ",
            "equation",
            "entity.endpoint_gain",
        ),
    ),
    "rri": (
        TheoryReference(
            "RRI equation",
            "https://github.com/JanDuchscherer104/ARIA-NBV/blob/main/docs/typst/shared/equations/rri.typ",
            "equation",
            "rri.rri",
        ),
        TheoryReference(
            "Target RRI equation",
            "https://github.com/JanDuchscherer104/ARIA-NBV/blob/main/docs/typst/shared/equations/rri.typ",
            "equation",
            "rri.target_rri",
        ),
        TheoryReference(
            "RRI glossary definition",
            "https://github.com/JanDuchscherer104/ARIA-NBV/blob/main/docs/typst/shared/glossary.typ",
            "glossary",
            "target-rri-reward",
        ),
    ),
}


def render_stored_rollouts_page() -> None:
    """Render the five-workspace stored-rollout inspection workflow."""

    st.header("Rollout Supervision")
    st.caption(
        "Inspect persisted rollout Zarr artifacts: trust the artifact first, compare only matched evidence, "
        "then inspect one failure or rollout in depth."
    )
    _render_role_legend()

    paths = PathConfig()
    inventory = session.cached_inventory(paths.offline_cache_dir.as_posix())
    store_path = _render_store_selector(paths, inventory)
    if store_path is None:
        st.info("No rollout store is selected. Choose a discovered store or enter a path.")
        return

    selected_inventory = next((row for row in inventory if Path(str(row["path"])) == store_path), None)
    try:
        stored_session = session.open_stored_rollout_session(store_path, inventory_row=selected_inventory)
        reader = stored_session.reader
        validation = stored_session.validation
        manifest_payload = stored_session.manifest_payload
    except Exception as exc:
        st.error(f"The selected store cannot be opened: {type(exc).__name__}: {exc}")
        _download_json("Download store identity JSON", "rollout-store-identity.json", selected_inventory or {})
        return

    tabs = st.tabs(
        list(_SECTIONS),
        default=st.session_state.get(_SECTION_KEY, _SECTIONS[0]),
        key=_SECTION_KEY,
        on_change="rerun",
        width="stretch",
    )
    current = bool(validation.ok)

    if tabs[0].open:
        with tabs[0]:
            _render_trust_and_topology(
                reader=reader,
                store_path=store_path,
                inventory_row=selected_inventory,
                manifest_payload=manifest_payload,
                paths=paths,
                validation_ok=current,
                stored_session=stored_session,
            )
    for tab, renderer in zip(
        tabs[1:],
        (_render_scientific_evidence, _render_targets_and_support, _render_failure_triage),
        strict=False,
    ):
        if not tab.open:
            continue
        with tab:
            if current:
                renderer(reader, stored_session=stored_session)
            else:
                _render_stale_store_boundary(
                    validation,
                    inventory_row=selected_inventory,
                    manifest_payload=manifest_payload,
                )
    if tabs[4].open:
        with tabs[4]:
            if current:
                _render_inspect_export_rerun(
                    reader,
                    store_path=store_path,
                    manifest_payload=manifest_payload,
                    paths=paths,
                    stored_session=stored_session,
                )
            else:
                _render_stale_store_boundary(
                    validation,
                    inventory_row=selected_inventory,
                    manifest_payload=manifest_payload,
                )


def _render_store_selector(paths: PathConfig, inventory: list[dict[str, object]]) -> Path | None:
    """Render compact store selection without materializing candidate evidence."""

    col_store, col_status = st.columns([4, 1])
    selected: Path | None = None
    if inventory:
        row = col_store.selectbox(
            "rollouts.zarr store",
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
        col_store.info(f"No `*.zarr` rollout stores found below `{paths.offline_cache_dir}`.")

    with st.expander("Store path override", expanded=not inventory):
        manual = st.text_input("Manual rollouts.zarr path", value="", key="rollout_store_manual_path")
        if manual.strip():
            candidate = Path(manual).expanduser()
            if not candidate.is_absolute():
                candidate = paths.resolve_cache_artifact_dir(manual)
            selected = candidate.resolve()
    if col_status.button("Refresh stores", help="Clear inspector caches after creating or replacing a store."):
        session.clear_stored_rollout_caches()
        st.rerun()
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
    reader: RolloutZarrStoreReader,
    store_path: Path,
    inventory_row: dict[str, object] | None,
    manifest_payload: dict[str, Any],
    paths: PathConfig,
    validation_ok: bool,
    stored_session: session.StoredRolloutSession,
) -> None:
    st.subheader("Trust & Topology")
    counts = inventory_row or {}
    cols = st.columns(5)
    cols[0].metric("Schema", str(counts.get("schema_status", "unknown")))
    cols[1].metric("Validation", "OK" if validation_ok else "BLOCKED")
    cols[2].metric("Rollouts", str(counts.get("observed_rollouts", "?")))
    cols[3].metric("Steps", str(counts.get("observed_steps", "?")))
    cols[4].metric("Candidates", str(counts.get("observed_candidates", "?")))

    _render_validated_store_header(stored_session, validation_ok=validation_ok)

    try:
        invariants = stored_session.invariants()
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
        topology = stored_session.topology(
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
                topology = stored_session.topology(
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


def _render_store_header_summary(stored_session: session.StoredRolloutSession) -> None:
    """Render reference coverage and physical cost without candidate projection."""

    header = stored_session.header()
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


def _render_validated_store_header(stored_session: session.StoredRolloutSession, *, validation_ok: bool) -> None:
    """Render scientific coverage only for a store that passed validation."""

    if not validation_ok:
        st.info("Coverage and physical-cost projections are withheld until store validation succeeds.")
        return
    _render_store_header_summary(stored_session)


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


def _render_scientific_evidence(
    reader: RolloutZarrStoreReader, *, stored_session: session.StoredRolloutSession | None = None
) -> None:
    st.subheader("Scientific Evidence")
    stored_session = stored_session or session.open_stored_rollout_session(reader.store_dir)
    reader = stored_session.reader
    _render_reconstruction_summary(stored_session)
    cohort = stored_session.cohorts()
    eligibility = bool(cohort.get("eligible"))
    st.metric("Matched comparison eligible", "YES" if eligibility else "NO")
    st.caption(
        "Policies are comparison dimensions only after source sample, target protocol, horizon/budget, candidate/oracle configuration, and branch schedule match."
    )
    if eligibility:
        comparison = pd.DataFrame(stored_session.paired())
        if comparison.empty:
            st.info("Matched cohorts exist, but no finite paired endpoint metric is available.")
        else:
            y = (
                "median_paired_delta"
                if "median_paired_delta" in comparison
                else comparison.select_dtypes("number").columns[-1]
            )
            label = "policy_pair" if "policy_pair" in comparison else comparison.columns[0]
            color = "metric" if "metric" in comparison else None
            comparison[y] = pd.to_numeric(comparison[y], errors="coerce")
            ci_high = pd.to_numeric(comparison["bootstrap_ci_high"], errors="coerce")
            ci_low = pd.to_numeric(comparison["bootstrap_ci_low"], errors="coerce")
            comparison["ci_plus"] = ci_high - comparison[y]
            comparison["ci_minus"] = comparison[y] - ci_low
            fig = px.bar(
                comparison,
                x=label,
                y=y,
                color=color,
                error_y="ci_plus",
                error_y_minus="ci_minus",
                barmode="group",
                title="Paired matched-cohort deltas with deterministic bootstrap intervals",
            )
            _render_plot(
                fig,
                ScientificExplanation(
                    question="Within exactly matched cohorts, how do policies differ at the rollout endpoint?",
                    population="One paired delta per matched source/target/recipe/budget cohort, summarized by policy pair.",
                    metric="Median paired target endpoint or root-gain delta; RRI/root gain are dimensionless.",
                    denominator_masks="Only finite matched endpoint rows; sample count and IQR/bootstrap interval remain in the table.",
                    comparability="All cohort keys must match; policy/recipe is the only intended comparison dimension.",
                    expected_pattern="Intervals and paired deltas are stable across cohorts rather than driven by one scene.",
                    failure_interpretation="Wide intervals or sign changes indicate weak evidence; they are not policy wins.",
                    evidence_role="oracle/evaluation",
                    source_fields=("inspection.paired_policy_comparison_rows", "rollouts", "steps"),
                ),
            )
            st.dataframe(comparison, hide_index=True, width="stretch")
            _download_frame("Download paired comparison CSV", "paired-policy-comparison.csv", comparison)
    else:
        mismatch = pd.DataFrame(cohort.get("mismatch_rows", []))
        st.warning("Policy comparison is blocked because the store does not contain an exact matched cohort.")
        if not mismatch.empty:
            st.dataframe(mismatch, hide_index=True, width="stretch")
            _download_frame("Download mismatch evidence CSV", "policy-cohort-mismatches.csv", mismatch)

    steps = pd.DataFrame(stored_session.steps())
    if not steps.empty:
        _render_temporal_explorer(stored_session, steps, matched_cohorts=eligibility)
        _download_frame("Download selected-chain CSV", "selected-chain-evidence.csv", steps)

    with st.expander("Additional branching and selected-rank evidence", expanded=False):
        if st.toggle(
            "Load branching, rank/regret, and root-relative evidence",
            value=False,
            help="These projections traverse every factual step and candidate shell, then remain cached for this store.",
        ):
            _render_branching_evidence(steps, pd.DataFrame(stored_session.tree()))
            _render_selected_rank_and_geometry(stored_session)


def _render_reconstruction_summary(stored_session: session.StoredRolloutSession) -> None:
    """Render frozen reconstruction, return, and headroom rows on demand."""

    if not st.toggle(
        "Load reconstruction endpoints, discounted returns, and oracle headroom",
        value=False,
        help="Materializes only frozen inspection projections after this explicit request.",
    ):
        return

    metric_rows = pd.DataFrame(stored_session.reconstruction_metrics())
    endpoint_rows = pd.DataFrame(stored_session.reconstruction_endpoints())
    discounted = stored_session.discounted_returns()
    headroom = stored_session.headroom()

    st.markdown("#### Reconstruction and selection metric plan")
    if metric_rows.empty:
        st.info("No factual reconstruction metric rows are available.")
    else:
        st.dataframe(metric_rows, hide_index=True, width="stretch")
        _download_frame("Download reconstruction metric CSV", "reconstruction-metrics.csv", metric_rows)
    if not endpoint_rows.empty:
        st.dataframe(endpoint_rows, hide_index=True, width="stretch")
        _download_frame("Download endpoint summary CSV", "reconstruction-endpoints.csv", endpoint_rows)

    st.markdown("#### Discounted factual selected gain")
    discounted_rows = pd.DataFrame(discounted.get("rows", []))
    if bool(discounted.get("available")) and not discounted_rows.empty:
        st.caption(str(discounted.get("reason")))
        st.dataframe(discounted_rows, hide_index=True, width="stretch")
        _download_frame("Download discounted return CSV", "discounted-returns.csv", discounted_rows)
    else:
        st.info(f"Discounted return unavailable: {discounted.get('reason', 'no factual rows')}")

    st.markdown("#### Exact-role oracle headroom diagnostics")
    st.caption("These are diagnostic contrasts, not causal policy comparisons. Exclusions remain explicit.")
    headroom_rows = pd.DataFrame(headroom.get("contrast_rows", []))
    headroom_summary = pd.DataFrame(headroom.get("summary_rows", []))
    if headroom_rows.empty:
        st.info("No exact-role headroom contrasts are available.")
    else:
        st.dataframe(headroom_rows, hide_index=True, width="stretch")
        _download_frame("Download headroom contrasts CSV", "oracle-headroom-contrasts.csv", headroom_rows)
    if not headroom_summary.empty:
        st.dataframe(headroom_summary, hide_index=True, width="stretch")


def _render_temporal_explorer(
    stored_session: session.StoredRolloutSession, steps: pd.DataFrame, *, matched_cohorts: bool
) -> None:
    """Render one population metric at a time and a one-rollout raw drill-down."""

    available_labels = [
        label
        for label, metric in _TEMPORAL_METRIC_LABELS.items()
        if (source := _TEMPORAL_SOURCE_FIELDS.get(metric, metric)) in steps and steps[source].notna().any()
    ]
    if not available_labels:
        st.info("No supported finite temporal metric is available in this store.")
        return
    metric_label = st.selectbox("Temporal metric", options=available_labels)
    metric = _TEMPORAL_METRIC_LABELS[metric_label]
    group_class = st.selectbox("Temporal grouping class", options=list(_TEMPORAL_GROUP_CLASSES))
    group_field = st.selectbox("Temporal grouping field", options=list(_TEMPORAL_GROUP_CLASSES[group_class]))
    if group_class.startswith("Selected-action provenance"):
        st.warning(
            "Selected-action provenance is descriptive and post-selection, not a causal sampling-policy effect. "
            "It explains which persisted provenance supplied selected outcomes; full candidate-family availability "
            "belongs to the support flow in Targets & Action Support."
        )
    elif group_field == "policy":
        comparison_status = "eligible" if matched_cohorts else "not eligible"
        st.caption(
            f"Policy trajectories are descriptive here; exact matched-cohort inference is {comparison_status} "
            "and remains a separate surface above."
        )

    summary = pd.DataFrame(
        stored_session.temporal(
            metric=metric,
            group_fields=(group_field,),
        )
    )
    if summary.empty:
        st.info(f"No temporal rows are available for {metric_label} grouped by {group_field}.")
        return
    finite_count = int(summary["finite_count"].sum())
    total_count = int(summary["total_count"].sum())
    missing_count = int(summary["missing_count"].sum())
    endpoint_depth = int(summary["step_index"].max())
    endpoint = rollout_endpoint_metric_summary(steps.to_dict("records"), metric=metric)
    endpoint_median = endpoint["median"]
    cols = st.columns(4)
    cols[0].metric("Finite temporal rows", f"{finite_count:,} / {total_count:,}")
    cols[1].metric("Missing temporal rows", f"{missing_count:,}")
    cols[2].metric("Observed depth", f"0–{endpoint_depth}")
    cols[3].metric(
        "Factual endpoint median",
        "n/a" if endpoint_median is None else f"{float(endpoint_median):.4g}",
        delta=f"{int(endpoint['finite_count']):,} / {int(endpoint['total_count']):,} finite",
        delta_color="off",
        help="One terminal factual step per rollout, including rollouts whose persisted horizon ends earlier.",
    )
    _render_plot(
        _temporal_summary_figure(summary, group_field=group_field, metric_label=metric_label),
        ScientificExplanation(
            question=f"How does {metric_label.lower()} change over persisted rollout depth?",
            population=f"One aggregate per {group_field} and step_index over factual selected-step rows; individual rollouts are not connected.",
            metric=f"Median with linear-interpolated IQR; units are {summary['units'].iloc[0]}.",
            denominator_masks="Each point reports finite_count / total_count and missing fraction; statistics use finite values only with no zero fill or depth interpolation.",
            comparability="Upstream policy/recipe groups are descriptive unless exact cohort keys match; selected-action provenance groups are post-selection strata only.",
            expected_pattern="Central tendency and dispersion change smoothly where repeated evidence exists, with sample size visible at every depth.",
            failure_interpretation="Wide IQR, small n, abrupt missingness, or divergent strata require row-level inspection; they are not automatically policy effects.",
            evidence_role=_temporal_evidence_role(metric),
            source_fields=(
                "inspection.temporal_metric_summary_rows",
                f"steps/{_TEMPORAL_SOURCE_FIELDS.get(metric, metric)}",
            ),
            theory_references=_THEORY[_temporal_theory_kind(metric)],
        ),
    )
    st.dataframe(summary, hide_index=True, width="stretch")
    _download_frame("Download temporal summary CSV", "temporal-metric-summary.csv", summary)

    with st.expander("Raw selected-rollout trajectory drill-down", expanded=False):
        rollout_ids = sorted(int(value) for value in steps["rollout_row_id"].dropna().unique().tolist())
        selected_rollout = st.selectbox("Raw trajectory rollout", options=rollout_ids)
        selected_rows = steps.loc[steps["rollout_row_id"] == selected_rollout].sort_values("step_index")
        source_field = _TEMPORAL_SOURCE_FIELDS.get(metric, metric)
        raw = selected_rows.dropna(subset=[source_field])
        if raw.empty:
            st.info(f"Rollout {selected_rollout} has no finite {metric_label.lower()} rows.")
        else:
            fig = px.line(
                raw,
                x="step_index",
                y=source_field,
                markers=True,
                title=f"Raw trajectory for rollout {selected_rollout}",
                hover_data=[column for column in ("step_row_id", "policy") if column in raw],
            )
            _render_plot(
                fig,
                ScientificExplanation(
                    question=f"What exact {metric_label.lower()} trajectory produced rollout {selected_rollout}?",
                    population="One explicitly selected rollout only; no line joins unrelated rollout_row_id values.",
                    metric=f"Persisted {source_field}; units follow the aggregate view above.",
                    denominator_masks="Finite factual selected-step rows for this rollout; missing depths remain absent rather than interpolated.",
                    comparability="Use this for case inspection, not population or policy inference.",
                    expected_pattern="The raw trajectory should explain one aggregate contribution without hiding its exact step ids.",
                    failure_interpretation="Abrupt jumps or negative valid gains can identify an interesting case for Inspect/Rerun.",
                    evidence_role=_temporal_evidence_role(metric),
                    source_fields=("inspection.rollout_step_objective_rows", f"steps/{source_field}"),
                    theory_references=_THEORY[_temporal_theory_kind(metric)],
                ),
            )


def _temporal_summary_figure(summary: pd.DataFrame, *, group_field: str, metric_label: str) -> go.Figure:
    """Build deterministic median/IQR traces without connecting rollout rows."""

    figure = go.Figure()
    palette = px.colors.qualitative.Plotly
    for index, (group_value, rows) in enumerate(summary.groupby(group_field, sort=True, dropna=False)):
        ordered = rows.sort_values("step_index")
        color = palette[index % len(palette)]
        custom = np.column_stack(
            (
                ordered["finite_count"],
                ordered["total_count"],
                ordered["missing_count"] / ordered["total_count"].clip(lower=1),
                ordered["mean"],
                ordered["min"],
                ordered["max"],
            )
        )
        figure.add_trace(
            go.Scatter(
                x=ordered["step_index"],
                y=ordered["q25"],
                mode="lines",
                line={"color": color, "width": 0},
                legendgroup=str(group_value),
                showlegend=False,
                hoverinfo="skip",
            )
        )
        figure.add_trace(
            go.Scatter(
                x=ordered["step_index"],
                y=ordered["q75"],
                mode="lines",
                line={"color": color, "width": 0},
                fill="tonexty",
                fillcolor=_with_alpha(color, 0.18),
                legendgroup=str(group_value),
                showlegend=False,
                hoverinfo="skip",
            )
        )
        figure.add_trace(
            go.Scatter(
                x=ordered["step_index"],
                y=ordered["median"],
                mode="lines+markers",
                line={"color": color},
                name=str(group_value),
                legendgroup=str(group_value),
                customdata=custom,
                hovertemplate=(
                    f"{group_field}={group_value}<br>step=%{{x}}<br>median=%{{y:.4g}}"
                    "<br>finite=%{customdata[0]:.0f} / %{customdata[1]:.0f}"
                    "<br>missing=%{customdata[2]:.1%}<br>mean=%{customdata[3]:.4g}"
                    "<br>min=%{customdata[4]:.4g}<br>max=%{customdata[5]:.4g}<extra></extra>"
                ),
            )
        )
    figure.update_layout(
        title=f"{metric_label}: median and interquartile range by rollout depth",
        xaxis_title="rollout step_index",
        yaxis_title=f"{summary['metric'].iloc[0]} ({summary['units'].iloc[0]})",
        hovermode="x unified",
    )
    return figure


def _with_alpha(color: str, alpha: float) -> str:
    """Convert one Plotly hex color into an rgba fill color."""

    red, green, blue = (int(color[index : index + 2], 16) for index in (1, 3, 5))
    return f"rgba({red},{green},{blue},{alpha})"


def _temporal_evidence_role(
    metric: str,
) -> Literal["actor-visible", "oracle/evaluation", "derived training data", "provenance"]:
    """Return the information boundary for one validated temporal metric."""

    try:
        return _TEMPORAL_EVIDENCE_ROLES[metric]
    except KeyError as exc:
        raise ValueError(f"Temporal metric {metric!r} has no explicit evidence role.") from exc


def _temporal_theory_kind(metric: str) -> TheoryKind:
    """Return the canonical theory owner for one temporal metric."""

    if metric in {"cumulative_target_root_gain", "selected_target_root_gain"}:
        return "endpoint_gain"
    if metric in {"selected_target_rri", "marginal_target_rri"}:
        return "rri"
    if metric in {"valid_fanout", "invalid_fraction"}:
        return "validity"
    return "action"


def _render_selected_rank_and_geometry(stored_session: session.StoredRolloutSession) -> None:
    """Render expensive selected-rank and complete root-relative evidence on demand."""

    ranks = pd.DataFrame(stored_session.ranks())
    if not ranks.empty:
        rank_col = "selected_rank" if "selected_rank" in ranks else next((c for c in ranks if "rank" in c), None)
        regret_col = "regret" if "regret" in ranks else next((c for c in ranks if "regret" in c), None)
        if rank_col and regret_col:
            fig = px.scatter(
                ranks,
                x=rank_col,
                y=regret_col,
                color="policy" if "policy" in ranks else None,
                hover_data=[c for c in ("rollout_row_id", "step_row_id", "valid_candidate_count") if c in ranks],
                title="Selected rank and regret among valid alternatives",
            )
            _render_plot(
                fig,
                ScientificExplanation(
                    question="How far is each selected action from the best valid persisted alternative?",
                    population="One factual selected step ranked only against actor-valid alternatives in its own candidate shell.",
                    metric="Rank is ordinal; regret is best-valid minus selected target root gain, dimensionless.",
                    denominator_masks="Actor-action-valid alternatives with finite target root gain; invalid/missing labels are excluded, not assigned low reward.",
                    comparability="Ranks are shell-local; compare regret only under equivalent reward definitions and budgets.",
                    expected_pattern="Most selected actions have low rank and small regret without total diversity collapse.",
                    failure_interpretation="High regret suggests selection/model mismatch; negative valid rewards remain distinct from invalid rows.",
                    evidence_role="oracle/evaluation",
                    source_fields=(
                        "inspection.selected_candidate_rank_rows",
                        "candidates/actor_action_mask",
                        "candidates/target_root_gain",
                    ),
                ),
            )
        st.dataframe(ranks, hide_index=True, width="stretch")
        _download_frame("Download selected rank/regret CSV", "selected-rank-regret.csv", ranks)

    geometry = pd.DataFrame(stored_session.root_geometry())
    if not geometry.empty:
        st.caption(
            "Coordinates are translated by each rollout root. Absolute world coordinates from unrelated scenes are never aggregated."
        )
        st.dataframe(geometry.head(500), hide_index=True, width="stretch")
        st.caption(f"Showing {min(500, len(geometry)):,} of {len(geometry):,}; export is complete.")
        _download_frame("Download root-relative geometry CSV", "root-relative-candidates.csv", geometry)


def _render_branching_evidence(steps: pd.DataFrame, tree: pd.DataFrame) -> None:
    """Restore selection, fanout, and family-provenance plots from the prior inspector."""

    with st.expander("Branching, selection confidence, and sampled families", expanded=True):
        probability_cols = [
            name for name in ("selected_probability", "selected_entropy") if name in steps and steps[name].notna().any()
        ]
        if probability_cols:
            long = steps.melt(
                id_vars=[name for name in ("rollout_row_id", "policy", "step_index") if name in steps],
                value_vars=probability_cols,
                var_name="metric",
                value_name="value",
            ).dropna(subset=["value"])
            fig = px.line(
                long,
                x="step_index",
                y="value",
                color="policy" if "policy" in long else "rollout_row_id",
                facet_row="metric",
                markers=True,
                title="Selected-action probability and entropy by depth",
            )
            fig.update_yaxes(matches=None)
            _render_plot(
                fig,
                ScientificExplanation(
                    question="Does action selection become prematurely deterministic or remain indecisive with depth?",
                    population="One factual selected step; probability and entropy are shown on independent axes.",
                    metric="Selected probability and categorical entropy, both dimensionless.",
                    denominator_masks="The persisted candidate shell and selection distribution for each factual step.",
                    comparability="Candidate budget, temperature, beam width, and policy recipe must agree.",
                    expected_pattern="Confidence can rise with evidence while entropy does not collapse identically across every sample.",
                    failure_interpretation="Near-zero entropy everywhere suggests collapse; low probability with high regret suggests selection mismatch.",
                    evidence_role=_temporal_evidence_role("selected_probability"),
                    source_fields=("steps/selected_probability", "steps/selected_entropy"),
                ),
            )

        fanout_cols = [
            name for name in ("num_valid_candidates", "invalid_fraction") if name in steps and steps[name].notna().any()
        ]
        if fanout_cols:
            long = steps.melt(
                id_vars=[name for name in ("rollout_row_id", "policy", "step_index") if name in steps],
                value_vars=fanout_cols,
                var_name="metric",
                value_name="value",
            ).dropna(subset=["value"])
            fig = px.line(
                long,
                x="step_index",
                y="value",
                color="policy" if "policy" in long else "rollout_row_id",
                facet_row="metric",
                markers=True,
                title="Valid fanout and invalid fraction by depth",
            )
            fig.update_yaxes(matches=None)
            _render_plot(
                fig,
                ScientificExplanation(
                    question="Where does the usable action set narrow along the selected chain?",
                    population="One candidate shell per factual rollout step.",
                    metric="Valid candidate count and invalid fraction; separate axes prevent mixed-unit distortion.",
                    denominator_masks="Fanout counts actor-action-valid candidates; invalid fraction uses the complete sampled shell.",
                    comparability="Candidate shell size and generator configuration must match.",
                    expected_pattern="Fanout remains sufficient across depth and invalidity does not abruptly dominate.",
                    failure_interpretation="Low fanout or rising invalidity points to geometry, collision, or generator-support failures.",
                    evidence_role="actor-visible",
                    source_fields=("steps/num_valid_candidates", "steps/invalid_fraction"),
                ),
            )

        if not tree.empty and {"step_label", "selected_steps", "selected_position"}.issubset(tree.columns):
            fig = px.bar(
                tree,
                x="step_label",
                y="selected_steps",
                color="selected_position",
                facet_col="policy" if "policy" in tree and tree["policy"].nunique() > 1 else None,
                hover_data=[
                    name
                    for name in ("selected_strategy", "selected_mixture", "mean_valid_fanout", "mean_invalid_fraction")
                    if name in tree
                ],
                title="Observed selected-family provenance by rollout depth",
            )
            _render_plot(
                fig,
                ScientificExplanation(
                    question="Which candidate families actually supply the selected actions at each depth?",
                    population="Aggregated factual selected steps grouped by recipe, depth, and persisted family provenance.",
                    metric="Selected-step count; this is observed provenance, not a reconstructed search tree.",
                    denominator_masks="Selected actor-valid transitions only.",
                    comparability="Family vocabulary, mixture weights, policy recipe, and horizon must match.",
                    expected_pattern="Multiple intended families contribute without unexplained monopolies or disappearing depths.",
                    failure_interpretation="Single-family dominance can reflect policy preference, generator imbalance, or mask collapse and needs row-level inspection.",
                    evidence_role="provenance",
                    source_fields=(
                        "inspection.rollout_tree_summary_rows",
                        "candidate family ids",
                        "steps/selected_candidate_row_id",
                    ),
                ),
            )
            _download_frame("Download branching provenance CSV", "rollout-branching-provenance.csv", tree)


def _render_targets_and_support(
    reader: RolloutZarrStoreReader, *, stored_session: session.StoredRolloutSession | None = None
) -> None:
    st.subheader("Targets & Action Support")
    stored_session = stored_session or session.open_stored_rollout_session(reader.store_dir)
    reader = stored_session.reader
    candidate_plot_limit = int(
        st.number_input(
            "Candidate plot row limit",
            min_value=1_000,
            max_value=500_000,
            value=50_000,
            step=10_000,
            help="Bounds interactive geometry traces only; aggregate masks and family counts still use the full store.",
        )
    )
    # Geometry is a bounded, deterministic inspection aid.  It deliberately
    # uses the existing limited candidate projection and never opens the
    # complete candidate audit used by the aggregate support views below.
    bounded_candidates = pd.DataFrame(stored_session.candidates(limit=candidate_plot_limit))
    if not bounded_candidates.empty:
        _render_complete_candidate_support(
            {
                "geometry": candidate_geometry_evidence_rows(bounded_candidates.to_dict("records")),
                "population_count": int(reader.array("candidates/candidate_row_id").size),
            }
        )
    targets = pd.DataFrame(stored_session.targets())
    if not targets.empty:
        protocol = (
            targets.groupby(["target_valid", "gt_label_valid", "gt_match_status"], dropna=False)
            .size()
            .reset_index(name="count")
        )
        fig = px.bar(
            protocol,
            x="gt_match_status",
            y="count",
            color="target_valid",
            pattern_shape="gt_label_valid",
            title="Target protocol: actor validity × GT-label validity",
        )
        _render_plot(
            fig,
            ScientificExplanation(
                question="Are actor target choices and privileged GT evaluation labels being kept distinct?",
                population="One persisted target row grouped by actor task validity, GT-label validity, and match status.",
                metric="Target count; no scientific effect units.",
                denominator_masks="All target rows; neither invalid population is silently removed.",
                comparability="Compare target protocols only when target selection and GT matching configuration agree.",
                expected_pattern="Actor-valid targets may lack GT labels, but such rows remain masked from oracle-label training.",
                failure_interpretation="Actor-valid/GT-invalid concentration signals evaluation coverage gaps, not low RRI.",
                evidence_role="oracle/evaluation",
                source_fields=(
                    "targets/target_valid_mask",
                    "targets/gt_label_valid_mask",
                    "targets/gt_match_status_id",
                ),
            ),
        )
        _download_frame("Download target protocol CSV", "target-protocol.csv", targets)
        _render_target_score_diagnostics(targets)

    _render_candidate_provenance_flow(stored_session)

    masks = pd.DataFrame(stored_session.masks())
    if not masks.empty:
        label_cols = [c for c in ("actor_action", "oracle_label", "q_train", "selected") if c in masks]
        masks["combination"] = masks[label_cols].astype(str).agg(" · ".join, axis=1)
        fig = px.bar(masks, x="combination", y="count", title="Observed candidate-mask combinations")
        _render_plot(
            fig,
            ScientificExplanation(
                question="Which actor, oracle, training, and selection mask combinations actually occur?",
                population="One candidate row summarized by its exact four-mask bit pattern.",
                metric="Candidate count and fraction of the full sampled shell.",
                denominator_masks="All persisted candidate rows; selected must imply actor_action, while q_train is not a selection stage.",
                comparability="Compare stores only under the same candidate-shell generation and label-availability protocol.",
                expected_pattern="No selected/actor_action violation; selected-but-not-q_train may legitimately occur.",
                failure_interpretation="A selected actor-invalid row is a hard contract failure; missing q_train is a label/cache issue, not invalid action support.",
                evidence_role="derived training data",
                source_fields=("candidates/actor_action_mask", "oracle_label_mask", "q_train_mask", "selected_mask"),
            ),
        )
        st.dataframe(masks.drop(columns="combination"), hide_index=True, width="stretch")
        _download_frame(
            "Download mask combinations CSV", "candidate-mask-combinations.csv", masks.drop(columns="combination")
        )

    if st.toggle(
        "Load complete candidate aggregate breakdowns",
        value=False,
        help="Builds the heavyweight candidate audit used by the restored family, mask-population, and invalid-reason tables.",
    ):
        _render_candidate_aggregate_breakdowns(stored_session)

    if st.toggle(
        "Load cohort composition, proposal calibration, and collision support",
        value=False,
        help="Materializes the complete candidate audit only after this explicit request and reuses its cached rows.",
    ):
        _render_candidate_population_evidence(stored_session)

    if st.toggle(
        "Load bounded candidate geometry and reward plots",
        value=False,
        help="Builds interactive candidate-level traces up to the row limit above; aggregate plots remain complete-store.",
    ):
        _render_raw_candidate_metrics(
            bounded_candidates,
            total_candidates=int(reader.array("candidates/candidate_row_id").size),
        )


def _render_candidate_population_evidence(stored_session: session.StoredRolloutSession) -> None:
    """Render complete candidate aggregates and a deterministic display-only sample."""

    group_by = st.selectbox("Candidate evidence grouping", options=list(CANDIDATE_GROUP_FIELDS))
    population = stored_session.candidate_population()
    _render_complete_candidate_support(population)
    composition = pd.DataFrame(population["composition"][group_by])
    calibration = pd.DataFrame(population["calibration"][group_by])
    sample = population["sample"]

    if not composition.empty:
        _render_plot(
            _candidate_group_bar(composition, group_by, "Candidate mask support by generation cohort"),
            _candidate_population_explanation(
                "How much actor-valid and selected support does each candidate family provide?",
                "Candidate rows grouped by exact persisted generation cohort and grouping key.",
                "Counts and descriptive within-cohort fractions; rates are dimensionless.",
                "Only finite, validated audit rows contribute; cohorts are never pooled.",
                "A healthy family remains available without monopolizing selected support.",
                "Zero availability or selected-without-actor-valid support points to a generator or mask defect.",
                "candidate audit masks and generation cohort",
                "actor-visible",
                theory_kind="validity",
            ),
        )
        with st.expander("Candidate composition rows and CSV"):
            st.dataframe(composition, hide_index=True, width="stretch")
            _download_frame("Download candidate composition CSV", "candidate-composition.csv", composition)

    if not calibration.empty:
        _render_plot(
            _candidate_group_bar(calibration, group_by, "Proposal frequency and selection enrichment"),
            _candidate_population_explanation(
                "Are proposals selected because they are useful, rather than merely frequent?",
                "Candidate proposals grouped by exact generation cohort and persisted family key.",
                "Empirical frequency, proposal mass, and selection enrichment are descriptive ratios.",
                "Each ratio retains its own persisted denominator; unavailable values remain missing.",
                "Useful families retain availability and non-degenerate selection.",
                "High frequency with low selection suggests proposal surplus; high enrichment with tiny support is unstable.",
                "candidate proposal counts, mixture mass, and selected mask",
                "actor-visible",
                theory_kind="validity",
            ),
        )
        with st.expander("Proposal calibration rows and CSV"):
            st.dataframe(calibration, hide_index=True, width="stretch")
            _download_frame("Download proposal calibration CSV", "candidate-proposal-calibration.csv", calibration)

    sample_rows = pd.DataFrame(sample.get("rows", []))
    if not sample_rows.empty:
        with st.expander("Deterministic raw candidate sample and CSV"):
            st.caption(
                f"Showing {int(sample.get('display_count', 0)):,} of {int(sample.get('population_count', 0)):,} rows. "
                "This bounded, order-invariant sample is display-only; aggregates above use the complete population."
            )
            st.dataframe(sample_rows, hide_index=True, width="stretch")
            _download_frame("Download deterministic candidate sample CSV", "candidate-sample.csv", sample_rows)


def _candidate_population_explanation(
    question: str,
    population: str,
    metric: str,
    denominator_masks: str,
    expected_pattern: str,
    failure_interpretation: str,
    source: str,
    role: Literal["actor-visible", "oracle/evaluation", "derived training data", "provenance"],
    *,
    intuition: str | None = None,
    visual_encoding: str | None = None,
    uncertainty: str | None = None,
    theory_kind: TheoryKind | None = None,
) -> ScientificExplanation:
    return ScientificExplanation(
        question=question,
        population=population,
        metric=metric,
        denominator_masks=denominator_masks,
        comparability="Compare only matching persisted candidate contracts and exact generation cohorts.",
        expected_pattern=expected_pattern,
        failure_interpretation=failure_interpretation,
        evidence_role=role,
        source_fields=(source,),
        intuition=intuition or "Read this as a diagnostic of persisted support, not as a causal policy comparison.",
        visual_encoding=visual_encoding or "Colours identify populations; facets identify compatible cohorts.",
        uncertainty=uncertainty
        or "Missing values remain unavailable; descriptive summaries do not imply inferential uncertainty.",
        theory_references=() if theory_kind is None else _THEORY[theory_kind],
    )


def _candidate_group_bar(frame: pd.DataFrame, group_by: str, title: str) -> go.Figure:
    """Build a compact cohort-aware bar plot from one typed summary frame."""

    value_columns = [
        column
        for column in ("actor_valid", "q_train", "selected", "empirical_frequency", "selection_enrichment")
        if column in frame.columns
    ]
    if not value_columns:
        value_columns = [column for column in frame.columns if column not in {group_by, "generation_cohort_id"}]
    id_vars = [column for column in (group_by, "generation_cohort_id") if column in frame.columns]
    long = frame.melt(id_vars=id_vars, value_vars=value_columns, var_name="measure", value_name="value")
    return px.bar(
        long,
        x=group_by if group_by in long else "measure",
        y="value",
        color="measure",
        facet_col="generation_cohort_id" if "generation_cohort_id" in long else None,
        title=title,
        barmode="group",
    )


def _direction_count_context(frame: pd.DataFrame) -> dict[str, str]:
    """Read one repeated typed direction facet without counting bins as rows."""

    fields = {
        "states": "state_count",
        "candidate directions": "candidate_direction_count",
        "finite directions": "finite_count",
        "missing/unavailable": "missing_count",
    }
    context: dict[str, str] = {}
    for label, column in fields.items():
        if column not in frame:
            context[label] = "unavailable"
            continue
        values = pd.to_numeric(frame[column], errors="coerce").dropna().astype(int).unique()
        if len(values) != 1 or values[0] < 0:
            context[label] = "unavailable"
        else:
            context[label] = f"{int(values[0]):,}"
    return context


def _select_evidence_grain(frame: pd.DataFrame, *, level: str, key: str) -> pd.DataFrame:
    """Apply an exact scene/state selector before plotting a finer grain.

    ``cohort_macro`` is already a single compatible population.  A scene or
    state macro is not: selecting it without its identity would silently
    combine rows from multiple scenes or factual states.
    """

    if level == "cohort_macro" or frame.empty:
        return frame
    if "scene" not in frame:
        st.warning(f"{level} evidence is unavailable because no scene identity was persisted.")
        return frame.iloc[0:0]
    if level == "scene_macro":
        scenes = sorted(str(value) for value in frame["scene"].dropna().unique())
        if not scenes:
            return frame.iloc[0:0]
        scene = st.selectbox("Exact scene", options=scenes, key=f"{key}_scene")
        return frame[frame["scene"].astype(str).eq(str(scene))]
    if level == "state":
        required = {"rollout_row_id", "step_row_id"}
        if not required <= set(frame.columns):
            st.warning("State evidence is unavailable because the factual state identity is incomplete.")
            return frame.iloc[0:0]
        state_rows = (
            frame[["scene", "rollout_row_id", "step_row_id"]]
            .drop_duplicates()
            .sort_values(["scene", "rollout_row_id", "step_row_id"], kind="stable")
        )
        state_options = [
            f"scene={row.scene} · rollout={row.rollout_row_id} · step={row.step_row_id}"
            for row in state_rows.itertuples(index=False)
        ]
        if not state_options:
            return frame.iloc[0:0]
        selected = st.selectbox("Exact factual state", options=state_options, key=f"{key}_state")
        selected_row = state_rows.iloc[state_options.index(selected)]
        return frame[
            frame["scene"].astype(str).eq(str(selected_row.scene))
            & frame["rollout_row_id"].astype(str).eq(str(selected_row.rollout_row_id))
            & frame["step_row_id"].astype(str).eq(str(selected_row.step_row_id))
        ]
    raise ValueError(f"Unsupported evidence aggregation level: {level}")


def _render_complete_candidate_support(population: dict[str, object]) -> None:
    """Render complete-population support plots before their collapsed rows."""

    geometry = pd.DataFrame(population.get("geometry", []))
    required_geometry = {"target_normalized_forward", "target_normalized_lateral"}
    points = (
        geometry.dropna(subset=sorted(required_geometry)) if required_geometry <= set(geometry.columns) else geometry
    )
    if not points.empty:
        if "generation_cohort_id" not in points:
            points = points.assign(generation_cohort_id="unknown")
        st.caption(
            f"Showing {len(points):,} finite normalized rows from the deterministic display sample "
            f"({int(population.get('population_count', len(geometry))):,} total candidate rows)."
        )
        fig = go.Figure()
        for label, x, y in (("root", 0.0, 0.0), ("target", 1.0, 0.0)):
            fig.add_trace(go.Scatter(x=[x], y=[y], mode="markers", name=label))
        context_columns = [column for column in ("position", "policy", "selected") if column in points]
        group_columns = ["generation_cohort_id", *context_columns]
        for context, cohort_rows in points.groupby(group_columns, sort=True, dropna=False):
            context = context if isinstance(context, tuple) else (context,)
            cohort = str(context[0])
            label = " · ".join(f"{column}={value}" for column, value in zip(group_columns, context, strict=True))
            x_values: list[float | None] = []
            y_values: list[float | None] = []
            for row in cohort_rows.itertuples(index=False):
                x_values.extend([0.0, float(row.target_normalized_forward), None])
                y_values.extend([0.0, float(row.target_normalized_lateral), None])
            fig.add_trace(go.Scatter(x=x_values, y=y_values, mode="lines", name=f"rays · {label}"))
            fig.add_trace(
                go.Scatter(
                    x=cohort_rows["target_normalized_forward"],
                    y=cohort_rows["target_normalized_lateral"],
                    mode="markers",
                    name=f"candidate · {label}",
                    customdata=cohort_rows[context_columns].to_numpy() if context_columns else None,
                    hovertemplate=(
                        "forward=%{x:.3f}<br>lateral=%{y:.3f}<br>"
                        + "<br>".join(
                            f"{column}=%{{customdata[{index}]}}" for index, column in enumerate(context_columns)
                        )
                        + "<extra></extra>"
                    )
                    if context_columns
                    else None,
                )
            )
        fig.update_layout(
            title="Target-normalized candidate endpoints (display sample)", xaxis_title="forward", yaxis_title="lateral"
        )
        fig.update_xaxes(scaleanchor="y", scaleratio=1)
        fig.update_yaxes(scaleanchor="x", scaleratio=1)
        _render_plot(
            fig,
            ScientificExplanation(
                question="Where do the displayed candidate endpoints lie relative to root and target?",
                population="Deterministic bounded display sample; aggregate conclusions require the complete audit population.",
                metric="Dimensionless forward/lateral coordinates; root=(0,0), target=(1,0).",
                denominator_masks="Degenerate target baselines are unavailable, never zero-filled.",
                comparability="Use the same target protocol and generation contract.",
                expected_pattern="Support covers the intended local shell without frame mirroring or collapse.",
                failure_interpretation="Offsets and asymmetry indicate frame or generator defects.",
                evidence_role="actor-visible",
                source_fields=("candidate audit", "target center"),
                intuition="Each ray starts at the root and ends at the candidate in a target-aligned frame.",
                visual_encoding="The fixed root and target anchors establish the frame; each candidate has its own line segment.",
                uncertainty="Only the bounded deterministic sample is shown; it is not a complete-store estimate.",
                theory_references=_THEORY["geometry"],
            ),
        )
        with st.expander("Target-normalized endpoint rows and CSV"):
            st.dataframe(points, hide_index=True, width="stretch")
            _download_frame("Download normalized candidate positions CSV", "candidate-normalized-positions.csv", points)
    direction = population.get("direction", {})
    density = pd.DataFrame(direction.get("density_rows", []) if isinstance(direction, dict) else [])
    if not density.empty:
        if "generation_cohort_id" not in density:
            density = density.assign(generation_cohort_id="unknown")
        if "population" not in density:
            density = density.assign(population="all")
        if "aggregation_level" not in density:
            density = density.assign(aggregation_level="state")
        cohorts = sorted(str(value) for value in density["generation_cohort_id"].dropna().unique())
        populations = sorted(str(value) for value in density["population"].dropna().unique())
        available_levels = {str(value) for value in density["aggregation_level"].dropna()}
        levels = [level for level in ("cohort_macro", "scene_macro", "state") if level in available_levels]
        cohort_col, population_col = st.columns(2)
        cohort = cohort_col.selectbox("Direction generation cohort", options=cohorts, key="candidate_direction_cohort")
        direction_population = population_col.selectbox(
            "Direction population", options=populations, key="candidate_direction_population"
        )
        aggregation = st.selectbox(
            "Direction aggregation", options=levels, index=0, key="candidate_direction_aggregation"
        )
        selected_density = density[
            (density["generation_cohort_id"].astype(str) == cohort)
            & (density["population"].astype(str) == direction_population)
            & (density["aggregation_level"].astype(str) == aggregation)
        ]
        selected_density = _select_evidence_grain(
            selected_density, level=aggregation, key="candidate_direction_density"
        )
        matrix = selected_density.pivot_table(
            index="sin_elevation_bin", columns="azimuth_bin", values="mean_state_fraction", aggfunc="mean"
        )
        count_context = _direction_count_context(selected_density)
        st.caption(
            f"Aggregation: {aggregation} · states={count_context['states']} · "
            f"candidate directions={count_context['candidate directions']} · "
            f"finite={count_context['finite directions']} · "
            f"missing/unavailable={count_context['missing/unavailable']} · "
            "protocol: azimuth × sin(elevation) equal-area bins."
        )
        fig = px.imshow(
            matrix,
            origin="lower",
            aspect="auto",
            labels={"x": "azimuth bin", "y": "sin(elevation) bin", "color": "fraction"},
            title=f"Candidate direction density (equal-area bins) · {cohort} · {aggregation}",
        )
        _render_plot(
            fig,
            ScientificExplanation(
                question="Does direction support cover solid angle without latitude bias?",
                population=f"Candidate rows at {aggregation} grain; cohort={cohort}, population={direction_population}.",
                metric="Fraction per azimuth × sin(elevation) bin.",
                denominator_masks="Zero-length vectors remain missing.",
                comparability="Match binning and candidate contract.",
                expected_pattern="No unexplained directional collapse.",
                failure_interpretation="Spikes expose orientation or generator support defects.",
                evidence_role="actor-visible",
                source_fields=("root-relative vectors",),
                intuition="Equal-area bins prevent latitude bands from being over-counted simply because of the coordinate system.",
                visual_encoding="Colour is the fraction of each factual state in an azimuth × sin(elevation) bin.",
                uncertainty="Missing or zero-length directions are excluded from the finite denominator, not treated as a direction.",
                theory_references=_THEORY["direction"],
            ),
        )
        with st.expander("Direction density rows and CSV"):
            st.dataframe(selected_density, hide_index=True, width="stretch")
            _download_frame("Download direction density CSV", "candidate-direction-density.csv", selected_density)
    for frame, value, title, key in (
        (
            pd.DataFrame(direction.get("cap_rows", []) if isinstance(direction, dict) else []),
            "discrepancy",
            "Spherical-cap directional discrepancy",
            "direction-cap",
        ),
        (
            pd.DataFrame(direction.get("angular_support_rows", []) if isinstance(direction, dict) else []),
            "nearest_neighbor_deg",
            "Angular nearest-neighbour and covering support",
            "direction-angular",
        ),
    ):
        if frame.empty:
            continue
        if "aggregation_level" in frame:
            levels = [
                level for level in ("cohort_macro", "scene_macro", "state") if level in set(frame["aggregation_level"])
            ]
            level = st.selectbox(f"{title} aggregation", options=levels, key=f"{key}_aggregation")
            frame = frame[frame["aggregation_level"].eq(level)]
            frame = _select_evidence_grain(frame, level=level, key=key)
        if frame.empty or value not in frame:
            continue
        if "generation_cohort_id" not in frame:
            frame = frame.assign(generation_cohort_id="unknown")
        if "population" not in frame:
            frame = frame.assign(population="all")
        if key == "direction-angular":
            measures = [measure for measure in ("nearest_neighbor_deg", "covering_radius_deg") if measure in frame]
            long = frame.melt(
                id_vars=[column for column in ("generation_cohort_id", "population") if column in frame],
                value_vars=measures,
                var_name="angular_measure",
                value_name="degrees",
            )
            fig = px.bar(
                long,
                x="angular_measure",
                y="degrees",
                color="population",
                facet_col="generation_cohort_id",
                barmode="group",
                title=title,
            )
        elif "radius_deg" in frame:
            fig = px.line(
                frame,
                x="radius_deg",
                y=value,
                color="population",
                facet_col="generation_cohort_id",
                markers=True,
                title=title,
            )
        else:
            fig = px.bar(
                frame,
                x="generation_cohort_id",
                y=value,
                color="population",
                barmode="group",
                title=title,
            )
        _render_plot(
            fig,
            _candidate_population_explanation(
                "Does candidate direction support cover solid angle without collapse?",
                "Stored candidate direction rows at the factual-state grain.",
                "Angular discrepancy or separation in degrees/fraction as labelled.",
                "Finite normalized vectors only; missing vectors remain unavailable.",
                "Low cap discrepancy and small covering gaps indicate broad directional support.",
                "Large discrepancy or angular gaps indicate directional collapse or missing generator families.",
                "candidate direction evidence",
                "actor-visible",
                theory_kind="direction",
            ),
        )
        with st.expander(f"{title} rows and CSV"):
            st.dataframe(frame, hide_index=True, width="stretch")
            _download_frame(f"Download {title} CSV", f"candidate-{key}.csv", frame)

    for key, title in (
        ("spatial", "Spatial support by shell"),
        ("target_view", "Target-view distance support"),
        ("motion", "Motion support"),
    ):
        frame = pd.DataFrame(population.get(key, []))
        if frame.empty:
            continue
        if "aggregation_level" in frame:
            levels = [
                level for level in ("cohort_macro", "scene_macro", "state") if level in set(frame["aggregation_level"])
            ]
            level = st.selectbox(f"{title} aggregation", options=levels, key=f"{key}_aggregation")
            frame = frame[frame["aggregation_level"].eq(level)]
            frame = _select_evidence_grain(frame, level=level, key=key)
        if "generation_cohort_id" not in frame:
            frame = frame.assign(generation_cohort_id="unknown")
        if "population" not in frame:
            frame = frame.assign(population="all")
        if "state_count" in frame:
            state_values = pd.to_numeric(frame["state_count"], errors="coerce").dropna().astype(int).unique()
            defined_values = (
                pd.to_numeric(frame["defined_state_count"], errors="coerce").dropna().astype(int).unique()
                if "defined_state_count" in frame
                else []
            )
            scene_values = (
                pd.to_numeric(frame["scene_count"], errors="coerce").dropna().astype(int).unique()
                if "scene_count" in frame
                else []
            )
            candidate_values = (
                pd.to_numeric(frame["candidate_total_count"], errors="coerce").dropna().astype(int).unique()
                if "candidate_total_count" in frame
                else []
            )
            if len(state_values) == len(defined_values) == len(scene_values) == len(candidate_values) == 1:
                st.caption(
                    f"{level}: {candidate_values[0]:,} candidate rows across {state_values[0]:,} factual states "
                    f"({defined_values[0]:,} with finite support) and {scene_values[0]:,} scene(s)."
                )
        y = "mean" if "mean" in frame else "count"
        x = "metric" if "metric" in frame else "evidence"
        unit_frames = [(None, frame)]
        if key == "motion" and "units" in frame:
            unit_frames = list(frame.groupby("units", sort=True, dropna=False))
        for units, unit_frame in unit_frames:
            # Metres, degrees, fractions, and counts are separate visual
            # scales.  Shell identity remains visible rather than being
            # collapsed into a human-readable family label.
            if key == "motion" and units == "fraction":
                unit_title = "Motion collision fraction"
            elif key == "motion" and units:
                unit_title = f"Motion support ({units})"
            else:
                unit_title = title
            fig_kwargs: dict[str, object] = {
                "x": x,
                "y": y,
                "color": "population",
                "facet_col": "generation_cohort_id",
                "title": unit_title,
                "barmode": "group",
            }
            if key == "spatial" and "declared_shell" in unit_frame:
                fig_kwargs["facet_row"] = "declared_shell"
            fig = px.bar(unit_frame, **fig_kwargs)
            _render_plot(
                fig,
                _candidate_population_explanation(
                    f"What physical support is present in {unit_title.lower()}?",
                    "Complete candidate audit support summaries at factual-state grain.",
                    f"Metric units are {units or 'as labelled by each persisted evidence row'}.",
                    "Finite support is plotted; unavailable optical and numeric values remain missing.",
                    "Support spans configured shell, target-view, and motion bounds.",
                    "Concentration, clipping, or missingness points to an invalid component or evaluator coverage issue.",
                    f"candidate {key} evidence",
                    "actor-visible",
                    theory_kind=(
                        "geometry"
                        if key == "spatial"
                        else "action"
                        if key == "motion"
                        else "target"
                        if key == "target_view"
                        else None
                    ),
                    uncertainty="Macro rows are descriptive summaries; they are not confidence intervals.",
                ),
            )
        with st.expander(f"{title} rows and CSV"):
            st.dataframe(frame, hide_index=True, width="stretch")
            _download_frame(f"Download {key} support CSV", f"candidate-{key}.csv", frame)
        if key == "target_view" and "missing_count" in frame:
            missing = frame[["evidence", "missing_count", "generation_cohort_id", "population"]].copy()
            missing = missing.rename(columns={"missing_count": "unavailable_count"})
            missing_fig = px.bar(
                missing,
                x="evidence",
                y="unavailable_count",
                color="population",
                facet_col="generation_cohort_id",
                barmode="group",
                title="Target-view unavailable evidence counts",
            )
            _render_plot(
                missing_fig,
                _candidate_population_explanation(
                    "Where is target-view evidence unavailable?",
                    "The same factual-state target-view rows as the distance plot.",
                    "Unavailable row count for FOV, pixel, line-of-sight, and distance evidence.",
                    "Missing counts are explicit; unavailable values are not treated as zero-valued quality.",
                    "Optical and line-of-sight evidence is available for the intended target-view protocol.",
                    "Large missing counts identify evaluator coverage gaps and must not be read as poor visibility.",
                    "candidate target-view evidence",
                    "actor-visible",
                    theory_kind="target",
                ),
            )
            with st.expander("Target-view availability rows and CSV"):
                st.dataframe(missing, hide_index=True, width="stretch")
                _download_frame(
                    "Download target-view availability CSV", "candidate-target-view-availability.csv", missing
                )

    collision = pd.DataFrame(population.get("collision", []))
    if not collision.empty:
        if "generation_cohort_id" not in collision:
            collision = collision.assign(generation_cohort_id="unknown")
        rate_columns = [
            column
            for column in (
                "population_collision_rate",
                "collision_rate",
                "population_clearance_mean_m",
                "clearance_mean_m",
            )
            if column in collision
        ]
        if rate_columns:
            fraction_columns = [column for column in rate_columns if "collision_rate" in column]
            clearance_columns = [column for column in rate_columns if "clearance" in column]
            if fraction_columns:
                rates = collision.melt(
                    id_vars=["generation_cohort_id"],
                    value_vars=fraction_columns,
                    var_name="measure",
                    value_name="value",
                )
                rate_fig = px.bar(
                    rates,
                    x="measure",
                    y="value",
                    color="generation_cohort_id",
                    barmode="group",
                    title="Collision rate (fraction)",
                )
                _render_plot(
                    rate_fig,
                    _candidate_population_explanation(
                        "How often do evaluated candidate paths collide?",
                        "Validated collision rows, separated by generation cohort.",
                        "Collision fraction over the applicable evaluated denominator.",
                        "Only evaluated applicable paths enter the fraction; unavailable and not-applicable rows stay separate.",
                        "Collision fractions remain low under the configured path contract.",
                        "A high fraction can indicate invalid geometry or evaluator coverage problems.",
                        "candidate diagnostics/path collision",
                        "actor-visible",
                        theory_kind="code",
                    ),
                )
            if clearance_columns:
                clearance = collision.melt(
                    id_vars=["generation_cohort_id"],
                    value_vars=clearance_columns,
                    var_name="measure",
                    value_name="value",
                )
                clearance_fig = px.bar(
                    clearance,
                    x="measure",
                    y="value",
                    color="generation_cohort_id",
                    barmode="group",
                    title="Mean path clearance (m)",
                )
                _render_plot(
                    clearance_fig,
                    _candidate_population_explanation(
                        "How much free-space clearance do evaluated paths retain?",
                        "Validated finite-clearance rows, separated by generation cohort.",
                        "Mean minimum path clearance in metres; this is not a collision fraction.",
                        "Only finite clearance values contribute to the clearance denominator.",
                        "Positive clearance with low spread indicates feasible paths.",
                        "Low or missing clearance requires checking path applicability and evaluator coverage.",
                        "candidate diagnostics/path clearance",
                        "actor-visible",
                        theory_kind="code",
                    ),
                )
        count_columns = [
            column
            for column in (
                "collision_available_count",
                "collision_evaluated_count",
                "collision_not_applicable_count",
                "collision_unavailable_count",
                "collision_count",
                "clearance_finite_count",
                "collision_denominator",
                "clearance_denominator",
            )
            if column in collision
        ]
        if count_columns:
            counts = collision.melt(
                id_vars=["generation_cohort_id"],
                value_vars=count_columns,
                var_name="denominator_state",
                value_name="count",
            )
            count_fig = px.bar(
                counts,
                x="denominator_state",
                y="count",
                color="generation_cohort_id",
                barmode="group",
                title="Collision applicability, evaluation, and denominators",
            )
            _render_plot(
                count_fig,
                _candidate_population_explanation(
                    "Which candidate rows are applicable, evaluated, unevaluated, or not applicable?",
                    "Validated collision and clearance rows by generation cohort.",
                    "Counts; denominator columns are shown explicitly alongside applicable/evaluated states.",
                    "Applicable evaluated, applicable unevaluated, not-applicable, collision, and finite-clearance counts are not interchangeable.",
                    "Evaluated counts account for most applicable rows and denominators are reproducible.",
                    "Unevaluated or missing-denominator rows indicate evaluator coverage gaps, not safe free space.",
                    "candidate diagnostics/path collision and clearance",
                    "actor-visible",
                    theory_kind="validity",
                ),
            )
        with st.expander("Collision and clearance rows and CSV"):
            st.dataframe(collision, hide_index=True, width="stretch")
            _download_frame("Download collision support CSV", "candidate-collision-support.csv", collision)


def _render_candidate_provenance_flow(stored_session: session.StoredRolloutSession) -> None:
    """Render the lightweight complete-population candidate provenance flow."""

    validation = stored_session.validation
    store_candidate_count = int(validation.num_candidates)
    steps = pd.DataFrame(stored_session.steps())
    policy_options = sorted(str(value) for value in steps.get("policy", pd.Series(dtype=str)).dropna().unique())
    depth_options = sorted(int(value) for value in steps.get("step_index", pd.Series(dtype=int)).dropna().unique())
    col_policy, col_depth = st.columns(2)
    selected_policies = col_policy.multiselect("Flow policies", options=policy_options, default=policy_options)
    selected_depths = col_depth.multiselect("Flow rollout depths", options=depth_options, default=depth_options)
    flow = pd.DataFrame(
        stored_session.candidate_flow(
            policies=tuple(selected_policies),
            step_indices=tuple(selected_depths),
        )
    )
    if flow.empty:
        st.info(
            "No candidate rows match the active policy and rollout-depth filters. "
            f"The unfiltered store contains {store_candidate_count:,} candidate rows."
        )
        return
    denominator = int(flow["root_denominator"].iloc[0])
    projected_store_count = int(flow["store_candidate_count"].iloc[0])
    if projected_store_count != store_candidate_count:
        raise ValueError("Candidate-flow projection disagrees with validated store candidate count.")
    st.caption(
        f"Active-scope root: {denominator:,} of {store_candidate_count:,} persisted candidate rows, including both "
        "actor-valid and actor-invalid candidates. Policy/depth filters define the scope; validity never filters the root."
    )
    _render_plot(
        _candidate_flow_figure(flow),
        ScientificExplanation(
            question="How does persisted candidate-generation provenance flow into actor-valid support and terminal outcomes?",
            population="Every candidate row matching the visible policy/depth filters, including actor-valid and actor-invalid rows, aggregated through proposal signature, actor validity, and outcome.",
            metric="Candidate count and fraction of the filtered root population; no reward or geometric units.",
            denominator_masks="The filtered complete candidate population is the root denominator. Actor validity is a hard action constraint; selected actor-invalid rows remain explicit selection_contract_violation evidence.",
            comparability="Candidate proposal signatures, budgets, and active policy/depth filters must match.",
            expected_pattern="Intended center/view proposal signatures retain actor-valid support, while invalid rows terminate at explicit reasons and selected rows remain actor-valid.",
            failure_interpretation="Unknown provenance indicates missing persisted labels; concentrated invalid reasons indicate support loss; selection_contract_violation is a hard invariant failure.",
            evidence_role="provenance",
            source_fields=(
                "inspection.candidate_flow_rows",
                "candidates/mixture_id",
                "candidates/position_id",
                "candidates/strategy_id",
                "candidates/actor_action_mask",
                "candidates/selected_mask",
                "candidates/primary_invalid_reason",
            ),
        ),
    )
    st.dataframe(flow, hide_index=True, width="stretch")
    _download_frame("Download candidate provenance flow CSV", "candidate-provenance-flow.csv", flow)

    ranks = pd.DataFrame(
        stored_session.ranks(
            policies=tuple(selected_policies),
            step_indices=tuple(selected_depths),
        )
    )
    _render_selected_action_policy_flow(ranks)


def _candidate_flow_figure(flow: pd.DataFrame) -> go.Figure:
    """Build one stage-stable Sankey from normalized candidate-flow links."""

    return _sankey_figure(
        flow,
        stage_order=("root", "proposal", "actor_validity", "candidate_outcome"),
        title="Candidate provenance and support flow",
    )


def _render_selected_action_policy_flow(ranks: pd.DataFrame) -> None:
    """Render policy mechanics and target-RRI rank for selected rollout steps."""

    st.markdown("#### Selected-action policy and rank")
    if ranks.empty or "selected_candidate_row_id" not in ranks:
        st.info("No selected rollout steps match the active policy and rollout-depth filters.")
        return
    selected_ranks = ranks[pd.to_numeric(ranks["selected_candidate_row_id"], errors="coerce").fillna(-1) >= 0].copy()
    if selected_ranks.empty:
        st.info("No selected rollout steps match the active policy and rollout-depth filters.")
        return
    st.caption(
        "Temperature-softmax is the primary behavior-policy view for training-data diversity; random-valid and "
        "oracle policies remain baseline and upper-bound evidence. Target-RRI rank is an oracle diagnostic and is "
        "kept distinct from the persisted selection-score rank."
    )
    selection_flow = pd.DataFrame(_selected_action_flow_rows(selected_ranks))
    if not selection_flow.empty:
        _render_plot(
            _selected_action_flow_figure(selection_flow),
            ScientificExplanation(
                question="Which candidate/action policy selected each persisted action, and where did that action rank by target RRI?",
                population="One persisted selected rollout step matching the active policy/depth filters.",
                metric="Selected-step count and target-RRI competition rank among finite actor-valid candidates.",
                denominator_masks="The root denominator is selected rollout steps. Target-RRI rank excludes actor-invalid and non-finite alternatives; unavailable ranks remain explicit.",
                comparability="Compare policies only under matched roots, targets, candidate proposals, acquisition budgets, and score semantics.",
                expected_pattern="Temperature-softmax covers more than rank one without collapsing to uniformly poor target-RRI ranks; greedy policies concentrate near the top.",
                failure_interpretation="Unavailable ranks indicate missing oracle diagnostics; high-rank concentration can indicate excessive temperature or score/RRI mismatch.",
                evidence_role="oracle/evaluation",
                source_fields=(
                    "inspection.selected_candidate_rank_rows",
                    "rollouts/policy_id",
                    "rollouts/temperature",
                    "candidates/selection_probabilities",
                    "candidates/selection_logits",
                    "candidates/target_rri",
                ),
            ),
        )
        st.dataframe(selection_flow, hide_index=True, width="stretch")
        _download_frame(
            "Download selected-action policy/rank flow CSV",
            "selected-action-policy-rank-flow.csv",
            selection_flow,
        )

    exact_columns = [
        column
        for column in (
            "rollout_row_id",
            "step_row_id",
            "step_index",
            "selected_candidate_row_id",
            "policy",
            "temperature",
            "score_source",
            "selected_probability",
            "selection_entropy",
            "selection_score_rank",
            "selection_score_rank_denominator",
            "target_rri_rank",
            "rank_denominator",
            "target_rri_rank_label",
            "selected_target_rri",
            "selected_target_root_gain",
        )
        if column in selected_ranks
    ]
    exact_table = selected_ranks[exact_columns].rename(
        columns={"target_rri_rank_label": "target-RRI rank / finite actor-valid candidates"}
    )
    st.dataframe(exact_table, hide_index=True, width="stretch")
    _download_frame(
        "Download exact selected-step evidence CSV",
        "selected-step-selection-evidence.csv",
        selected_ranks,
    )


def _selected_action_flow_rows(ranks: pd.DataFrame) -> list[dict[str, object]]:
    """Aggregate selected-step policy and target-RRI ranks for a Sankey."""

    if ranks.empty or "selected_candidate_row_id" not in ranks:
        return []
    selected = ranks[pd.to_numeric(ranks["selected_candidate_row_id"], errors="coerce").fillna(-1) >= 0]
    denominator = len(selected)
    if denominator <= 0:
        return []
    counts: Counter[tuple[str, str, str, str, str, str]] = Counter()
    root = ("selected_root:steps", f"Selected rollout steps ({denominator:,})", "selected_root")
    for _, row in selected.iterrows():
        policy = str(row.get("policy") or "unknown")
        temperature = pd.to_numeric(pd.Series([row.get("temperature")]), errors="coerce").iloc[0]
        policy_label = policy
        if policy == "temperature_softmax" and pd.notna(temperature):
            policy_label = f"{policy} (τ={float(temperature):g})"
        actor_valid = bool(row.get("selected_actor_valid", True))
        rank_label = (
            "selection_contract_violation" if not actor_valid else _target_rri_rank_bucket(row.get("target_rri_rank"))
        )
        nodes = (
            root,
            (f"candidate_action_policy:{policy_label}", policy_label, "candidate_action_policy"),
            (f"target_rri_rank:{rank_label}", rank_label, "target_rri_rank"),
        )
        for source_node, target_node in pairwise(nodes):
            counts[(*source_node, *target_node)] += 1

    stage_order = {stage: index for index, stage in enumerate(("selected_root", "candidate_action_policy"))}
    output: list[dict[str, object]] = []
    for transition, count in sorted(
        counts.items(),
        key=lambda item: (stage_order[item[0][2]], item[0][0], item[0][3]),
    ):
        source_id, source_label, source_stage, target_id, target_label, target_stage = transition
        output.append(
            {
                "source_id": source_id,
                "source_label": source_label,
                "source_stage": source_stage,
                "target_id": target_id,
                "target_label": target_label,
                "target_stage": target_stage,
                "transition": f"{source_stage} -> {target_stage}",
                "count": int(count),
                "root_denominator": denominator,
                "fraction_of_root": float(count) / float(denominator),
            }
        )
    return output


def _target_rri_rank_bucket(value: object) -> str:
    """Return the compact displayed bucket for one exact target-RRI rank."""

    try:
        rank = int(value)
    except (TypeError, ValueError):
        return "unavailable"
    if rank <= 0:
        return "unavailable"
    return str(rank) if rank <= 10 else ">10"


def _selected_action_flow_figure(flow: pd.DataFrame | list[dict[str, object]]) -> go.Figure:
    """Build the selected-step policy-to-target-RRI-rank Sankey."""

    return _sankey_figure(
        pd.DataFrame(flow),
        stage_order=("selected_root", "candidate_action_policy", "target_rri_rank"),
        title="Selected-action policy and target-RRI rank flow",
    )


def _sankey_figure(flow: pd.DataFrame, *, stage_order: tuple[str, ...], title: str) -> go.Figure:
    """Build one stage-stable Sankey from normalized count-conserving links."""

    nodes: list[tuple[str, str, str]] = []
    seen: set[str] = set()
    for stage in stage_order:
        candidates = [
            (str(row[f"{side}_id"]), str(row[f"{side}_label"]), stage)
            for _, row in flow.iterrows()
            for side in ("source", "target")
            if str(row[f"{side}_stage"]) == stage
        ]
        for node in sorted(candidates, key=lambda value: (value[1], value[0])):
            if node[0] not in seen:
                seen.add(node[0])
                nodes.append(node)
    node_index = {node_id: index for index, (node_id, _label, _stage) in enumerate(nodes)}
    custom = np.column_stack((flow["root_denominator"], flow["fraction_of_root"]))
    figure = go.Figure(
        go.Sankey(
            arrangement="snap",
            node={
                "label": [label for _node_id, label, _stage in nodes],
                "customdata": [stage for _node_id, _label, stage in nodes],
                "hovertemplate": "%{label}<br>stage=%{customdata}<extra></extra>",
            },
            link={
                "source": [node_index[str(value)] for value in flow["source_id"]],
                "target": [node_index[str(value)] for value in flow["target_id"]],
                "value": flow["count"].astype(int).tolist(),
                "customdata": custom,
                "hovertemplate": (
                    "%{source.label} → %{target.label}<br>count=%{value:,}"
                    "<br>root denominator=%{customdata[0]:,.0f}<br>fraction of root=%{customdata[1]:.2%}<extra></extra>"
                ),
            },
        )
    )
    figure.update_layout(title=title)
    return figure


def _render_candidate_aggregate_breakdowns(stored_session: session.StoredRolloutSession) -> None:
    """Render restored complete-store candidate audit plots on demand."""

    population = stored_session.candidate_population()
    composition = population["composition"]
    families = pd.DataFrame(composition["position"])
    if not families.empty:
        families["actor_valid"] = families["actor_valid_count"]
        families["selected"] = families["selected_count"]
        families["actor_valid_fraction"] = families["macro_actor_valid_rate"]
        families["selection_rate_given_available"] = np.where(
            families["actor_valid_count"] > 0,
            families["selected_count"] / families["actor_valid_count"],
            np.nan,
        )
        long = families.melt(
            id_vars=["family", "generation_cohort_id"],
            value_vars=["actor_valid_fraction", "selection_rate_given_available"],
            var_name="metric",
            value_name="fraction",
        )
        fig = px.bar(
            long,
            x="family",
            y="fraction",
            color="metric",
            barmode="group",
            facet_col="generation_cohort_id",
            title="Candidate-family availability and normalized selection",
        )
        _render_plot(
            fig,
            ScientificExplanation(
                question="Is a candidate family selected because it is useful, or merely because it is frequently available?",
                population="Candidate rows grouped by root-relative position family.",
                metric="Actor-valid fraction of sampled rows and selected/actor-valid rate; both dimensionless fractions.",
                denominator_masks="Availability uses the full family shell; selection rate uses actor-valid family rows only.",
                comparability="Family names, mixture weights, and branch budgets must match across stores.",
                expected_pattern="Useful families retain availability and non-degenerate normalized selection without monopolizing support.",
                failure_interpretation="High raw selection with tiny availability can be unstable; zero availability is a generator/mask clue.",
                evidence_role="actor-visible",
                source_fields=("candidate position_id", "actor_action_mask", "selected_mask"),
                theory_references=_THEORY["validity"],
            ),
        )
        _download_frame("Download family support CSV", "candidate-family-support.csv", families)

    breakdown_by = st.selectbox(
        "Candidate aggregate breakdown",
        options=list(CANDIDATE_GROUP_FIELDS),
        help="Switches one complete-store aggregate plot without rebuilding the candidate audit.",
    )
    breakdown = pd.DataFrame(composition[breakdown_by])
    count_field_map = {
        "actor_valid_count": "actor_valid",
        "trainable_count": "q_train",
        "selected_count": "selected",
    }
    count_fields = [name for name in count_field_map if name in breakdown]
    if not breakdown.empty and count_fields:
        breakdown = breakdown.rename(columns=count_field_map)
        long = breakdown.melt(
            id_vars=["family", "generation_cohort_id"],
            value_vars=[count_field_map[name] for name in count_fields],
            var_name="mask_population",
            value_name="count",
        )
        fig = px.bar(
            long,
            x="family",
            y="count",
            color="mask_population",
            barmode="group",
            facet_col="generation_cohort_id",
            title=f"Candidate support by {breakdown_by}",
        )
        _render_plot(
            fig,
            ScientificExplanation(
                question=f"How do actor-valid, trainable, and selected populations differ across {breakdown_by}?",
                population=f"Complete-store candidate rows grouped by persisted {breakdown_by} provenance.",
                metric="Candidate count in each explicitly named mask population.",
                denominator_masks="Actor-valid, q_train, and selected are overlapping sets, not sequential waterfall stages.",
                comparability="Candidate protocol, group vocabulary, and store schema must match.",
                expected_pattern="Trainable support is no larger than label availability permits, and selection stays within actor support.",
                failure_interpretation="Missing groups, selected-only spikes, or large actor/train gaps identify generator, mask, or label-cache issues.",
                evidence_role="derived training data",
                source_fields=(
                    "inspection.candidate_group_summary_rows",
                    f"candidate {breakdown_by}",
                    "candidate masks",
                ),
                theory_references=_THEORY["validity"],
            ),
        )

    with st.expander("Invalid reasons and valid fanout"):
        invalid = pd.DataFrame(composition["invalid_reason"])
        fanout = pd.DataFrame(stored_session.steps())
        if not invalid.empty:
            st.dataframe(invalid, hide_index=True, width="stretch")
        if not fanout.empty:
            st.dataframe(
                fanout[
                    [
                        c
                        for c in (
                            "rollout_row_id",
                            "step_row_id",
                            "step_index",
                            "num_candidates",
                            "num_valid_candidates",
                            "invalid_fraction",
                        )
                        if c in fanout
                    ]
                ],
                hide_index=True,
                width="stretch",
            )


def _render_target_score_diagnostics(targets: pd.DataFrame) -> None:
    """Restore interpretable target-selection plots and replace the scatter matrix."""

    with st.expander("Target selection score diagnostics", expanded=True):
        rank_rows = targets.dropna(subset=[name for name in ("selection_rank", "selection_score") if name in targets])
        if {"selection_rank", "selection_score"}.issubset(targets.columns) and not rank_rows.empty:
            fig = px.scatter(
                rank_rows,
                x="selection_rank",
                y="selection_score",
                color="gt_match_status" if "gt_match_status" in rank_rows else None,
                symbol="gt_label_valid" if "gt_label_valid" in rank_rows else None,
                hover_data=[
                    name
                    for name in ("target_row_id", "class", "source", "target_valid", "effective_support")
                    if name in rank_rows
                ],
                title="Target selection rank versus score",
            )
            _render_plot(
                fig,
                ScientificExplanation(
                    question="Does persisted target rank agree with the score used to prioritize targets?",
                    population="One target proposal with finite rank and selection score.",
                    metric="Selection rank is ordinal; selection score is a dimensionless configured composite.",
                    denominator_masks="All scored target proposals, including actor-invalid and GT-invalid rows.",
                    comparability="Target-selection weights, proposal source, and GT-matching protocol must match.",
                    expected_pattern="Higher-priority ranks follow higher scores while validity classes remain visibly distinct.",
                    failure_interpretation="Rank inversions, score ties, or high-scoring invalid targets indicate selection or matching problems.",
                    evidence_role="provenance",
                    source_fields=("targets/selection_rank", "targets/selection_score", "targets/gt_match_status_id"),
                ),
            )

        support_field = next(
            (
                name
                for name in ("effective_support", "projected_area_fraction", "visibility_score")
                if name in targets and targets[name].notna().any()
            ),
            None,
        )
        if support_field is not None and "selection_score" in targets:
            support_rows = targets.dropna(subset=[support_field, "selection_score"])
            if not support_rows.empty:
                fig = px.scatter(
                    support_rows,
                    x=support_field,
                    y="selection_score",
                    color="gt_match_status" if "gt_match_status" in support_rows else None,
                    symbol="target_valid" if "target_valid" in support_rows else None,
                    hover_data=[name for name in ("target_row_id", "class", "gt_label_valid") if name in support_rows],
                    title=f"Selection score versus {support_field}",
                )
                _render_plot(
                    fig,
                    ScientificExplanation(
                        question="How strongly does visible target support influence the persisted target score?",
                        population=f"One target proposal with finite selection score and {support_field}.",
                        metric=f"{support_field} and selection score are dimensionless configured diagnostics.",
                        denominator_masks="Scored target proposals; actor and GT validity remain explicit marks.",
                        comparability="Support computation, crop geometry, score weights, and target source must match.",
                        expected_pattern="Support contributes monotonically without becoming the only determinant of score.",
                        failure_interpretation="High scores at negligible support or validity-separated clusters can reveal weighting or GT-association issues.",
                        evidence_role="oracle/evaluation",
                        source_fields=(
                            f"targets/{support_field}",
                            "targets/selection_score",
                            "targets/gt_label_valid_mask",
                        ),
                    ),
                )

        component_cols = [
            name
            for name in (
                "selection_score",
                "visibility_score",
                "support_score",
                "deficit_score",
                "projected_area_fraction",
                "gt_match_iou",
            )
            if name in targets and targets[name].notna().any()
        ]
        if len(component_cols) >= 3:
            corr = targets[component_cols].apply(pd.to_numeric, errors="coerce").corr(min_periods=2)
            fig = go.Figure(
                go.Heatmap(
                    z=corr.to_numpy(),
                    x=corr.columns.tolist(),
                    y=corr.index.tolist(),
                    zmin=-1,
                    zmax=1,
                    colorscale="RdBu",
                    reversescale=True,
                    text=np.round(corr.to_numpy(), 2),
                    texttemplate="%{text}",
                )
            )
            fig.update_layout(title="Target score-component correlation", height=440)
            _render_plot(
                fig,
                ScientificExplanation(
                    question="Which target-score components are redundant, opposed, or unexpectedly disconnected?",
                    population="Pairwise-complete target proposals for each component pair.",
                    metric="Pearson correlation coefficient, dimensionless in [-1, 1].",
                    denominator_masks="Finite pairwise component values; pairwise denominators may differ.",
                    comparability="Only compare matrices from identical score definitions and target protocols.",
                    expected_pattern="Components reflect their intended roles without perfect accidental duplication.",
                    failure_interpretation="Near-perfect correlations suggest redundancy; unexpected signs can expose score wiring errors.",
                    evidence_role="oracle/evaluation",
                    source_fields=tuple(f"targets/{name}" for name in component_cols),
                ),
            )


def _render_raw_candidate_metrics(candidates: pd.DataFrame, *, total_candidates: int) -> None:
    """Render bounded per-row diagnostics only; aggregate science owns the full audit path."""

    if candidates.empty:
        return
    with st.expander("Raw candidate reward and metric distribution", expanded=True):
        st.caption(
            f"Showing {len(candidates):,} of {total_candidates:,} rows. Aggregate geometry and support plots use the explicit complete audit above."
        )
        options = [
            name
            for name in (
                "motion_step_length_m",
                "motion_height_delta_m",
                "motion_backward_step_m",
                "motion_yaw_delta_deg",
                "mesh_distance_m",
                "path_min_clearance_m",
                "free_space_margin_m",
                "target_distance_m",
                "target_root_gain",
                "target_rri",
            )
            if name in candidates and candidates[name].notna().any()
        ]
        if not options:
            st.info("No finite per-row metric is available in the bounded sample.")
            return
        metric = st.selectbox("Geometry / label distribution", options=options, key="raw_candidate_metric")
        rows = candidates.dropna(subset=[metric])
        fig = px.histogram(
            rows,
            x=metric,
            color="invalid_reason" if "invalid_reason" in rows else None,
            marginal="box",
            title=f"Raw {metric} distribution",
        )
        _render_plot(
            fig,
            _candidate_population_explanation(
                f"What does the bounded raw {metric} distribution look like?",
                "A deterministic bounded sample of persisted candidate rows; this is not a population estimate.",
                f"{metric}; units follow the field suffix or are dimensionless for reward/RRI.",
                "Finite values only; invalid reasons remain explicit.",
                "The sample reflects the persisted row-level support without claiming complete-store aggregation.",
                "Tails and invalidity-specific modes guide row-level debugging; use aggregate plots for cohort conclusions.",
                f"candidate audit/{metric}",
                "oracle/evaluation" if metric in {"target_root_gain", "target_rri"} else "actor-visible",
                theory_kind=(
                    "endpoint_gain" if metric == "target_root_gain" else "rri" if metric == "target_rri" else None
                ),
            ),
        )
        with st.expander("Raw candidate metric rows and CSV"):
            st.dataframe(rows, hide_index=True, width="stretch")
            _download_frame("Download raw candidate metric CSV", "candidate-raw-metric.csv", rows)


def _render_failure_triage(
    reader: RolloutZarrStoreReader, *, stored_session: session.StoredRolloutSession | None = None
) -> None:
    st.subheader("Failure Triage")
    stored_session = stored_session or session.open_stored_rollout_session(reader.store_dir)
    reader = stored_session.reader
    with st.expander("Advanced thresholds"):
        min_valid = int(st.number_input("Minimum valid fanout", min_value=0, value=3, step=1))
        dominant = float(st.slider("Dominant invalidity fraction", min_value=0.0, max_value=1.0, value=0.8))
        max_step = float(st.slider("Maximum selected step (m)", min_value=0.1, max_value=5.0, value=1.25))
    failures = pd.DataFrame(stored_session.failures(min_valid, dominant, max_step))
    if failures.empty:
        st.success("No failure rows match the active thresholds.")
        return
    severity = failures.groupby(["severity", "kind"], dropna=False).size().reset_index(name="count")
    fig = px.bar(severity, x="kind", y="count", color="severity", title="Failure evidence by kind and severity")
    _render_plot(
        fig,
        ScientificExplanation(
            question="Which contract or data-quality failures dominate this store, and where should inspection begin?",
            population="One emitted triage finding per rollout, step, candidate, target, or store-level condition.",
            metric="Finding count by severity and predicate; counts are not independent scientific samples.",
            denominator_masks="All rows checked by the active threshold configuration.",
            comparability="Thresholds and store schema must match before comparing counts across stores.",
            expected_pattern="Few hard mask/linkage failures; warnings are sparse and traceable to exact rows.",
            failure_interpretation="Counts prioritize debugging only; they do not estimate policy performance.",
            evidence_role="provenance",
            source_fields=(
                "inspection.suspicious_rollout_rows",
                "selected depth",
                "candidate diagnostics",
                "target audit",
            ),
        ),
    )
    st.dataframe(failures, hide_index=True, width="stretch")
    _download_frame("Download failure triage CSV", "failure-triage.csv", failures)
    choices = failures.to_dict("records")
    chosen = st.selectbox(
        "Failure to inspect",
        choices,
        format_func=lambda row: f"{row.get('severity', '?')} · {row.get('kind', '?')} · {row.get('message', '')}",
    )
    st.button(
        "Inspect selected failure",
        on_click=_carry_failure_to_inspect,
        args=(chosen,),
        type="primary",
    )


def _carry_failure_to_inspect(row: dict[str, object]) -> None:
    """Carry stable rollout/step identifiers into the inspection workspace."""

    if row.get("rollout_row_id") is not None:
        st.session_state["stored_rollout_id"] = int(row["rollout_row_id"])
    if row.get("step_row_id") is not None:
        st.session_state["stored_step_id"] = int(row["step_row_id"])
    st.session_state[_SECTION_KEY] = "Inspect, Export & Rerun"


def _canonical_query_store_identity(store_path: Path) -> str:
    """Return a stable compact identity for one canonical immutable-store path."""

    canonical = store_path.expanduser().resolve().as_posix()
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()[:16]


def _query_namespace(store_identity: str, scope: str, candidate_population: str) -> str:
    """Return the disjoint session-state namespace for one query grain."""

    grain = hashlib.sha256(f"{scope}\0{candidate_population}".encode()).hexdigest()[:12]
    return f"stored_query:{store_identity}:{grain}"


def _query_key(namespace: str, name: str) -> str:
    """Return one namespaced query or inspector widget key."""

    return f"{namespace}:{name}"


def _activate_query_store(state: MutableMapping[str, Any], store_identity: str) -> None:
    """Discard query state from the previously active canonical store."""

    previous = state.get(_ACTIVE_QUERY_STORE_KEY)
    if previous is not None and previous != store_identity:
        prefix = f"stored_query:{previous}:"
        for key in [str(value) for value in state if str(value).startswith(prefix)]:
            state.pop(key, None)
    state[_ACTIVE_QUERY_STORE_KEY] = store_identity


def _normalized_query_frame(frame: pd.DataFrame) -> pd.DataFrame:
    """Copy a projection into deterministic columns, row order, and RangeIndex."""

    normalized = frame.loc[:, sorted(str(column) for column in frame.columns)].copy()
    row_keys = [
        column
        for column in ("rollout_row_id", "step_row_id", "candidate_row_id", "target_row_id")
        if column in normalized
    ]
    if row_keys:
        normalized = normalized.sort_values(row_keys, kind="mergesort")
    return normalized.reset_index(drop=True)


def _evaluate_query_frame(frame: pd.DataFrame, expression: str) -> pd.DataFrame:
    """Evaluate one trusted-local pandas expression against a copied frame."""

    source = _normalized_query_frame(frame)
    if not expression.strip():
        return source
    result = source.query(
        expression,
        engine="python",
        local_dict={},
        global_dict={},
    )
    return result.loc[:, source.columns].copy().reset_index(drop=True)


def _clear_query_state(state: MutableMapping[str, Any], namespace: str) -> None:
    """Clear expression/result state without mutating rollout or step selection."""

    for name in (
        "draft_expression",
        "applied_expression",
        "last_valid_result",
        "last_error",
        "selected_result_row",
        "pending_promotion",
        "source_signature",
    ):
        state.pop(_query_key(namespace, name), None)


def _apply_query_state(
    state: MutableMapping[str, Any],
    namespace: str,
    source: pd.DataFrame,
) -> None:
    """Apply the draft expression, preserving the last valid result on error."""

    draft = str(state.get(_query_key(namespace, "draft_expression"), ""))
    try:
        result = _evaluate_query_frame(source, draft)
    except Exception as exc:
        state[_query_key(namespace, "last_error")] = f"{type(exc).__name__}: {exc}"
        return
    state[_query_key(namespace, "applied_expression")] = draft
    state[_query_key(namespace, "last_valid_result")] = result
    state[_query_key(namespace, "last_error")] = None
    state.pop(_query_key(namespace, "selected_result_row"), None)
    state.pop(_query_key(namespace, "pending_promotion"), None)


def _queue_query_promotion(namespace: str, payload: dict[str, int | None]) -> None:
    """Streamlit callback that writes only a pending promotion record."""

    st.session_state[_query_key(namespace, "pending_promotion")] = dict(payload)


def _apply_query_callback(namespace: str, source: pd.DataFrame) -> None:
    """Apply callback evaluated only after the operator presses Apply."""

    _apply_query_state(st.session_state, namespace, source)


def _clear_query_callback(namespace: str, signature: str) -> None:
    """Clear callback that runs before expression/result widgets instantiate."""

    _clear_query_state(st.session_state, namespace)
    st.session_state[_query_key(namespace, "source_signature")] = signature


def _consume_pending_promotion(
    state: MutableMapping[str, Any],
    namespace: str,
    *,
    rollout_ids: list[int],
    steps_by_rollout: dict[int, list[int]],
) -> str | None:
    """Validate and apply pending ids before rollout/step widgets instantiate."""

    pending_key = _query_key(namespace, "pending_promotion")
    pending = state.pop(pending_key, None)
    if not isinstance(pending, dict):
        return None
    try:
        rollout_id = int(pending["rollout_row_id"])
    except (KeyError, TypeError, ValueError):
        return "Pending query promotion has no valid rollout_row_id; prior selection was preserved."
    if rollout_id not in rollout_ids:
        return f"Pending query promotion references stale rollout_row_id={rollout_id}; prior selection was preserved."
    valid_steps = steps_by_rollout.get(rollout_id, [])
    if not valid_steps:
        return f"Pending query promotion rollout_row_id={rollout_id} has no persisted steps; prior selection was preserved."
    requested_step = pending.get("step_row_id")
    try:
        step_id = valid_steps[0] if requested_step is None else int(requested_step)
    except (TypeError, ValueError):
        return "Pending query promotion has no valid step_row_id; prior selection was preserved."
    if step_id not in valid_steps:
        return (
            f"Pending query promotion references stale step_row_id={step_id} for rollout_row_id={rollout_id}; "
            "prior selection was preserved."
        )
    state[_query_key(namespace, "rollout_widget")] = rollout_id
    state[_query_key(namespace, "step_widget")] = step_id
    return None


def _query_source_frame(
    stored_session: session.StoredRolloutSession,
    *,
    scope: str,
    candidate_population: str,
    rollout_id: int,
    step_id: int,
    all_steps: pd.DataFrame,
) -> pd.DataFrame:
    """Return the normalized source projection for one explicit query grain."""

    if scope == "Rollout summaries":
        if all_steps.empty:
            return _normalized_query_frame(all_steps)
        endpoints = (
            all_steps.sort_values(["rollout_row_id", "step_index"], kind="mergesort")
            .groupby("rollout_row_id", as_index=False, sort=True)
            .tail(1)
        )
        return _normalized_query_frame(endpoints)
    if scope == "Factual steps":
        return _normalized_query_frame(all_steps)
    if scope != "Candidates":
        raise ValueError(f"Unsupported query scope: {scope}")
    if candidate_population == "Selected step":
        rows = stored_session.candidates(rollout_row_id=rollout_id, step_row_id=step_id)
    elif candidate_population == "Selected rollout":
        rows = stored_session.candidates(rollout_row_id=rollout_id)
    elif candidate_population == "Explicit full store":
        rows = stored_session.candidates()
    else:
        raise ValueError(f"Unsupported candidate population: {candidate_population}")
    return _normalized_query_frame(pd.DataFrame(rows))


def _query_source_signature(frame: pd.DataFrame) -> str:
    """Return a deterministic identity for the active immutable source population."""

    identifiers = [
        column for column in ("rollout_row_id", "step_row_id", "candidate_row_id") if column in frame.columns
    ]
    payload = "\0".join(frame.columns.astype(str).tolist()).encode("utf-8")
    if identifiers and not frame.empty:
        payload += pd.util.hash_pandas_object(frame[identifiers], index=False).values.tobytes()
    return hashlib.sha256(payload).hexdigest()


def _promotion_payload(row: pd.Series) -> dict[str, int | None]:
    """Extract exact owning rollout/step ids from one normalized query row."""

    rollout = row.get("rollout_row_id")
    step = row.get("step_row_id")
    return {
        "rollout_row_id": None if pd.isna(rollout) else int(rollout),
        "step_row_id": None if pd.isna(step) else int(step),
    }


def _render_query_workbench(
    namespace: str,
    source: pd.DataFrame,
    *,
    scope: str,
    candidate_population: str,
) -> None:
    """Render trusted-local pandas querying, complete export, and row promotion."""

    st.markdown("#### Query and promote evidence")
    st.caption(
        "Trusted local operator feature: the expression is evaluated only against a copied normalized DataFrame "
        'with `df.query(expression, engine="python")`. It is not a security sandbox and never mutates the store.'
    )
    st.caption(f"Available columns: {', '.join(f'`{column}`' for column in source.columns)}")
    st.caption(
        "Examples: `cumulative_target_root_gain > 0.5`, `selected_target_root_gain < 0`, "
        '`position == "lateral_target_bypass" and actor_action`, `root_distance_m > 1.0`.'
    )
    signature = _query_source_signature(source)
    signature_key = _query_key(namespace, "source_signature")
    if st.session_state.get(signature_key) not in (None, signature):
        _clear_query_state(st.session_state, namespace)
    st.session_state[signature_key] = signature
    draft_key = _query_key(namespace, "draft_expression")
    st.text_area("Pandas query expression", key=draft_key, placeholder="Leave empty to match every row")
    col_apply, col_clear = st.columns(2)
    col_apply.button(
        "Apply query",
        key=_query_key(namespace, "apply"),
        type="primary",
        on_click=_apply_query_callback,
        args=(namespace, source),
    )
    col_clear.button(
        "Clear query",
        key=_query_key(namespace, "clear"),
        on_click=_clear_query_callback,
        args=(namespace, signature),
    )
    error = st.session_state.get(_query_key(namespace, "last_error"))
    if error:
        st.error(f"Query failed; the last valid result is preserved. {error}")
    result = st.session_state.get(_query_key(namespace, "last_valid_result"))
    result = source if result is None else result
    result = _normalized_query_frame(result)
    preview_limit = int(
        st.number_input(
            "Query preview row limit",
            min_value=1,
            max_value=10_000,
            value=200,
            step=50,
            key=_query_key(namespace, "preview_limit"),
        )
    )
    shown = result.head(preview_limit)
    applied = str(st.session_state.get(_query_key(namespace, "applied_expression"), ""))
    st.caption(
        f"Scope: {scope}; candidate population: {candidate_population}. Applied expression: {applied or '(empty)'}. "
        f"Input rows: {len(source):,}; matched rows: {len(result):,}; displayed rows: {len(shown):,}; "
        f"exported rows: {len(result):,}. Preview truncation never affects export."
    )
    st.dataframe(shown, hide_index=True, width="stretch")
    _download_frame("Download queried rows CSV", "stored-rollout-query.csv", result)
    if result.empty or "rollout_row_id" not in result:
        st.info("No matched row with a rollout_row_id is available for promotion.")
        return
    choices = result.index.astype(int).tolist()
    selection_key = _query_key(namespace, "selected_result_row")
    if st.session_state.get(selection_key) not in choices:
        st.session_state[selection_key] = choices[0]
    selected_index = int(
        st.selectbox(
            "Matched row to promote",
            options=choices,
            key=selection_key,
            format_func=lambda index: _query_row_label(result.loc[index]),
        )
    )
    payload = _promotion_payload(result.loc[selected_index])
    st.button(
        "Promote queried row",
        key=_query_key(namespace, "promote"),
        on_click=_queue_query_promotion,
        args=(namespace, payload),
        type="primary",
    )


def _query_row_label(row: pd.Series) -> str:
    """Format stable ids for one query-result promotion choice."""

    fields = [
        f"{name}={int(row[name])}"
        for name in ("rollout_row_id", "step_row_id", "candidate_row_id")
        if name in row and not pd.isna(row[name])
    ]
    return " · ".join(fields)


def _render_inspect_export_rerun(
    reader: RolloutZarrStoreReader,
    *,
    store_path: Path,
    manifest_payload: dict[str, Any],
    paths: PathConfig,
    stored_session: session.StoredRolloutSession | None = None,
) -> None:
    st.subheader("Inspect, Export & Rerun")
    stored_session = stored_session or session.open_stored_rollout_session(store_path)
    reader = stored_session.reader
    store_identity = _canonical_query_store_identity(store_path)
    _activate_query_store(st.session_state, store_identity)
    scope_key = f"stored_query:{store_identity}:scope"
    population_key = f"stored_query:{store_identity}:candidate_population"
    scope = st.selectbox("Query scope", options=_QUERY_SCOPES, key=scope_key)
    candidate_population = (
        st.selectbox("Candidate population", options=_CANDIDATE_POPULATIONS, key=population_key)
        if scope == "Candidates"
        else "not_applicable"
    )
    namespace = _query_namespace(store_identity, scope, candidate_population)

    rollout_ids = np.asarray(reader.array("rollouts/rollout_row_id"), dtype=np.int64).reshape(-1).tolist()
    if not rollout_ids:
        st.warning("This store has no rollout rows to inspect or query.")
        return
    all_steps = pd.DataFrame(stored_session.steps())
    steps_by_rollout = {
        int(rollout): sorted(group["step_row_id"].astype(int).tolist())
        for rollout, group in all_steps.groupby("rollout_row_id", sort=True)
    }
    promotion_error = _consume_pending_promotion(
        st.session_state,
        namespace,
        rollout_ids=[int(value) for value in rollout_ids],
        steps_by_rollout=steps_by_rollout,
    )
    if promotion_error:
        st.error(promotion_error)
    rollout_widget_key = _query_key(namespace, "rollout_widget")
    step_widget_key = _query_key(namespace, "step_widget")
    legacy_rollout = st.session_state.pop("stored_rollout_id", None)
    legacy_step = st.session_state.pop("stored_step_id", None)
    if legacy_rollout in rollout_ids:
        st.session_state[rollout_widget_key] = int(legacy_rollout)
        if legacy_step in steps_by_rollout.get(int(legacy_rollout), []):
            st.session_state[step_widget_key] = int(legacy_step)
    requested_rollout = st.session_state.get(rollout_widget_key)
    if requested_rollout not in rollout_ids:
        st.session_state[rollout_widget_key] = int(rollout_ids[0])
    rollout_id = int(
        st.selectbox(
            "Rollout row",
            rollout_ids,
            key=rollout_widget_key,
        )
    )
    steps = pd.DataFrame(stored_session.steps(rollout_row_id=rollout_id))
    step_ids = steps["step_row_id"].astype(int).tolist() if not steps.empty else []
    if not step_ids:
        st.warning("The selected rollout has no persisted steps.")
        return
    requested_step = st.session_state.get(step_widget_key)
    if requested_step not in step_ids:
        st.session_state[step_widget_key] = step_ids[0]
    step_id = int(st.selectbox("Step row", step_ids, key=step_widget_key))

    if scope == "Candidates" and candidate_population == "Explicit full store":
        st.warning(
            "Explicit full-store candidate query selected. This materializes the heavyweight normalized candidate audit; "
            "use Selected step or Selected rollout for routine inspection."
        )
    query_source = _query_source_frame(
        stored_session,
        scope=scope,
        candidate_population=candidate_population,
        rollout_id=rollout_id,
        step_id=step_id,
        all_steps=all_steps,
    )
    _render_query_workbench(
        namespace,
        query_source,
        scope=scope,
        candidate_population=candidate_population,
    )

    candidates = pd.DataFrame(
        stored_session.candidates(
            rollout_row_id=rollout_id,
            step_row_id=step_id,
        )
    )
    preview_limit = int(st.number_input("Candidate preview row limit", min_value=1, max_value=5000, value=200, step=25))
    shown = candidates.head(preview_limit)
    st.caption(
        f"Showing {len(shown):,} of {len(candidates):,} filtered candidate rows. Download contains all {len(candidates):,} rows."
    )
    st.dataframe(shown, hide_index=True, width="stretch")
    _download_frame(
        "Download selected-step candidate CSV", f"rollout-{rollout_id}-step-{step_id}-candidates.csv", candidates
    )

    depth_rows = pd.DataFrame(stored_session.depth_summary(rollout_row_id=rollout_id))
    selected_depth = depth_rows[depth_rows["step_row_id"] == step_id] if not depth_rows.empty else depth_rows
    with st.expander("Privileged selected-depth evaluation artifact", expanded=not selected_depth.empty):
        st.warning("Selected depth is privileged oracle/evaluation evidence, never actor-visible policy input.")
        if selected_depth.empty:
            st.info("No selected-depth row exists for this step.")
        else:
            st.dataframe(selected_depth, hide_index=True, width="stretch")
            preview = selected_depth_preview(reader, step_row_id=step_id)
            if bool(preview.get("available")):
                array = preview["depth_m"]
                fig = px.imshow(
                    np.asarray(array),
                    color_continuous_scale="Turbo",
                    labels={"color": "depth (m)"},
                    title="Selected-action mesh depth",
                )
                _render_plot(
                    fig,
                    ScientificExplanation(
                        question="Is the persisted selected-action depth artifact finite, aligned, and geometrically plausible?",
                        population="One selected rollout step, downsampled only for display.",
                        metric="Mesh depth in metres; invalid pixels are masked.",
                        denominator_masks="Pixels marked valid and finite in selected_depth; full row statistics remain in the table.",
                        comparability="Compare only cameras with compatible calibration and depth representation.",
                        expected_pattern="Finite depth support aligns with the selected candidate and target evaluation crop.",
                        failure_interpretation="Missing or corrupt depth disables this view only; it does not erase factual rollout rows.",
                        evidence_role="oracle/evaluation",
                        source_fields=(
                            "selected_depth/depth_m",
                            "selected_depth/valid_mask",
                            "steps/selected_candidate_row_id",
                        ),
                    ),
                )
            else:
                warning = str(preview.get("warning") or "not persisted")
                st.info(f"No selected-depth row is available for this step: {warning}")

    with st.expander("Metadata and advanced normalized tables"):
        st.json(manifest_payload, expanded=False)
        st.dataframe(steps, hide_index=True, width="stretch")
    _download_json("Download selected metadata JSON", f"rollout-{rollout_id}-metadata.json", manifest_payload)
    _render_q_h_evidence(stored_session)
    _render_evidence_bundle_download(stored_session)
    _render_rerun_launcher(store_path=store_path, rollout_id=rollout_id, paths=paths)


def _render_q_h_evidence(stored_session: session.StoredRolloutSession) -> None:
    """Render metadata-only Q_H facts and gate mask counts behind an explicit toggle."""

    st.markdown("#### Store-local Q_H evidence")
    deep_count = st.toggle(
        "Count current-store Q_H masks",
        value=False,
        help="Off reads metadata only. On performs the bounded current-store mask projection.",
    )
    chunk_size = int(
        st.number_input(
            "Q_H state chunk size",
            min_value=1,
            value=1024,
            step=256,
            disabled=not deep_count,
            help="Bounded Zarr read size used by the optional Q_H mask count.",
        )
    )
    state_limit_value = st.number_input(
        "Q_H state-row limit (0 = full store)",
        min_value=0,
        value=0,
        step=1024,
        disabled=not deep_count,
        help="Optional bounded prefix for diagnostics; 0 counts all persisted Q_H states.",
    )
    state_limit = None if int(state_limit_value) == 0 else int(state_limit_value)
    if not deep_count:
        evidence_rows = stored_session.q_h(deep_count=False)
    else:
        cancel_key = f"q_h_cancel:{stored_session.canonical_path.as_posix()}"
        stop_requested = bool(
            st.checkbox(
                "Stop after the current Q_H chunk",
                value=bool(st.session_state.get(cancel_key, False)),
                key=cancel_key,
                help="Cancellation is observed at the next bounded chunk boundary.",
            )
        )
        progress = st.progress(0.0, text="Preparing bounded Q_H count…")
        status = st.empty()
        reader = stored_session.reader
        validation = stored_session.validation

        def update_progress(completed: int, total: int) -> bool:
            fraction = 1.0 if total <= 0 else min(1.0, float(completed) / float(total))
            progress.progress(fraction, text=f"Q_H count: {completed:,}/{total:,} state rows")
            status.caption(
                "Stop requested; finishing the current chunk." if stop_requested else "Reading bounded Q_H slices…"
            )
            return not stop_requested

        evidence_rows = session.q_h_evidence_rows(
            reader,
            deep_count=True,
            chunk_size=chunk_size,
            state_row_limit=state_limit,
            progress_callback=update_progress,
            validation_result=validation,
        )
        evidence = evidence_rows[0] if evidence_rows else {}
        if str(evidence.get("count_reason", "")).startswith("cancelled"):
            status.caption("Q_H count stopped at a chunk boundary.")
        elif bool(evidence.get("truncated")):
            status.caption("Q_H bounded-prefix count complete.")
        else:
            status.caption("Q_H full-store count complete.")
    rows = pd.DataFrame(evidence_rows)
    st.dataframe(rows, hide_index=True, width="stretch")
    if not rows.empty and not bool(rows.iloc[0].get("available", False)):
        st.info(f"Q_H evidence unavailable: {rows.iloc[0].get('blocking_reason', 'unknown reason')}")
    _download_frame("Download Q_H evidence CSV", "q-h-evidence.csv", rows)


def _render_evidence_bundle_download(stored_session: session.StoredRolloutSession) -> None:
    st.markdown("#### Canonical evidence bundle")
    status = st.radio("Evidence status", options=["pilot", "confirmatory"], horizontal=True, key="evidence_status")
    acknowledge = st.checkbox(
        "I acknowledge that confirmatory status requires frozen protocols and matched evidence.",
        value=False,
        disabled=status != "confirmatory",
    )
    allowed = status == "pilot" or acknowledge
    if allowed:
        st.download_button(
            "Download deterministic evidence bundle",
            data=lambda: stored_session.evidence_bundle(status),
            file_name=f"rollout-evidence-{status}.json",
            mime="application/json",
            on_click="ignore",
            help="Built lazily on click, then cached by immutable store path and evidence status.",
        )
    else:
        st.info("Acknowledge the confirmatory evidence contract to enable this download.")


def _render_rerun_launcher(*, store_path: Path, rollout_id: int, paths: PathConfig) -> None:
    st.markdown("#### Rerun launch")
    base_config = st.text_input(
        "Rerun inspector config",
        value=str(paths.root / ".configs" / "rerun_offline.toml"),
        key="stored_rerun_config",
    )
    artifact_dir = Path(
        st.text_input(
            "Launch artifact directory",
            value=str(paths.root / ".logs" / "rerun" / "stored_rollouts"),
            key="stored_rerun_artifact_dir",
        )
    ).expanduser()
    preset = st.selectbox(
        "Layer preset",
        options=list(RolloutLayerPreset),
        format_func=lambda value: str(value.value).replace("_", " ").title(),
    )
    with st.expander("Advanced included and initially visible layers"):
        overrides: dict[RolloutLayerName, dict[str, bool]] = {}
        defaults = resolve_rollout_launch_config(
            base_config_path=base_config,
            artifact_dir=artifact_dir,
            preset=preset,
        ).config.rollout_layers
        for layer in RolloutLayerName:
            state = getattr(defaults, layer.value)
            col_name, col_inc, col_vis = st.columns([3, 1, 1])
            col_name.markdown(layer.value.replace("_", " ").title())
            included = col_inc.checkbox("Included", value=state.included, key=f"rerun_inc_{layer.value}")
            visible = col_vis.checkbox(
                "Visible",
                value=state.visible and included,
                disabled=not included,
                key=f"rerun_vis_{layer.value}",
            )
            overrides[layer] = {"included": included, "visible": bool(visible and included)}

    mode = st.selectbox(
        "Launch mode",
        options=list(RerunLaunchMode),
        format_func=lambda value: {
            RerunLaunchMode.native_live: "Native live spawn",
            RerunLaunchMode.native_view: "Save then open native viewer",
            RerunLaunchMode.serve_web: "Save then serve web",
            RerunLaunchMode.save_only: "Save-only artifact",
        }[value],
    )
    save_path = artifact_dir / f"rollout-{rollout_id}.rrd"
    web_port = int(st.number_input("Web viewer port", min_value=1, max_value=65535, value=9090))
    grpc_port = int(st.number_input("Rerun gRPC/proxy port", min_value=1, max_value=65535, value=9877))
    lan = st.checkbox("Expose web viewer on the LAN", value=False, disabled=mode is not RerunLaunchMode.serve_web)

    try:
        resolved = resolve_rollout_launch_config(
            base_config_path=base_config,
            artifact_dir=artifact_dir,
            preset=preset,
            overrides=overrides,
        )
        command = build_rerun_rollout_command(
            config_path=resolved.config_path,
            rollout_store=store_path,
            rollout_row_id=rollout_id,
            mode=mode,
            save_path=None if mode is RerunLaunchMode.native_live else save_path,
            web_viewer_port=web_port,
            ws_server_port=grpc_port,
            lan=lan,
        )
    except Exception as exc:
        st.error(f"Rerun launch configuration is invalid: {type(exc).__name__}: {exc}")
        return
    st.code(format_command(command), language="bash")
    st.caption(f"Resolved layer policy: `{resolved.config_path}` · digest `{resolved.digest[:16]}`")

    if st.button("Launch Rerun", type="primary"):
        try:
            previous = st.session_state.get(_LAUNCH_HANDLE_KEY)
            if previous is not None and previous.process.poll() is None:
                stop_rerun_launch(previous)
            url = (
                rerun_web_url(web_viewer_port=web_port, ws_server_port=grpc_port, lan=lan)
                if mode is RerunLaunchMode.serve_web
                else None
            )
            handle = start_rerun_launch(
                command,
                artifact_dir=artifact_dir,
                config_path=resolved.config_path,
                rrd_path=None if mode is RerunLaunchMode.native_live else save_path,
                url=url,
            )
            st.session_state[_LAUNCH_HANDLE_KEY] = handle
        except Exception as exc:
            _report_exception(exc, context="Rerun launch failed")

    handle = st.session_state.get(_LAUNCH_HANDLE_KEY)
    if handle is not None:
        verify_url = handle.url is not None
        status = poll_rerun_launch(handle, verify_url=verify_url)
        (st.success if status.healthy else st.warning)(status.message)
        st.caption(
            f"PID {status.pid} · running={status.running} · exit={status.exit_code} · "
            f"config={status.config_path} · rrd={status.rrd_path}"
        )
        if status.url and status.url_reachable:
            st.link_button("Open Rerun Web Viewer", status.url)
            if st.checkbox("Embed viewer inline", value=False):
                st.components.v1.iframe(status.url, height=720, scrolling=True)
        with st.expander("Rerun stdout/stderr"):
            st.code(status.stdout_tail or "(no stdout)", language="text")
            st.code(status.stderr_tail or "(no stderr)", language="text")
        col_restart, col_stop = st.columns(2)
        if col_restart.button("Restart Rerun"):
            try:
                st.session_state[_LAUNCH_HANDLE_KEY] = restart_rerun_launch(handle)
            except Exception as exc:
                _report_exception(exc, context="Rerun restart failed")
            else:
                st.rerun()
        if col_stop.button("Stop Rerun"):
            stop_rerun_launch(handle)
            st.session_state.pop(_LAUNCH_HANDLE_KEY, None)
            st.rerun()


def _render_stale_store_boundary(
    validation: Any, *, inventory_row: dict[str, object] | None, manifest_payload: dict[str, Any]
) -> None:
    st.warning(
        "Scientific evidence and Rerun are disabled because this store does not pass the current schema contract."
    )
    for error in getattr(validation, "errors", ()):
        st.error(str(error))
    payload = {
        "inventory": inventory_row,
        **manifest_payload,
        "validation_errors": list(getattr(validation, "errors", ())),
    }
    _download_json("Download stale-store diagnostics JSON", "stale-rollout-store.json", payload)


def _render_plot(fig: go.Figure, explanation: ScientificExplanation) -> None:
    """Render one primary plot with a complete scientific interpretation popover."""

    badge_color = _ROLE_COLORS[explanation.evidence_role]
    col_title, col_info = st.columns([5, 1])
    col_title.markdown(
        f'<span style="padding:.15rem .45rem;border-radius:.35rem;background:{badge_color};color:white">'
        f"{html.escape(explanation.evidence_role)}</span>",
        unsafe_allow_html=True,
    )
    with col_info.popover("How to read this", icon="ℹ️"):
        _explanation_item("Question", explanation.question)
        if explanation.intuition:
            _explanation_item("Intuition", explanation.intuition)
        _explanation_item("Population / grain", explanation.population)
        _explanation_item("Metric / units", explanation.metric)
        _explanation_item("Denominator / masks", explanation.denominator_masks)
        if explanation.visual_encoding:
            _explanation_item("Visual encoding", explanation.visual_encoding)
        _explanation_item("Valid comparison conditions", explanation.comparability)
        _explanation_item("Expected pattern", explanation.expected_pattern)
        _explanation_item("Warnings / failure modes", explanation.failure_interpretation)
        if explanation.uncertainty:
            _explanation_item("Uncertainty / missingness", explanation.uncertainty)
        if explanation.theory_references:
            st.markdown("**Canonical theory references**")
            for reference in explanation.theory_references:
                registry = f" · `{reference.registry_key}`" if reference.registry_key else ""
                st.markdown(f"- [{reference.title}]({reference.url}) ({reference.kind}){registry}")
        _explanation_item("Sources", ", ".join(explanation.source_fields), code=True)
    st.plotly_chart(fig, width="stretch")


def _explanation_item(label: str, value: str, *, code: bool = False) -> None:
    """Render one explanation field without leaking patch or HTML escapes."""

    rendered = f"`{value}`" if code else value
    st.markdown(f"**{label}**\n\n{rendered}")


def _download_frame(label: str, file_name: str, frame: pd.DataFrame) -> None:
    """Offer a complete filtered CSV without registering eager media URLs."""

    st.download_button(
        label,
        data=lambda: _serialize_frame_csv(frame),
        file_name=file_name,
        mime="text/csv",
        on_click="ignore",
        help="Materialized lazily on click so tab reruns do not retain stale media URLs.",
    )
    st.caption(f"Export rows: {len(frame):,} (complete filtered dataset).")


def _download_json(label: str, file_name: str, payload: object) -> None:
    """Offer deterministic JSON without registering eager media URLs."""

    st.download_button(
        label,
        data=lambda: _serialize_json(payload),
        file_name=file_name,
        mime="application/json",
        on_click="ignore",
        help="Materialized lazily on click so tab reruns do not retain stale media URLs.",
    )


def _serialize_frame_csv(frame: pd.DataFrame) -> bytes:
    """Serialize every dataframe row in deterministic displayed column order."""

    return frame.to_csv(index=False).encode("utf-8")


def _serialize_json(payload: object) -> bytes:
    """Serialize one payload as stable, indented UTF-8 JSON."""

    return json.dumps(payload, indent=2, sort_keys=True, default=_json_default).encode("utf-8") + b"\n"


def _json_default(value: object) -> object:
    if isinstance(value, Path):
        return value.as_posix()
    if isinstance(value, np.generic):
        return value.item()
    if hasattr(value, "__dataclass_fields__"):
        return asdict(value)
    return str(value)


__all__ = [
    "ScientificExplanation",
    "TheoryReference",
    "render_stored_rollouts_page",
]
