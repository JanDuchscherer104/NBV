r"""Factual views of finite-candidate, fixed-budget rollout chains.

These immutable DTOs separate actor-visible state from oracle supervision and
CPU-only source identity. They describe stored facts only: learner-specific
backup admission and value-target construction belong to the fitted-Q learner.
The shapes below use this shared legend. A :class:`QhChain` has no batch axis:
``S`` is its realized number of decision states, ``N`` its stored candidate
width, ``P`` its semidense-point capacity, and ``F`` its root trajectory
length. :class:`~aria_nbv.data_handling.qh_data.batching.QhBatch` adds a
leading ``B`` axis and pads variable axes to ``S_max``, ``N_max``, ``P_max``,
and ``F_max``. ``D_v H_v W_v`` are EVL voxel-grid axes;
``V=D_v*H_v*W_v`` is the flattened voxel-centre axis; ``H_d W_d`` are selected
depth-raster axes; and ``C_p`` is the number of extra semidense point channels
after XYZ. ``12`` is the stored ``PoseTW`` representation and ``6`` is the
voxel-frame extent ``[x_min, x_max, y_min, y_max, z_min, z_max]``.

Every tensor field therefore documents its unbatched chain form and its padded
batch form explicitly. Remaining horizon is represented as the stored
acquisition budget at each state, not as a scorer query object.
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
    """Root evidence: chain points [P, 3+C_p], lengths [1], trajectory [F,12]; batch [B,P_max,3+C_p], [B,1], [B,F_max,12]."""

    t_world_voxel: Tensor | None
    """Optional world-from-voxel pose: chain Tensor[12, float32]; batch Tensor[B 12, float32]."""

    voxel_extent: Tensor | None
    """Optional metric voxel-frame extent: chain Tensor[6, float32]; batch Tensor[B 6, float32]."""

    occ_pr: Tensor | None
    """Optional occupancy prediction: chain Tensor[1, D_v, H_v, W_v]; batch Tensor[B, 1, D_v_max, H_v_max, W_v_max]."""

    occ_input: Tensor | None
    """Optional occupied input: chain Tensor[1, D_v, H_v, W_v]; batch Tensor[B, 1, D_v_max, H_v_max, W_v_max]."""

    free_input: Tensor | None
    """Optional free-space input: chain Tensor[1, D_v, H_v, W_v]; batch Tensor[B, 1, D_v_max, H_v_max, W_v_max]."""

    counts: Tensor | None
    """Optional observation counts: chain Tensor[D_v, H_v, W_v]; batch Tensor[B, D_v_max, H_v_max, W_v_max]."""

    cent_pr: Tensor | None
    """Optional centerness: chain Tensor[1, D_v, H_v, W_v]; batch Tensor[B, 1, D_v_max, H_v_max, W_v_max]."""

    pts_world: Tensor | None
    """Optional world voxel centres: chain Tensor[V, 3] with V=D_v*H_v*W_v; batch Tensor[B, V_max, 3]."""

    evl_presence: Tensor
    """Availability: chain Tensor[8]; batch Tensor[B, 8] for pose, extent, then six optional EVL fields."""


@dataclass(frozen=True, slots=True)
class QhSelectedObservationPrefix:
    """Strictly causal CF-GT depth history for every realized rollout state.

    Row ``s`` contains only observations acquired by selected actions before
    state ``s``. Entries outside ``prefix_mask`` are padding, not future
    observations. The source protocol is fixed to ``"cf_gt"`` for this first
    rich carrier.
    """

    depth_m: Tensor
    """Selected-depth metres: chain Tensor[S, S, H_d, W_d]; batch Tensor[B, S_max, S_max, H_d_max, W_d_max]. Axes are query state s then selected observation j; only j<s is supported."""

    valid_mask: Tensor
    """Metric-depth support aligned with depth_m: chain Tensor[S, S, H_d, W_d]; batch Tensor[B, S_max, S_max, H_d_max, W_d_max]."""

    focal_px: Tensor
    """Focal lengths [f_x,f_y]: chain Tensor[S, S, 2]; batch Tensor[B, S_max, S_max, 2], indexed by query state s and observation j."""

    principal_point_px: Tensor
    """Principal points [c_x,c_y]: chain Tensor[S, S, 2]; batch Tensor[B, S_max, S_max, 2]."""

    image_size_hw: Tensor
    """Raster size [H_d,W_d]: chain Tensor[S, S, 2]; batch Tensor[B, S_max, S_max, 2]."""

    camera_pose_relative_root: Tensor
    """Root-rig-from-selected-camera poses: chain Tensor[S, S, 12]; batch Tensor[B, S_max, S_max, 12]. Entry [s,j] belongs to selected action j."""

    prefix_mask: Tensor
    """Causal selected-observation support: chain Tensor[S, S]; batch Tensor[B, S_max, S_max]; true exactly for realized j<s pairs."""

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
    """Chain-constant VIN root observation: chain points [P,3+C_p], lengths [1], trajectory [F,12]; batch forms are documented on QhStaticContext.vin_snippet."""

    root_pose_world: Tensor
    """World-from-root-rig pose: chain Tensor[12]; batch Tensor[B,12]."""

    target_pose_relative_root: Tensor
    """Root-rig-from-target-object pose: chain Tensor[12]; batch Tensor[B,12]."""

    target_extents: Tensor
    """Target OBB side lengths [x,y,z] in metres: chain Tensor[3]; batch Tensor[B,3]."""

    candidate_pose_relative_root: Tensor
    """Stored candidate poses: chain Tensor[S,N,12]; batch Tensor[B,S_max,N_max,12]. N is per-state candidate width, never a planning-tree branch axis."""

    candidate_mask: Tensor
    """Materialization support: chain Tensor[S,N]; batch Tensor[B,S_max,N_max]. False means stored-row or batch padding."""

    action_mask: Tensor
    """Actor-valid candidate support: chain Tensor[S,N]; batch Tensor[B,S_max,N_max]. It is a subset of candidate_mask."""

    history_pose_relative_root: Tensor
    """Factual selected-pose prefix: chain Tensor[S,S,12]; batch Tensor[B,S_max,S_max,12]. At query state s, history index j stores selected pose j only when j<s."""

    history_mask: Tensor
    """Factual pose-prefix support: chain Tensor[S,S]; batch Tensor[B,S_max,S_max]; true exactly for realized j<s pairs."""

    horizon_remaining: Tensor
    """Remaining acquisition budget: chain Tensor[S]; batch Tensor[B,S_max]. Each value includes the current factual action."""

    step_mask: Tensor
    """Realized-state support: chain Tensor[S] (all true); batch Tensor[B,S_max] (false only for time padding)."""

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
    """Reward-label support: chain Tensor[S,N]; batch Tensor[B,S_max,N_max]. It is a subset of action_mask."""

    candidate_reward: Tensor
    """Persisted immediate rewards: chain Tensor[S,N]; batch Tensor[B,S_max,N_max]. Values matter only where label_mask is true."""

    selected_index: Tensor
    """Factual selected candidate index: chain Tensor[S]; batch Tensor[B,S_max]. Batch-padding rows use -1."""

    discount: Tensor
    """Stored TD discount: chain Tensor[S]; batch Tensor[B,S_max]. It applies only when the learner admits a successor backup."""

    terminal: Tensor
    """Persisted terminal flag: chain Tensor[S]; batch Tensor[B,S_max]. Batch-padding rows are true and cannot bootstrap."""


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
