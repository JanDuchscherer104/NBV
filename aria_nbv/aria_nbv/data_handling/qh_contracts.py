r"""Dependency-light Q_H profile and selected-observation contracts.

This leaf owns the shared names and structural validation needed by Q_H data,
VIN scorers, Lightning, and bundle admission. It intentionally does not import
the rich :mod:`aria_nbv.data_handling.qh_data` runtime graph, so scorers can
depend on these contracts during package initialization without forming a
``data_handling -> vin -> qh_data`` cycle. Tensor DTOs, materialization,
learning, and deployment remain in their respective owners.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Literal

import torch
from torch import Tensor

if TYPE_CHECKING:
    from .qh_data.views import QhSelectedObservationPrefix

QhRootEvlProfile = Literal["none", "evl_v1"]
QhSelectedObservationProtocol = Literal["none", "cf_gt"]
QhExperimentProfile = Literal["qh_cf0_v1", "qh_cfplus_gt_depth_v1"]


def validate_experiment_profile(
    profile: QhExperimentProfile,
    *,
    root_evl_profile: QhRootEvlProfile,
    selected_observation_protocol: QhSelectedObservationProtocol,
    target_protocol: str | None = None,
    privileged: bool = False,
) -> None:
    """Validate one named Q_H source/execution role.

    Args:
        profile: Closed CF0 or privileged CF+ role.
        root_evl_profile: Root scene-evidence carrier paired with the role.
        selected_observation_protocol: Dynamic selected-observation source.
        target_protocol: Optional target-source identity when known.
        privileged: Whether the calling execution owner admits privileged CF+.

    Raises:
        ValueError: If the named role and its source or execution contracts are
            inconsistent.
    """

    if selected_observation_protocol == "cf_gt" and profile != "qh_cfplus_gt_depth_v1":
        raise ValueError("Q_H selected_observation_protocol='cf_gt' requires qh_cfplus_gt_depth_v1.")
    if root_evl_profile != "evl_v1":
        raise ValueError(f"Q_H profile {profile!r} requires compact root EVL profile 'evl_v1'.")
    expected_observation = "none" if profile == "qh_cf0_v1" else "cf_gt"
    if selected_observation_protocol != expected_observation:
        raise ValueError(f"Q_H profile {profile!r} requires selected_observation_protocol={expected_observation!r}.")
    if profile == "qh_cfplus_gt_depth_v1" and not privileged:
        raise ValueError("Deployable Q_H configuration rejects privileged qh_cfplus_gt_depth_v1.")
    if profile == "qh_cf0_v1" and target_protocol is not None and target_protocol != "v1_observed":
        raise ValueError("Deployable qh_cf0_v1 requires target_protocol='v1_observed'.")


def validate_selected_observation_prefix(
    prefix: QhSelectedObservationPrefix,
    *,
    history_mask: Tensor,
    step_mask: Tensor,
) -> None:
    r"""Validate the structural contract of one causal CF-GT carrier.

    This validator owns only carrier identity, tensor layout, dtype, device,
    and causal support. It deliberately does not interpret depth, calibration,
    or pose values. That distinction lets the ``root_moments_v1`` CF+ H0
    control admit the exact same source population as a later S1 encoder while
    proving that no selected-observation payload reaches its prediction.

    The two trailing axes of ``history_mask`` are query state :math:`s` and
    selected-observation index :math:`j`. ``prefix_mask`` must equal the
    factual pose-history mask and must be true exactly for realized
    :math:`j<s` pairs. Therefore neither future observations nor observations
    attached to padded query/source states can enter the carrier.

    Args:
        prefix: Unbatched ``S,S,...`` or batched ``B,S,S,...`` selected-depth
            carrier.
        history_mask: Factual selected-pose support with shape ``S,S`` or
            ``B,S,S``.
        step_mask: Realized-state support with shape ``S`` or ``B,S``.

    Raises:
        ValueError: If source identity, shapes, dtypes, devices, or exact
            strictly causal support differ from the Q_H actor contract.
    """

    if prefix.source_protocol != "cf_gt":
        raise ValueError("Q_H selected-observation prefix requires source_protocol='cf_gt'.")
    if history_mask.ndim not in {2, 3} or history_mask.shape[-2] != history_mask.shape[-1]:
        raise ValueError("Q_H history_mask must have shape (S,S) or (B,S,S) for selected observations.")
    if step_mask.shape != history_mask.shape[:-1]:
        raise ValueError("Q_H selected-observation step_mask must match the query-state axes.")
    if history_mask.dtype is not torch.bool or step_mask.dtype is not torch.bool:
        raise ValueError("Q_H selected-observation history_mask and step_mask must use bool dtype.")

    state_shape = tuple(history_mask.shape)
    if prefix.depth_m.ndim != history_mask.ndim + 2 or tuple(prefix.depth_m.shape[: history_mask.ndim]) != state_shape:
        raise ValueError("Q_H selected depth must have shape (...,S,S,H_d,W_d).")
    if prefix.depth_m.shape[-2] < 1 or prefix.depth_m.shape[-1] < 1:
        raise ValueError("Q_H selected-depth raster axes must be non-empty.")
    if prefix.valid_mask.shape != prefix.depth_m.shape:
        raise ValueError("Q_H selected-depth valid_mask must match depth_m exactly.")
    if tuple(prefix.camera.tensor().shape) != (*state_shape, 22):
        raise ValueError("Q_H selected-depth camera must have shape (...,S,S,22).")
    if tuple(prefix.camera_pose_relative_root.tensor().shape) != (*state_shape, 12):
        raise ValueError("Q_H selected-depth camera pose must have shape (...,S,S,12).")
    if prefix.prefix_mask.shape != history_mask.shape:
        raise ValueError("Q_H selected-depth prefix_mask must match history_mask exactly.")
    if prefix.depth_m.dtype is not torch.float16:
        raise ValueError("Q_H selected depth must use float16 metres.")
    if prefix.valid_mask.dtype is not torch.bool or prefix.prefix_mask.dtype is not torch.bool:
        raise ValueError("Q_H selected-depth support masks must use bool dtype.")
    if prefix.camera.tensor().dtype is not torch.float32:
        raise ValueError("Q_H selected-depth camera rows must use float32.")
    if prefix.camera_pose_relative_root.tensor().dtype is not torch.float32:
        raise ValueError("Q_H selected-depth camera poses must use float32.")

    tensors = (
        prefix.depth_m,
        prefix.valid_mask,
        prefix.camera.tensor(),
        prefix.camera_pose_relative_root.tensor(),
        prefix.prefix_mask,
        history_mask,
        step_mask,
    )
    if any(value.device != history_mask.device for value in tensors):
        raise ValueError("Q_H selected-observation tensors and actor masks must share one device.")

    steps = history_mask.shape[-1]
    query = torch.arange(steps, device=history_mask.device).view(*([1] * (history_mask.ndim - 2)), steps, 1)
    observation = torch.arange(steps, device=history_mask.device).view(*([1] * (history_mask.ndim - 2)), 1, steps)
    expected = step_mask.unsqueeze(-1) & step_mask.unsqueeze(-2) & observation.lt(query)
    if not torch.equal(prefix.prefix_mask, expected):
        raise ValueError(
            "Q_H selected-depth prefix_mask must be true exactly for realized strictly causal j < s pairs."
        )
    if not torch.equal(history_mask, expected):
        raise ValueError("Q_H selected-depth support must match the complete factual pose-history prefix.")


__all__ = [
    "QhExperimentProfile",
    "QhRootEvlProfile",
    "QhSelectedObservationProtocol",
    "validate_experiment_profile",
    "validate_selected_observation_prefix",
]
