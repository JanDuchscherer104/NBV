r"""Validated rollout-to-VIN joins for finite-candidate Q_H chains.

The dataset joins private rollout source references to the exact immutable VIN
actor sample, verifies manifest and split identity before iteration, and
tensorizes stored variable-length chains into factual fixed-budget views. It
never chooses a scorer, learning objective, or fitted-Q admission policy;
candidate actions, rewards, discounts, terminal flags, and remaining budgets
are persisted rollout facts.
This module owns the validated join and tensorization; rollout decoding and VIN
storage remain with their respective readers.
"""

from __future__ import annotations

from functools import cached_property
from pathlib import Path
from typing import TYPE_CHECKING

import numpy as np
import torch
from efm3d.aria.pose import PoseTW
from pydantic import Field, field_validator
from torch import Tensor
from torch.utils.data import Dataset

from ...rollouts.qh_reader import QhDataContract, QhRolloutReader, _QhSourceRef
from ...rollouts.shard_manifest import build_rollout_split_manifest_hash
from ...utils import Stage, TargetConfig
from ...utils.fingerprints import stable_msgspec_hash
from ..identifiers import compact_ase_atek_sample_id
from ..vin_store.format import VinOfflineIndexRecord
from ..vin_store.store import VinOfflineStoreConfig, VinOfflineStoreReader
from ..vin_store.views import VinSnippetView
from .batching import _gather_candidates, _pad
from .views import (
    QhActorTensors,
    QhAudit,
    QhChain,
    QhChainKey,
    QhSelectedObservationPrefix,
    QhStaticContext,
    QhSupervision,
)

if TYPE_CHECKING:
    from ...rollouts.qh_reader import _StoredChain


class QhDatasetConfig(TargetConfig["QhDataset"]):
    """Configure ordered rollout stores and their exact immutable VIN actor source."""

    rollout_store_dirs: tuple[Path, ...] = Field(min_length=1)
    """Non-empty rollout-store paths; tuple order defines ``QhChainKey.store_index``."""

    actor: VinOfflineStoreConfig = Field(default_factory=VinOfflineStoreConfig)
    """Immutable VIN store whose actor-visible root rows must match every rollout source reference."""

    split: Stage | None = None
    """Learning/campaign split admitted by the rollout reader; ``None`` reads all chains."""

    require_rich_modalities: bool = False
    """Require root EVL evidence and selected CF-GT depth instead of permitting an explicit diagnostic-only legacy read."""

    include_audit: bool = False
    """Attach CPU-only chain provenance for debugging; never adds payloads to scorer tensors or device transfer."""

    @field_validator("split", mode="before")
    @classmethod
    def _normalize_split(cls, value: Stage | str | None) -> Stage | None:
        """Normalize a serialized stage and map ``None`` or ``"all"`` to no split filter."""

        return None if value is None or value == "all" else Stage.from_str(value)

    @property
    def target_type(self) -> type[QhDataset]:
        """Return :class:`QhDataset` for config-as-factory construction."""

        return QhDataset

    def setup_target(self) -> QhDataset:
        """Construct both readers and preflight rollout-to-actor source identity.

        Returns:
            :class:`QhDataset` ready for indexed chain reads after validating
            the configured actor manifest, split, and source rows.
        """

        return QhDataset(
            rollout_reader=QhRolloutReader(
                self.rollout_store_dirs,
                campaign_split=self.split,
                include_selected_depth=self.require_rich_modalities,
            ),
            actor_reader=VinOfflineStoreReader(self.actor),
            split=self.split,
            require_rich_modalities=self.require_rich_modalities,
            include_audit=self.include_audit,
        )


