"""EVL backbone exchange containers for VIN scorer inputs.

This module owns the typed payloads shared by EVL adapters, offline stores,
VIN models, and target-selection code. The aggregate `aria_nbv.vin.types`
package re-exports these names for compatibility, but this file is the
canonical definition owner.
"""

from __future__ import annotations

from dataclasses import dataclass, field, fields
from typing import TYPE_CHECKING, Annotated, Literal, TypedDict, cast

import torch
from typing_extensions import Doc

from ...utils.semantic_names import normalize_semantic_name_map
from ...utils.typed_payloads import from_serializable, to_serializable

if TYPE_CHECKING:
    from efm3d.aria.obb import ObbTW
    from efm3d.aria.pose import PoseTW

Tensor = torch.Tensor
FreeInputMode = Literal["native", "derived"]
FreeInputProvenance = Literal["native_evl_v1", "derived_observed_complement_occ_input_v1"]


def validate_free_input_provenance(value: object) -> FreeInputProvenance:
    """Validate and narrow the persisted free-input provenance label."""

    if value not in {"native_evl_v1", "derived_observed_complement_occ_input_v1"}:
        raise ValueError(
            f"Unknown free-input provenance {value!r}; expected 'native_evl_v1' or "
            "'derived_observed_complement_occ_input_v1'."
        )
    return cast(FreeInputProvenance, value)


