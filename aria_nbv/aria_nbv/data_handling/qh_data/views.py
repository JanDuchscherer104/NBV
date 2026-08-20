r"""Factual views of finite-candidate, fixed-budget rollout chains.

These immutable DTOs separate actor-visible state from oracle supervision and
CPU-only source identity. They describe stored facts only: learner-specific
backup admission and value-target construction belong to the fitted-Q learner.
``S`` denotes realized states, ``N`` the per-state candidate width, and an
optional leading ``B`` denotes a padded batch. Remaining horizon is represented
as the stored acquisition budget at each state, not as a scorer query object.
This module owns those factual DTO definitions, not storage decoding or batch
construction.
"""

from __future__ import annotations

from dataclasses import dataclass

from torch import Tensor

from ..vin_store.views import VinSnippetView


@dataclass(frozen=True, slots=True)
class QhStaticContext:
    """Immutable root evidence shared by every realized state in one chain.

    The optional EVL fields are never substituted with numeric zeros. Their
    corresponding entries in ``evl_presence`` distinguish unavailable source
    evidence from an observed zero-valued voxel. Rich-training admission owns
    whether every field must be present.
    """

    vin_snippet: VinSnippetView
    """Root semidense actor evidence and trajectory from the immutable VIN source row."""

    t_world_voxel: Tensor | None
    """Optional ``Tensor["... 12", float32]`` world-from-voxel pose for root EVL evidence."""

    voxel_extent: Tensor | None
    """Optional ``Tensor["... 6", float32]`` metric EVL voxel-frame extent in metres."""

    occ_pr: Tensor | None
    """Optional ``Tensor["... 1 D H W", float32]`` root EVL occupancy prediction."""

    occ_input: Tensor | None
    """Optional ``Tensor["... 1 D H W", float32]`` voxelized occupied input evidence."""

    free_input: Tensor | None
    """Optional ``Tensor["... 1 D H W", float32]`` voxelized free-space input evidence."""

    counts: Tensor | None
    """Optional ``Tensor["... D H W", int64]`` root per-voxel observation counts."""

    cent_pr: Tensor | None
    """Optional ``Tensor["... 1 D H W", float32]`` root EVL centerness prediction."""

    pts_world: Tensor | None
    """Optional ``Tensor["... V 3", float32]`` world coordinates for root EVL voxel centres."""

    evl_presence: Tensor
    """``Tensor["8", bool]`` availability for pose, extent, then the six optional EVL fields in declaration order."""


@dataclass(frozen=True, slots=True)
class QhSelectedObservationPrefix:
    """Strictly causal CF-GT depth history for every realized rollout state.

    Row ``s`` contains only observations acquired by selected actions before
    state ``s``. Entries outside ``prefix_mask`` are padding, not future
    observations. The source protocol is fixed to ``"cf_gt"`` for this first
    rich carrier.
    """

    depth_m: Tensor
    """``Tensor["S S H W", float16]`` selected-depth prefix rasters in metres; unsupported rows are zero padding."""

    valid_mask: Tensor
    """``Tensor["S S H W", bool]`` valid metric-depth support aligned with ``depth_m``."""

    focal_px: Tensor
    """``Tensor["S S 2", float32]`` focal lengths for each selected prefix observation."""

    principal_point_px: Tensor
    """``Tensor["S S 2", float32]`` principal points for each selected prefix observation."""

    image_size_hw: Tensor
    """``Tensor["S S 2", int64]`` raster height and width for each selected prefix observation."""

    camera_pose_relative_root: Tensor
    """``Tensor["S S 12", float32]`` root-rig-from-selected-camera poses aligned with prefix observations."""

    prefix_mask: Tensor
    """``Tensor["S S", bool]`` strict lower-triangular causal observation support."""

    source_protocol: str = "cf_gt"
    """Declared selected-observation protocol; only ``"cf_gt"`` is admitted by this carrier."""


@dataclass(frozen=True, slots=True)
class QhAudit:
    """CPU-only chain provenance retained when explicit diagnostics are requested."""

    rollout_store_dir: str
    """Absolute validated rollout-store directory for reopening presentation-only diagnostics."""

    actor_store_version: str
    """Immutable VIN actor-store version bound to the source row."""

    source_manifest_hash: str
    """VIN source-manifest digest bound to the chain's immutable source identity."""

    selected_depth_renderer: str
    """Selected-depth renderer recorded by the validated rollout store."""