class QhDataset(Dataset[QhChain]):
    """Join validated rollout chains to one immutable actor snippet per chain.

    Construction preflights every private source reference against the actor
    manifest and complete immutable actor index. ``split`` has already selected
    campaign chains at the rollout-reader boundary. ``__getitem__`` then reads one stored chain
    and its chain-constant root snippet exactly once. The result separates
    actor state from label support and other oracle transition facts; it does
    not decide which rows are admissible to a fitted-Q objective.
    """

    _REBUILD_GUIDANCE = "Rebuild the VIN offline store and rollout corpus from the same immutable source manifest."

    def __init__(
        self,
        *,
        rollout_reader: QhRolloutReader,
        actor_reader: VinOfflineStoreReader,
        split: Stage | None = None,
        require_rich_modalities: bool = False,
        include_audit: bool = False,
    ) -> None:
        """Validate rollout provenance against the configured immutable actor store.

        Args:
            rollout_reader: Complete stored chains plus private immutable-source
                references and the fixed Q_H data contract.
            actor_reader: Reader for the immutable VIN actor rows referenced by
                the rollout corpus.
            split: Optional campaign/learning split selected by the rollout
                reader; physical source splits remain validated independently.
        """

        self.rollout_reader = rollout_reader
        self.actor_reader = actor_reader
        reader_split = getattr(rollout_reader, "campaign_split", None)
        if split is not None and reader_split != split:
            raise ValueError(
                "Q_H dataset split must match rollout_reader.campaign_split; "
                f"received split={split!r}, reader campaign_split={reader_split!r}."
            )
        self.split = reader_split
        self.require_rich_modalities = require_rich_modalities
        self.include_audit = include_audit
        self._manifest_hash = stable_msgspec_hash(actor_reader.manifest)
        # ``split`` selects campaign chains above; actor rows are loaded from
        # the complete immutable index so source_ref.split can validate the
        # physical VIN lineage independently.
        self._records = {record.sample_index: record for record in actor_reader.get_split_records(None)}
        self._validate_source_refs()

    def __len__(self) -> int:
        """Return the number of complete stored rollout chains."""

        return len(self.rollout_reader)

    def __getitem__(self, index: int) -> QhChain:
        """Read and tensorize one chain with its chain-constant root observation.

        Args:
            index: Zero-based rollout-reader position.

        Returns:
            :class:`QhChain` containing actor-visible tensors, separately owned
            supervision facts, and a CPU-only audit key. Candidate rows retain
            stored widths until collation.
        """

        stored = self.rollout_reader[index]
        record = self._record(stored.source_ref)
        snippet = self.actor_reader.read_actor_snippet(record, device="cpu")
        static_context = _read_static_context(self.actor_reader, record, snippet)
        if self.require_rich_modalities and (static_context is None or not bool(static_context.evl_presence.all())):
            raise ValueError(
                "Q_H rich training requires every root EVL evidence field; rebuild the VIN offline store with backbone materialization."
            )
        return _tensor_chain(
            stored,
            snippet,
            static_context=static_context,
            require_rich_modalities=self.require_rich_modalities,
            audit=_audit_for(stored, self.rollout_reader.store_dirs[stored.store_index])
            if self.include_audit
            else None,
        )

    @cached_property
    def scenes(self) -> frozenset[str]:
        """Return immutable ASE scene identifiers represented by the validated corpus."""

        return self.rollout_reader.scenes

    @property
    def max_horizon(self) -> int:
        """Return the largest realized horizon among the validated chains."""

        return self.rollout_reader.max_horizon

    @property
    def contract(self) -> QhDataContract:
        """Return compatibility facts shared across the corpus's realized horizons.

        Horizon length is a per-chain fact represented by state count and
        ``horizon_remaining``; it is intentionally absent from this common
        reward, return, discount, schema, and provenance contract.
        """

        return self.rollout_reader.contract

    @property
    def provenance(self) -> dict[str, object]:
        """Return rollout/actor store identity for audit displays, never scorer input."""

        return {
            "rollout": self.rollout_reader.provenance,
            "actor": {
                "store_path": str(self.actor_reader.config.store_dir),
                "store_version": str(self.actor_reader.manifest.version),
                "manifest_hash": self._manifest_hash,
                "split": self.split,
                "row_count": len(self._records),
            },
        }

    def _validate_source_refs(self) -> None:
        """Preflight exact actor rows and ordered per-source split membership.

        Each source reference must resolve through :meth:`_record`. References
        sharing source-manifest, split, and expected split-manifest hashes are
        then replayed in corpus order to reproduce the persisted split hash.
        """

        for source_ref in self.rollout_reader.source_refs:
            self._record(source_ref)
        groups: dict[tuple[str, Stage, str], list[_QhSourceRef]] = {}
        for source_ref in self.rollout_reader.source_refs:
            groups.setdefault(
                (source_ref.source_manifest_hash, source_ref.split, source_ref.split_manifest_hash), []
            ).append(source_ref)
        for (manifest_hash, split, expected), source_refs in groups.items():
            records = [self._record(source_ref) for source_ref in source_refs]
            actual = build_rollout_split_manifest_hash(
                source_manifest_hash=manifest_hash,
                split=split.value,
                records=[
                    {
                        "order": order,
                        "sample_index": record.sample_index,
                        "sample_key": record.sample_key,
                        "scene_id": record.scene_id,
                        "snippet_id": record.snippet_id,
                        "split": record.split,
                        "source_shard_id": record.shard_id,
                        "source_shard_row": record.row,
                        **(
                            {
                                "campaign_split": source_ref.campaign_split.value
                                if source_ref.campaign_split is not Stage.VAL
                                else "validation"
                            }
                            if source_ref.campaign_split is not None
                            else {}
                        ),
                    }
                    for order, (record, source_ref) in enumerate(zip(records, source_refs, strict=True))
                ],
            )
            if actual != expected:
                raise ValueError(f"VIN split manifest does not match rollout source identity. {self._REBUILD_GUIDANCE}")

    def _record(self, source_ref: _QhSourceRef) -> VinOfflineIndexRecord:
        """Resolve one actor row and verify every persisted source-identity field.

        Args:
            source_ref: Private rollout reference naming the actor row, sample,
                shard position, scene, snippet, split, store version, and
                manifest hash expected by the chain.

        Returns:
            Exact immutable VIN index record admitted by the configured split.

        Raises:
            KeyError: If the referenced actor sample index is absent.
            ValueError: If any resolved identity field differs from the
                persisted rollout reference.
        """

        try:
            record = self._records[source_ref.source_sample_index]
        except KeyError as error:
            raise KeyError(
                f"VIN sample_index={source_ref.source_sample_index} is absent from split {self.split!r}. "
                f"{self._REBUILD_GUIDANCE}"
            ) from error
        actual = (
            record.sample_index,
            compact_ase_atek_sample_id(record.sample_key),
            record.shard_id,
            record.row,
            record.scene_id,
            compact_ase_atek_sample_id(record.snippet_id),
            Stage.from_str(record.split),
            str(self.actor_reader.manifest.version),
            self._manifest_hash,
        )
        expected = (
            source_ref.source_sample_index,
            compact_ase_atek_sample_id(source_ref.source_sample_key),
            source_ref.source_shard_id,
            source_ref.source_shard_row,
            source_ref.scene_id,
            compact_ase_atek_sample_id(source_ref.snippet_id),
            source_ref.split,
            source_ref.actor_store_version,
            source_ref.source_manifest_hash,
        )
        if actual != expected:
            raise ValueError(f"VIN source identity does not match rollout chain. {self._REBUILD_GUIDANCE}")
        return record


