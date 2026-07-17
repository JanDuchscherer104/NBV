"""Checkpoint-backed VIN forward-pass diagnostics and tab orchestration.

The panel owns session reuse of the experiment runtime, obtains one staged
batch, records predictions and intermediate tensors, and dispatches them to
focused diagnostic tabs.
"""

from __future__ import annotations

import traceback
from collections.abc import Iterator

import streamlit as st

from ...configs import PathConfig
from ...data_handling import VinOracleBatch
from ...data_handling.offline.source import VinOfflineSourceConfig
from ...lightning.lit_datamodule import VinDataModule
from ...utils import Stage
from ..state import VIN_DIAG_STATE_KEY, get_vin_state
from ..state_types import config_signature
from .vin_diag_tabs import (
    VinDiagContext,
    render_bin_values_tab,
    render_coral_tab,
    render_encodings_tab,
    render_evidence_tab,
    render_field_tab,
    render_geometry_tab,
    render_pose_tab,
    render_summary_tab,
    render_tokens_tab,
    render_transforms_tab,
)
from .vin_diagnostics_runtime import (
    build_vin_diagnostics_config,
    run_vin_diagnostics,
    setup_vin_diagnostics_runtime,
)


def _iter_stage_batches(datamodule: VinDataModule, *, stage: Stage) -> Iterator[VinOracleBatch]:
    if stage is Stage.TRAIN:
        return iter(datamodule.train_dataloader())
    if stage is Stage.TEST:
        return iter(datamodule.test_dataloader())
    return iter(datamodule.val_dataloader())


def render_vin_diagnostics_page() -> None:
    """Render VIN forward diagnostics using the configured datamodule source."""

    st.header("VIN Diagnostics")
    st.caption(
        "Run VIN forward_with_debug on oracle batches and inspect internal tensors.",
    )

    state = get_vin_state()

    with st.sidebar.form("vin_diag_form"):
        st.subheader("VIN Diagnostics")
        paths = PathConfig()
        config_dir = paths.configs_dir
        config_paths = sorted(
            config_dir.glob("*.toml"),
            key=lambda p: p.stat().st_mtime,
            reverse=True,
        )
        toml_options = ["(none)"] + [path.name for path in config_paths]
        toml_choice = st.selectbox(
            "Experiment config TOML (optional)",
            options=toml_options,
            index=0,
        )
        toml_path = None if toml_choice == "(none)" else str(config_dir / toml_choice)
        stage = st.selectbox(
            "Stage",
            options=[Stage.TRAIN, Stage.VAL, Stage.TEST],
            format_func=lambda s: s.value,
        )
        run = st.form_submit_button("Run / refresh VIN diagnostics")

    if st.sidebar.button("Clear VIN cache"):
        st.session_state.pop(VIN_DIAG_STATE_KEY, None)
        st.rerun()

    if run:
        try:
            cfg = build_vin_diagnostics_config(toml_path=toml_path, stage=stage)
            cfg_sig = config_signature(cfg)

            if state.cfg_sig != cfg_sig or state.module is None or state.datamodule is None:
                runtime = setup_vin_diagnostics_runtime(cfg, stage=stage)
                state.cfg_sig = cfg_sig
                state.experiment = cfg
                state.module = runtime.module
                state.datamodule = runtime.datamodule

            assert state.module is not None and state.datamodule is not None
            with st.spinner("Running datamodule + VIN forward..."):
                batch = next(_iter_stage_batches(state.datamodule, stage=stage))
                pred, debug = run_vin_diagnostics(state.module, batch)

            state.batch = batch
            state.pred = pred
            state.debug = debug
            state.error = None
        except Exception:  # pragma: no cover - UI error guard
            trace = traceback.format_exc()
            print(trace, flush=True)
            state.error = trace

    if state.error:
        st.error("VIN diagnostics failed. See traceback below.")
        st.code(state.error, language="text")
        return

    if state.debug is None or state.pred is None or state.batch is None or state.experiment is None:
        st.info("Run the VIN diagnostics to load a batch.")
        return

    debug = state.debug
    pred = state.pred
    batch = state.batch
    cfg = state.experiment

    num_candidates = int(debug.candidate_valid.shape[-1])
    valid_mask = debug.candidate_valid.reshape(-1)
    valid_count = int(valid_mask.sum().item())
    has_tokens = hasattr(debug, "token_valid")
    has_semidense_frustum = getattr(debug, "semidense_frustum", None) is not None
    if has_tokens:
        valid_frac = debug.token_valid.float().mean(dim=-1).reshape(-1)
        mean_valid_frac = f"{float(valid_frac.mean().item()):.3f}"
    elif getattr(debug, "voxel_valid_frac", None) is not None:
        valid_frac = debug.voxel_valid_frac.reshape(-1)
        mean_valid_frac = f"{float(valid_frac.mean().item()):.3f}"
    else:
        mean_valid_frac = "n/a"

    col_a, col_b, col_c = st.columns(3)
    col_a.metric("Candidates", num_candidates)
    col_b.metric("Valid candidates", f"{valid_count}/{num_candidates}")
    col_c.metric("Mean token valid frac", mean_valid_frac)

    source_is_offline = isinstance(cfg.datamodule_config.source, VinOfflineSourceConfig)
    source_label = "VIN offline store" if source_is_offline else "online oracle labeler"
    st.markdown(
        f"**Scene:** `{batch.scene_id}` &nbsp;&nbsp; "
        f"**Snippet:** `{batch.snippet_id}` &nbsp;&nbsp; "
        f"**Device:** `{debug.candidate_center_rig_m.device!s}` &nbsp;&nbsp; "
        f"**Source:** `{source_label}`"
    )

    (
        tab_summary,
        tab_pose,
        tab_geometry,
        tab_field,
        tab_tokens,
        tab_evidence,
        tab_transforms,
        tab_concept,
        tab_coral,
        tab_bin_values,
    ) = st.tabs(
        [
            "Summary",
            "Pose Descriptor",
            "Geometry",
            "Field Slices",
            "Frustum Tokens",
            "Backbone Evidence",
            "Transforms",
            "FF Encodings",
            "CORAL / Ordinal",
            "Bin Values",
        ],
    )

    ctx = VinDiagContext(
        state=state,
        debug=debug,
        pred=pred,
        batch=batch,
        cfg=cfg,
        use_offline_cache=source_is_offline,
        attach_snippet=True,
        include_gt_mesh=False,
        has_tokens=has_tokens,
        has_semidense_frustum=has_semidense_frustum,
        num_candidates=num_candidates,
    )

    with tab_summary:
        render_summary_tab(ctx)

    with tab_pose:
        render_pose_tab(ctx)

    with tab_geometry:
        render_geometry_tab(ctx)

    with tab_field:
        render_field_tab(ctx)

    with tab_tokens:
        render_tokens_tab(ctx)

    with tab_evidence:
        render_evidence_tab(ctx)

    with tab_transforms:
        render_transforms_tab(ctx)

    with tab_concept:
        render_encodings_tab(ctx)

    with tab_coral:
        render_coral_tab(ctx)

    with tab_bin_values:
        render_bin_values_tab(ctx)
