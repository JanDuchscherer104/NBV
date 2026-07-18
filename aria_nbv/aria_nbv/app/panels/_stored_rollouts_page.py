"""Science-first Streamlit workflow for persisted rollout inspection.

The page deliberately keeps data semantics in :mod:`aria_nbv.rollouts.inspection`
and lifecycle semantics in :mod:`aria_nbv.app.rerun_launch`.  This module owns
only interaction state, progressive disclosure, plotting, and download widgets.
"""

from __future__ import annotations

import html
import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Literal

import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from ...configs import PathConfig
from ...dataset_topology import build_dataset_topology, discover_vin_store_dirs
from ...rerun_inspector import RolloutLayerName, RolloutLayerPreset
from ...rollouts import RolloutZarrStoreReader
from ...rollouts.inspection import (
    RolloutSuspiciousQueryConfig,
    candidate_audit_rows,
    candidate_group_summary_rows,
    comparable_policy_cohorts,
    discover_rollout_store_paths,
    mask_combination_rows,
    paired_policy_comparison_rows,
    rollout_step_objective_rows,
    rollout_store_inventory_rows,
    root_relative_candidate_rows,
    selected_candidate_rank_rows,
    selected_depth_preview,
    selected_depth_summary_rows,
    store_invariant_rows,
    suspicious_rollout_rows,
    target_audit_rows,
)
from ...rollouts.reporting import build_thesis_report_frames, serialize_thesis_report_bundle
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


def render_stored_rollouts_page() -> None:
    """Render the five-workspace stored-rollout inspection workflow."""

    st.header("Stored Rollout Zarr")
    st.caption("Trust the artifact first, compare only matched evidence, then inspect one failure or rollout in depth.")
    _render_role_legend()

    paths = PathConfig()
    inventory = rollout_store_inventory_rows(discover_rollout_store_paths(paths.offline_cache_dir))
    store_path = _render_store_selector(paths, inventory)
    if store_path is None:
        st.info("No rollout store is selected. Choose a discovered store or enter a path.")
        return

    selected_inventory = next((row for row in inventory if Path(str(row["path"])) == store_path), None)
    try:
        reader = RolloutZarrStoreReader(store_path)
        validation = reader.validate()
    except Exception as exc:
        st.error(f"The selected store cannot be opened: {type(exc).__name__}: {exc}")
        _download_json("Download store identity JSON", "rollout-store-identity.json", selected_inventory or {})
        return

    try:
        manifest_payload = reader.manifest()
    except Exception:
        manifest_payload = {"root_attrs": {}, "manifest": {}}

    section = st.segmented_control(
        "Inspection workspace",
        options=list(_SECTIONS),
        default=_SECTIONS[0],
        key=_SECTION_KEY,
        width="stretch",
    )
    section = section or _SECTIONS[0]
    current = bool(validation.ok)

    if section == "Trust & Topology":
        _render_trust_and_topology(
            reader=reader,
            store_path=store_path,
            inventory_row=selected_inventory,
            manifest_payload=manifest_payload,
            paths=paths,
        )
        return

    if not current:
        _render_stale_store_boundary(validation, inventory_row=selected_inventory, manifest_payload=manifest_payload)
        return

    if section == "Scientific Evidence":
        _render_scientific_evidence(reader)
    elif section == "Targets & Action Support":
        _render_targets_and_support(reader)
    elif section == "Failure Triage":
        _render_failure_triage(reader)
    else:
        _render_inspect_export_rerun(reader, store_path=store_path, manifest_payload=manifest_payload, paths=paths)


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
        col_status.metric("Validation", "OK" if row.get("validation_ok") else "BLOCKED")
    else:
        col_store.info(f"No `*.zarr` rollout stores found below `{paths.offline_cache_dir}`.")

    with st.expander("Store path override", expanded=not inventory):
        manual = st.text_input("Manual rollouts.zarr path", value="", key="rollout_store_manual_path")
        if manual.strip():
            candidate = Path(manual).expanduser()
            if not candidate.is_absolute():
                candidate = paths.resolve_cache_artifact_dir(manual)
            selected = candidate.resolve()
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
        + "  \\n+        Actor-visible inputs, privileged evaluation, derived training caches, and provenance are never interchangeable.",
        unsafe_allow_html=True,
    )