def _tensor_chain(
    stored: _StoredChain,
    snippet: VinSnippetView,
    *,
    static_context: QhStaticContext | None = None,
    require_rich_modalities: bool = False,
    audit: QhAudit | None = None,
) -> QhChain:
    """Tensorize one stored chain and construct strictly causal selected-pose history.

    Candidate rows retain stored widths before batch collation.
    ``candidate_mask`` records materialization, ``action_mask`` is its
    actor-valid subset, and ``label_mask`` is the label-supported subset of
    actor validity. Selected indices are factual rollout-policy actions. At
    state ``s``, history slots ``0`` through ``s-1`` contain those earlier
    selected poses in chronological order and every slot from ``s`` onward is
    masked out. Stored remaining budget, TD discount, and terminal state are
    copied without learner-specific reinterpretation.

    Args:
        stored: Complete CPU/NumPy rollout chain with ``S`` states and
            variable candidate-row widths.
        snippet: Chain-constant immutable VIN actor observation.

    Returns:
        :class:`QhChain` with float32 pose/reward tensors, int64 action/budget
        tensors, bool support/terminal tensors, and strict causal history.
    """

    candidate_pose = _stack_rows(stored.candidate_pose_relative_root, 0, torch.float32)
    action_mask = _stack_rows(stored.action_mask, False, torch.bool)
    label_mask = _stack_rows(stored.label_mask, False, torch.bool)
    reward = _stack_rows(stored.candidate_reward, 0, torch.float32)
    selected = _from_numpy(stored.selected_index, torch.int64)
    steps, width = action_mask.shape
    candidate_mask = torch.zeros((steps, width), dtype=torch.bool)
    for row, values in enumerate(stored.candidate_pose_relative_root):
        candidate_mask[row, : values.shape[0]] = True
    if bool((label_mask & ~action_mask).any() or (action_mask & ~candidate_mask).any()):
        raise ValueError("Q_H masks must satisfy label_mask <= action_mask <= candidate_mask.")
    history_pose = torch.zeros((steps, steps, 12), dtype=torch.float32)
    history_mask = torch.zeros((steps, steps), dtype=torch.bool)
    selected_pose = _gather_candidates(candidate_pose, selected)
    for step in range(1, steps):
        history_pose[step, :step] = selected_pose[:step]
        history_mask[step, :step] = True
    root_pose = PoseTW(_from_numpy(stored.root_pose_world, torch.float32))
    target_pose = PoseTW(_from_numpy(stored.target_pose_world_object, torch.float32))
    selected_observation_prefix = _selected_observation_prefix(stored, history_pose, history_mask)
    if require_rich_modalities and selected_observation_prefix is None:
        raise ValueError(
            "Q_H rich training requires aligned selected CF-GT depth; rebuild the rollout store with selected depth enabled."
        )
    return QhChain(
        actor=QhActorTensors(
            vin_snippet=snippet,
            root_pose_world=root_pose.tensor(),
            target_pose_relative_root=root_pose.inverse().compose(target_pose).tensor(),
            target_extents=_from_numpy(stored.target_extents, torch.float32),
            candidate_pose_relative_root=candidate_pose,
            candidate_mask=candidate_mask,
            action_mask=action_mask,
            history_pose_relative_root=history_pose,
            history_mask=history_mask,
            horizon_remaining=_from_numpy(stored.horizon_remaining, torch.int64),
            step_mask=torch.ones(steps, dtype=torch.bool),
            static_context=static_context,
            selected_observation_prefix=selected_observation_prefix,
        ),
        supervision=QhSupervision(
            label_mask=label_mask,
            candidate_reward=reward,
            selected_index=selected,
            discount=_from_numpy(stored.discount, torch.float32),
            terminal=_from_numpy(stored.terminal, torch.bool),
        ),
        key=QhChainKey(
            store_index=stored.store_index,
            rollout_row_id=stored.rollout_row_id,
            source_sample_index=stored.source_ref.source_sample_index,
            scene_id=stored.source_ref.scene_id,
            target_row_id=stored.target_row_id,
        ),
        audit=audit,
    )


