"""End-to-end oracle RRI label generation pipeline (non-Streamlit).

This module provides a small orchestration layer that is reusable in:

- the Streamlit dashboard (visualization),
- offline dataset preprocessing, and
- training-time *online* label generation (candidates + oracle RRI).

The goal is to make data-flow explicit and to keep performance controls
local to the compute code (chunk sizes, backprojection stride, etc.).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Annotated

import torch
from pydantic import Field, field_validator

from aria_nbv.utils.console import Verbosity

from ...data_handling import EfmSnippetView
from ...pose_generation import CandidateViewGeneratorConfig
from ...pose_generation.types import CandidateSamplingResult
from ...rendering.candidate_depth_renderer import CandidateDepthRendererConfig, CandidateDepths
from ...rendering.candidate_pointclouds import CandidatePointClouds, build_candidate_pointclouds
from ...rri_metrics.rri import RriResult
from ...utils import BaseConfig, Console, TargetConfig
from .._scoring import PreparedRriScorerConfig


@dataclass(slots=True)
class OracleRriSample:
    sample: EfmSnippetView
    candidates: CandidateSamplingResult
    depths: CandidateDepths
    candidate_pcs: CandidatePointClouds
    rri: RriResult


def _target_cls():
    return OracleRriLabeler


class OracleRriLabelerConfig(TargetConfig["OracleRriLabeler"]):
    """Config-as-factory wrapper for `OracleRriLabeler`.

    This config composes the existing stage configs (generation, rendering,
    scoring) and adds a small number of pipeline-level knobs.
    """

    @property
    def target_type(self) -> type[OracleRriLabeler]:
        return _target_cls()

    device: Annotated[torch.device, Field(default="auto")]

    generator: CandidateViewGeneratorConfig = Field(
        default_factory=CandidateViewGeneratorConfig,
    )
    """Candidate generation configuration."""

    depth: CandidateDepthRendererConfig = Field(
        default_factory=CandidateDepthRendererConfig,
    )
    """Depth rendering configuration."""

    oracle: PreparedRriScorerConfig = Field(default_factory=PreparedRriScorerConfig)
    """Oracle RRI scoring configuration."""

    backprojection_stride: int = 1
    """Pixel stride used when backprojecting depth maps to point clouds."""

    verbosity: Verbosity = Verbosity.QUIET

    _resolve_device = field_validator("device", mode="before")(BaseConfig._resolve_device)


class OracleRriLabeler:
    """Compute oracle RRI labels for candidates in a single snippet."""

    def __init__(self, config: OracleRriLabelerConfig) -> None:
        self.config = config
        self.console = Console.with_prefix(self.__class__.__name__)

        self._generator = self.config.generator.setup_target()
        self._depth_renderer = self.config.depth.setup_target()
        self._oracle = self.config.oracle.setup_target()

    def run(self, sample: EfmSnippetView) -> OracleRriSample:
        """Run the full candidate→render→RRI pipeline for one snippet.

        Args:
            sample: Input snippet including semi-dense points and GT mesh tensors.

        Returns:
            A batch containing candidates, renders, backprojected point clouds,
            and oracle RRI values.
        """
        if sample.mesh_verts is None or sample.mesh_faces is None:
            raise ValueError(
                "OracleRriLabeler requires mesh_verts/mesh_faces on the sample (enable load_meshes).",
            )

        self.console.log(
            f"Running label pipeline for scene={sample.scene_id} snippet={sample.snippet_id}",
        )

        candidates = self._generator.generate_from_typed_sample(sample)
        num_candidates = int(candidates.views.tensor().shape[0])
        if num_candidates == 0:
            msg = (
                "Candidate generation produced 0 candidates. This usually means the sampling/pruning rules are too "
                "strict for the current snippet. Try reducing `CandidateViewGeneratorConfig.min_distance_to_mesh`, "
                "disabling collision/free-space checks, or increasing `num_samples`/`oversample_factor`."
            )
            self.console.error(msg)
            raise ValueError(msg)

        self.console.log(f"Generated {num_candidates} valid candidates.")

        depths = self._depth_renderer.render(sample=sample, candidates=candidates)
        self.console.log(
            f"Rendered depths for {int(depths.depths.shape[0])} candidates.",
        )

        candidate_pcs = build_candidate_pointclouds(
            sample,
            depths,
            stride=int(self.config.backprojection_stride),
        )
        device = candidate_pcs.points.device
        dtype = candidate_pcs.points.dtype

        self.console.log(
            "Backprojected candidate PCs: "
            f"C={int(candidate_pcs.points.shape[0])} #Pcand={int(candidate_pcs.points.shape[1])} "
            f"| #Psemi={int(candidate_pcs.semidense_points.shape[0])}",
        )

        rri = self._oracle.score(
            points_t=candidate_pcs.semidense_points.to(device=device, dtype=dtype),
            points_q=candidate_pcs.points,
            lengths_q=candidate_pcs.lengths,
            gt_verts=sample.mesh_verts.to(device=device, dtype=dtype),
            gt_faces=sample.mesh_faces.to(device=device),
            extend=candidate_pcs.occupancy_bounds.to(device=device, dtype=dtype),
        )

        return OracleRriSample(
            sample=sample,
            candidates=candidates,
            depths=depths,
            candidate_pcs=candidate_pcs,
            rri=rri,
        )


__all__ = [
    "OracleRriSample",
    "OracleRriLabeler",
    "OracleRriLabelerConfig",
]
