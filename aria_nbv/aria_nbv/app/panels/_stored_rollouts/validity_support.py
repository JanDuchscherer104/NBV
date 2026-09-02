"""Target-admission and support presentation."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any, cast

import pandas as pd
import plotly.express as px
import streamlit as st

from ....rollouts.candidate_benchmark import (
    CandidateBenchmark,
    CandidateFamilySelection,
    select_candidate_family_shell,
)
from ....rollouts.candidate_support_plotting import candidate_benchmark_figures as _candidate_benchmark_figures
from ....rollouts.candidate_support_plotting import candidate_family_preflight_figures, candidate_support_figures
from ...scientific_labels import TheoryReferences
from ..common import ExplanationSection, ScientificExplanation
from ..common import download_frame as _download_frame
from ..common import render_plot as _render_plot
from .candidate_generation import (
    _render_candidate_aggregate_breakdowns,
    _render_candidate_geometry_diagnostics,
    _render_candidate_population_evidence,
    _render_candidate_provenance_flow,
    _render_target_score_diagnostics,
)
from .session import CANDIDATE_BENCHMARK_STATE_KEY, CandidateBenchmarkBuildResult

_CANDIDATE_FAMILY_SHELL_STATE_KEY = "stored-rollouts:candidate-family-shell"


def _candidate_family_selection_from_plotly_event(event: Mapping[str, Any]) -> CandidateFamilySelection | None:
    """Decode exact heatmap customdata at the presentation boundary."""

    selection = event.get("selection")
    if not isinstance(selection, Mapping):
        return None
    points = selection.get("points")
    if not isinstance(points, list) or not points or not isinstance(points[0], Mapping):
        return None
    customdata = points[0].get("customdata")
    if not isinstance(customdata, list | tuple) or len(customdata) < 3:
        return None
    scene_key, state_key, family = customdata[:3]
    if not all(isinstance(value, str) and value for value in (scene_key, state_key, family)):
        return None
    return CandidateFamilySelection(scene_key, state_key, family)


def _candidate_family_funnel_identities(
    cells: tuple[tuple[str, str, Any], ...], audit_strata: Mapping[str, tuple[str, ...]]
) -> tuple[tuple[str, str], ...]:
    """Choose one deterministic factual state per audit stratum for the app funnel."""

    identities = tuple(dict.fromkeys((scene, state) for scene, state, _cell in cells))
    selected = []
    for scenes in audit_strata.values():
        identity = next((item for item in identities if item[0] in scenes), None)
        if identity is not None:
            selected.append(identity)
    return tuple(dict.fromkeys(selected))


def _selected_candidate_family_shell(
    session_handle: Any,
    *,
    selection: CandidateFamilySelection,
    candidate_limit: int,
) -> tuple[CandidateBenchmark, ...]:
    """Explicitly fetch and filter one identity-bound shell, cached across ordinary reruns."""

    cache_identity = (str(session_handle.store_identity), selection, candidate_limit)
    retained = st.session_state.get(_CANDIDATE_FAMILY_SHELL_STATE_KEY)
    if (
        isinstance(retained, tuple)
        and len(retained) == 2
        and retained[0] == cache_identity
        and isinstance(retained[1], tuple)
        and all(isinstance(record, CandidateBenchmark) for record in retained[1])
    ):
        return cast(tuple[CandidateBenchmark, ...], retained[1])
    records = session_handle.candidate_benchmark_records(
        state_key=selection.state_key,
        candidate_limit=candidate_limit,
    )
    exact = tuple(
        record
        for record in records
        if record.scene_key == selection.scene_key and record.state_key == selection.state_key
    )
    shell = select_candidate_family_shell(exact, selection)
    st.session_state[_CANDIDATE_FAMILY_SHELL_STATE_KEY] = (cache_identity, shell)
    return shell


def _render_bounded_candidate_geometry(session_handle: Any, *, limit: int) -> None:
    """Render geometry from one identity-bound, bounded candidate read."""

    candidates = pd.DataFrame(session_handle.candidates(limit=limit))
    proposal = session_handle.proposal_geometry(limit=limit)
    _render_candidate_geometry_diagnostics(
        candidates,
        proposal,
        session_handle.trajectory_geometry(),
        total_candidates=int(session_handle.validation.num_candidates),
    )


def _render_candidate_benchmark_card(session_handle: Any) -> None:
    """Render the explicit immutable benchmark card and its six support plots."""
    with st.form("candidate_benchmark_build", border=False):
        benchmark_state = (
            st.text_input(
                "Benchmark state key (optional)",
                value="",
                help="Restrict the benchmark to one persisted rollout/step key; leave empty for all states.",
            ).strip()
            or None
        )
        benchmark_limit = int(
            st.number_input(
                "Benchmark candidate row limit",
                min_value=1,
                max_value=500_000,
                value=500,
                step=100,
                help="Bounds interactive figures only; the download always contains the complete selected state.",
            )
        )
        build_requested = st.form_submit_button(
            "Build candidate benchmark",
            help="Construct bounded display records and the complete deterministic export.",
        )
    show_view_directions = st.toggle(
        "Show valid-candidate view directions",
        value=False,
        help="Adds short arrows for the camera optical axes projected into the target-aligned ground plane.",
    )
    store_identity = str(session_handle.store_identity)
    if build_requested:
        try:
            st.session_state[CANDIDATE_BENCHMARK_STATE_KEY] = session_handle.build_candidate_benchmark(
                state_key=benchmark_state,
                candidate_limit=benchmark_limit,
            )
        except (OSError, RuntimeError, ValueError) as error:
            st.session_state.pop(CANDIDATE_BENCHMARK_STATE_KEY, None)
            st.error(f"Candidate benchmark build failed: {error}")
            return
    retained = st.session_state.get(CANDIDATE_BENCHMARK_STATE_KEY)
    if not isinstance(retained, CandidateBenchmarkBuildResult):
        if retained is not None:
            st.session_state.pop(CANDIDATE_BENCHMARK_STATE_KEY, None)
        st.info("Choose the state and display limit, then build the candidate benchmark.")
        return
    if retained.store_identity != store_identity:
        st.session_state.pop(CANDIDATE_BENCHMARK_STATE_KEY, None)
        st.warning("The selected rollout store changed; rebuild the candidate benchmark.")
        return
    if retained.state_key != benchmark_state or retained.candidate_limit != benchmark_limit:
        st.info("The controls changed; build again to replace the retained candidate benchmark.")
        return
    st.download_button(
        "Download candidate benchmark bundle",
        retained.bundle_bytes,
        "candidate-benchmark.zip",
    )
    if retained.family_preflight is not None:
        gate = retained.family_preflight
        status = "GO" if gate.go else "BLOCKED"
        st.markdown(f"#### Candidate-family preflight: {status}")
        st.caption(
            f"Resolved root min_valid={gate.resolved_min_valid} for Nq={gate.query_width}; "
            f"config SHA-256 `{gate.config_sha256}`."
        )
        if gate.blockers:
            st.dataframe(
                pd.DataFrame(
                    [
                        {
                            "code": blocker.code.value,
                            "scene": blocker.scene_key,
                            "state": blocker.state_key,
                            "family": blocker.family,
                            "detail": blocker.detail,
                        }
                        for blocker in gate.blockers
                    ]
                ),
                hide_index=True,
                width="stretch",
            )
        selectable = tuple(
            CandidateFamilySelection(scene_key, state_key, cell.family) for scene_key, state_key, cell in gate.cells
        )
        heatmap, funnel = candidate_family_preflight_figures(
            gate,
            funnel_identities=_candidate_family_funnel_identities(gate.cells, gate.audit_strata),
        )
        heatmap_event = _render_plot(
            heatmap,
            ScientificExplanation(
                question="Does every applicable proposal family survive the frozen Phase-A support gate?",
                answer="The heatmap distinguishes applicable, inapplicable, and unknown cells; click a cell to inspect its persisted shell.",
                sections=(
                    ExplanationSection(
                        "Gate semantics",
                        "Root support, family collapse, target-family support, and oracle-label flat gain are separate typed outcomes.",
                    ),
                ),
                evidence_role="derived training data",
                source_fields=("candidate_family_preflight",),
            ),
            selection_key=f"candidate-family-heatmap:{store_identity}",
        )
        _render_plot(
            funnel,
            ScientificExplanation(
                question="Does every applicable proposal family survive the frozen Phase-A support gate?",
                answer="The funnels retain attempted, actor-valid, and selected denominators.",
                sections=(
                    ExplanationSection(
                        "Gate semantics",
                        "Root support, family collapse, target-family support, and oracle-label flat gain are separate typed outcomes.",
                    ),
                ),
                evidence_role="derived training data",
                source_fields=("candidate_family_preflight",),
            ),
        )
        clicked = (
            _candidate_family_selection_from_plotly_event(heatmap_event) if isinstance(heatmap_event, Mapping) else None
        )
        if selectable:
            selection_by_label = {
                f"{value.scene_key} · {value.state_key} · {value.family}": value for value in selectable
            }
            selectbox_key = f"candidate-family-shell:{store_identity}"
            if clicked in selectable:
                st.session_state[selectbox_key] = next(
                    label for label, value in selection_by_label.items() if value == clicked
                )
            selected_label = st.selectbox(
                "Inspect one scene × state × family shell",
                tuple(selection_by_label),
                key=selectbox_key,
                help="Cell clicks drive the existing target-aligned shell; this control is the keyboard-accessible fallback.",
            )
            selection = selection_by_label[selected_label]
            shell = _selected_candidate_family_shell(
                session_handle,
                selection=selection,
                candidate_limit=gate.query_width,
            )
            for figure in candidate_support_figures(shell)[:2]:
                _render_plot(
                    figure,
                    ScientificExplanation(
                        question="Where is the selected factual-state family supported?",
                        answer="The existing target-aligned shell is filtered by the selected scene, state, and persisted family identity.",
                        sections=(
                            ExplanationSection(
                                "Selection semantics",
                                "The adapter selects only persisted points; it does not recompute geometry or candidate validity.",
                            ),
                        ),
                        evidence_role="derived training data",
                        source_fields=("candidate_family_preflight", "candidate_benchmark.parquet"),
                    ),
                )
    st.markdown("#### Candidate benchmark support")
    for figure in _candidate_benchmark_figures(
        retained.records,
        show_view_directions=show_view_directions,
    ):
        _render_plot(
            figure,
            ScientificExplanation(
                question="What candidate support does the immutable benchmark contain?",
                answer="The plot shows only validated, persisted candidate coordinates and IDs.",
                sections=(
                    ExplanationSection("Availability", "Unavailable metrics remain absent rather than zero-filled."),
                ),
                evidence_role="derived training data",
                source_fields=("candidate_benchmark.parquet",),
            ),
        )


def _render_targets_and_support(session_handle: Any) -> None:
    st.subheader("Targets and action support")
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
    targets = pd.DataFrame(session_handle.targets())
    if not targets.empty:
        required_protocol_fields = {"target_valid", "gt_label_valid", "gt_match_status"}
        missing_protocol_fields = sorted(required_protocol_fields.difference(targets.columns))
        if missing_protocol_fields:
            st.warning(
                "Target-admission plot unavailable: the selected store does not expose the current target audit "
                f"fields ({', '.join(missing_protocol_fields)}). Raw target evidence remains available below."
            )
            protocol = pd.DataFrame()
        else:
            protocol = targets.groupby(sorted(required_protocol_fields), dropna=False).size().reset_index(name="count")
        if not protocol.empty:
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
                    answer="Actor task validity and privileged GT-label validity are separate masks, so an actor-valid target is not silently treated as trainable.",
                    sections=(
                        ExplanationSection(
                            "Population and metric",
                            "Rows are grouped by actor validity, GT-label validity, and match status; the metric is a count, not an effect size.",
                        ),
                        ExplanationSection(
                            "Denominator and comparison",
                            "All target rows remain in the denominator. Compare protocols only when target selection and GT matching agree.",
                        ),
                        ExplanationSection(
                            "Expected pattern and warning",
                            "Actor-valid targets may lack GT labels and remain masked from oracle training; concentration of such rows indicates evaluation coverage gaps.",
                        ),
                    ),
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

    _render_candidate_provenance_flow(session_handle)

    _render_candidate_benchmark_card(session_handle)

    masks = pd.DataFrame(session_handle.masks())
    if not masks.empty:
        label_cols = [c for c in ("actor_action", "oracle_label", "q_train", "selected") if c in masks]
        if "count" not in masks.columns or not label_cols:
            st.warning(
                "Candidate mask-combination plot unavailable: the selected store exposes no grouped mask counts. "
                "The validated store summary remains available in the raw evidence export."
            )
        else:
            masks["combination"] = masks[label_cols].astype(str).agg(" · ".join, axis=1)
            fig = px.bar(masks, x="combination", y="count", title="Observed candidate-mask combinations")
            _render_plot(
                fig,
                ScientificExplanation(
                    question="Which actor, oracle, training, and selection mask combinations actually occur?",
                    answer="The mask combinations expose the boundary between actor admissibility, oracle labels, trainability, and realized selection.",
                    sections=(
                        ExplanationSection(
                            "Population and metric",
                            "Each candidate row contributes its exact four-mask pattern and count within the complete sampled shell.",
                        ),
                        ExplanationSection(
                            "Denominator and comparison",
                            "All persisted rows are retained; selection must imply actor action validity, while q_train is not a selection stage. Compare only matched shell and label protocols.",
                        ),
                        ExplanationSection(
                            "Expected pattern and warning",
                            "Selected actor-invalid rows are hard contract failures. Selected-but-not-q_train rows can be valid when labels are unavailable.",
                        ),
                    ),
                    evidence_role="derived training data",
                    source_fields=(
                        "candidates/actor_action_mask",
                        "oracle_label_mask",
                        "q_train_mask",
                        "selected_mask",
                    ),
                    theory=TheoryReferences(
                        equation_ids=("rl.masked_candidate_selection",),
                        symbol_ids=("rl.validity_mask",),
                        term_ids=("validity-mask",),
                    ),
                ),
            )
        st.dataframe(masks.drop(columns="combination", errors="ignore"), hide_index=True, width="stretch")
        _download_frame(
            "Download mask combinations CSV",
            "candidate-mask-combinations.csv",
            masks.drop(columns="combination", errors="ignore"),
        )

    if st.toggle(
        "Load complete candidate aggregate breakdowns",
        value=False,
        help="Builds the heavyweight candidate audit used by the restored family, mask-population, and invalid-reason tables.",
    ):
        _render_candidate_aggregate_breakdowns(session_handle)

    if st.toggle(
        "Load complete candidate-family lineage and choice evidence",
        value=False,
        help=(
            "Materializes the complete candidate audit only after this explicit request. "
            "The resulting surface exposes allocation share, valid share, policy mass, realized selection, "
            "and expected-versus-realized family transitions with exact contract controls and pooled temperatures."
        ),
    ):
        _render_candidate_population_evidence(session_handle)

    with st.expander(
        "Bounded candidate geometry and reward plots",
        expanded=True,
    ):
        st.caption(
            "Bounded preview is loaded automatically from the validated candidate shell; "
            "the explicit heavy population audit above remains opt-in."
        )
        _render_bounded_candidate_geometry(session_handle, limit=candidate_plot_limit)
