"""Pipeline controller for the refactored Streamlit app.

This module contains all heavy compute orchestration. Pages should call the
controller methods and remain responsible only for UI and plotting.
"""

from __future__ import annotations

from collections.abc import Callable
from contextlib import AbstractContextManager, nullcontext

from ..data_handling import EfmSnippetView
from ..pose_generation.types import CandidateSamplingResult
from ..rendering import CandidateDepths, build_candidate_pointclouds
from ..rendering.candidate_pointclouds import CandidatePointClouds
from ..rri_metrics.rri import RriResult
from ..utils import Console
from .state_types import (
    AppState,
    candidates_key,
    config_signature,
    depths_key,
    pcs_key,
    sample_key,
)

ProgressCallback = Callable[[str], AbstractContextManager[None]]


def _noop_progress(_: str) -> AbstractContextManager[None]:
    return nullcontext()


class PipelineController:
    """Compute + cache pipeline stages in Streamlit session state."""

    def __init__(
        self,
        state: AppState,
        *,
        console: Console,
        progress: ProgressCallback | None = None,
    ) -> None:
        self.state = state
        self.console = console
        self.progress = progress or _noop_progress

    # ------------------------------------------------------------------ public
    def get_sample(self, *, force: bool) -> EfmSnippetView:
        """Load and cache the selected dataset sample."""

        cfg = self.state.dataset_cfg
        cfg_sig = config_signature(cfg)
        cache = self.state.data

        if (
            not force
            and cache.sample is not None
            and cache.cfg_sig == cfg_sig
            and cache.sample_idx == int(self.state.sample_idx)
        ):
            return cache.sample

        ds_iter = cache.dataset_iter

        # Reset iterator when config changed or we need to go backwards.
        reset_iter = cache.cfg_sig != cfg_sig or ds_iter is None or cache.last_iter_idx is None
        if not reset_iter and self.state.sample_idx <= int(cache.last_iter_idx):
            reset_iter = True

        if reset_iter:
            self.console.log("Initialising dataset iterator")
            ds = cfg.setup_target()
            ds_iter = iter(ds)
            start_idx = 0
        else:
            assert cache.last_iter_idx is not None
            start_idx = int(cache.last_iter_idx) + 1

        target_idx = int(self.state.sample_idx)
        steps = max(target_idx - start_idx, 0)
        self.console.log(f"Advancing dataset iterator from {start_idx} to {target_idx} (steps={steps})")

        assert ds_iter is not None
        sample = None
        for _ in range(steps + 1):
            sample = next(ds_iter)
        assert sample is not None

        cache.cfg_sig = cfg_sig
        cache.sample_idx = target_idx
        cache.dataset_iter = ds_iter
        cache.last_iter_idx = target_idx
        cache.sample = sample

        # Invalidate downstream stages.
        self._invalidate_after_data()

        return sample

    def get_candidates(self, *, force: bool) -> CandidateSamplingResult:
        """Generate and cache candidates for the current sample."""

        sample = self.get_sample(force=False)
        cfg = self.state.labeler_cfg.generator
        cfg_sig = config_signature(cfg)
        skey = sample_key(sample)
        cache = self.state.candidates

        if not force and cache.candidates is not None and cache.cfg_sig == cfg_sig and cache.sample_key == skey:
            return cache.candidates

        generator = cfg.setup_target()
        with self.progress("Generating candidates..."):
            candidates = generator.generate_from_typed_sample(sample)

        cache.cfg_sig = cfg_sig
        cache.sample_key = skey
        cache.candidates = candidates

        self._invalidate_after_candidates()
        return candidates

    def get_depths(self, *, force: bool) -> CandidateDepths:
        """Render and cache candidate depths for the current sample."""

        sample = self.get_sample(force=False)
        candidates = self.get_candidates(force=False)
        cfg = self.state.labeler_cfg.depth
        cfg_sig = config_signature(cfg)
        skey = sample_key(sample)
        ckey = candidates_key(candidates)
        cache = self.state.depth

        if (
            not force
            and cache.depths is not None
            and cache.cfg_sig == cfg_sig
            and cache.sample_key == skey
            and cache.candidates_key == ckey
        ):
            return cache.depths

        renderer = cfg.setup_target()
        with self.progress("Rendering depth maps..."):
            depths = renderer.render(sample=sample, candidates=candidates)

        cache.cfg_sig = cfg_sig
        cache.sample_key = skey
        cache.candidates_key = ckey
        cache.depths = depths

        self._invalidate_after_depths()
        return depths

    def get_renders(self, *, force: bool) -> tuple[CandidateDepths, CandidatePointClouds]:
        """Compute the "renders" stage: depth maps + depth-hit point clouds.

        The app treats candidate point clouds as part of the rendering stage so
        the Candidate Renders page can always show the depth-hit backprojection
        without requiring a separate toggle/button.
        """

        depths = self.get_depths(force=force)
        stride = int(self.state.labeler_cfg.backprojection_stride)
        pcs = self.get_candidate_pointclouds(stride=stride, force=force)
        return depths, pcs

    def get_candidate_pointclouds(self, *, stride: int, force: bool) -> CandidatePointClouds:
        """Backproject and cache candidate point clouds for the current depth batch."""

        sample = self.get_sample(force=False)
        depths = self.get_depths(force=False)
        depth_key = depths_key(depths)
        pcs_cache = self.state.pcs
        if pcs_cache.by_stride is None or pcs_cache.depth_key != depth_key:
            pcs_cache.depth_key = depth_key
            pcs_cache.by_stride = {}

        assert pcs_cache.by_stride is not None
        if not force and stride in pcs_cache.by_stride:
            return pcs_cache.by_stride[stride]

        with self.progress("Backprojecting depth maps..."):
            pcs = build_candidate_pointclouds(sample, depths, stride=stride)

        pcs_cache.by_stride[stride] = pcs
        # Only invalidate RRI if we potentially overwrote the stride used by the oracle labeler.
        if force or stride == int(self.state.labeler_cfg.backprojection_stride):
            self._invalidate_after_pcs()
        return pcs

    def run_labeler(self, *, force: bool) -> tuple[CandidateDepths, CandidatePointClouds, RriResult]:
        """Run the full oracle label pipeline and cache the outputs.

        Uses `aria_nbv.oracle.pipelines.scene_labels.OracleRriLabeler` under the hood so the
        dashboard and training-time labeling share the exact same execution path.
        """

        sample = self.get_sample(force=False)
        cfg = self.state.labeler_cfg
        cfg_sig = config_signature(cfg)
        skey = sample_key(sample)

        cache = self.state.rri
        if (
            not force
            and cache.result is not None
            and cache.cfg_sig == cfg_sig
            and cache.pcs_key is not None
            and self.state.depth.depths is not None
        ):
            pcs_cached = None
            if self.state.pcs.by_stride is not None:
                pcs_cached = self.state.pcs.by_stride.get(int(cfg.backprojection_stride))
            if pcs_cached is not None:
                return self.state.depth.depths, pcs_cached, cache.result

        labeler = cfg.setup_target()
        with self.progress("Running oracle label pipeline..."):
            batch = labeler.run(sample)

        # Update caches from the returned batch.
        self.state.candidates.candidates = batch.candidates
        self.state.candidates.cfg_sig = config_signature(cfg.generator)
        self.state.candidates.sample_key = skey

        self.state.depth.depths = batch.depths
        self.state.depth.cfg_sig = config_signature(cfg.depth)
        self.state.depth.sample_key = skey
        self.state.depth.candidates_key = candidates_key(batch.candidates)

        dkey = depths_key(batch.depths)
        if self.state.pcs.by_stride is None or self.state.pcs.depth_key != dkey:
            self.state.pcs.depth_key = dkey
            self.state.pcs.by_stride = {}
        assert self.state.pcs.by_stride is not None
        self.state.pcs.by_stride[int(cfg.backprojection_stride)] = batch.candidate_pcs

        cache.cfg_sig = cfg_sig
        cache.pcs_key = pcs_key(batch.candidate_pcs)
        cache.result = batch.rri

        return batch.depths, batch.candidate_pcs, batch.rri

    # ------------------------------------------------------------------ invalidation
    def _invalidate_after_data(self) -> None:
        self.state.candidates = type(self.state.candidates)()
        self.state.depth = type(self.state.depth)()
        self.state.pcs = type(self.state.pcs)()
        self.state.rri = type(self.state.rri)()

    def _invalidate_after_candidates(self) -> None:
        self.state.depth = type(self.state.depth)()
        self.state.pcs = type(self.state.pcs)()
        self.state.rri = type(self.state.rri)()

    def _invalidate_after_depths(self) -> None:
        self.state.pcs = type(self.state.pcs)()
        self.state.rri = type(self.state.rri)()

    def _invalidate_after_pcs(self) -> None:
        self.state.rri = type(self.state.rri)()


__all__ = ["PipelineController"]