@dataclass(slots=True)
class EvlBackboneOutput:
    """Actor-visible EVL evidence exchanged with VIN scorers and caches.

    The tensors are local to the EVL model configuration and checkpoint that
    produced them; they are learned evidence, not ground truth. This container
    does not embed source, config, or checkpoint hashes. Any durable offline
    payload must therefore pair it with provenance metadata that identifies the
    EVL source, resolved configuration, and checkpoint content.

    Attributes:
        t_world_voxel: ``PoseTW["B 12"]`` world←voxel pose for the voxel grid.
        voxel_extent: ``Tensor["6", float32]`` voxel grid extent in voxel frame
            ``[x_min,x_max,y_min,y_max,z_min,z_max]`` (meters).
        voxel_feat: Optional ``Tensor["B F D H W", float32]`` raw voxel features from the 3D backbone.
        occ_feat: Optional ``Tensor["B C D H W", float32]`` neck features for occupancy.
        obb_feat: Optional ``Tensor["B C D H W", float32]`` neck features for OBB detection.
        occ_pr: Optional ``Tensor["B 1 D H W", float32]`` EVL occupancy probability.
        occ_input: Optional ``Tensor["B 1 D H W", float32]`` voxelized occupied evidence from input points.
        free_input: Optional ``Tensor["B 1 D H W", float32]`` voxelized free-space evidence.
        free_input_provenance: Native EVL output or the explicit derived construction.
        counts: Optional ``Tensor["B D H W", int64]`` per-voxel observation counts.
        counts_m: Optional ``Tensor["B D H W", int64]`` masked/debug variant of counts.
        voxel_select_t: Optional ``Tensor["B 1", int64]`` frame index anchoring the voxel grid.
        cent_pr: Optional ``Tensor["B 1 D H W", float32]`` centerness probabilities.
        bbox_pr: Optional ``Tensor["B 7 D H W", float32]`` bounding box regressions.
        clas_pr: Optional ``Tensor["B K D H W", float32]`` class probabilities.
        cent_pr_nms: Optional ``Tensor["B 1 D H W", float32]`` centerness after NMS.
        obbs_pr_nms: Optional ``ObbTW["B M 34"]`` OBB predictions after NMS (voxel frame).
        obb_pred: Optional ``ObbTW["B M 34"]`` OBB predictions in snippet coordinates.
        obb_pred_viz: Optional ``ObbTW["B M 34"]`` visualization OBB predictions in snippet coordinates.
        obb_pred_sem_id_to_name: Optional sparse semantic id to class-name map aligned with EVL taxonomy.
        obb_pred_probs_full: Optional list of per-OBB class probability tensors.
        obb_pred_probs_full_viz: Optional list of per-OBB class probability tensors for visualization.
        pts_world: Optional ``Tensor["B (D·H·W) 3", float32]`` world-space voxel centers.
        feat2d_upsampled: Per-stream 2D feature maps keyed by stream name.
        token2d: Per-stream 2D tokens keyed by stream name.
    """

    t_world_voxel: PoseTW
    """``PoseTW["B 12"]`` world←voxel pose for the voxel grid."""

    voxel_extent: Tensor
    """``Tensor["6", float32]`` voxel grid extent in the voxel frame."""

    voxel_feat: Tensor | None = None
    """``Tensor["B F D H W", float32]`` raw voxel features from the 3D backbone."""

    occ_feat: Tensor | None = None
    """``Tensor["B C D H W", float32]`` neck occupancy features."""

    obb_feat: Tensor | None = None
    """``Tensor["B C D H W", float32]`` neck OBB features."""

    occ_pr: Tensor | None = None
    """``Tensor["B 1 D H W", float32]`` occupancy probabilities."""

    occ_input: Tensor | None = None
    """``Tensor["B 1 D H W", float32]`` occupied evidence from input points."""

    free_input: Tensor | None = None
    """``Tensor["B 1 D H W", float32]`` free-space evidence."""

    free_input_provenance: FreeInputProvenance | None = None
    """How ``free_input`` was produced; required for persisted backbone rows."""

    counts: Tensor | None = None
    """``Tensor["B D H W", int64]`` per-voxel observation counts."""

    counts_m: Tensor | None = None
    """``Tensor["B D H W", int64]`` masked/debug observation counts."""

    voxel_select_t: Tensor | None = None
    """``Tensor["B 1", int64]`` frame index anchoring the voxel grid."""

    cent_pr: Tensor | None = None
    """``Tensor["B 1 D H W", float32]`` centerness probabilities."""

    bbox_pr: Tensor | None = None
    """``Tensor["B 7 D H W", float32]`` bounding box regression outputs."""

    clas_pr: Tensor | None = None
    """``Tensor["B K D H W", float32]`` class probability outputs."""

    cent_pr_nms: Tensor | None = None
    """``Tensor["B 1 D H W", float32]`` centerness after NMS."""

    obbs_pr_nms: ObbTW | None = None
    """``ObbTW["B M 34"]`` OBB predictions after NMS in voxel coordinates."""

    obb_pred: ObbTW | None = None
    """``ObbTW["B M 34"]`` OBB predictions in snippet coordinates."""

    obb_pred_viz: ObbTW | None = None
    """``ObbTW["B M 34"]`` OBB predictions for visualization in snippet coordinates."""

    obb_pred_sem_id_to_name: dict[int, str] | None = None
    """Sparse semantic id to class-name mapping used by EVL's OBB predictions."""

    obb_pred_probs_full: list[Tensor] | None = None
    """Per-OBB class probability tensors aligned with ``obb_pred``."""

    obb_pred_probs_full_viz: list[Tensor] | None = None
    """Per-OBB class probability tensors aligned with ``obb_pred_viz``."""

    pts_world: Tensor | None = None
    """``Tensor["B (D·H·W) 3", float32]`` world-space voxel centers."""

    feat2d_upsampled: dict[str, Tensor] = field(default_factory=dict)
    """Per-stream ``Tensor["B T C H W", float32]`` feature maps."""

    token2d: dict[str, Tensor] = field(default_factory=dict)
    """Per-stream 2D token tensors keyed by stream name.

    EVL variants may expose either ``Tensor["B T C H W", float32]`` maps or
    model-specific token layouts. Consumers must preserve the producing
    config/checkpoint identity rather than treating channel semantics as
    globally interchangeable.
    """

    def to_serializable(self, *, include_fields: set[str] | None = None) -> dict[str, object]:
        """Serialize this backbone output into a cache-friendly CPU payload.

        Args:
            include_fields: Optional dataclass field names to include. When
                omitted, all fields are serialized.

        Returns:
            CPU-only payload suitable for immutable offline-store records.
        """

        exclude: set[str] | None = None
        if include_fields is not None:
            known_fields = {field.name for field in fields(self)}
            exclude = known_fields - include_fields
        payload = to_serializable(self, exclude=exclude)
        if not isinstance(payload, dict):
            raise TypeError(f"Expected serialized EvlBackboneOutput payload dict, got {type(payload)!r}.")
        if "obb_pred_sem_id_to_name" in payload:
            payload["obb_pred_sem_id_to_name"] = normalize_semantic_name_map(payload["obb_pred_sem_id_to_name"])
        return payload

    @classmethod
    def from_serializable(
        cls,
        payload: dict[str, object],
        *,
        device: torch.device,
        include_fields: set[str] | None = None,
    ) -> "EvlBackboneOutput":
        """Reconstruct one backbone output from a serialized payload.

        Args:
            payload: Serialized payload produced by `to_serializable`.
            device: Destination device for tensors and wrappers.
            include_fields: Optional subset of fields to decode.

        Returns:
            Reconstructed backbone output.
        """

        return from_serializable(
            cls,
            payload,
            device=device,
            include_fields=include_fields,
        )

    def to(self, device: torch.device) -> EvlBackboneOutput:
        """Move all tensors to the specified device."""

        def _move(value: Tensor | None) -> Tensor | None:
            if value is None:
                return None
            return value.to(device=device)

        def _move_list(values: list[Tensor] | None) -> list[Tensor] | None:
            if values is None:
                return None
            return [item.to(device=device) if isinstance(item, torch.Tensor) else item for item in values]

        def _move_dict(values: dict[str, Tensor]) -> dict[str, Tensor]:
            return {key: val.to(device=device) for key, val in values.items()}

        return EvlBackboneOutput(
            t_world_voxel=self.t_world_voxel.to(device=device),
            voxel_extent=self.voxel_extent.to(device=device),
            voxel_feat=_move(self.voxel_feat),
            occ_feat=_move(self.occ_feat),
            obb_feat=_move(self.obb_feat),
            occ_pr=_move(self.occ_pr),
            occ_input=_move(self.occ_input),
            free_input=_move(self.free_input),
            free_input_provenance=self.free_input_provenance,
            counts=_move(self.counts),
            counts_m=_move(self.counts_m),
            voxel_select_t=_move(self.voxel_select_t),
            cent_pr=_move(self.cent_pr),
            bbox_pr=_move(self.bbox_pr),
            clas_pr=_move(self.clas_pr),
            cent_pr_nms=_move(self.cent_pr_nms),
            obbs_pr_nms=self.obbs_pr_nms.to(device=device) if self.obbs_pr_nms is not None else None,
            obb_pred=self.obb_pred.to(device=device) if self.obb_pred is not None else None,
            obb_pred_viz=self.obb_pred_viz.to(device=device) if self.obb_pred_viz is not None else None,
            obb_pred_sem_id_to_name=self.obb_pred_sem_id_to_name,
            obb_pred_probs_full=_move_list(self.obb_pred_probs_full),
            obb_pred_probs_full_viz=_move_list(self.obb_pred_probs_full_viz),
            pts_world=_move(self.pts_world),
            feat2d_upsampled=_move_dict(self.feat2d_upsampled),
            token2d=_move_dict(self.token2d),
        )


