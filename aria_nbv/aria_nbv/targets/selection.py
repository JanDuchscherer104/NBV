"""Actor-visible observed-target selection.

This module deliberately stops at immutable detector descriptors.  Privileged
GT matching belongs to :mod:`aria_nbv.oracle.target_selection` and is a
separate, evaluation-only step.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from typing import TYPE_CHECKING

import torch
from efm3d.aria.aria_constants import ARIA_SNIPPET_T_WORLD_SNIPPET
from efm3d.aria.obb import ObbTW
from efm3d.aria.pose import PoseTW

from ..data_handling.ase_efm.views import EfmSnippetView
from ..data_handling.vin_store.batch import CompactObbBlock
from ..data_handling.vin_store.views import VinSnippetView
from .descriptor import TargetDescriptor

if TYPE_CHECKING:
    from ..data_handling.vin_store.dataset import VinOfflineSample


@dataclass(frozen=True, slots=True)
class ObservedTargetDescriptor:
    """One actor-visible detected OBB and its stable descriptor identity.

    No ground-truth row, match score, or privileged label is present.  The
    ``descriptor_hash`` is intended for manifest/evidence provenance only.
    """

    sample_key: str
    """Immutable source sample identity."""

    source: str
    """Actor-visible OBB source label."""

    source_row: int
    """Row index in the detected OBB table before padding removal."""

    target_id: str
    """Stable identity for this detected source row."""

    descriptor: TargetDescriptor | None
    """Sanitized actor instruction, or ``None`` for retained invalid geometry."""

    confidence: float
    """Detector confidence retained for audit."""

    inst_id: int
    """Detector instance identifier."""

    obb_data: tuple[float, ...] | None = None
    """Flattened actor OBB payload retained for privileged evaluation only."""

    @property
    def descriptor_hash(self) -> str:
        """Return the canonical hash of actor-visible identity fields."""

        payload = {
            "sample_key": self.sample_key,
            "source": self.source,
            "source_row": self.source_row,
            "target_id": self.target_id,
            "descriptor": (
                None
                if self.descriptor is None
                else {
                    "sem_id": self.descriptor.sem_id,
                    "class_name": self.descriptor.class_name,
                    "pose_world_object": self.descriptor.pose_world_object,
                    "extents_m": self.descriptor.extents_m,
                    "relative_pose_reference_object": self.descriptor.relative_pose_reference_object,
                }
            ),
        }
        encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
        return hashlib.sha256(encoded).hexdigest()


def snippet_t_world_snippet(sample: "VinOfflineSample") -> PoseTW | None:
    """Return the canonical world-from-snippet transform for OBB normalization."""
    snippet = sample.efm_snippet_view if sample.efm_snippet_view is not None else sample.vin_snippet
    if isinstance(snippet, EfmSnippetView):
        value = snippet.efm.get(ARIA_SNIPPET_T_WORLD_SNIPPET)
        if isinstance(value, PoseTW):
            return PoseTW(value.tensor().reshape(-1, 12)[:1])
        if torch.is_tensor(value):
            return PoseTW(value.reshape(-1, 12)[:1])
    if isinstance(snippet, VinSnippetView):
        poses = snippet.t_world_snippet.tensor().reshape(-1, 12)
        if poses.shape[0] > 0:
            return PoseTW(poses[:1])
    return None


def observed_target_descriptors(sample: "VinOfflineSample") -> tuple[ObservedTargetDescriptor, ...]:
    """Convert detected OBB rows into deterministic actor-visible descriptors.

    Padded rows are omitted and source-row order is preserved.  The function
    reads only actor-visible geometry, the neutral reference-frame pose, and
    sample identity; it never accesses the oracle payload or GT OBBs.
    """

    block = getattr(sample, "detected_obbs", None)
    if block is None:
        return ()
    obbs = block.obbs if isinstance(block, CompactObbBlock) or hasattr(block, "obbs") else block
    if obbs is None:
        return ()
    obbs = obbs if isinstance(obbs, ObbTW) else ObbTW(torch.as_tensor(obbs, dtype=torch.float32))
    data = obbs.tensor().detach().cpu().to(dtype=torch.float32)
    if data.ndim == 1:
        data = data.unsqueeze(0)
    if data.ndim > 2:
        data = data.reshape(-1, data.shape[-1])
    t_world_snippet = snippet_t_world_snippet(sample)
    if t_world_snippet is None:
        raise ValueError("observed target extraction requires T_world_snippet")
    t_world_snippet = t_world_snippet.to(device=data.device)
    flat = ObbTW(data).transform(t_world_snippet)
    data = flat.tensor().detach().cpu().to(dtype=torch.float32)
    valid = (~flat.get_padding_mask()).reshape(-1)
    names = getattr(block, "sem_id_to_name", None) if isinstance(block, CompactObbBlock) else None
    sample_key = str(getattr(sample, "sample_key", ""))
    reference_pose = sample.reference_pose_world_rig.to(device=data.device)
    result: list[ObservedTargetDescriptor] = []
    for source_row in torch.nonzero(valid, as_tuple=False).reshape(-1).tolist():
        obb = ObbTW(data[source_row])
        sem_id = int(obb.sem_id.reshape(-1)[0].item())
        inst_id = int(obb.inst_id.reshape(-1)[0].item())
        class_name = str(names.get(sem_id, f"class_{sem_id}") if isinstance(names, dict) else f"class_{sem_id}")
        pose = tuple(float(v) for v in obb.T_world_object.tensor().reshape(-1).tolist())
        extent = tuple(float(v) for v in obb.bb3_diagonal.reshape(-1).tolist())
        relative_pose = tuple(
            float(v) for v in (reference_pose.inverse() @ obb.T_world_object).tensor().reshape(-1).tolist()
        )
        try:
            descriptor = TargetDescriptor(
                sem_id=sem_id,
                class_name=class_name,
                pose_world_object=pose,
                extents_m=extent,  # type: ignore[arg-type]
                relative_pose_reference_object=relative_pose,
            )
        except ValueError:
            descriptor = None
        target_id = f"{sample_key}:detected:{source_row}:{inst_id}"
        result.append(
            ObservedTargetDescriptor(
                sample_key=sample_key,
                source="detected_obbs",
                source_row=int(source_row),
                target_id=target_id,
                descriptor=descriptor,
                confidence=float(obb.prob.reshape(-1)[0].item()),
                inst_id=inst_id,
                obb_data=tuple(float(value) for value in data[source_row].tolist()),
            )
        )
    return tuple(result)


select_observed_target_descriptors = observed_target_descriptors

__all__ = [
    "ObservedTargetDescriptor",
    "observed_target_descriptors",
    "select_observed_target_descriptors",
    "snippet_t_world_snippet",
]