def _render_trust_and_topology(
    *,
    reader: RolloutZarrStoreReader,
    store_path: Path,
    inventory_row: dict[str, object] | None,
    manifest_payload: dict[str, Any],
    paths: PathConfig,
) -> None:
    st.subheader("Trust & Topology")
    counts = inventory_row or {}
    cols = st.columns(4)
    cols[0].metric("Schema", str(counts.get("schema_status", "unknown")))
    cols[1].metric("Rollouts", str(counts.get("observed_rollouts", "?")))
    cols[2].metric("Steps", str(counts.get("observed_steps", "?")))
    cols[3].metric("Candidates", str(counts.get("observed_candidates", "?")))

    try:
        invariants = store_invariant_rows(reader, manifest_payload=manifest_payload)
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
        topology = build_dataset_topology(
            rollout_store_dir=store_path,
            vin_store_dirs=vin_dirs,
            path_config=paths,
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
                topology = build_dataset_topology(
                    rollout_store_dir=store_path,
                    vin_store_dirs=vin_dirs,
                    path_config=paths,
                    selected_source_row_id=int(source_id),
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


def _render_scientific_evidence(reader: RolloutZarrStoreReader) -> None:
    st.subheader("Scientific Evidence")
    cohort = comparable_policy_cohorts(reader)
    eligibility = bool(cohort.get("eligible"))
    st.metric("Matched comparison eligible", "YES" if eligibility else "NO")
    st.caption(
        "Policies are comparison dimensions only after source sample, target protocol, horizon/budget, candidate/oracle configuration, and branch schedule match."
    )
    if eligibility:
        comparison = pd.DataFrame(paired_policy_comparison_rows(reader))
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

    steps = pd.DataFrame(rollout_step_objective_rows(reader))
    if not steps.empty:
        value_cols = [
            column
            for column in ("cumulative_target_root_gain", "marginal_target_rri")
            if column in steps and steps[column].notna().any()
        ]
        if value_cols:
            long = steps.melt(
                id_vars=[column for column in ("rollout_row_id", "policy", "step_index") if column in steps],
                value_vars=value_cols,
                var_name="metric",
                value_name="value",
            )
            fig = px.line(
                long,
                x="step_index",
                y="value",
                color="policy",
                facet_row="metric",
                markers=True,
                title="Selected-chain gain by depth",
            )
            fig.update_yaxes(matches=None)
            _render_plot(
                fig,
                ScientificExplanation(
                    question="Does the factual selected chain accumulate useful target evidence beyond the first action?",
                    population="One row per selected rollout step; lines retain rollout policy and depth.",
                    metric="Cumulative root-normalized gain and marginal target RRI, dimensionless, on independent axes.",
                    denominator_masks="Selected transitions only; invalid and unselected alternatives are excluded.",
                    comparability="Compare depths only within equal horizons/budgets; policy conclusions still require matched cohorts.",
                    expected_pattern="Cumulative gain grows while marginal gain remains informative rather than collapsing immediately.",
                    failure_interpretation="Flat or negative valid marginal gain can be scientifically real; linkage/mask failures are separate invariants.",
                    evidence_role="oracle/evaluation",
                    source_fields=("steps/cumulative_target_root_gain", "steps/cumulative_target_rri"),
                ),
            )
        _download_frame("Download selected-chain CSV", "selected-chain-evidence.csv", steps)

    ranks = pd.DataFrame(selected_candidate_rank_rows(reader))
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
                    evidence_role="derived training data",
                    source_fields=(
                        "inspection.selected_candidate_rank_rows",
                        "candidates/actor_action_mask",
                        "candidates/target_root_gain",
                    ),
                ),
            )
        st.dataframe(ranks, hide_index=True, width="stretch")
        _download_frame("Download selected rank/regret CSV", "selected-rank-regret.csv", ranks)

    with st.expander("Root-relative candidate geometry (Z-up metres)"):
        if st.checkbox("Load root-relative candidate rows", value=False):
            geometry = pd.DataFrame(root_relative_candidate_rows(reader, actor_valid_only=False))
            if geometry.empty:
                st.info("No candidate geometry is available.")
            else:
                st.caption(
                    "Coordinates are translated by each rollout root. Absolute world coordinates from unrelated scenes are never aggregated."
                )
                st.dataframe(geometry.head(500), hide_index=True, width="stretch")
                st.caption(f"Showing {min(500, len(geometry)):,} of {len(geometry):,}; export is complete.")
                _download_frame("Download root-relative geometry CSV", "root-relative-candidates.csv", geometry)


def _render_targets_and_support(reader: RolloutZarrStoreReader) -> None:
    st.subheader("Targets & Action Support")
    candidate_rows = candidate_audit_rows(reader)
    targets = pd.DataFrame(target_audit_rows(reader))
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

    masks = pd.DataFrame(mask_combination_rows(reader))
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

    families = pd.DataFrame(candidate_group_summary_rows(reader, group_by="position", audit_rows=candidate_rows))
    if not families.empty:
        families["selection_rate_given_available"] = np.where(
            families["actor_valid"] > 0,
            families["selected"] / families["actor_valid"],
            np.nan,
        )
        long = families.melt(
            id_vars="position",
            value_vars=["actor_valid_fraction", "selection_rate_given_available"],
            var_name="metric",
            value_name="fraction",
        )
        fig = px.bar(
            long,
            x="position",
            y="fraction",
            color="metric",
            barmode="group",
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
            ),
        )
        _download_frame("Download family support CSV", "candidate-family-support.csv", families)

    with st.expander("Invalid reasons and valid fanout"):
        invalid = pd.DataFrame(
            candidate_group_summary_rows(reader, group_by="invalid_reason", audit_rows=candidate_rows)
        )
        fanout = pd.DataFrame(rollout_step_objective_rows(reader))
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


