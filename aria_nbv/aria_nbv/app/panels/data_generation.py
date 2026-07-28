"""Thin Streamlit page for typed local dataset generation."""

from __future__ import annotations

from typing import TYPE_CHECKING

import streamlit as st

from ...configs import PathConfig
from ...oracle.pipelines.generation import (
    GenerationKind,
    discover_generation_configs,
    load_generation_plan,
    run_generation,
)

if TYPE_CHECKING:
    from ...oracle.pipelines.progress import GenerationProgress


def render_data_generation_page() -> None:
    """Render explicit, synchronous VIN-offline and rollout generation."""

    st.header("Data Generation")
    st.caption(
        "Run bounded local VIN offline or rollout generation from typed TOMLs. "
        "Production LRZ/Slurm campaigns remain CLI-owned."
    )
    paths = PathConfig()
    refs = discover_generation_configs(paths.configs_dir)
    if not refs:
        st.info(f"No generation TOMLs found below `{paths.configs_dir / 'generation'}`.")
        return

    available_kinds = tuple(kind for kind in GenerationKind if any(ref.kind is kind for ref in refs))
    kind = st.radio(
        "Dataset type",
        options=available_kinds,
        format_func=lambda value: "VIN offline store" if value is GenerationKind.VIN_OFFLINE else "Rollout samples",
        horizontal=True,
    )
    kind_refs = tuple(ref for ref in refs if ref.kind is kind)
    selected = st.selectbox("Generation config", options=kind_refs, format_func=lambda ref: ref.label)

    try:
        plan = load_generation_plan(selected.path, selected.kind)
    except Exception as exc:
        st.error(f"Configuration is invalid: {type(exc).__name__}: {exc}")
        return

    st.code(plan.config_path.as_posix(), language="text")
    columns = st.columns(3)
    columns[0].metric("Mode", "VIN offline" if plan.kind is GenerationKind.VIN_OFFLINE else "Rollouts")
    columns[1].metric("Max samples", "all" if plan.max_samples is None else str(plan.max_samples))
    columns[2].metric("Destination state", "exists" if plan.destination.exists() else "new")
    st.markdown(f"**Destination:** `{plan.destination}`")
    if plan.source is not None:
        st.markdown(f"**VIN source:** `{plan.source}`")

    with st.expander("Resolved effective configuration"):
        st.json(plan.effective_config, expanded=False)

    for blocker in plan.blockers:
        st.error(blocker)
    if not plan.blockers:
        st.success("Preflight passed")

    allow_overwrite = False
    if plan.requires_overwrite_confirmation:
        st.warning("This VIN config enables overwrite and the destination already exists.")
        allow_overwrite = st.checkbox("Confirm replacement of the existing VIN offline store", value=False)

    disabled = bool(plan.blockers) or (plan.requires_overwrite_confirmation and not allow_overwrite)
    if not st.button("Generate local dataset", type="primary", disabled=disabled):
        return

    bar = st.progress(0.0, text="Preparing writer")
    with st.status("Generating dataset", expanded=True) as status:

        def _render_progress(event: GenerationProgress) -> None:
            if event.total is not None and event.total > 0:
                fraction = min(1.0, max(0.0, float(event.completed) / float(event.total)))
                bar.progress(fraction, text=event.message)
            else:
                bar.progress(0.0, text=event.message)
            status.update(label=event.message)

        try:
            result = run_generation(plan, progress=_render_progress, allow_overwrite=allow_overwrite)
        except Exception as exc:
            status.update(label="Generation failed", state="error", expanded=True)
            st.exception(exc)
            return
        status.update(label="Generation complete", state="complete", expanded=False)
    bar.progress(1.0, text="Generation complete")
    st.success(f"Generation complete: `{result.destination}`")
    st.json(result.summary, expanded=True)


__all__ = ["render_data_generation_page"]
