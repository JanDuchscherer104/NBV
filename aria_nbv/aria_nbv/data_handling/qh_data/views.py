r"""Factual views of finite-candidate, fixed-budget rollout chains.

These immutable DTOs separate actor-visible state from oracle supervision and
CPU-only source identity. They describe stored facts only: learner-specific
backup admission and value-target construction belong to the fitted-Q learner.
The shapes below use this shared legend. A :class:`QhChain` has no batch axis:
``S`` is its realized number of decision states, ``N`` its stored candidate
width, ``P`` its semidense-point capacity, and ``F`` its root trajectory
length. :class:`~aria_nbv.data_handling.qh_data.batching.QhBatch` adds a
leading ``B`` axis and owns all padded-batch shape documentation.
``D_v H_v W_v`` are EVL voxel-grid axes;
``V=D_v*H_v*W_v`` is the flattened voxel-centre axis; ``H_d W_d`` are selected
depth-raster axes; and ``C_p`` is the number of extra semidense point channels
after XYZ. ``12`` is the stored ``PoseTW`` representation and ``6`` is the
voxel-frame extent ``[x_min, x_max, y_min, y_max, z_min, z_max]``.

Every tensor field below documents only its canonical, non-batched chain
shape. Remaining horizon is represented as the stored acquisition budget at
each state, not as a scorer query object.
This module owns those factual DTO definitions, not storage decoding or batch
construction.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Literal

from torch import Tensor

from ..vin_store.views import VinSnippetView

if TYPE_CHECKING:
    from efm3d.aria.pose import PoseTW

QhRootEvlProfile = Literal["none", "evl_v1"]
QhSelectedObservationProtocol = Literal["none", "cf_gt"]


@dataclass(frozen=True, slots=True)
class QhActorStateContract:
    """Metadata-only compatibility contract for scorer-visible root evidence."""

    root_evl_profile: QhRootEvlProfile
    """Closed root-EVL carrier profile; ``none`` omits EVL and ``evl_v1`` requires all eight fields."""

    selected_observation_protocol: QhSelectedObservationProtocol
    """Causal selected-observation source admitted to actor state; disabled by default."""

    actor_manifest_hash: str
    """Exact immutable VIN manifest digest used by every configured stage."""

    evl_block_signature: tuple[tuple[str, str, tuple[int, ...]], ...]
    """Sorted ``(block, dtype, canonical row shape)`` facts for root EVL tensors."""


@dataclass(frozen=True, slots=True)
class QhStaticContext:
    """Immutable root evidence shared by every realized state in one chain.

    The optional EVL fields are never substituted with numeric zeros. Their
    corresponding entries in ``evl_presence`` distinguish unavailable source
    evidence from an observed zero-valued voxel. Rich-training admission owns
    whether every field must be present.
    """

    vin_snippet: VinSnippetView
    """``VinSnippetView`` with ``points_world`` ``Tensor["P 3+C_p", float32]``, ``lengths`` ``Tensor["1", int64]``, and trajectory ``PoseTW["F 12"]``."""

    t_world_voxel: PoseTW | None
    """``PoseTW["12"]``: world-from-voxel pose for root EVL evidence; translation is metres."""

    voxel_extent: Tensor | None
    """``Tensor["6", float32]``: metric voxel-frame extent in metres."""

    occ_pr: Tensor | None
    """``Tensor["1 D_v H_v W_v", float32]``: root EVL occupancy prediction."""

    occ_input: Tensor | None
    """``Tensor["1 D_v H_v W_v", float32]``: voxelized occupied input evidence."""

    free_input: Tensor | None
    """``Tensor["1 D_v H_v W_v", float32]``: voxelized free-space input evidence."""

    counts: Tensor | None
    """``Tensor["D_v H_v W_v", int64]``: per-voxel observation counts."""

    cent_pr: Tensor | None
    """``Tensor["1 D_v H_v W_v", float32]``: root EVL centerness prediction."""

    pts_world: Tensor | None
    """``Tensor["V 3", float32]``: world voxel centres, where ``V=D_v*H_v*W_v``."""

    evl_presence: Tensor
    """``Tensor["8", bool]``: availability for pose, extent, then six optional EVL fields."""


@dataclass(frozen=True, slots=True)
class QhSelectedObservationPrefix:
    """Strictly causal CF-GT depth history for every realized rollout state.

    Row ``s`` contains only observations acquired by selected actions before
    state ``s``. Entries outside ``prefix_mask`` are padding, not future
    observations. The source protocol is fixed to ``"cf_gt"`` for this first
    rich carrier.
    """

    depth_m: Tensor
    """``Tensor["S S H_d W_d", float16]``: selected-depth rasters in metres. Axes are query state ``s`` then selected observation ``j``; only ``j<s`` is supported."""

    valid_mask: Tensor
    """``Tensor["S S H_d W_d", bool]``: valid metric-depth support aligned with ``depth_m``."""

    focal_px: Tensor
    """``Tensor["S S 2", float32]``: focal lengths ``[f_x,f_y]`` indexed by query state ``s`` and observation ``j``."""

    principal_point_px: Tensor
    """``Tensor["S S 2", float32]``: principal points ``[c_x,c_y]``."""

    image_size_hw: Tensor
    """``Tensor["S S 2", int64]``: raster size ``[H_d,W_d]``."""

    camera_pose_relative_root: PoseTW
    """``PoseTW["S S 12"]``: root-rig-from-selected-camera poses; entry ``[s,j]`` belongs to selected action ``j``."""

    prefix_mask: Tensor
    """``Tensor["S S", bool]``: causal selected-observation support, true exactly for realized ``j<s`` pairs."""

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

    selected_depth_renderer: str | None
    """Selected-depth renderer recorded by the store, or ``None`` when disabled."""


@dataclass(frozen=True, slots=True)
class QhActorTensors:
    r"""Actor-visible tensors for one complete, non-batched chain.

    A chain state combines immutable root observation evidence with a finite
    candidate table, strictly causal factual-action history, and the fixed-task
    acquisition budget remaining at that state. Oracle rewards and label
    availability are deliberately absent so a scorer cannot condition on
    privileged supervision. For every row, ``action_mask`` implies
    ``candidate_mask``. :class:`~aria_nbv.data_handling.qh_data.batching.QhBatch`
    owns padding and its leading batch axis.
    """

    vin_snippet: VinSnippetView
    """``VinSnippetView`` with ``points_world`` ``Tensor["P 3+C_p", float32]``; see :attr:`QhStaticContext.vin_snippet` for complete root fields."""

    root_pose_world: PoseTW
    """``PoseTW["12"]``: world-from-root-rig pose; translation is metres."""

    target_pose_relative_root: PoseTW
    """``PoseTW["12"]``: root-rig-from-target-object pose; translation is metres."""

    target_extents: Tensor
    """``Tensor["3", float32]``: target object-frame OBB side lengths ``[x,y,z]`` in metres."""

    candidate_pose_relative_root: PoseTW
    """``PoseTW["S N 12"]``: root-rig-from-candidate-rig poses in stored order. ``N`` is per-state width, never a planning-tree branch axis."""

    candidate_mask: Tensor
    """``Tensor["S N", bool]``: materialization support; false means stored-row padding."""

    action_mask: Tensor
    """``Tensor["S N", bool]``: actor-valid candidate support, a subset of ``candidate_mask``."""

    history_pose_relative_root: PoseTW
    """``PoseTW["S S 12"]``: factual selected-pose prefix. At query state ``s``, history index ``j`` stores selected pose ``j`` only when ``j<s``."""

    history_mask: Tensor
    """``Tensor["S S", bool]``: factual-pose-prefix support, true exactly for realized ``j<s`` pairs."""

    horizon_remaining: Tensor
    """``Tensor["S", int64]``: acquisition budget remaining, including the current factual action."""

    step_mask: Tensor
    """``Tensor["S", bool]``: realized candidate-bearing states; this complete chain has all entries true."""

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
    """``Tensor["S N", bool]``: reward-label support, a subset of ``action_mask``."""

    candidate_reward: Tensor
    """``Tensor["S N", float32]``: persisted immediate rewards; values matter only where ``label_mask`` is true."""

    selected_index: Tensor
    """``Tensor["S", int64]``: factual rollout-policy candidate index."""

    discount: Tensor
    """``Tensor["S", float32]``: stored TD discount, applied only when the learner admits a successor backup."""

    terminal: Tensor
    """``Tensor["S", bool]``: persisted terminal flag."""


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
