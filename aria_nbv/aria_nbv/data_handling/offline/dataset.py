"""Runtime views over the strict immutable VIN offline dataset.

The VIN offline store is the frozen one-step substrate for current ARIA-NBV
training and diagnostics. It materializes ASE/EFM snippets into shard-local
numeric blocks plus optional MessagePack diagnostics, then exposes either:

- `VinOfflineSample` for diagnostics, Rerun/Streamlit inspection, rollout-root
  generation, and live attachment of raw snippets or meshes; or
- `VinOracleBatch` for Lightning/VIN training.

The store is intentionally strict: readers accept the current
`OFFLINE_DATASET_VERSION` only, split membership comes from file-backed arrays,
and `sample_index.jsonl` owns scene/snippet coverage. Rebuild stale stores with
`nbv-build-offline`; do not patch manifests, split arrays, or shard payloads by
hand.
"""

from __future__ import annotations

from collections.abc import Iterator, Mapping
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Literal

import numpy as np
import torch
from efm3d.aria.pose import PoseTW
from pydantic import Field, field_validator
from pytorch3d.renderer.cameras import PerspectiveCameras
from torch import Tensor
from torch.utils.data import Dataset

from ...configs import PathConfig
from ...pose_generation.types import CandidateSamplingResult
from ...rendering.candidate_depth_renderer import CandidateDepths
from ...rendering.candidate_pointclouds import CandidatePointClouds
from ...utils import BaseConfig, Console, TargetConfig, Verbosity
from ...utils.semantic_names import normalize_semantic_name_map
from ...vin.types import EvlBackboneOutput
from ..efm_dataset_utils import compact_ase_atek_sample_id, raw_ase_atek_sample_id
from ..raw import EfmSnippetLoader, EfmSnippetView, VinSnippetView
from .batch import CompactObbBlock, CompactTrajectoryBlock, VinOracleBatch
from .store import VinOfflineStoreConfig, VinOfflineStoreReader

if TYPE_CHECKING:
    from .format import VinOfflineIndexRecord


@dataclass(slots=True)
class VinOfflineOracleBlock:
    """Oracle-label block stored for one offline VIN sample. :py:module:`aria_nbv.data_handling` owns the typed boundary between upstream ASE/ATEK/EFM"""

    candidate_poses_world_cam: PoseTW
    """Candidate world←camera poses."""

    reference_pose_world_rig: PoseTW
    """Reference world←rig pose."""

    candidate_count: int
    """Number of valid candidates inside the fixed-width tensors."""

    rri: Tensor
    """Oracle RRI values per candidate."""

    pm_dist_before: Tensor
    """Pre-observation Chamfer distance per candidate."""

    pm_dist_after: Tensor
    """Post-observation Chamfer distance per candidate."""

    pm_acc_before: Tensor
    """Pre-observation accuracy distance per candidate."""

    pm_comp_before: Tensor
    """Pre-observation completeness distance per candidate."""

    pm_acc_after: Tensor
    """Post-observation accuracy distance per candidate."""

    pm_comp_after: Tensor
    """Post-observation completeness distance per candidate."""

    p3d_cameras: PerspectiveCameras
    """PyTorch3D cameras aligned with the candidate set."""


@dataclass(slots=True)
class VinOfflineSample:
    """Canonical root sample for diagnostics and rollout generation.

    `VinOfflineSample` is intentionally richer than `VinOracleBatch`: it keeps
    sample-index lineage, optional raw snippet/mesh attachments, and diagnostic
    blocks needed to regenerate counterfactual candidates. Model training still
    goes through `VinOracleBatch`, while rollout writers consume this sample
    shape and carry its source shard fields into standalone rollout stores.
    """

    sample_key: str
    """Stable dataset sample key."""

    scene_id: str
    """ASE scene identifier."""

    snippet_id: str
    """ASE snippet identifier."""

    vin_snippet: VinSnippetView
    """Minimal model-facing VIN snippet view."""

    oracle: VinOfflineOracleBlock
    """Oracle-label block stored for the sample."""

    sample_index: int = -1
    """Global zero-based sample index from ``sample_index.jsonl``."""

    split: str = "all"
    """Split membership from ``sample_index.jsonl``."""

    source_shard_id: str | None = None
    """VIN offline shard id that stores this immutable source row."""

    source_shard_row: int | None = None
    """Zero-based row offset inside ``source_shard_id`` used for rollout lineage."""

    candidates: CandidateSamplingResult | None = None
    """Optional candidate-sampling payload preserved for diagnostics."""

    backbone_out: EvlBackboneOutput | None = None
    """Optional cached EVL backbone outputs."""

    depths: CandidateDepths | None = None
    """Optional cached candidate depth maps."""

    candidate_pcs: CandidatePointClouds | None = None
    """Optional cached candidate point clouds."""

    efm_snippet_view: EfmSnippetView | None = None
    """Optional raw EFM snippet view attached live from the source dataset in `aria_nbv.data_handling`."""

    gt_obbs: CompactObbBlock | None = None
    """Optional compact GT OBBs decoded from persisted blocks."""

    detected_obbs: CompactObbBlock | None = None
    """Optional compact detected OBBs decoded from persisted blocks."""

    trajectory: CompactTrajectoryBlock | None = None
    """Optional persisted trajectory timing and gravity metadata."""