@dataclass(frozen=True, slots=True)
class QhActorTensors:
    r"""Actor-visible tensors for one chain or one padded batch.

    A chain state combines immutable root observation evidence with a finite
    candidate table, strictly causal factual-action history, and the fixed-task
    acquisition budget remaining at that state. Oracle rewards and label
    availability are deliberately absent so a scorer cannot condition on
    privileged supervision. For every row, ``action_mask`` implies
    ``candidate_mask``; batch padding makes both masks false.
    """

    vin_snippet: VinSnippetView
    """Chain-constant actor observation; points are ``Tensor["... P 3+C", float32]`` in world-frame metres."""

    root_pose_world: Tensor
    """``Tensor["... 12", float32]`` world-from-root-rig pose in ``PoseTW`` storage layout."""

    target_pose_relative_root: Tensor
    """``Tensor["... 12", float32]`` root-rig-from-target-object pose in ``PoseTW`` storage layout."""

    target_extents: Tensor
    """``Tensor["... 3", float32]`` target object-frame OBB side lengths in metres."""

    candidate_pose_relative_root: Tensor
    """``Tensor["... S N 12", float32]`` root-rig-from-candidate-rig poses in stored candidate order."""

    candidate_mask: Tensor
    """``Tensor["... S N", bool]`` materialization support; false entries are candidate-axis padding."""

    action_mask: Tensor
    """``Tensor["... S N", bool]`` actor-valid subset of ``candidate_mask`` at each realized state."""

    history_pose_relative_root: Tensor
    """``Tensor["... S S 12", float32]`` factual selected poses ordered from state ``0`` to ``s-1`` in row ``s``."""

    history_mask: Tensor
    """``Tensor["... S S", bool]`` strict lower-triangular support for causal factual-action history."""

    horizon_remaining: Tensor
    """``Tensor["... S", int64]`` fixed-task acquisition budget remaining, including the current action."""

    step_mask: Tensor
    """``Tensor["... S", bool]`` realized candidate-bearing states; false rows are time-axis padding."""

    static_context: QhStaticContext | None = None
    """Optional compositional root EVL context; absent only for explicit legacy diagnostic reads."""

    selected_observation_prefix: QhSelectedObservationPrefix | None = None
    """Optional strictly causal selected CF-GT depth prefix; required by rich-training admission."""


@dataclass(frozen=True, slots=True)
class QhSupervision:
    r"""Oracle labels and factual selected transitions kept outside the actor.

    Candidate rewards provide immediate supervision where ``label_mask`` is
    true, and label support always implies actor validity. The selected action
    is the factual rollout-policy decision, not a learner choice. Discount and
    terminal state describe the persisted TD transition; they do not guarantee
    actor-valid or label-supported successor candidates.
    """

    label_mask: Tensor
    """``Tensor["... S N", bool]`` reward-label support, constrained by ``label_mask <= action_mask``."""

    candidate_reward: Tensor
    """``Tensor["... S N", float32]`` persisted immediate rewards; values matter only where ``label_mask`` is true."""

    selected_index: Tensor
    """``Tensor["... S", int64]`` factual rollout-policy action index; padded rows use ``-1``."""

    discount: Tensor
    """``Tensor["... S", float32]`` stored TD discount, applied only when the learner admits a successor backup."""

    terminal: Tensor
    """``Tensor["... S", bool]`` persisted terminal flag; padded rows are true and cannot bootstrap."""


@dataclass(frozen=True, slots=True)
class QhChainKey:
    """CPU-only identity for one joined rollout chain and actor-store sample."""

    store_index: int
    """Zero-based ordinal of the rollout store within the configured reader sequence."""

    rollout_row_id: int
    """Persistent rollout-chain row identifier inside the selected source store."""

    source_sample_index: int
    """Exact immutable VIN actor-store row joined through rollout source identity."""

    scene_id: str
    """ASE scene identifier verified equal across rollout and actor-store records."""

    target_row_id: int
    """Persistent target-entity row identifier for this chain within the rollout record."""


@dataclass(frozen=True, slots=True)
class QhChain:
    """One complete, non-empty rollout chain before batch-axis padding.

    ``actor.step_mask`` is true for all ``S`` stored states. Candidate widths
    may already be row-padded, but ``candidate_mask`` preserves which entries
    were materially present in each stored state.
    """

    actor: QhActorTensors
    """Actor-visible state, candidates, causal history, and remaining budget for all ``S`` states."""

    supervision: QhSupervision
    """Oracle support and factual actions aligned exactly with the actor's ``S`` state rows."""

    key: QhChainKey
    """CPU-only source identity retained for audit and debugging, never scorer input."""

    audit: QhAudit | None = None
    """Optional CPU-only diagnostic provenance; batch tensor transfer never touches this payload."""

    @property
    def num_steps(self) -> int:
        """Return the number of true entries in the chain's ``step_mask``."""

        return int(self.actor.step_mask.sum().item())


__all__ = [
    "QhActorTensors",
    "QhAudit",
    "QhChain",
    "QhChainKey",
    "QhSelectedObservationPrefix",
    "QhStaticContext",
    "QhSupervision",
]