def _read_static_context(
    actor_reader: VinOfflineStoreReader,
    record: VinOfflineIndexRecord,
    snippet: VinSnippetView,
) -> QhStaticContext | None:
    """Read root EVL evidence through the VIN-store owner when materialized."""

    read_backbone = getattr(actor_reader, "read_backbone_evidence", None)
    if not callable(read_backbone):
        return None
    backbone = read_backbone(record, device="cpu")
    if backbone is None:
        return None
    values = (
        backbone.t_world_voxel.tensor(),
        backbone.voxel_extent,
        backbone.occ_pr,
        backbone.occ_input,
        backbone.free_input,
        backbone.counts,
        backbone.cent_pr,
        backbone.pts_world,
    )
    return QhStaticContext(
        vin_snippet=snippet,
        t_world_voxel=values[0],
        voxel_extent=values[1],
        occ_pr=values[2],
        occ_input=values[3],
        free_input=values[4],
        counts=values[5],
        cent_pr=values[6],
        pts_world=values[7],
        evl_presence=torch.tensor([value is not None for value in values], dtype=torch.bool),
    )


def _selected_observation_prefix(
    stored: _StoredChain,
    history_pose: Tensor,
    history_mask: Tensor,
) -> QhSelectedObservationPrefix | None:
    """Materialize a no-future-observation CF-GT prefix for each chain state."""

    values = (
        getattr(stored, "selected_depth_m", None),
        getattr(stored, "selected_depth_valid_mask", None),
        getattr(stored, "selected_depth_focal_px", None),
        getattr(stored, "selected_depth_principal_point_px", None),
        getattr(stored, "selected_depth_image_size_hw", None),
        getattr(stored, "selected_depth_renderer", None),
    )
    if all(value is None for value in values):
        return None
    if any(value is None for value in values):
        raise ValueError("Q_H selected CF-GT depth payload is incomplete; rebuild the rollout store.")
    depth, valid, focal, principal, image_size, renderer = values
    assert isinstance(depth, np.ndarray)
    assert isinstance(valid, np.ndarray)
    assert isinstance(focal, np.ndarray)
    assert isinstance(principal, np.ndarray)
    assert isinstance(image_size, np.ndarray)
    if renderer != "Pytorch3DDepthRenderer":
        raise ValueError("Q_H selected observation must retain CF-GT Pytorch3D renderer provenance.")
    steps, height, width = depth.shape
    prefix_depth = torch.zeros((steps, steps, height, width), dtype=torch.float16)
    prefix_valid = torch.zeros((steps, steps, height, width), dtype=torch.bool)
    prefix_focal = torch.zeros((steps, steps, 2), dtype=torch.float32)
    prefix_principal = torch.zeros((steps, steps, 2), dtype=torch.float32)
    prefix_size = torch.zeros((steps, steps, 2), dtype=torch.int64)
    for state in range(1, steps):
        prefix_depth[state, :state] = _from_numpy(depth[:state], torch.float16)
        prefix_valid[state, :state] = _from_numpy(valid[:state], torch.bool)
        prefix_focal[state, :state] = _from_numpy(focal[:state], torch.float32)
        prefix_principal[state, :state] = _from_numpy(principal[:state], torch.float32)
        prefix_size[state, :state] = _from_numpy(image_size[:state], torch.int64)
    return QhSelectedObservationPrefix(
        depth_m=prefix_depth,
        valid_mask=prefix_valid,
        focal_px=prefix_focal,
        principal_point_px=prefix_principal,
        image_size_hw=prefix_size,
        camera_pose_relative_root=history_pose,
        prefix_mask=history_mask,
    )