EfmDict = TypedDict(
    "EfmDict",
    {
        "occ_pr": Annotated[
            Tensor,
            Doc("""``Tensor["B 1 D H W", float32]`` Occupancy probabilities for the EVL voxel grid."""),
        ],
        "voxel_extent": Annotated[
            Tensor,
            Doc(
                """``Tensor["6", float32]`` Voxel grid extent in voxel frame (metres):
``[x_min,x_max,y_min,y_max,z_min,z_max]``."""
            ),
        ],
        "rgb/feat2d_upsampled": Annotated[
            Tensor,
            Doc("""``Tensor["B T C H W", float32]`` Up-sampled 2D RGB features used by the lifter."""),
        ],
        "rgb/token2d": Annotated[
            Tensor | list[Tensor],
            Doc(
                """2D RGB backbone tokens for visualization/debugging.

- If a single tensor: ``Tensor["B T C H W", float32]``.
- If multi-layer: list of tensors (e.g. length 4) with per-layer shapes
  ``Tensor["B T C_i H_i W_i", float32]``."""
            ),
        ],
        "voxel/feat": Annotated[
            Tensor,
            Doc("""``Tensor["B F D H W", float32]`` Lifted voxel features (incl. appended evidence channels)."""),
        ],
        "voxel/counts": Annotated[
            Tensor,
            Doc("""``Tensor["B D H W", int64]`` Per-voxel observation counts (unmasked)."""),
        ],
        "voxel/counts_m": Annotated[
            Tensor,
            Doc("""``Tensor["B D H W", int64]`` Masked/debug variant of per-voxel observation counts."""),
        ],
        "voxel/pts_world": Annotated[
            Tensor,
            Doc("""``Tensor["B (D·H·W) 3", float32]`` World-space voxel center coordinates."""),
        ],
        "voxel/T_world_voxel": Annotated[
            "PoseTW",
            Doc("""``PoseTW["B 12"]`` World←voxel pose of the EVL voxel grid."""),
        ],
        "voxel/selectT": Annotated[
            Tensor,
            Doc("""``Tensor["B", int64]`` Frame index used to anchor the voxel grid (typically ``T-1``)."""),
        ],
        "voxel/occ_input": Annotated[
            Tensor,
            Doc("""``Tensor["B 1 D H W", float32]`` Voxelized occupied evidence from input points (binary mask)."""),
        ],
        "neck/occ_feat": Annotated[
            Tensor,
            Doc("""``Tensor["B C D H W", float32]`` Neck features feeding the occupancy head."""),
        ],
        "neck/obb_feat": Annotated[
            Tensor,
            Doc("""``Tensor["B C D H W", float32]`` Neck features feeding the OBB heads."""),
        ],
        "cent_pr": Annotated[
            Tensor,
            Doc("""``Tensor["B 1 D H W", float32]`` Centerness probabilities (pre-NMS)."""),
        ],
        "bbox_pr": Annotated[
            Tensor,
            Doc("""``Tensor["B 7 D H W", float32]`` Bounding box regression head output (pre-NMS)."""),
        ],
        "clas_pr": Annotated[
            Tensor,
            Doc("""``Tensor["B C_sem D H W", float32]`` Semantic class probabilities (pre-NMS)."""),
        ],
        "obbs_pr_nms": Annotated[
            "ObbTW",
            Doc("""``ObbTW["B K 34"]`` Sparse OBB predictions after NMS (in voxel coords)."""),
        ],
        "cent_pr_nms": Annotated[
            Tensor,
            Doc("""``Tensor["B 1 D H W", float32]`` Centerness probabilities after NMS suppression."""),
        ],
        "obbs/pred/sem_id_to_name": Annotated[
            dict[int, str],
            Doc("""Mapping from predicted semantic ids to human-readable class names."""),
        ],
        "obbs/pred": Annotated[
            "ObbTW",
            Doc("""``ObbTW["B K 34"]`` OBB predictions transformed to snippet coordinates (post-processing output)."""),
        ],
        "obbs/pred_viz": Annotated[
            "ObbTW",
            Doc("""``ObbTW["B K 34"]`` Visualization-oriented variant of ``obbs/pred`` (typically identical)."""),
        ],
        "obbs/pred/probs_full": Annotated[
            list[Tensor],
            Doc("""List of full class probability tensors per batch element, aligned with ``obbs/pred``."""),
        ],
        "obbs/pred/probs_ful_viz": Annotated[
            list[Tensor],
            Doc("""Visualization-oriented variant of ``obbs/pred/probs_full``."""),
        ],
    },
    total=False,
)


__all__ = ["EfmDict", "EvlBackboneOutput"]