VinOfflineDatasetItem = VinOfflineSample | VinOracleBatch
"""Item returned by `VinOfflineDataset` depending on `return_format`."""


class VinOfflineDatasetConfig(TargetConfig["VinOfflineDataset"]):
    """Configuration for reading immutable VIN offline datasets."""

    @property
    def target_type(self) -> type["VinOfflineDataset"]:
        """Return the dataset factory target."""

        return VinOfflineDataset

    paths: PathConfig = Field(default_factory=PathConfig)
    """Project path resolver."""

    store: VinOfflineStoreConfig = Field(default_factory=VinOfflineStoreConfig)
    """Immutable VIN offline dataset location."""

    split: Literal["all", "train", "val"] = "all"
    """Subset of samples to expose."""

    limit: int | None = None
    """Optional cap on the number of exposed samples."""

    simplification: float | None = None
    """Optional fraction of the split to expose for debugging."""

    include_efm_snippet: bool = False
    """Whether to attach a live raw EFM snippet."""

    include_gt_mesh: bool = False
    """Whether the live raw snippet loader should attach GT meshes."""

    load_backbone: bool = True
    """Whether to decode cached backbone outputs."""

    load_candidates: bool = True
    """Whether to decode cached candidate-sampling payloads."""

    backbone_keep_fields: list[str] | None = None
    """Optional allowlist of backbone fields to materialize."""

    load_depths: bool = True
    """Whether to decode cached candidate depth maps."""

    load_candidate_pcs: bool = True
    """Whether to decode cached candidate point clouds."""

    load_gt_obbs: bool = True
    """Whether to decode compact GT OBB blocks."""

    load_detected_obbs: bool = True
    """Whether to decode compact detected OBB blocks."""

    load_trajectory_metadata: bool = True
    """Whether to decode compact trajectory timing/gravity blocks."""

    return_format: Literal["sample", "vin_batch"] = "sample"
    """Whether to return full offline samples or model-facing VIN batches."""

    map_location: torch.device = Field(default="cpu")
    """Device used for returned tensors."""

    verbosity: Verbosity = Verbosity.NORMAL
    """Verbosity level for dataset diagnostics."""

    _validate_map_location = field_validator("map_location", mode="before")(BaseConfig._resolve_device)