def _audit_for(stored: _StoredChain, store_dir: Path) -> QhAudit:
    """Build CPU-only source and selected-depth provenance for explicit diagnostics."""

    return QhAudit(
        rollout_store_dir=str(store_dir),
        actor_store_version=stored.source_ref.actor_store_version,
        source_manifest_hash=stored.source_ref.source_manifest_hash,
        selected_depth_renderer=stored.selected_depth_renderer or "not_loaded",
    )


def _from_numpy(value: np.ndarray, dtype: torch.dtype) -> Tensor:
    """Copy a NumPy array into an owned CPU tensor with the requested dtype.

    Args:
        value: NumPy payload whose shape is preserved.
        dtype: Destination PyTorch dtype required by the Q_H DTO contract.

    Returns:
        Owned CPU tensor that cannot alias rollout-reader NumPy storage.
    """

    return torch.from_numpy(np.array(value, copy=True)).to(dtype=dtype)


def _stack_rows(values: tuple[np.ndarray, ...], fill: int | float | bool, dtype: torch.dtype) -> Tensor:
    """Tensorize variable-width NumPy rows into one rectangular CPU table.

    Args:
        values: Non-empty equal-rank state rows in chronological order.
        fill: Padding scalar appropriate to the field's factual support.
        dtype: Destination dtype shared by every row.

    Returns:
        Tensor with leading state axis ``S`` and remaining axes padded to their
        per-axis maxima. Padding does not create support; callers construct the
        corresponding masks explicitly.
    """

    return _pad([_from_numpy(value, dtype) for value in values], fill)


__all__ = ["QhDataset", "QhDatasetConfig"]
