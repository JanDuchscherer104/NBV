r"""Scene-carrier modules for the finite-horizon :math:`Q_H` scorer.

A scene carrier maps actor-visible geometric evidence to one fixed-width state
feature per realized decision state.  It is deliberately narrower than the
complete scorer: it does not read candidates, targets, rewards, requested
horizon, remaining budget, labels, or authoritative action validity.  This
boundary keeps three scientific questions separable:

* which observations constitute the causal scene state;
* how that state is compressed into a shared state feature; and
* how a candidate later queries the resulting memory.

``QhRootMomentsSceneEncoder`` is the parameter-free ``root_moments_v1``
control.  Every configured root EVL channel contributes global mean, standard
deviation, minimum, and maximum.  Root semidense points contribute
coordinate-wise mean and standard deviation in the rollout-root frame plus
explicit presence and finite-support fraction.  The fraction is normalized by
each chain's persisted point length, never by a collated batch width, so an
actor state is invariant to batch composition and DDP partitioning.  A later
dynamic carrier must introduce its state axis explicitly rather than hiding a
semantic change in this control.

``QhSelectedSurfacePointSceneEncoder`` is the first ``S1-points`` carrier.  It
uses the canonical rendering backprojection for strictly causal selected
CF-GT depth, expresses the resulting surface points from the factual current
camera, and applies a bounded Deep-Sets-style shared point map followed by
masked mean and maximum pooling.  Its learned residual has exactly the root
carrier width and its final projection is initialized to zero.  S1 therefore
starts as the exact H0 function under a matched seed rather than perturbing the
control merely because another carrier exists.  The projection itself can
learn on the first backward pass; gradients reach the upstream point map only
after that projection opens.  Adding S1 leaves the scorer's physical and scene
projection widths unchanged, so every common downstream H0/S1 weight remains
identical and only the named scene carrier adds parameters.

Global moments are intentionally lossy.  They discard topology, occlusion,
view direction, free-versus-unknown geometry, and selected-observation
updates.  The module is therefore a checkpoint-compatible control, not a
claim that root evidence is a sufficient Markov state.  Candidate-local point
or ray queries belong to a later relation module rather than being hidden in
this shared-carrier interface.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Annotated, Literal, TypeAlias

import torch
from efm3d.aria.camera import CameraTW
from efm3d.aria.pose import PoseTW
from pydantic import Field
from torch import Tensor, nn

from ...data_handling.qh_contracts import validate_selected_observation_prefix
from ...rendering.unproject import backproject_depths_camera_tw_batch
from ...utils import TargetConfig

if TYPE_CHECKING:
    from ...data_handling.qh_data import QhActorTensors

QhSceneChannel: TypeAlias = Literal["occ_pr", "occ_input", "free_input", "counts", "cent_pr"]
"""Persisted root-EVL channels admitted by ``root_moments_v1``."""


class QhRootMomentsSceneEncoderConfig(TargetConfig["QhRootMomentsSceneEncoder"]):
    """Configure the explicit parameter-free S0 root-moments control."""

    kind: Literal["root_moments_v1"] = "root_moments_v1"
    """Versioned scene-carrier discriminator persisted with the scorer."""

    @property
    def target_type(self) -> type["QhRootMomentsSceneEncoder"]:
        """Return the runtime root-moments encoder class."""

        return QhRootMomentsSceneEncoder


class QhSelectedSurfacePointSceneEncoderConfig(TargetConfig["QhSelectedSurfacePointSceneEncoder"]):
    r"""Configure the privileged S1 selected-surface point memory.

    The raster stride and view-chunk bound are representation identity.  They
    determine which stored pixels become set elements and the largest number
    of selected views backprojected at once.  ``coordinate_scale_m`` only
    nondimensionalizes current-camera XYZ before the shared point MLP; it is
    neither a clipping radius nor an asserted scene extent.  The residual's
    zero-output initialization is part of this versioned architecture: a fresh
    S1 model is exactly its source-matched H0 control, without adding a config
    switch or a second initialization profile.
    """

    kind: Literal["root_moments_plus_selected_surface_points_identity_start_v1"] = (
        "root_moments_plus_selected_surface_points_identity_start_v1"
    )
    """Active identity-start S1 carrier and ``representation_semantics`` value."""

    pixel_stride: int = Field(default=8, gt=0)
    """Deterministic row/column stride applied before canonical depth backprojection."""

    view_chunk_size: int = Field(default=16, gt=0)
    """Maximum flattened selected-view rows backprojected in one call."""

    point_hidden_dim: int = Field(default=64, gt=0)
    """Shared point-feature width before invariant mean/maximum pooling."""

    coordinate_scale_m: float = Field(default=2.0, gt=0.0)
    """Metric divisor for current-camera XYZ supplied to the point MLP."""

    @property
    def target_type(self) -> type["QhSelectedSurfacePointSceneEncoder"]:
        """Return the runtime selected-surface encoder class."""

        return QhSelectedSurfacePointSceneEncoder


class QhLegacySelectedSurfacePointSceneEncoderConfig(TargetConfig["QhSelectedSurfacePointSceneEncoder"]):
    r"""Read the historical S1 discriminator without granting reuse authority.

    The old ``...selected_surface_points_v1`` label did not say whether the
    residual projection was random- or identity-initialized. It can therefore
    reconstruct an archived state dictionary for inspection, but cannot define
    a new fit, warm start, inference runtime, or scientific bundle. New work
    uses :class:`QhSelectedSurfacePointSceneEncoderConfig`, whose discriminator
    makes the zero-residual initialization part of architecture identity.
    """

    kind: Literal["root_moments_plus_selected_surface_points_v1"] = "root_moments_plus_selected_surface_points_v1"
    """Ambiguous historical discriminator classified as ``unknown_legacy_v1``."""

    pixel_stride: int = Field(default=8, gt=0)
    """Historical deterministic raster stride."""

    view_chunk_size: int = Field(default=16, gt=0)
    """Historical selected-view chunk bound."""

    point_hidden_dim: int = Field(default=64, gt=0)
    """Historical shared point-feature width."""

    coordinate_scale_m: float = Field(default=2.0, gt=0.0)
    """Historical current-camera coordinate divisor."""

    @property
    def target_type(self) -> type["QhSelectedSurfacePointSceneEncoder"]:
        """Return the runtime class solely for historical inspection."""

        return QhSelectedSurfacePointSceneEncoder


QhSceneEncoderConfig: TypeAlias = Annotated[
    QhRootMomentsSceneEncoderConfig
    | QhSelectedSurfacePointSceneEncoderConfig
    | QhLegacySelectedSurfacePointSceneEncoderConfig,
    Field(discriminator="kind"),
]
"""Versioned S0/S1 scene-carrier configurations persisted with the scorer."""


class QhRootMomentsSceneEncoder(nn.Module):
    r"""Encode immutable root evidence as global moments.

    For every configured scalar EVL field :math:`x_c`, the encoder records
    :math:`(\mu_c,\sigma_c,\min x_c,\max x_c)`.  Let
    :math:`T_{r\leftarrow w}` be root-from-world and :math:`p_k^w` a supported
    semidense point.  Root-frame points
    :math:`p_k^r=T_{r\leftarrow w}p_k^w` contribute coordinate-wise mean and
    population standard deviation.  Two final scalars distinguish no points
    from measured all-zero geometry: presence is
    :math:`1[|P|>0]`, while support is the finite supported-count divided by
    that chain's persisted point length.  The latter is the pre-collation row
    capacity carried by :attr:`VinSnippet.lengths`; batch padding is only a
    storage detail and cannot change a physical state feature.  Empty chains
    use support zero rather than dividing by zero.

    The resulting width is ``4 * len(scene_channels) + 8``.  Source tensors
    are detached because this carrier consumes persisted actor observations;
    it is not an end-to-end EFM3D training path.  Jointly translating the world
    points and root pose leaves the point moments invariant.  The evidence is
    immutable within one stored chain; scorer orchestration owns repetition
    over states and downstream candidate and step masks.
    """

    def __init__(
        self,
        config: QhRootMomentsSceneEncoderConfig | None = None,
        *,
        scene_channels: tuple[QhSceneChannel, ...],
        dropout: float = 0.0,
    ) -> None:
        """Construct the parameter-free root-moments control.

        Args:
            scene_channels: Non-empty, unique, ordered root-EVL fields.  Order
                is representation identity because it fixes feature layout.

        Raises:
            ValueError: If the channel list is empty or contains duplicates.
        """

        super().__init__()
        del config, dropout
        if not scene_channels:
            raise ValueError("Q_H root-moments scene_channels must contain at least one field.")
        if len(set(scene_channels)) != len(scene_channels):
            raise ValueError("Q_H root-moments scene_channels must be unique and ordered.")
        self.scene_channels = scene_channels
        self.output_dim = 4 * len(scene_channels) + 8

    def forward(self, actor: QhActorTensors) -> Tensor:
        """Return ``Tensor[\"B F\", float32]`` root-scene features.

        ``B`` is taken from ``actor.step_mask`` and ``F == output_dim``.
        Missing configured EVL fields, non-finite source
        values, malformed point capacity, and non-finite active root poses fail
        closed instead of being encoded as ordinary zeros.
        """

        context = actor.static_context
        if context is None:
            raise ValueError("Q_H root-moments scene encoder requires compact root EVL context.")
        pooled = [self._pool_channel(getattr(context, name)) for name in self.scene_channels]

        points = actor.vin_snippet.points_world.detach().float()[..., :3]
        if points.ndim != 3:
            raise ValueError(f"Q_H batched semidense points must have shape (B,P,C), got {tuple(points.shape)}.")
        lengths = actor.vin_snippet.lengths.reshape(points.shape[0], -1)[:, 0].long()
        if bool((lengths < 0).any() or (lengths > points.shape[1]).any()):
            raise ValueError(f"Q_H semidense lengths must be in [0,{points.shape[1]}].")
        point_mask = torch.arange(points.shape[1], device=points.device).unsqueeze(0) < lengths.unsqueeze(1)
        point_mask &= torch.isfinite(points).all(dim=-1)

        root_active = actor.step_mask.any(dim=-1)
        root_values = actor.root_pose_world.tensor()
        root_finite = torch.isfinite(root_values).all(dim=-1)
        if bool((root_active & ~root_finite).any()):
            raise ValueError("Q_H active root poses must be finite.")
        identity = PoseTW().tensor().to(device=root_values.device, dtype=root_values.dtype).expand_as(root_values)
        root_from_world = PoseTW(torch.where(root_active.unsqueeze(-1), root_values, identity)).inverse()
        points_root = root_from_world.transform(points)

        safe_points = torch.where(point_mask.unsqueeze(-1), points_root, torch.zeros_like(points_root))
        valid_count = point_mask.sum(dim=1, keepdim=True)
        count = valid_count.clamp_min(1)
        mean = safe_points.sum(dim=1) / count
        centered = torch.where(
            point_mask.unsqueeze(-1),
            points_root - mean.unsqueeze(1),
            torch.zeros_like(points_root),
        )
        std = (centered.square().sum(dim=1) / count).sqrt()
        support_capacity = lengths.unsqueeze(-1).clamp_min(1)
        support = (valid_count.float() / support_capacity).clamp(0.0, 1.0)
        present = valid_count.gt(0).float()
        return torch.cat((*pooled, mean, std, present, support), dim=-1)

    @staticmethod
    def _pool_channel(value: Tensor | None) -> Tensor:
        """Return mean, population deviation, minimum, and maximum per row."""

        if value is None:
            raise ValueError("Q_H root-moments scene encoder requires every configured root EVL field.")
        detached = value.detach().float()
        if detached.ndim < 2:
            raise ValueError(f"Q_H root EVL fields require a batch axis, got {tuple(detached.shape)}.")
        flat = detached.reshape(detached.shape[0], -1)
        if not bool(torch.isfinite(flat).all()):
            raise ValueError("Q_H root EVL fields must be finite.")
        return torch.stack(
            (
                flat.mean(dim=-1),
                flat.std(dim=-1, unbiased=False),
                flat.amin(dim=-1),
                flat.amax(dim=-1),
            ),
            dim=-1,
        )


class QhSelectedSurfacePointSceneEncoder(nn.Module):
    r"""Add a bounded causal selected-surface residual to root moments.

    For state :math:`s_t`, the carrier admits only selected observations
    :math:`j<t`.  The persisted camera and pose define
    :math:`T_{r\leftarrow c_j}`; canonical backprojection therefore returns
    root-frame points.  The scorer supplies factual
    :math:`T_{r\leftarrow c_t}`, and the encoder forms
    :math:`p^{c_t}=T_{c_t\leftarrow r}p^r`.  Dividing XYZ by the configured
    metric scale yields each set element; no target, candidate, budget,
    horizon, reward, label, or authoritative action mask enters this path.

    A shared MLP maps every valid sampled point independently.  Masked mean
    and elementwise maximum are invariant to point order.  They are not
    generally invariant to partial duplication: overlapping observations
    receive one vote per valid sampled pixel, so S1 is explicitly a
    density-weighted surface-set control.  Three diagnostics remain learned
    inputs: presence, valid sampled pixels divided by causal sampled-pixel
    capacity, and observations with any valid point divided by causal
    observation count.  Empty prefixes produce an exact zero residual.

    Geometry validation, backprojection, frame transforms, and point-set
    reductions remain float32 under mixed-precision training.  Autocast is
    retained for the learned point encoder and final residual projection, so
    reduced-precision execution cannot change geometric support or make the
    float32 sum/max accumulators dtype-incompatible.

    The output is ``Tensor["B S F_root", float32]``.  It adds a learned point
    update to the unchanged static root moments and zeros padded states.  Let
    :math:`g_t^{\mathrm{S1}}` denote the pooled point statistic and
    :math:`W_{\mathrm{pt}}` the bias-free final projection.  Initializing
    :math:`W_{\mathrm{pt}}^{(0)}=0` makes
    :math:`\Phi_t^{\mathrm{S1},(0)}=\Phi_t^{\mathrm{root}}` exactly.  This is
    an experimental-control property, not a claim that the surface branch is
    initially useless: for downstream loss :math:`L`,
    :math:`\partial L/\partial W_{\mathrm{pt}}` can be nonzero immediately
    because :math:`g_t^{\mathrm{S1}}` is already nonzero.  The upstream point
    MLP receives zero gradient on that first step through the zero projection
    and begins learning once the projection departs from zero.

    The fixed width and identity start prevent S1 from changing downstream
    scorer shapes or initial predictions.  This carrier still cannot
    distinguish observed free space from unknown space or retain ray direction
    after fusion; those are S2 responsibilities.
    """

    def __init__(
        self,
        config: QhSelectedSurfacePointSceneEncoderConfig | QhLegacySelectedSurfacePointSceneEncoderConfig,
        *,
        scene_channels: tuple[QhSceneChannel, ...],
        dropout: float,
    ) -> None:
        """Construct the root control and an identity-start point residual.

        Only the residual's final bias-free projection is zeroed.  The shared
        point map keeps its ordinary random initialization so its pooled
        statistic can drive a first-step gradient into that projection.  This
        preserves exact H0 predictions at construction while allowing the S1
        branch to open under ordinary gradient descent without a special
        training phase, gate parameter, checkpoint field, or optimizer rule.

        Args:
            config: Persisted sampling, chunking, metric-scale, and width
                identity for the S1 carrier.
            scene_channels: Ordered root-EVL fields whose width fixes both H0
                and S1 scorer inputs.
            dropout: Training-only point-feature dropout inherited from the
                top-level scorer configuration.
        """

        super().__init__()
        if not 0.0 <= float(dropout) < 1.0:
            raise ValueError("Q_H S1 scene-encoder dropout must lie in [0, 1).")
        self.config = config
        self.root_encoder = QhRootMomentsSceneEncoder(scene_channels=scene_channels)
        self.output_dim = self.root_encoder.output_dim
        point_hidden_dim = int(config.point_hidden_dim)
        self.point_encoder = nn.Sequential(
            nn.Linear(3, point_hidden_dim),
            nn.GELU(),
            nn.LayerNorm(point_hidden_dim),
            nn.Linear(point_hidden_dim, point_hidden_dim),
            nn.GELU(),
            nn.Dropout(float(dropout)),
        )
        self.point_update = nn.Linear(2 * point_hidden_dim + 3, self.output_dim, bias=False)
        nn.init.zeros_(self.point_update.weight)

    def forward(self, actor: QhActorTensors, *, current_pose_relative_root: PoseTW) -> Tensor:
        """Return fixed-width state features for every realized decision state.

        Args:
            actor: Batched CF+ actor whose selected-observation prefix has
                exact ``[B,S,S,H,W]`` causal support.
            current_pose_relative_root: ``PoseTW["B S 12"]`` storing
                root-from-current-camera poses derived once by the scorer.

        Returns:
            ``Tensor["B S F_root", float32]`` equal to repeated root moments
            plus the selected-surface residual on realized states, and zero on
            padded states.
        """

        prefix = actor.selected_observation_prefix
        if prefix is None:
            raise ValueError("Q_H S1 scene encoder requires the causal selected-observation prefix.")
        validate_selected_observation_prefix(
            prefix,
            history_mask=actor.history_mask,
            step_mask=actor.step_mask,
        )
        self._validate_selected_geometry(actor)
        if current_pose_relative_root.tensor().shape[:-1] != actor.step_mask.shape:
            raise ValueError("Q_H S1 current pose must share the actor B,S axes.")
        current_values = current_pose_relative_root.tensor()
        current_finite = torch.isfinite(current_values).all(dim=-1)
        if bool((actor.step_mask & ~current_finite).any()):
            raise ValueError("Q_H S1 realized current-camera poses must be finite.")

        root = self.root_encoder(actor).unsqueeze(1).expand(-1, actor.step_mask.shape[1], -1)
        update = self._selected_surface_update(
            actor,
            current_pose_relative_root=current_pose_relative_root,
        )
        encoded = root + update
        return torch.where(actor.step_mask.unsqueeze(-1), encoded, torch.zeros_like(encoded)).float()

    @staticmethod
    def _validate_selected_geometry(actor: QhActorTensors) -> None:
        """Reject malformed active metric depth, pinholes, and rigid poses.

        The dependency-light carrier validator intentionally checks structure
        only so H0 can prove value independence.  S1 interprets numeric
        geometry and therefore strengthens the boundary before PyTorch3D:
        valid pixels carry finite positive metres, active camera rows are
        finite positive-focal pinholes matching the raster, camera-to-rig is
        identity, and root-from-camera transforms are proper rigid poses.
        """

        prefix = actor.selected_observation_prefix
        assert prefix is not None
        active_views = prefix.prefix_mask
        active_pixels = active_views[..., None, None] & prefix.valid_mask
        active_depth = prefix.depth_m[active_pixels].float()
        if not bool(torch.isfinite(active_depth).all() and active_depth.gt(0).all()):
            raise ValueError("Q_H S1 valid selected depth must contain finite positive metres.")

        camera_values = prefix.camera.tensor()[active_views]
        if not bool(torch.isfinite(camera_values).all()):
            raise ValueError("Q_H S1 active selected cameras must be finite.")
        focal = prefix.camera.f[active_views]
        principal = prefix.camera.c[active_views]
        raster_size = prefix.camera.size[active_views]
        expected_size = torch.tensor(
            [prefix.depth_m.shape[-1], prefix.depth_m.shape[-2]],
            dtype=raster_size.dtype,
            device=raster_size.device,
        )
        if not bool(focal.gt(0).all() and torch.isfinite(principal).all()):
            raise ValueError("Q_H S1 active selected cameras require finite positive pinhole intrinsics.")
        if not bool(torch.equal(raster_size, expected_size.expand_as(raster_size))):
            raise ValueError("Q_H S1 selected camera raster size must match the depth raster.")
        camera_rig = prefix.camera.T_camera_rig.tensor()[active_views]
        identity = PoseTW().tensor().to(device=camera_rig.device, dtype=camera_rig.dtype)
        if not bool(torch.equal(camera_rig, identity.expand_as(camera_rig))):
            raise ValueError("Q_H S1 selected pinholes require identity camera-to-rig extrinsics.")

        pose_values = prefix.camera_pose_relative_root.tensor()[active_views]
        if not bool(torch.isfinite(pose_values).all()):
            raise ValueError("Q_H S1 active root-from-camera poses must be finite.")
        with torch.autocast(device_type=pose_values.device.type, enabled=False):
            rotations = pose_values[..., :9].reshape(-1, 3, 3).float()
            rotation_identity = torch.eye(3, dtype=rotations.dtype, device=rotations.device).expand_as(rotations)
            orthogonality = rotations @ rotations.transpose(-1, -2)
            determinant = torch.linalg.det(rotations)
        if not bool(
            torch.allclose(orthogonality, rotation_identity, rtol=1e-4, atol=1e-5)
            and torch.allclose(determinant, torch.ones_like(determinant), rtol=1e-4, atol=1e-5)
        ):
            raise ValueError("Q_H S1 active root-from-camera poses must be proper rigid transforms.")

    def _selected_surface_update(
        self,
        actor: QhActorTensors,
        *,
        current_pose_relative_root: PoseTW,
    ) -> Tensor:
        """Backproject causal views in bounded chunks and pool their point set."""

        prefix = actor.selected_observation_prefix
        assert prefix is not None
        depth = prefix.depth_m.detach().float()
        batch_size, steps, history_slots, height, width = depth.shape
        group_count = batch_size * steps
        view_count = group_count * history_slots
        flat_depth = depth.reshape(view_count, height, width)
        flat_valid = prefix.valid_mask.reshape(view_count, height, width)
        flat_view_mask = prefix.prefix_mask.reshape(view_count)
        flat_camera = prefix.camera.tensor().reshape(view_count, -1)
        flat_pose = prefix.camera_pose_relative_root.tensor().reshape(view_count, -1)
        with torch.autocast(device_type=depth.device.type, enabled=False):
            current_from_root = current_pose_relative_root.inverse().tensor().float().reshape(group_count, -1)

        hidden_dim = int(self.config.point_hidden_dim)
        point_sum = torch.zeros((group_count, hidden_dim), dtype=torch.float32, device=depth.device)
        point_max = torch.full_like(point_sum, -torch.inf)
        valid_count = torch.zeros((group_count, 1), dtype=torch.float32, device=depth.device)
        valid_view_count = torch.zeros_like(valid_count)
        sampled_height = (height + int(self.config.pixel_stride) - 1) // int(self.config.pixel_stride)
        sampled_width = (width + int(self.config.pixel_stride) - 1) // int(self.config.pixel_stride)
        sampled_pixels_per_view = sampled_height * sampled_width

        active_view_indices = torch.nonzero(flat_view_mask, as_tuple=False).flatten()
        for start in range(0, active_view_indices.numel(), int(self.config.view_chunk_size)):
            stop = min(start + int(self.config.view_chunk_size), active_view_indices.numel())
            view_indices = active_view_indices[start:stop]
            group_indices = torch.div(view_indices, history_slots, rounding_mode="floor")
            valid_pixels = flat_valid[view_indices]
            with torch.autocast(device_type=depth.device.type, enabled=False):
                points_root, lengths = backproject_depths_camera_tw_batch(
                    flat_depth[view_indices],
                    valid_pixels,
                    CameraTW(flat_camera[view_indices]),
                    PoseTW(flat_pose[view_indices]),
                    stride=int(self.config.pixel_stride),
                )
            valid_view_count.index_add_(0, group_indices, lengths.gt(0).float().unsqueeze(-1))
            if points_root.shape[1] == 0:
                continue
            point_mask = torch.arange(points_root.shape[1], device=depth.device).unsqueeze(0) < lengths.unsqueeze(1)
            with torch.autocast(device_type=depth.device.type, enabled=False):
                safe_root = torch.where(point_mask.unsqueeze(-1), points_root, torch.zeros_like(points_root))
                points_current = PoseTW(current_from_root[group_indices]).transform(safe_root)
                normalized = points_current.float() / float(self.config.coordinate_scale_m)
            point_features = self.point_encoder(normalized)
            # Reductions intentionally accumulate in float32 under autocast;
            # the learned point MLP and final projection remain autocast-aware.
            selected_features = point_features[point_mask].float()
            selected_groups = group_indices.unsqueeze(1).expand_as(point_mask)[point_mask]
            if selected_features.numel() == 0:
                continue
            # Rebind differentiable accumulators rather than mutating the
            # output of an earlier chunk's autograd node. CUDA backward keeps
            # those prior versions to route gradients to every point chunk.
            point_sum = point_sum.index_add(0, selected_groups, selected_features)
            valid_count.index_add_(
                0,
                selected_groups,
                torch.ones((selected_groups.shape[0], 1), dtype=torch.float32, device=depth.device),
            )
            point_max = point_max.scatter_reduce(
                0,
                selected_groups.unsqueeze(-1).expand(-1, hidden_dim),
                selected_features,
                reduce="amax",
                include_self=True,
            )

        mean = point_sum / valid_count.clamp_min(1.0)
        maximum = torch.where(torch.isfinite(point_max), point_max, torch.zeros_like(point_max))
        causal_views = prefix.prefix_mask.sum(dim=-1).reshape(group_count, 1).float()
        capacity = causal_views * float(sampled_pixels_per_view)
        presence = valid_count.gt(0).float()
        support = torch.where(capacity.gt(0), valid_count / capacity.clamp_min(1.0), torch.zeros_like(valid_count))
        view_support = torch.where(
            causal_views.gt(0),
            valid_view_count / causal_views.clamp_min(1.0),
            torch.zeros_like(valid_view_count),
        )
        pooled = torch.cat((mean, maximum, presence, support.clamp(0.0, 1.0), view_support), dim=-1)
        return self.point_update(pooled).reshape(batch_size, steps, self.output_dim)


__all__ = [
    "QhRootMomentsSceneEncoder",
    "QhRootMomentsSceneEncoderConfig",
    "QhLegacySelectedSurfacePointSceneEncoderConfig",
    "QhSceneChannel",
    "QhSceneEncoderConfig",
    "QhSelectedSurfacePointSceneEncoder",
    "QhSelectedSurfacePointSceneEncoderConfig",
]