class VinOfflineDataset(Dataset[VinOfflineDatasetItem]):
    """Map-style random-access dataset backed by the immutable VIN offline store."""

    is_map_style: bool = True
    """Whether the dataset supports random access and batching."""

    def __init__(self, config: VinOfflineDatasetConfig) -> None:
        """Initialize the dataset reader and select split records.

        Args:
            config: Dataset configuration.
        """

        super().__init__()
        self.config = config
        self.console = Console.with_prefix(self.__class__.__name__).set_verbosity(config.verbosity)
        self._store = VinOfflineStoreReader(config.store)
        self.manifest = self._store.manifest
        self._records = self._select_records()
        self._record_by_pair = {(record.scene_id, record.snippet_id): record for record in self._records}
        self._loader_by_device: dict[str, EfmSnippetLoader] = {}

    def __getstate__(self) -> dict[str, Any]:
        """Drop worker-local loader state before pickling.

        Returns:
            Dataset state without worker-local loaders.
        """

        state = self.__dict__.copy()
        state["console"] = None
        state["_loader_by_device"] = {}
        state["_store"] = VinOfflineStoreReader(self.config.store)
        return state

    def __setstate__(self, state: dict[str, Any]) -> None:
        """Restore worker-local loader state after unpickling.

        Args:
            state: Pickled dataset state.
        """

        self.__dict__.update(state)
        if self.__dict__.get("console") is None:
            self.console = Console.with_prefix(self.__class__.__name__).set_verbosity(self.config.verbosity)
        if self.__dict__.get("_loader_by_device") is None:
            self._loader_by_device = {}
        if not isinstance(self.__dict__.get("_store"), VinOfflineStoreReader):
            self._store = VinOfflineStoreReader(self.config.store)

    def _select_records(self) -> list[VinOfflineIndexRecord]:
        """Apply split, simplification, and limit to the global index.

        Returns:
            Selected sample-index records.
        """

        records = self._store.get_split_records(self.config.split)
        if self.config.simplification is not None:
            target = int(len(records) * float(self.config.simplification))
            records = records[:target]
        if self.config.limit is not None:
            records = records[: int(self.config.limit)]
        return records

    def __len__(self) -> int:
        """Return the number of selected samples."""

        return len(self._records)

    def __getitem__(self, idx: int) -> VinOfflineSample | VinOracleBatch:
        """Return one offline sample or VIN batch.

        Args:
            idx: Zero-based position inside the selected split.

        Returns:
            ``VinOfflineSample`` or ``VinOracleBatch`` depending on the configured
            return format.
        """

        record = self._records[idx]
        if self.config.return_format == "vin_batch":
            return self._build_vin_batch(record)
        return self._build_sample(record)

    def __iter__(self) -> Iterator[VinOfflineSample | VinOracleBatch]:
        """Iterate samples in index order.

        Yields:
            Offline samples or VIN batches depending on configuration.
        """

        for idx in range(len(self)):
            yield self[idx]

    def _tensor(self, value: np.ndarray, *, dtype: torch.dtype | None = None) -> Tensor:
        """Convert a NumPy array into a tensor on the configured device.

        Args:
            value: NumPy array to convert.
            dtype: Optional target dtype.

        Returns:
            Tensor on the configured device.
        """

        tensor = torch.as_tensor(np.asarray(value), device=self.config.map_location)
        if dtype is not None:
            tensor = tensor.to(dtype=dtype)
        return tensor

    def _read_candidate_count(self, record: VinOfflineIndexRecord) -> int:
        """Read the number of valid candidates for one sample.

        Args:
            record: Sample-index record.

        Returns:
            Number of valid candidates.
        """

        count = int(self._store.read_numeric_block(record, "oracle.candidate_count").reshape(()))
        return max(count, 0)

    def _build_vin_snippet(self, record: VinOfflineIndexRecord) -> VinSnippetView:
        """Decode the model-facing VIN snippet block.

        Args:
            record: Sample-index record.

        Returns:
            Decoded VIN snippet view.
        """

        points_world = self._tensor(self._store.read_numeric_block(record, "vin.points_world"), dtype=torch.float32)
        lengths = self._tensor(self._store.read_numeric_block(record, "vin.lengths"), dtype=torch.int64).reshape(-1)
        t_world_rig = PoseTW(
            self._tensor(self._store.read_numeric_block(record, "vin.t_world_rig"), dtype=torch.float32)
        )
        return VinSnippetView(points_world=points_world, lengths=lengths, t_world_rig=t_world_rig)

    @staticmethod
    def _restore_padded_rows(values: Tensor, *, candidate_count: int) -> Tensor:
        """Copy the last valid row across the padded tail to keep runtime tensors usable."""

        if values.ndim == 0:
            return values
        total = int(values.shape[0])
        if candidate_count <= 0 or candidate_count >= total:
            return values
        restored = values.clone()
        restored[candidate_count:] = restored[candidate_count - 1 : candidate_count].expand_as(
            restored[candidate_count:]
        )
        return restored

    def _build_cameras(self, record: VinOfflineIndexRecord, candidate_count: int) -> PerspectiveCameras:
        """Decode PyTorch3D camera parameters for one sample.

        Args:
            record: Sample-index record.
            candidate_count: Number of valid candidates.

        Returns:
            PyTorch3D cameras aligned with the candidate set.
        """

        r = self._restore_padded_rows(
            self._tensor(self._store.read_numeric_block(record, "oracle.p3d.R"), dtype=torch.float32),
            candidate_count=candidate_count,
        )
        t = self._restore_padded_rows(
            self._tensor(self._store.read_numeric_block(record, "oracle.p3d.T"), dtype=torch.float32),
            candidate_count=candidate_count,
        )
        focal_length = self._restore_padded_rows(
            self._tensor(
                self._store.read_numeric_block(record, "oracle.p3d.focal_length"),
                dtype=torch.float32,
            ),
            candidate_count=candidate_count,
        )
        principal_point = self._restore_padded_rows(
            self._tensor(
                self._store.read_numeric_block(record, "oracle.p3d.principal_point"),
                dtype=torch.float32,
            ),
            candidate_count=candidate_count,
        )
        image_size = self._restore_padded_rows(
            self._tensor(
                self._store.read_numeric_block(record, "oracle.p3d.image_size"),
                dtype=torch.float32,
            ),
            candidate_count=candidate_count,
        )
        in_ndc = bool(self._store.read_numeric_block(record, "oracle.p3d.in_ndc").reshape(()))
        kwargs: dict[str, Any] = {
            "device": self.config.map_location,
            "R": r,
            "T": t,
            "focal_length": focal_length,
            "principal_point": principal_point,
            "image_size": image_size,
            "in_ndc": in_ndc,
        }
        if self._has_block("oracle.p3d.znear"):
            kwargs["znear"] = self._tensor(
                self._store.read_numeric_block(record, "oracle.p3d.znear"), dtype=torch.float32
            )
        if self._has_block("oracle.p3d.zfar"):
            kwargs["zfar"] = self._tensor(
                self._store.read_numeric_block(record, "oracle.p3d.zfar"), dtype=torch.float32
            )
        try:
            return PerspectiveCameras(**kwargs)
        except TypeError:
            kwargs.pop("znear", None)
            kwargs.pop("zfar", None)
            cameras = PerspectiveCameras(**kwargs)
            return cameras

    def _build_oracle(self, record: VinOfflineIndexRecord) -> VinOfflineOracleBlock:
        """Decode the stored oracle block for one sample.

        Args:
            record: Sample-index record.

        Returns:
            Decoded oracle block.
        """

        candidate_count = self._read_candidate_count(record)
        candidate_poses_tensor = self._restore_padded_rows(
            self._tensor(
                self._store.read_numeric_block(record, "oracle.candidate_poses_world_cam"),
                dtype=torch.float32,
            ),
            candidate_count=candidate_count,
        )
        candidate_poses = PoseTW(candidate_poses_tensor)
        reference_pose = PoseTW(
            self._tensor(
                self._store.read_numeric_block(record, "oracle.reference_pose_world_rig"), dtype=torch.float32
            ),
        )
        cameras = self._build_cameras(record, candidate_count)
        return VinOfflineOracleBlock(
            candidate_poses_world_cam=candidate_poses,
            reference_pose_world_rig=reference_pose,
            candidate_count=candidate_count,
            rri=self._tensor(self._store.read_numeric_block(record, "oracle.rri"), dtype=torch.float32),
            pm_dist_before=self._tensor(
                self._store.read_numeric_block(record, "oracle.pm_dist_before"),
                dtype=torch.float32,
            ),
            pm_dist_after=self._tensor(
                self._store.read_numeric_block(record, "oracle.pm_dist_after"),
                dtype=torch.float32,
            ),
            pm_acc_before=self._tensor(
                self._store.read_numeric_block(record, "oracle.pm_acc_before"),
                dtype=torch.float32,
            ),
            pm_comp_before=self._tensor(
                self._store.read_numeric_block(record, "oracle.pm_comp_before"),
                dtype=torch.float32,
            ),
            pm_acc_after=self._tensor(
                self._store.read_numeric_block(record, "oracle.pm_acc_after"),
                dtype=torch.float32,
            ),
            pm_comp_after=self._tensor(
                self._store.read_numeric_block(record, "oracle.pm_comp_after"),
                dtype=torch.float32,
            ),
            p3d_cameras=cameras,
        )

    def _build_candidates(self, record: VinOfflineIndexRecord) -> CandidateSamplingResult | None:
        """Decode cached candidate-sampling payloads when requested.

        Args:
            record: Sample-index record.

        Returns:
            Decoded candidate-sampling payload or ``None``.
        """

        if not self.config.load_candidates:
            return None
        payload = self._store.read_optional_record(record, "oracle.candidates")
        if payload is None:
            return None
        return CandidateSamplingResult.from_serializable(payload, device=None)

    def _has_block(self, block_name: str) -> bool:
        """Return whether the dataset contains one stored block.

        Args:
            block_name: Logical block name.

        Returns:
            ``True`` when at least one shard exposes the block.
        """

        return any(block_name in shard.blocks for shard in self.manifest.shards)

    def _build_backbone(self, record: VinOfflineIndexRecord) -> EvlBackboneOutput | None:
        """Decode cached backbone outputs when requested.

        Args:
            record: Sample-index record.

        Returns:
            Decoded backbone output or ``None``.
        """

        if not self.config.load_backbone:
            return None
        if not self.manifest.materialized_blocks.backbone:
            return None

        if self.config.return_format == "sample":
            payload = self._store.read_optional_record(record, "backbone.payload")
            if payload is not None:
                keep_fields = set(self.config.backbone_keep_fields) if self.config.backbone_keep_fields else None
                return EvlBackboneOutput.from_serializable(
                    payload,
                    device=self.config.map_location,
                    include_fields=keep_fields,
                )

        keep = set(self.config.backbone_keep_fields or [])

        def _keep(field_name: str) -> bool:
            return not keep or field_name in keep

        def _tensor_or_none(block_name: str, field_name: str, *, dtype: torch.dtype) -> Tensor | None:
            if not _keep(field_name) or not self._has_block(block_name):
                return None
            return self._tensor(self._store.read_numeric_block(record, block_name), dtype=dtype)

        return EvlBackboneOutput(
            t_world_voxel=PoseTW(
                self._tensor(self._store.read_numeric_block(record, "backbone.t_world_voxel"), dtype=torch.float32)
            ),
            voxel_extent=self._tensor(
                self._store.read_numeric_block(record, "backbone.voxel_extent"), dtype=torch.float32
            ),
            occ_pr=_tensor_or_none("backbone.occ_pr", "occ_pr", dtype=torch.float32),
            occ_input=_tensor_or_none("backbone.occ_input", "occ_input", dtype=torch.float32),
            free_input=_tensor_or_none("backbone.free_input", "free_input", dtype=torch.float32),
            counts=_tensor_or_none("backbone.counts", "counts", dtype=torch.int64),
            cent_pr=_tensor_or_none("backbone.cent_pr", "cent_pr", dtype=torch.float32),
            pts_world=_tensor_or_none("backbone.pts_world", "pts_world", dtype=torch.float32),
        )

    def _build_depths(self, record: VinOfflineIndexRecord, oracle: VinOfflineOracleBlock) -> CandidateDepths | None:
        """Decode cached candidate depth maps when requested.

        Args:
            record: Sample-index record.
            oracle: Decoded oracle block.

        Returns:
            Decoded candidate depth batch or ``None``.
        """

        if not self.config.load_depths:
            return None
        if not self.manifest.materialized_blocks.depths:
            return None
        if self.config.return_format == "sample":
            payload = self._store.read_optional_record(record, "oracle.depths_payload")
            if payload is not None:
                return CandidateDepths.from_serializable(payload, device=self.config.map_location)
        candidate_width = int(oracle.rri.shape[0])
        depths = self._tensor(self._store.read_numeric_block(record, "oracle.depths"), dtype=torch.float32)
        mask = self._tensor(self._store.read_numeric_block(record, "oracle.depths_valid_mask"), dtype=torch.bool)
        if self._has_block("oracle.candidate_indices"):
            indices = self._tensor(
                self._store.read_numeric_block(record, "oracle.candidate_indices"),
                dtype=torch.long,
            )
        else:
            indices = torch.arange(candidate_width, device=self.config.map_location, dtype=torch.long)
        return CandidateDepths(
            depths=depths,
            depths_valid_mask=mask,
            poses=oracle.candidate_poses_world_cam,
            reference_pose=oracle.reference_pose_world_rig,
            candidate_indices=indices,
            camera=oracle.p3d_cameras,
            p3d_cameras=oracle.p3d_cameras,
        )

    def _build_candidate_pcs(self, record: VinOfflineIndexRecord) -> CandidatePointClouds | None:
        """Decode cached candidate point clouds when requested.

        Args:
            record: Sample-index record.

        Returns:
            Decoded candidate point clouds or ``None``.
        """

        if not self.config.load_candidate_pcs:
            return None
        if not self.manifest.materialized_blocks.candidate_pcs:
            return None
        payload = self._store.read_optional_record(record, "oracle.candidate_pcs")
        if payload is None:
            return None
        return CandidatePointClouds.from_serializable(payload, device=self.config.map_location)

    def _build_gt_obbs(
        self,
        record: VinOfflineIndexRecord,
        efm_snippet: EfmSnippetView | None = None,
    ) -> CompactObbBlock | None:
        """Decode compact GT OBB tensors when requested and available."""

        if not self.config.load_gt_obbs:
            return None
        if not self.manifest.materialized_blocks.gt_obbs:
            if efm_snippet is None or efm_snippet.obbs is None:
                return None
            return CompactObbBlock(
                obbs=efm_snippet.obbs.obbs.tensor().detach().cpu().to(dtype=torch.float32),
                sem_id_to_name=self._normalize_semantic_names(efm_snippet.efm.get("obbs/sem_id_to_name")),
            )
        if not self._has_block("gt.obbs"):
            return None
        sem_id_to_name = self._normalize_semantic_names(
            self._store.read_optional_record(record, "gt.obb_sem_id_to_name")
        )
        return CompactObbBlock(
            obbs=self._tensor(self._store.read_numeric_block(record, "gt.obbs"), dtype=torch.float32),
            sem_id_to_name=sem_id_to_name,
        )

    def _build_detected_obbs(self, record: VinOfflineIndexRecord) -> CompactObbBlock | None:
        """Decode compact detected OBB tensors when requested and available."""

        if not self.config.load_detected_obbs:
            return None
        if not self.manifest.materialized_blocks.detected_obbs:
            return None
        if not self._has_block("detected.obbs"):
            return None
        probs = None
        if self._has_block("detected.obb_probs"):
            probs = self._tensor(self._store.read_numeric_block(record, "detected.obb_probs"), dtype=torch.float32)
        sem_id_to_name = self._normalize_semantic_names(
            self._store.read_optional_record(record, "detected.obb_sem_id_to_name")
        )
        return CompactObbBlock(
            obbs=self._tensor(self._store.read_numeric_block(record, "detected.obbs"), dtype=torch.float32),
            sem_id_to_name=sem_id_to_name,
            probs=probs,
        )

    @staticmethod
    def _normalize_semantic_names(value: object | None) -> dict[int, str] | None:
        """Normalize stored semantic maps to sparse integer-key dictionaries."""

        if value is None:
            return None
        if isinstance(value, (Mapping, list, tuple)):
            return normalize_semantic_name_map(value)
        return None

    def _build_trajectory_metadata(self, record: VinOfflineIndexRecord) -> CompactTrajectoryBlock | None:
        """Decode compact trajectory timing/gravity metadata."""

        if not self.config.load_trajectory_metadata:
            return None
        if not self.manifest.materialized_blocks.trajectory:
            return None
        time_ns = None
        gravity = None
        if self._has_block("vin.trajectory.time_ns"):
            time_ns = self._tensor(self._store.read_numeric_block(record, "vin.trajectory.time_ns"), dtype=torch.int64)
        if self._has_block("vin.trajectory.gravity_in_world"):
            gravity = self._tensor(
                self._store.read_numeric_block(record, "vin.trajectory.gravity_in_world"),
                dtype=torch.float32,
            )
        if time_ns is None and gravity is None:
            return None
        return CompactTrajectoryBlock(time_ns=time_ns, gravity_in_world=gravity)

    def _ensure_loader(self) -> EfmSnippetLoader:
        """Create or reuse the worker-local raw snippet loader.

        Returns:
            Worker-local raw snippet loader.
        """

        key = str(self.config.map_location)
        loader = self._loader_by_device.get(key)
        if loader is not None:
            return loader
        dataset_payload = dict(self.manifest.source.get("dataset_config", {}))
        loader = EfmSnippetLoader(
            dataset_payload=dataset_payload,
            device=key,
            paths=self.config.paths,
            include_gt_mesh=self.config.include_gt_mesh,
        )
        self._loader_by_device[key] = loader
        return loader

    def _attach_efm_snippet(self, record: VinOfflineIndexRecord, vin_snippet: VinSnippetView) -> EfmSnippetView | None:
        """Attach a live raw EFM snippet when requested.

        Args:
            record: Sample-index record.
            vin_snippet: Fallback VIN snippet used when live load fails.

        Returns:
            Live raw EFM snippet or ``None``.
        """

        if not self.config.include_efm_snippet:
            return None
        try:
            loader = self._ensure_loader()
            return loader.load(scene_id=record.scene_id, snippet_id=record.snippet_id)
        except Exception as exc:
            self.console.warn(
                f"Failed to attach raw EFM snippet for scene={record.scene_id} snippet={record.snippet_id}: {exc}",
            )
            _ = vin_snippet
            return None

    def _build_sample(self, record: VinOfflineIndexRecord) -> VinOfflineSample:
        """Decode one offline sample from the immutable store.

        Args:
            record: Sample-index record to decode.

        Returns:
            Decoded offline sample.
        """

        vin_snippet = self._build_vin_snippet(record)
        oracle = self._build_oracle(record)
        efm_snippet = self._attach_efm_snippet(record, vin_snippet)
        sample = VinOfflineSample(
            sample_key=record.sample_key,
            scene_id=record.scene_id,
            snippet_id=record.snippet_id,
            vin_snippet=vin_snippet,
            oracle=oracle,
            sample_index=int(record.sample_index),
            split=record.split,
            source_shard_id=record.shard_id,
            source_shard_row=int(record.row),
            candidates=self._build_candidates(record),
            backbone_out=self._build_backbone(record),
            depths=self._build_depths(record, oracle),
            candidate_pcs=self._build_candidate_pcs(record),
            efm_snippet_view=efm_snippet,
            gt_obbs=self._build_gt_obbs(record, efm_snippet),
            detected_obbs=self._build_detected_obbs(record),
            trajectory=self._build_trajectory_metadata(record),
        )
        return sample

    def _build_vin_batch(self, record: VinOfflineIndexRecord) -> VinOracleBatch:
        """Decode only the training-critical blocks required for a VIN batch."""

        vin_snippet = self._build_vin_snippet(record)
        oracle = self._build_oracle(record)
        efm_snippet = self._attach_efm_snippet(record, vin_snippet)
        return VinOracleBatch(
            efm_snippet_view=vin_snippet if efm_snippet is None else efm_snippet,
            candidate_poses_world_cam=oracle.candidate_poses_world_cam,
            reference_pose_world_rig=oracle.reference_pose_world_rig,
            rri=oracle.rri,
            pm_dist_before=oracle.pm_dist_before,
            pm_dist_after=oracle.pm_dist_after,
            pm_acc_before=oracle.pm_acc_before,
            pm_comp_before=oracle.pm_comp_before,
            pm_acc_after=oracle.pm_acc_after,
            pm_comp_after=oracle.pm_comp_after,
            p3d_cameras=oracle.p3d_cameras,
            candidate_count=torch.tensor(
                int(oracle.candidate_count),
                device=oracle.rri.device,
                dtype=torch.int64,
            ),
            scene_id=record.scene_id,
            snippet_id=record.snippet_id,
            backbone_out=self._build_backbone(record),
            gt_obbs=self._build_gt_obbs(record, efm_snippet),
            detected_obbs=self._build_detected_obbs(record),
            trajectory=self._build_trajectory_metadata(record),
        )

    def get_by_scene_snippet(
        self,
        *,
        scene_id: str,
        snippet_id: str,
    ) -> VinOfflineSample | None:
        """Look up one sample by ``(scene_id, snippet_id)``.

        Args:
            scene_id: ASE scene identifier.
            snippet_id: ASE snippet identifier.

        Returns:
            Matching offline sample or ``None``.
        """

        candidates = [snippet_id, compact_ase_atek_sample_id(snippet_id)]
        raw = raw_ase_atek_sample_id(snippet_id)
        if raw is not None:
            candidates.append(raw)
        record = None
        for candidate in dict.fromkeys(candidates):
            record = self._record_by_pair.get((scene_id, candidate))
            if record is not None:
                break
        if record is None:
            return None
        return self._build_sample(record)


__all__ = [
    "VinOfflineDataset",
    "VinOfflineDatasetConfig",
    "VinOfflineOracleBlock",
    "VinOfflineSample",
]