def _render_failure_triage(reader: RolloutZarrStoreReader) -> None:
    st.subheader("Failure Triage")
    with st.expander("Advanced thresholds"):
        min_valid = int(st.number_input("Minimum valid fanout", min_value=0, value=3, step=1))
        dominant = float(st.slider("Dominant invalidity fraction", min_value=0.0, max_value=1.0, value=0.8))
        max_step = float(st.slider("Maximum selected step (m)", min_value=0.1, max_value=5.0, value=1.25))
    cfg = RolloutSuspiciousQueryConfig(
        min_valid_candidates=min_valid,
        dominant_invalid_fraction=dominant,
        max_step_distance_m=max_step,
    )
    failures = pd.DataFrame(suspicious_rollout_rows(reader, config=cfg))
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


def _render_inspect_export_rerun(
    reader: RolloutZarrStoreReader,
    *,
    store_path: Path,
    manifest_payload: dict[str, Any],
    paths: PathConfig,
) -> None:
    st.subheader("Inspect, Export & Rerun")
    rollout_ids = np.asarray(reader.array("rollouts/rollout_row_id"), dtype=np.int64).reshape(-1).tolist()
    rollout_id = int(
        st.selectbox(
            "Rollout row",
            rollout_ids,
            key="stored_rollout_id",
        )
    )
    steps = pd.DataFrame(rollout_step_objective_rows(reader, rollout_row_id=rollout_id))
    step_ids = steps["step_row_id"].astype(int).tolist() if not steps.empty else []
    if not step_ids:
        st.warning("The selected rollout has no persisted steps.")
        return
    requested_step = st.session_state.get("stored_step_id")
    if requested_step not in step_ids:
        st.session_state["stored_step_id"] = step_ids[0]
    step_id = int(st.selectbox("Step row", step_ids, key="stored_step_id"))

    candidates = pd.DataFrame(candidate_audit_rows(reader, rollout_row_id=rollout_id, step_row_id=step_id))
    preview_limit = int(st.number_input("Candidate preview row limit", min_value=1, max_value=5000, value=200, step=25))
    shown = candidates.head(preview_limit)
    st.caption(
        f"Showing {len(shown):,} of {len(candidates):,} filtered candidate rows. Download contains all {len(candidates):,} rows."
    )
    st.dataframe(shown, hide_index=True, width="stretch")
    _download_frame(
        "Download selected-step candidate CSV", f"rollout-{rollout_id}-step-{step_id}-candidates.csv", candidates
    )

    depth_rows = pd.DataFrame(selected_depth_summary_rows(reader, rollout_row_id=rollout_id, limit=None))
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
    _render_evidence_bundle_download(store_path)
    _render_rerun_launcher(store_path=store_path, rollout_id=rollout_id, paths=paths)


def _render_evidence_bundle_download(store_path: Path) -> None:
    st.markdown("#### Canonical evidence bundle")
    status = st.radio("Evidence status", options=["pilot", "confirmatory"], horizontal=True, key="evidence_status")
    acknowledge = st.checkbox(
        "I acknowledge that confirmatory status requires frozen protocols and matched evidence.",
        value=False,
        disabled=status != "confirmatory",
    )
    allowed = status == "pilot" or acknowledge
    if allowed:
        try:
            frames = build_thesis_report_frames([store_path], evidence_status=status)
            data = serialize_thesis_report_bundle(frames)
        except Exception as exc:
            st.warning(f"Evidence bundle unavailable: {type(exc).__name__}: {exc}")
        else:
            st.download_button(
                "Download deterministic evidence bundle",
                data=data,
                file_name=f"rollout-evidence-{status}.json",
                mime="application/json",
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
        st.markdown(f"**Question**  \\n+{html.escape(explanation.question)}")
        st.markdown(f"**Population / grain**  \\n+{html.escape(explanation.population)}")
        st.markdown(f"**Metric / units**  \\n+{html.escape(explanation.metric)}")
        st.markdown(f"**Denominator / masks**  \\n+{html.escape(explanation.denominator_masks)}")
        st.markdown(f"**Valid comparison conditions**  \\n+{html.escape(explanation.comparability)}")
        st.markdown(f"**Expected pattern**  \\n+{html.escape(explanation.expected_pattern)}")
        st.markdown(f"**Warnings / failure modes**  \\n+{html.escape(explanation.failure_interpretation)}")
        st.markdown("**Sources**  \\n+" + ", ".join(f"`{html.escape(value)}`" for value in explanation.source_fields))
    st.plotly_chart(fig, width="stretch")


def _download_frame(label: str, file_name: str, frame: pd.DataFrame) -> None:
    """Offer the complete filtered frame and state its exact exported row count."""

    data = frame.to_csv(index=False).encode("utf-8")
    st.download_button(label, data=data, file_name=file_name, mime="text/csv")
    st.caption(f"Export rows: {len(frame):,} (complete filtered dataset).")


def _download_json(label: str, file_name: str, payload: object) -> None:
    """Offer a deterministic, human-readable JSON payload."""

    data = json.dumps(payload, indent=2, sort_keys=True, default=_json_default).encode("utf-8") + b"\n"
    st.download_button(label, data=data, file_name=file_name, mime="application/json")


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
    "render_stored_rollouts_page",
]
