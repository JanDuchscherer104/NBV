"""Refactored Streamlit app entrypoint."""

from __future__ import annotations

import traceback
from dataclasses import dataclass

import streamlit as st

from aria_nbv.app.panels.optuna_sweep import render_optuna_sweep_page

from ..utils import Console, Verbosity
from .config import NbvStreamlitAppConfig
from .controller import PipelineController
from .panels import (
    render_candidates_page,
    render_counterfactual_rollouts_page,
    render_data_page,
    render_depth_page,
    render_offline_dataset_page,
    render_rl_page,
    render_rri_binning_page,
    render_rri_page,
    render_stored_rollouts_panel,
    render_testing_attribution_page,
    render_vin_diagnostics_page,
    render_wandb_analysis_page,
)
from .state import clear_state, get_state, safe_rerun, store_state
from .ui import (
    candidate_config_ui,
    dataset_config_ui,
    oracle_config_ui,
    renderer_config_ui,
)


@dataclass(slots=True)
class NbvStreamlitApp:
    config: NbvStreamlitAppConfig

    def run(self) -> None:  # pragma: no cover - UI code
        console = Console.with_prefix("nbv_streamlit_app")
        try:
            self._render(console)
        except Exception as exc:  # pragma: no cover
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

    def _render(self, console: Console) -> None:  # pragma: no cover - UI code
        st.set_page_config(page_title="NBV Explorer", layout="wide")

        state = get_state(self.config.dataset, self.config.labeler)
        console = console.set_verbosity(
            st.sidebar.selectbox(
                "Verbosity (global)",
                options=[Verbosity.QUIET, Verbosity.NORMAL, Verbosity.VERBOSE],
                format_func=lambda v: v.name.title(),
                index=2,
            ),
        )

        controller = PipelineController(
            state,
            console=console,
            progress=lambda msg: st.status(msg, expanded=False),
        )

        # Global controls -------------------------------------------------
        st.sidebar.divider()
        st.sidebar.subheader("Run controls")
        run_all = st.sidebar.button("Run ALL (data → candidates → renders)")
        clear = st.sidebar.button("Clear session state")
        if clear:
            clear_state()
            safe_rerun()

        # Show cache status ----------------------------------------------
        st.sidebar.divider()
        st.sidebar.subheader("Cache status")
        st.sidebar.caption(f"sample_idx={state.sample_idx}")
        st.sidebar.write(
            {
                "data": state.data.sample is not None,
                "candidates": state.candidates.candidates is not None,
                "depth": state.depth.depths is not None,
                "pcs": bool(state.pcs.by_stride),
                "rri": state.rri.result is not None,
            },
        )

        if run_all:
            controller.get_sample(force=True)
            controller.get_candidates(force=True)
            controller.get_renders(force=True)
            store_state(state)
            safe_rerun()

        # Pages ----------------------------------------------------------
        def _page_data() -> None:
            with st.sidebar.form("data_form"):
                dataset_cfg_prev = state.dataset_cfg
                dataset_cfg = dataset_config_ui(
                    st.sidebar,
                    verbosity=console.verbosity,
                    is_debug=dataset_cfg_prev.is_debug,
                )
                sample_idx = st.number_input(
                    "Sample index",
                    min_value=0,
                    value=int(state.sample_idx),
                    step=1,
                )
                next_sample = st.form_submit_button("Next sample")
                refresh_data = st.form_submit_button("Run / refresh data")
            if next_sample:
                sample_idx += 1
                refresh_data = True
            state.sample_idx = int(sample_idx)
            state.dataset_cfg = dataset_cfg
            sample = controller.get_sample(force=refresh_data)
            store_state(state)

            render_data_page(sample, crop_margin=dataset_cfg.mesh_crop_margin_m)

        def _page_candidates() -> None:
            cand_cfg_prev = state.labeler_cfg.generator
            with st.sidebar.form("cand_form"):
                cand_cfg = candidate_config_ui(
                    cand_cfg_prev,
                    st.sidebar,
                    is_debug=cand_cfg_prev.is_debug,
                    verbosity=console.verbosity,
                )
                refresh_cand = st.form_submit_button("Run / refresh candidates")
            state.labeler_cfg = state.labeler_cfg.model_copy(
                update={"generator": cand_cfg},
            )
            sample = controller.get_sample(force=False)
            candidates = controller.get_candidates(force=refresh_cand)

            store_state(state)

            render_candidates_page(
                sample,
                candidates,
                cand_cfg,
            )

        def _page_counterfactual_rollouts() -> None:
            render_counterfactual_rollouts_page()

        def _page_stored_rollouts() -> None:
            render_stored_rollouts_panel()

        def _page_renders() -> None:
            with st.sidebar.form("depth_form"):
                depth_cfg_prev = state.labeler_cfg.depth
                depth_cfg = renderer_config_ui(
                    depth_cfg_prev,
                    st.sidebar,
                    is_debug=depth_cfg_prev.is_debug,
                    verbosity=console.verbosity,
                )
                stride_prev = int(state.labeler_cfg.backprojection_stride)
                stride = st.slider(
                    "Backprojection stride",
                    1,
                    32,
                    stride_prev,
                    step=1,
                    key="depth_stride",
                )
                refresh_depth = st.form_submit_button("Run / refresh renders")
            state.labeler_cfg = state.labeler_cfg.model_copy(
                update={
                    "depth": depth_cfg,
                    "backprojection_stride": int(stride),
                },
            )

            depth_batch, pcs = controller.get_renders(force=refresh_depth)
            sample = controller.get_sample(force=False)
            store_state(state)

            render_depth_page(sample, depth_batch, pcs=pcs)

        def _page_rri() -> None:
            with st.sidebar.form("rri_form"):
                labeler_cfg_prev = state.labeler_cfg
                oracle_cfg_prev = labeler_cfg_prev.oracle
                oracle_cfg = oracle_config_ui(oracle_cfg_prev, st.sidebar)
                stride = st.slider(
                    "Backprojection stride",
                    1,
                    32,
                    int(labeler_cfg_prev.backprojection_stride),
                    step=1,
                    key="rri_stride",
                )
                refresh_rri = st.form_submit_button("Run / refresh RRI")

            # Always plot on CPU to keep Plotly conversions predictable.
            labeler_cfg = state.labeler_cfg.model_copy(
                update={
                    "oracle": oracle_cfg,
                    "backprojection_stride": int(stride),
                    "output_device": "cpu",
                },
            )
            state.labeler_cfg = labeler_cfg

            sample = controller.get_sample(force=False)
            depths, pcs, rri = controller.run_labeler(force=refresh_rri)
            store_state(state)

            render_rri_page(sample, depths, pcs, rri)

        def _page_rl() -> None:
            sample = controller.get_sample(force=False)
            store_state(state)
            render_rl_page(
                sample,
                labeler_cfg=state.labeler_cfg,
                panel_cfg=self.config.rl,
            )

        def _page_vin() -> None:
            render_vin_diagnostics_page()

        def _page_offline_dataset() -> None:
            render_offline_dataset_page()

        def _page_rri_binning() -> None:
            render_rri_binning_page()

        def _page_wandb() -> None:
            render_wandb_analysis_page()

        def _page_testing_attr() -> None:
            render_testing_attribution_page()

        def _page_optuna_sweep() -> None:
            render_optuna_sweep_page()

        pages = [
            st.Page(_page_data, title="Data", default=True),
            st.Page(_page_candidates, title="Candidate Poses"),
            st.Page(_page_counterfactual_rollouts, title="Counterfactual Rollouts"),
            st.Page(_page_stored_rollouts, title="Stored Rollout Zarr"),
            st.Page(_page_renders, title="Candidate Renders"),
            st.Page(_page_rri, title="RRI"),
        ]
        if self.config.rl.enabled:
            pages.append(st.Page(_page_rl, title="RL Inspector"))
        pages.extend(
            [
                st.Page(_page_vin, title="VIN Diagnostics"),
                st.Page(_page_offline_dataset, title="VIN Offline Dataset"),
                st.Page(_page_wandb, title="W&B Analysis"),
                st.Page(_page_optuna_sweep, title="Optuna Sweep"),
                st.Page(_page_testing_attr, title="Testing & Attribution"),
                st.Page(_page_rri_binning, title="RRI Binning"),
            ]
        )
        st.navigation(pages, position="top").run()


# Resolve forward refs now that NbvStreamlitApp is defined
NbvStreamlitAppConfig.model_rebuild(
    _types_namespace={"NbvStreamlitApp": NbvStreamlitApp},
)


__all__ = ["NbvStreamlitApp"]
