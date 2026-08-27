"""Lazy page router for the ARIA-NBV Streamlit application.

The application frame owns page configuration, grouped navigation, and
exception containment. Each page callback imports its panel and constructs any
single-step pipeline state only after the user selects that page.
"""

from __future__ import annotations

import traceback
from collections.abc import Callable
from contextlib import AbstractContextManager
from dataclasses import dataclass
from typing import TYPE_CHECKING, cast

import streamlit as st

if TYPE_CHECKING:
    from aria_nbv.app.config import NbvStreamlitAppConfig
    from aria_nbv.app.controller import PipelineController
    from aria_nbv.app.state_types import AppState
    from aria_nbv.utils import Console


@dataclass(slots=True)
class NbvStreamlitApp:
    """Render the grouped NBV inspection application from one configuration.

    Dataset, rollout, and model pages remain independent of the legacy
    single-step controller. Only Candidate Proposals and the Foundations /
    Single-step pages construct :class:`aria_nbv.app.controller.PipelineController`
    state.
    """

    config: NbvStreamlitAppConfig
    """Dataset and oracle-pipeline configuration owned by this app instance."""

    def run(self) -> None:  # pragma: no cover - Streamlit runner
        """Render one Streamlit session and surface any uncaught traceback."""

        from aria_nbv.utils import Console

        console = Console.with_prefix("nbv_streamlit_app")
        try:
            self._render()
        except Exception as exc:  # pragma: no cover - UI containment
            trace = traceback.format_exc()
            print(trace, flush=True)
            console.error(trace)
            st.error(
                "Unexpected error encountered. The session stays alive; see full traceback below.",
            )
            st.exception(exc)
            with st.expander("Full traceback", expanded=True):
                st.code(trace, language="text")
            st.stop()

    def _single_step_runtime(self) -> tuple[Console, AppState, PipelineController]:
        """Construct state and controls for a selected single-step page only."""

        from aria_nbv.app.controller import PipelineController
        from aria_nbv.app.state import clear_state, get_state, safe_rerun, store_state
        from aria_nbv.utils import Console, Verbosity

        state = get_state(self.config.dataset, self.config.labeler)
        with st.sidebar.expander("Single-step session", expanded=False):
            verbosity = st.selectbox(
                "Verbosity",
                options=[Verbosity.QUIET, Verbosity.NORMAL, Verbosity.VERBOSE],
                format_func=lambda value: value.name.title(),
                index=2,
                key="single_step_verbosity",
            )
            st.caption(f"sample_idx={state.sample_idx}")
            st.write(
                {
                    "data": state.data.sample is not None,
                    "candidates": state.candidates.candidates is not None,
                    "depth": state.depth.depths is not None,
                    "pcs": bool(state.pcs.by_stride),
                    "rri": state.rri.result is not None,
                },
            )
            run_all = st.button(
                "Run full single-step pipeline",
                key="single_step_run_all",
                width="stretch",
            )
            clear = st.button(
                "Clear single-step session",
                key="single_step_clear",
                width="stretch",
            )

        if clear:
            clear_state()
            safe_rerun()

        console = Console.with_prefix("nbv_streamlit_app").set_verbosity(verbosity)
        controller = PipelineController(
            state,
            console=console,
            progress=cast(
                Callable[[str], AbstractContextManager[None, bool | None]],
                lambda message: st.status(message, expanded=False),
            ),
        )
        if run_all:
            controller.get_sample(force=True)
            controller.get_candidates(force=True)
            controller.get_renders(force=True)
            store_state(state)
            safe_rerun()
        return console, state, controller

    def _page_training_dataset(self) -> None:
        """Render the training-dataset composition hub."""

        from aria_nbv.app.panels.training_dataset import render_training_dataset_page

        render_training_dataset_page()

    def _page_root_observation_store(self) -> None:
        """Render immutable root-observation-store diagnostics."""

        from aria_nbv.app.panels.offline_dataset import render_offline_dataset_page

        render_offline_dataset_page()

    def _page_rollout_supervision(self) -> None:
        """Render persisted multi-step rollout supervision."""

        from aria_nbv.app.panels.stored_rollouts import render_stored_rollouts_panel

        recipe, recipe_path = self.config.load_s2_report_recipe()
        render_stored_rollouts_panel(
            s2_recipe=recipe,
            s2_section_id=self.config.s2_report_section_id,
            s2_recipe_label=recipe_path.as_posix(),
        )

    def _page_live_rollout_lab(self) -> None:
        """Render the interactive counterfactual-rollout laboratory."""

        from aria_nbv.app.panels.counterfactual_rollouts import render_counterfactual_rollouts_page

        render_counterfactual_rollouts_page()

    def _page_candidate_proposals(self) -> None:
        """Render proposal diagnostics with page-owned single-step controls."""

        from aria_nbv.app.panels.candidates import render_candidates_page
        from aria_nbv.app.state import store_state
        from aria_nbv.app.ui import candidate_config_ui

        console, state, controller = self._single_step_runtime()
        previous_config = state.labeler_cfg.generator
        with st.sidebar.form("candidate_proposals_form"):
            candidate_config = candidate_config_ui(
                previous_config,
                st.sidebar,
                is_debug=previous_config.is_debug,
                verbosity=console.verbosity,
            )
            refresh = st.form_submit_button("Run / refresh proposals")
        state.labeler_cfg = state.labeler_cfg.model_copy(
            update={"generator": candidate_config},
        )
        sample = controller.get_sample(force=False)
        candidates = controller.get_candidates(force=refresh)
        store_state(state)
        render_candidates_page(sample, candidates, candidate_config)

    def _page_campaign_generation(self) -> None:
        """Render the bounded CUDA campaign operator page."""

        from aria_nbv.app.panels.campaign_generation import render_campaign_generation_page

        recipe, recipe_path = self.config.load_s2_report_recipe()
        render_campaign_generation_page(
            s2_recipe=recipe,
            s2_section_id=self.config.s2_report_section_id,
            s2_recipe_label=recipe_path.as_posix(),
        )

    def _page_vin_diagnostics(self) -> None:
        """Render VIN model diagnostics."""

        from aria_nbv.app.panels.vin_diagnostics import render_vin_diagnostics_page

        render_vin_diagnostics_page()

    def _page_rri_binning(self) -> None:
        """Render ordinal RRI binning diagnostics."""

        from aria_nbv.app.panels.rri_binning import render_rri_binning_page

        render_rri_binning_page()

    def _page_wandb_runs(self) -> None:
        """Render Weights & Biases run analysis."""

        from aria_nbv.app.panels.wandb import render_wandb_analysis_page

        render_wandb_analysis_page()

    def _page_scientific_reporting(self) -> None:
        """Render immutable report preview and exact-snapshot export."""

        from aria_nbv.app.panels.reporting import render_reporting_workspace

        render_reporting_workspace()

    def _page_configuration_workspace(self) -> None:
        """Render trusted, metadata-only TOML configuration authoring."""

        from aria_nbv.app.panels.configuration import (
            render_configuration_workspace,
            trusted_config_catalog,
            trusted_config_patterns,
        )

        render_configuration_workspace(trusted_config_catalog(), path_patterns=trusted_config_patterns())

    def _page_optuna_studies(self) -> None:
        """Render Optuna study analysis."""

        from aria_nbv.app.panels.optuna_sweep import render_optuna_sweep_page

        render_optuna_sweep_page()

    def _page_observed_snippet(self) -> None:
        """Render one observed snippet with page-owned dataset controls."""

        from aria_nbv.app.panels.data import render_data_page
        from aria_nbv.app.state import store_state
        from aria_nbv.app.ui import dataset_config_ui

        console, state, controller = self._single_step_runtime()
        with st.sidebar.form("observed_snippet_form"):
            previous_config = state.dataset_cfg
            dataset_config = dataset_config_ui(
                st.sidebar,
                verbosity=console.verbosity,
                is_debug=previous_config.is_debug,
            )
            sample_index = st.number_input(
                "Sample index",
                min_value=0,
                value=int(state.sample_idx),
                step=1,
            )
            next_sample = st.form_submit_button("Next sample")
            refresh = st.form_submit_button("Run / refresh observation")
        if next_sample:
            sample_index += 1
            refresh = True
        state.sample_idx = int(sample_index)
        state.dataset_cfg = dataset_config
        sample = controller.get_sample(force=refresh)
        store_state(state)
        render_data_page(sample)

    def _page_candidate_renders(self) -> None:
        """Render candidate depths with page-owned renderer controls."""

        from aria_nbv.app.panels.depth import render_depth_page
        from aria_nbv.app.state import store_state
        from aria_nbv.app.ui import renderer_config_ui

        console, state, controller = self._single_step_runtime()
        with st.sidebar.form("candidate_renders_form"):
            previous_config = state.labeler_cfg.depth
            depth_config = renderer_config_ui(
                previous_config,
                st.sidebar,
                is_debug=previous_config.is_debug,
                verbosity=console.verbosity,
            )
            stride = st.slider(
                "Backprojection stride",
                1,
                32,
                int(state.labeler_cfg.backprojection_stride),
                step=1,
                key="candidate_renders_stride",
            )
            refresh = st.form_submit_button("Run / refresh renders")
        state.labeler_cfg = state.labeler_cfg.model_copy(
            update={
                "depth": depth_config,
                "backprojection_stride": int(stride),
            },
        )
        depth_batch, point_clouds = controller.get_renders(force=refresh)
        sample = controller.get_sample(force=False)
        store_state(state)
        render_depth_page(sample, depth_batch, pcs=point_clouds)

    def _page_single_step_rri(self) -> None:
        """Render oracle RRI with page-owned scoring controls."""

        from aria_nbv.app.panels.rri import render_rri_page
        from aria_nbv.app.state import store_state
        from aria_nbv.app.ui import oracle_config_ui

        _, state, controller = self._single_step_runtime()
        with st.sidebar.form("single_step_rri_form"):
            previous_config = state.labeler_cfg
            oracle_config = oracle_config_ui(previous_config.oracle, st.sidebar)
            stride = st.slider(
                "Backprojection stride",
                1,
                32,
                int(previous_config.backprojection_stride),
                step=1,
                key="single_step_rri_stride",
            )
            refresh = st.form_submit_button("Run / refresh oracle RRI")
        state.labeler_cfg = state.labeler_cfg.model_copy(
            update={
                "oracle": oracle_config,
                "backprojection_stride": int(stride),
                "output_device": "cpu",
            },
        )
        sample = controller.get_sample(force=False)
        depths, point_clouds, rri = controller.run_labeler(force=refresh)
        store_state(state)
        render_rri_page(sample, depths, point_clouds, rri)

    @staticmethod
    def _render_label_display_control() -> None:
        """Render the single app-wide scientific-label preference."""

        segmented_control = getattr(st, "segmented_control", None)
        if not callable(segmented_control):
            return
        from aria_nbv.app.scientific_labels import LABEL_DISPLAY_MODES
        from aria_nbv.app.state import get_label_display_mode, set_label_display_mode

        current = get_label_display_mode()
        selected = segmented_control(
            "Scientific labels",
            options=LABEL_DISPLAY_MODES,
            default=current,
            key="nbv_scientific_label_display",
            help="Choose canonical symbols, readable descriptions, or both where a surface supports mathematics.",
        )
        if selected is not None and selected != current:
            set_label_display_mode(str(selected))

    def _render(self) -> None:  # pragma: no cover - Streamlit UI
        """Configure the frame and run only the currently selected page."""

        st.set_page_config(page_title="ARIA-NBV Training Data", layout="wide")
        pages = {
            "": [st.Page(self._page_training_dataset, title="Training Dataset", default=True)],
            "Training Data": [
                st.Page(self._page_root_observation_store, title="Root Observation Store"),
                st.Page(self._page_rollout_supervision, title="Rollout Supervision"),
            ],
            "Generation": [
                st.Page(self._page_campaign_generation, title="Campaign Generation"),
                st.Page(self._page_live_rollout_lab, title="Live Rollout Lab"),
                st.Page(self._page_candidate_proposals, title="Candidate Proposals"),
            ],
            "Models & Experiments": [
                st.Page(self._page_vin_diagnostics, title="VIN Diagnostics"),
                st.Page(self._page_rri_binning, title="RRI Binning"),
                st.Page(self._page_wandb_runs, title="W&B Runs"),
                st.Page(self._page_optuna_studies, title="Optuna Studies"),
            ],
            "Reporting & Configuration": [
                st.Page(self._page_scientific_reporting, title="Scientific Reporting"),
                st.Page(self._page_configuration_workspace, title="Configuration Workspace"),
            ],
            "Foundations / Single-step": [
                st.Page(self._page_observed_snippet, title="Observed Snippet"),
                st.Page(self._page_candidate_renders, title="Candidate Renders"),
                st.Page(self._page_single_step_rri, title="Single-step Oracle RRI"),
            ],
        }
        self._render_label_display_control()
        st.navigation(pages, position="top").run()


from aria_nbv.app.config import NbvStreamlitAppConfig  # noqa: E402

NbvStreamlitAppConfig.model_rebuild(
    _types_namespace={"NbvStreamlitApp": NbvStreamlitApp},
)


__all__ = ["NbvStreamlitApp"]
