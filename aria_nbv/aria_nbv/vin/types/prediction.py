"""Prediction containers emitted by VIN candidate scorers.

`VinPrediction` is the training-visible output contract consumed by Lightning,
metrics, diagnostics, and downstream candidate ranking code.
"""

from __future__ import annotations

from dataclasses import dataclass

from torch import Tensor


@dataclass(slots=True)
class VinPrediction:
    """VIN predictions for a candidate set.

    This is the primary output of `aria_nbv.vin.models.scene_myopic.VinModelV3`.
    It is consumed by the Lightning training loop (loss + metrics) and by
    downstream NBV selection (ranking candidates by predicted improvement).
    The expected score is a learned one-step ranking proxy; rollout-level
    endpoint metrics and cumulative target RRI are produced by rollout stores
    and oracle re-scoring, not by this container.

    The candidate axis is row-aligned with the input poses and PyTorch3D camera
    batch. ``VinModelV3`` uses row-wise maps, shared-token queries, and symmetric
    normalization without candidate-index embeddings. A joint permutation of
    aligned inputs therefore produces the same permutation of every ``N_q``
    output in deterministic evaluation; training-time dropout preserves this
    symmetry only in distribution.

    Typical usage in training (see ``aria_nbv/lightning/lit_module.py``):
        - ``logits`` / ``prob``: CORAL ordinal loss and optional auxiliary losses.
        - ``expected_normalized``: correlation/top-k metrics and candidate ranking proxy.
        - ``voxel_valid_frac`` / ``semidense_candidate_vis_frac``: optional scheduled
          coverage reweighting of the loss + diagnostics.
        - ``candidate_valid``: conservative validity heuristic used for logging and
          optional filtering in analysis/visualization.
    """

    logits: Tensor
    """``Tensor["B N_q K-1", float32]`` CORAL threshold logits."""

    prob: Tensor
    """``Tensor["B N_q K", float32]`` class probabilities from the logits."""

    expected: Tensor
    """``Tensor["B N_q", float32]`` expected class value in ``[0, K-1]``."""

    expected_normalized: Tensor
    """``Tensor["B N_q", float32]`` expected value normalized to ``[0, 1]``."""

    candidate_valid: Tensor
    """``Tensor["B N_q", bool]`` candidate validity diagnostic.

    This is a conservative heuristic meant to detect candidates that cannot be
    scored reliably (e.g. non-finite pose, empty voxel evidence, or no visible
    semidense support). It is not automatically applied as a training mask
    unless explicitly used by the training loop/config.
    """

    voxel_valid_frac: Tensor | None = None
    """``Tensor["B N_q", float32]`` candidate voxel-coverage proxy, if available.

    In v3 this is derived from sampling the normalized EVL observation counts
    (``counts_norm``) at the candidate camera center in world coordinates.
    """

    semidense_candidate_vis_frac: Tensor | None = None
    """``Tensor["B N_q", float32]`` candidate semidense-visibility proxy, if available.

    In v3 this is derived from projecting semidense world points into each
    candidate camera and computing a weighted visible fraction among finite
    projections.
    """

    @property
    def semidense_valid_frac(self) -> Tensor | None:
        """Read-only compatibility alias for ``semidense_candidate_vis_frac``."""

        return self.semidense_candidate_vis_frac


__all__ = ["VinPrediction"]
