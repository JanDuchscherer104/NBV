r"""Independent Oracle-GT endpoint evaluation for persisted rollout paths.

This module reopens one immutable VIN source row, rebuilds its Oracle-GT target,
and evaluates only the factual stored pose chain. Persisted gains and
point--mesh values are deliberately absent from the evaluator signature. The
source repository owns immutable-row identity; this pipeline owns calibrated
rendering, root/history fusion, target cropping, and terminal error measurement.

Theory:
    For root evidence $P_0$, selected-view evidence $P_{1:H}$, and target mesh
    crop $M_t$, the independent endpoint is

    $$
    J = \frac{\Delta(P_0,M_t)-\Delta(P_0\cup P_{1:H},M_t)}
             {\Delta(P_0,M_t)+\epsilon}.
    $$

    Invalid or unavailable evidence blocks evaluation. It is never converted
    into a low endpoint gain.
"""

from __future__ import annotations

import hashlib
import math
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
from time import perf_counter
from typing import Protocol, TypedDict, runtime_checkable

import msgspec
import numpy as np
import torch
from efm3d.aria.camera import CameraTW
from efm3d.aria.obb import ObbTW
from efm3d.aria.pose import PoseTW
from pydantic import Field, field_validator, model_validator

from ...configs import PathConfig
from ...data_handling.vin_store.dataset import VinOfflineDataset, VinOfflineDatasetConfig, VinOfflineSample
from ...oracle.evidence import (
    _OracleEvidenceError,
    build_root_eval_pointcloud,
    canonical_fuse_points,
    crop_mesh_to_obb,
    crop_points_to_obb,
    target_gt_obb_world,
)
from ...oracle.target_rri import TARGET_CROP_POLICY_GT_OBB_ORIENTED_ANY_VERTEX_V1, TargetRriScorerConfig
from ...oracle.target_selection import (
    ORACLE_TARGET_TASK_SOURCE,
    OracleTargetTask,
    OracleTargetTaskSampler,
    OracleTargetTaskSamplerConfig,
    TargetTaskIdentityStatus,
)
from ...pose_generation.types import CandidateSamplingResult
from ...rendering.candidate_pointclouds import build_candidate_pointclouds
from ...rollouts.read_model import (
    StoredEndpointEvaluationUnit,
    StoredEvaluationLineage,
    StoredRootActionSetIdentity,
    StoredSelectedPoseChain,
    StoredTarget,
    persisted_pre_treatment_context_sha256,
    selected_pose_chain_sha256,
)
from ...rollouts.scientific_audit import (
    EndpointAuditRow,
    EquivalenceVerdict,
    NamedSha256,
    PolicyMatchIdentity,
    RowEvaluationStatus,
    ScientificAuditConfig,
)
from ...rollouts.shard_manifest import read_rollout_source_manifest
from ...rri_metrics.point_mesh import chamfer_point_mesh
from ...targets.protocol import TargetInputProtocol
from ...utils import TargetConfig
from ...utils.fingerprints import stable_config_hash, stable_msgspec_hash


class EndpointEvaluationBlockedReason(StrEnum):
    """Stable reason codes for fail-closed endpoint evaluation."""

    UNSUPPORTED_TARGET_PROTOCOL = "unsupported_target_protocol"
    SOURCE_NOT_FOUND = "source_not_found"
    SOURCE_IDENTITY_MISMATCH = "source_identity_mismatch"
    SPLIT_IDENTITY_MISMATCH = "split_identity_mismatch"
    SOURCE_ROW_MISMATCH = "source_row_mismatch"
    CONFIG_IDENTITY_MISMATCH = "config_identity_mismatch"
    TARGET_NOT_FOUND = "target_not_found"
    TARGET_IDENTITY_MISMATCH = "target_identity_mismatch"
    MESH_MISSING = "mesh_missing"
    CALIBRATION_MISSING = "calibration_missing"
    ROOT_DEPTH_MISSING = "root_depth_missing"
    POSE_CHAIN_INVALID = "pose_chain_invalid"
    NONFINITE_GEOMETRY = "nonfinite_geometry"
    RENDER_FAILED = "render_failed"
    DEPTH_MISSING = "depth_missing"
    BACKPROJECTION_FAILED = "backprojection_failed"
    TARGET_CROP_FAILED = "target_crop_failed"
    SCORER_FAILED = "scorer_failed"


class EndpointEvaluationBlockedError(RuntimeError):
    """Typed control flow for an endpoint unit that cannot be evaluated."""

    def __init__(self, reason: EndpointEvaluationBlockedReason, message: str) -> None:
        super().__init__(f"{reason.value}: {message}")
        self.reason = reason
        """Stable machine-readable blocker reason."""
        self.message = message
        """Human-readable context safe for audit artifacts and UI blockers."""


@dataclass(frozen=True, slots=True)
class EndpointRawAssetSha256:
    """Full content identity for one independently reopened raw asset."""

    name: str
    """Stable asset role such as ``scene_mesh`` or ``target_mesh_crop``."""
    sha256: str
    """Lowercase 64-character SHA-256 content digest."""

    def __post_init__(self) -> None:
        if not self.name or len(self.sha256) != 64 or any(char not in "0123456789abcdef" for char in self.sha256):
            raise ValueError("Endpoint raw assets require a non-empty name and full lowercase SHA-256.")


@dataclass(frozen=True, slots=True)
class IndependentEndpointMeasurement:
    r"""Independent terminal target-quality measurement and provenance.

    Attributes:
        delta_0: Initial bidirectional point--mesh error in square metres.
        delta_h: Terminal error after all selected acquisitions, in square
            metres. A valid root-only early termination has
            ``delta_h == delta_0``.
        endpoint_gain: Root-normalized error reduction $J$.
        evaluation_cost_s: Wall-clock cost of source verification, rendering,
            fusion, cropping, and scoring in seconds.
        acquisition_path_length_m: Sum of root-to-selected and selected-to-
            selected camera-centre distances in metres.
    """

    delta_0: float
    r"""Initial independently recomputed target error $\Delta_0$."""
    delta_h: float
    r"""Terminal independently recomputed target error $\Delta_H$."""
    endpoint_gain: float
    r"""Dimensionless $(\Delta_0-\Delta_H)/(\Delta_0+\epsilon)$."""
    evaluation_cost_s: float
    """Non-negative evaluator wall-clock cost in seconds."""
    acquisition_path_length_m: float
    """Physical camera-centre path length for the selected acquisitions."""
    achieved_steps: int
    """Number of rendered selected poses in the factual chain."""
    source_store_sha256: str
    """Full canonical SHA-256 of the immutable VIN manifest payload."""
    split_manifest_sha256: str
    """Full canonical SHA-256 of the reviewed ordered split payload."""
    raw_assets: tuple[EndpointRawAssetSha256, ...]
    """Full hashes of source manifests, scene mesh, target OBB, and target crop."""

    def __post_init__(self) -> None:
        numeric = (
            self.delta_0,
            self.delta_h,
            self.endpoint_gain,
            self.evaluation_cost_s,
            self.acquisition_path_length_m,
        )
        if not all(np.isfinite(value) for value in numeric):
            raise ValueError("Independent endpoint measurements must be finite.")
        if self.delta_0 < 0.0 or self.delta_h < 0.0 or self.evaluation_cost_s < 0.0:
            raise ValueError("Endpoint errors and evaluator cost must be non-negative.")
        if self.acquisition_path_length_m < 0.0 or self.achieved_steps < 0:
            raise ValueError("Acquisition path length and achieved steps must be non-negative.")
        for digest in (self.source_store_sha256, self.split_manifest_sha256):
            if len(digest) != 64 or any(char not in "0123456789abcdef" for char in digest):
                raise ValueError("Endpoint source and split identities must be full lowercase SHA-256 values.")
        if len({asset.name for asset in self.raw_assets}) != len(self.raw_assets):
            raise ValueError("Endpoint raw-asset names must be unique.")


@runtime_checkable
class IndependentEndpointEvaluator(Protocol):
    """Evaluate a stored path without accepting any persisted comparator."""

    def evaluate(
        self,
        *,
        lineage: StoredEvaluationLineage,
        target: StoredTarget,
        pose_chain: StoredSelectedPoseChain,
    ) -> IndependentEndpointMeasurement:
        """Reopen source geometry and measure the factual selected path."""


class _EndpointRowIdentity(TypedDict):
    """Common frozen identity arguments for complete and blocked audit rows."""

    unit_id: str
    stratum_id: str
    match_identity: PolicyMatchIdentity
    rollout_row_id: int
    scene_id: str
    rollout_id: str
    source_sample_key: str
    target_id: str
    pose_chain_sha256: str


@dataclass(frozen=True, slots=True)
class ResolvedEndpointSource:
    """Strict source-row result supplied to the geometry evaluator."""

    sample: VinOfflineSample
    """VIN row with live EFM snippet, GT mesh, and GT OBB payload."""
    source_store_sha256: str
    """Full canonical immutable VIN manifest SHA-256."""
    split_manifest_sha256: str
    """Full canonical reviewed split SHA-256."""
    raw_assets: tuple[EndpointRawAssetSha256, ...] = ()
    """Source-owned raw manifest and row-asset hashes."""


class EndpointSourceRepository(Protocol):
    """Resolve and verify one immutable source row from persisted lineage."""

    def resolve(self, lineage: StoredEvaluationLineage) -> ResolvedEndpointSource:
        """Return the exact source row or raise a typed blocker."""


class OracleGtEndpointEvaluatorConfig(TargetConfig["OracleGtEndpointEvaluator"]):
    """Configure independent evaluation for the frozen Oracle-GT/v0 protocol."""

    @property
    def target_type(self) -> type["OracleGtEndpointEvaluator"]:
        """Return the independent Oracle-GT evaluator factory target."""

        return OracleGtEndpointEvaluator

    source: VinOfflineDatasetConfig = Field(
        default_factory=lambda: VinOfflineDatasetConfig(
            split=None,
            return_format="sample",
            include_efm_snippet=True,
            include_gt_mesh=True,
            load_backbone=False,
            load_candidates=False,
            load_depths=False,
            load_candidate_pcs=False,
            load_gt_obbs=True,
            load_detected_obbs=False,
            load_trajectory_metadata=True,
        )
    )
    """Immutable VIN reader configuration with live source and Oracle assets."""

    source_manifest_path: Path
    """Reviewed ordered rollout-source manifest used to verify split ownership."""

    expected_source_store_sha256: str
    """Required full SHA-256 of the configured immutable VIN manifest payload."""

    expected_split_manifest_sha256: str
    """Required full SHA-256 of the reviewed ordered split-manifest payload."""

    target_scorer: TargetRriScorerConfig = Field(default_factory=TargetRriScorerConfig)
    """Frozen render, root-evidence, fusion, crop, and point--mesh configuration."""

    expected_candidate_config_hashes: tuple[str, ...] = Field(min_length=1)
    """Approved candidate-config fingerprints for the evaluated cohort."""

    expected_rollout_config_hashes: tuple[str, ...] = Field(min_length=1)
    """Approved rollout-policy/config fingerprints for the evaluated cohort."""

    endpoint_epsilon: float = Field(default=1e-8, gt=0.0)
    """Positive denominator guard in the endpoint-gain definition."""

    @field_validator("source_manifest_path", mode="before")
    @classmethod
    def _resolve_source_manifest_path(cls, value: Path | str) -> Path:
        """Resolve the reviewed manifest through the project artifact contract."""

        return PathConfig().resolve_artifact_path(value, expected_suffix=".json", create_parent=False)

    @field_validator("expected_candidate_config_hashes", "expected_rollout_config_hashes")
    @classmethod
    def _validate_expected_hashes(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        normalized = tuple(item.strip().lower() for item in value)
        if any(
            len(item) not in {16, 64} or any(char not in "0123456789abcdef" for char in item) for item in normalized
        ):
            raise ValueError(
                "Expected config hashes must be canonical 16-character fingerprints or full SHA-256 values."
            )
        if len(set(normalized)) != len(normalized):
            raise ValueError("Expected config hashes must be unique.")
        return normalized

    @field_validator("expected_source_store_sha256", "expected_split_manifest_sha256")
    @classmethod
    def _validate_expected_full_hash(cls, value: str) -> str:
        normalized = value.strip().lower()
        if len(normalized) != 64 or any(char not in "0123456789abcdef" for char in normalized):
            raise ValueError("Expected source identities must be full lowercase SHA-256 values.")
        return normalized

    @model_validator(mode="after")
    def _validate_independent_source(self) -> "OracleGtEndpointEvaluatorConfig":
        if self.source.return_format != "sample":
            raise ValueError("Endpoint evaluation requires source.return_format='sample'.")
        if not self.source.include_efm_snippet or not self.source.include_gt_mesh or not self.source.load_gt_obbs:
            raise ValueError("Endpoint evaluation requires live EFM snippets, GT meshes, and GT OBBs.")
        if self.target_scorer.target_crop_policy != TARGET_CROP_POLICY_GT_OBB_ORIENTED_ANY_VERTEX_V1:
            raise ValueError("Endpoint evaluation supports only the frozen Oracle-GT target crop policy.")
        if self.target_scorer.eval_camera_label != "rgb":
            raise ValueError("Endpoint evaluation requires the source RGB CameraTW calibration template.")
        return self


class VinOfflineEndpointSourceRepository:
    """Open one configured VIN dataset and verify reviewed row lineage."""

    def __init__(self, config: OracleGtEndpointEvaluatorConfig) -> None:
        self.config = config
        dataset = config.source.setup_target()
        if not isinstance(dataset, VinOfflineDataset):
            raise TypeError("VinOfflineDatasetConfig did not construct VinOfflineDataset.")
        self._dataset = dataset
        self._manifest = read_rollout_source_manifest(config.source_manifest_path)
        self._manifest.validate()
        self._source_sha256 = stable_msgspec_hash(dataset.manifest, length=64)
        if self._source_sha256 != config.expected_source_store_sha256:
            raise EndpointEvaluationBlockedError(
                EndpointEvaluationBlockedReason.SOURCE_IDENTITY_MISMATCH,
                "Computed VIN manifest SHA-256 does not equal the explicitly configured source identity.",
            )
        self._verify_prefix(
            self._manifest.source_manifest_hash,
            self._source_sha256,
            EndpointEvaluationBlockedReason.SOURCE_IDENTITY_MISMATCH,
            "Reviewed source manifest does not match the configured immutable VIN manifest.",
        )
        split_payload = {
            "source_manifest_hash": self._manifest.source_manifest_hash,
            "split": self._manifest.split,
            "records": [row.hash_record() for row in self._manifest.rows],
        }
        self._split_sha256 = hashlib.sha256(msgspec.json.encode(split_payload)).hexdigest()
        if self._split_sha256 != config.expected_split_manifest_sha256:
            raise EndpointEvaluationBlockedError(
                EndpointEvaluationBlockedReason.SPLIT_IDENTITY_MISMATCH,
                "Computed reviewed split SHA-256 does not equal the explicitly configured split identity.",
            )
        self._verify_prefix(
            self._manifest.split_manifest_hash,
            self._split_sha256,
            EndpointEvaluationBlockedReason.SPLIT_IDENTITY_MISMATCH,
            "Reviewed split manifest has drifted from its ordered source rows.",
        )
        self._records_by_index = {int(record.sample_index): record for record in dataset._records}

    @staticmethod
    def _verify_prefix(
        persisted: str,
        full: str,
        reason: EndpointEvaluationBlockedReason,
        message: str,
    ) -> None:
        if not _hash_matches(persisted, full):
            raise EndpointEvaluationBlockedError(reason, message)

    def resolve(self, lineage: StoredEvaluationLineage) -> ResolvedEndpointSource:
        """Resolve one row after checking every persisted source identity."""

        self._verify_prefix(
            lineage.source_offline_store_manifest_hash,
            self._source_sha256,
            EndpointEvaluationBlockedReason.SOURCE_IDENTITY_MISMATCH,
            "Rollout source-store fingerprint does not match the configured immutable VIN store.",
        )
        self._verify_prefix(
            lineage.split_manifest_hash,
            self._split_sha256,
            EndpointEvaluationBlockedReason.SPLIT_IDENTITY_MISMATCH,
            "Rollout split fingerprint does not match the reviewed ordered source manifest.",
        )
        rows = [
            row
            for row in self._manifest.rows
            if int(row.sample_index) == int(lineage.source_sample_index)
            and row.sample_key == lineage.source_sample_key
            and row.source_shard_id == lineage.source_shard_id
            and int(row.source_shard_row) == int(lineage.source_shard_row)
        ]
        if len(rows) != 1:
            raise EndpointEvaluationBlockedError(
                EndpointEvaluationBlockedReason.SOURCE_ROW_MISMATCH,
                "Persisted source row is absent or ambiguous in the reviewed source manifest.",
            )
        row = rows[0]
        if row.scene_id != lineage.scene_id or row.snippet_id != lineage.snippet_id or row.split != lineage.split:
            raise EndpointEvaluationBlockedError(
                EndpointEvaluationBlockedReason.SOURCE_ROW_MISMATCH,
                "Persisted scene, snippet, or split differs from the reviewed source row.",
            )
        record = self._records_by_index.get(int(lineage.source_sample_index))
        if record is None or not row.matches_record(record):
            raise EndpointEvaluationBlockedError(
                EndpointEvaluationBlockedReason.SOURCE_ROW_MISMATCH,
                "Reviewed source row does not match sample_index.jsonl in the configured VIN store.",
            )
        try:
            dataset_position = self._dataset._records.index(record)
            sample = self._dataset[dataset_position]
        except Exception as exc:
            raise EndpointEvaluationBlockedError(
                EndpointEvaluationBlockedReason.SOURCE_NOT_FOUND,
                f"Failed to materialize immutable VIN source row: {exc}",
            ) from exc
        if not isinstance(sample, VinOfflineSample):
            raise EndpointEvaluationBlockedError(
                EndpointEvaluationBlockedReason.SOURCE_NOT_FOUND,
                "Configured VIN dataset returned a training batch instead of a source sample.",
            )
        if sample.efm_snippet_view is None:
            raise EndpointEvaluationBlockedError(
                EndpointEvaluationBlockedReason.SOURCE_NOT_FOUND,
                "The immutable source row could not attach its live EFM snippet.",
            )
        raw_assets = (
            EndpointRawAssetSha256("vin_manifest_json", _file_sha256(self.config.source.store.manifest_path)),
            EndpointRawAssetSha256("reviewed_source_manifest_json", _file_sha256(self.config.source_manifest_path)),
        )
        return ResolvedEndpointSource(
            sample=sample,
            source_store_sha256=self._source_sha256,
            split_manifest_sha256=self._split_sha256,
            raw_assets=raw_assets,
        )


class OracleGtEndpointEvaluator:
    """Re-render and score factual Oracle-GT rollout endpoints independently."""

    def __init__(
        self,
        config: OracleGtEndpointEvaluatorConfig,
        *,
        source_repository: EndpointSourceRepository | None = None,
    ) -> None:
        self.config = config
        self._source_repository = source_repository or VinOfflineEndpointSourceRepository(config)
        self._oracle_config_sha256 = stable_config_hash(config.target_scorer, length=64)

    def evaluate(
        self,
        *,
        lineage: StoredEvaluationLineage,
        target: StoredTarget,
        pose_chain: StoredSelectedPoseChain,
    ) -> IndependentEndpointMeasurement:
        r"""Evaluate one selected path from immutable geometry only.

        Args:
            lineage: Exact source, target, temporal, and config identities.
            target: Persisted target identity and geometry used only for
                equality checks against the independently rebuilt task.
            pose_chain: Root plus selected world-from-camera poses. No stored
                gain, RRI, or point--mesh comparator is accepted.

        Returns:
            :class:`IndependentEndpointMeasurement` with independently computed
            $\Delta_0$, $\Delta_H$, $J$, costs, and full content hashes.

        Raises:
            EndpointEvaluationBlockedError: If any required identity, source
                asset, geometry, rendering, crop, or score is unavailable.
        """

        started = perf_counter()
        self._validate_lineage_and_target(lineage, target)
        self._validate_pose_chain(pose_chain)
        try:
            source = self._source_repository.resolve(lineage)
        except EndpointEvaluationBlockedError:
            raise
        except Exception as exc:
            raise EndpointEvaluationBlockedError(
                EndpointEvaluationBlockedReason.SOURCE_NOT_FOUND,
                f"Failed to resolve the immutable source row: {exc}",
            ) from exc
        if source.source_store_sha256 != self.config.expected_source_store_sha256:
            raise EndpointEvaluationBlockedError(
                EndpointEvaluationBlockedReason.SOURCE_IDENTITY_MISMATCH,
                "Resolved source SHA-256 does not equal the evaluator's explicit source identity.",
            )
        if source.split_manifest_sha256 != self.config.expected_split_manifest_sha256:
            raise EndpointEvaluationBlockedError(
                EndpointEvaluationBlockedReason.SPLIT_IDENTITY_MISMATCH,
                "Resolved split SHA-256 does not equal the evaluator's explicit split identity.",
            )
        sample = source.sample
        snippet = sample.efm_snippet_view
        if snippet is None:
            raise EndpointEvaluationBlockedError(
                EndpointEvaluationBlockedReason.SOURCE_NOT_FOUND,
                "Resolved source sample has no live EFM snippet.",
            )
        if snippet.mesh_verts is None or snippet.mesh_faces is None or snippet.mesh is None:
            raise EndpointEvaluationBlockedError(
                EndpointEvaluationBlockedReason.MESH_MISSING,
                "Resolved source sample has no complete GT scene mesh.",
            )

        try:
            target_task = self._rebuild_target(sample, target, lineage)
        except EndpointEvaluationBlockedError:
            raise
        except Exception as exc:
            raise EndpointEvaluationBlockedError(
                EndpointEvaluationBlockedReason.TARGET_NOT_FOUND,
                f"Failed to rebuild the Oracle-GT target task: {exc}",
            ) from exc
        root_pose = PoseTW(torch.as_tensor(pose_chain.root_pose_world, dtype=torch.float32))
        try:
            root_eval = build_root_eval_pointcloud(
                snippet,
                source=self.config.target_scorer.eval_point_cloud_source,
                camera_label="rgb",
                reference_pose_world=root_pose,
                reference_time_ns=lineage.root_time_ns,
                reference_trajectory_index=lineage.root_trajectory_index,
                reference_frame_index=lineage.root_frame_index,
                stride=int(self.config.target_scorer.backprojection_stride),
                far_m=self.config.target_scorer.eval_depth_far_m,
                voxel_size_m=float(self.config.target_scorer.eval_fusion_voxel_size_m),
                max_points=None,
            )
        except _OracleEvidenceError as exc:
            reason = (
                EndpointEvaluationBlockedReason.ROOT_DEPTH_MISSING
                if "depth" in exc.reason.value or "frame" in exc.reason.value
                else EndpointEvaluationBlockedReason.NONFINITE_GEOMETRY
            )
            raise EndpointEvaluationBlockedError(reason, str(exc)) from exc
        except Exception as exc:
            raise EndpointEvaluationBlockedError(
                EndpointEvaluationBlockedReason.ROOT_DEPTH_MISSING,
                f"Failed to rebuild root evaluation points: {exc}",
            ) from exc

        history_points = self._render_history(sample, root_pose=root_pose, pose_chain=pose_chain)
        try:
            target_obb = target_gt_obb_world(target_task, sample)
            mesh_verts = snippet.mesh_verts.to(device=root_eval.points_world.device, dtype=torch.float32)
            mesh_faces = snippet.mesh_faces.to(device=root_eval.points_world.device, dtype=torch.long)
            target_mesh_verts, target_mesh_faces = crop_mesh_to_obb(
                mesh_verts,
                mesh_faces,
                target_obb.to(device=mesh_verts.device, dtype=mesh_verts.dtype),  # type: ignore[no-untyped-call]
                margin_m=float(self.config.target_scorer.target_crop_margin_m),
            )
            root_points = canonical_fuse_points(
                root_eval.points_world,
                voxel_size_m=float(self.config.target_scorer.eval_fusion_voxel_size_m),
                max_points=self.config.target_scorer.eval_fusion_max_points,
            )
            terminal_points = root_points
            if history_points.numel() > 0:
                terminal_points = canonical_fuse_points(
                    torch.cat([root_points, history_points.to(root_points)], dim=0),
                    voxel_size_m=float(self.config.target_scorer.eval_fusion_voxel_size_m),
                    max_points=self.config.target_scorer.eval_fusion_max_points,
                )
            root_target = crop_points_to_obb(
                root_points,
                target_obb.to(device=root_points.device, dtype=root_points.dtype),  # type: ignore[no-untyped-call]
                margin_m=float(self.config.target_scorer.target_crop_margin_m),
            )
            terminal_target = crop_points_to_obb(
                terminal_points,
                target_obb.to(device=terminal_points.device, dtype=terminal_points.dtype),  # type: ignore[no-untyped-call]
                margin_m=float(self.config.target_scorer.target_crop_margin_m),
            )
            root_target = canonical_fuse_points(
                root_target,
                voxel_size_m=float(self.config.target_scorer.eval_fusion_voxel_size_m),
                max_points=int(self.config.target_scorer.target_eval_max_points),
            )
            terminal_target = canonical_fuse_points(
                terminal_target,
                voxel_size_m=float(self.config.target_scorer.eval_fusion_voxel_size_m),
                max_points=int(self.config.target_scorer.target_eval_max_points),
            )
        except _OracleEvidenceError as exc:
            raise EndpointEvaluationBlockedError(
                EndpointEvaluationBlockedReason.TARGET_CROP_FAILED,
                str(exc),
            ) from exc
        except Exception as exc:
            raise EndpointEvaluationBlockedError(
                EndpointEvaluationBlockedReason.TARGET_CROP_FAILED,
                f"Failed to build independent target crops: {exc}",
            ) from exc

        minimum = int(self.config.target_scorer.min_current_target_points)
        if root_target.shape[0] < minimum or terminal_target.shape[0] < minimum:
            raise EndpointEvaluationBlockedError(
                EndpointEvaluationBlockedReason.TARGET_CROP_FAILED,
                f"Target crop support is below the configured minimum of {minimum} points.",
            )
        try:
            delta_0 = float(chamfer_point_mesh(root_target, target_mesh_verts, target_mesh_faces).bidirectional.item())
            delta_h = float(
                chamfer_point_mesh(terminal_target, target_mesh_verts, target_mesh_faces).bidirectional.item()
            )
        except Exception as exc:
            raise EndpointEvaluationBlockedError(
                EndpointEvaluationBlockedReason.SCORER_FAILED,
                f"Independent point--mesh scoring failed: {exc}",
            ) from exc
        if not np.isfinite(delta_0) or not np.isfinite(delta_h) or delta_0 < 0.0 or delta_h < 0.0:
            raise EndpointEvaluationBlockedError(
                EndpointEvaluationBlockedReason.NONFINITE_GEOMETRY,
                "Independent endpoint scoring produced a non-finite or negative error.",
            )
        endpoint_gain = (delta_0 - delta_h) / (delta_0 + float(self.config.endpoint_epsilon))
        raw_assets = (
            *source.raw_assets,
            *_geometry_asset_hashes(sample, target_obb, target_mesh_verts, target_mesh_faces),
        )
        return IndependentEndpointMeasurement(
            delta_0=delta_0,
            delta_h=delta_h,
            endpoint_gain=float(endpoint_gain),
            evaluation_cost_s=perf_counter() - started,
            acquisition_path_length_m=_pose_chain_path_length_m(pose_chain),
            achieved_steps=int(pose_chain.selected_poses_world_cam.shape[0]),
            source_store_sha256=source.source_store_sha256,
            split_manifest_sha256=source.split_manifest_sha256,
            raw_assets=tuple(sorted(raw_assets, key=lambda item: item.name)),
        )

    def _validate_lineage_and_target(self, lineage: StoredEvaluationLineage, target: StoredTarget) -> None:
        if lineage.target_protocol_version != TargetInputProtocol.V0_GT_INPUT.value:
            raise EndpointEvaluationBlockedError(
                EndpointEvaluationBlockedReason.UNSUPPORTED_TARGET_PROTOCOL,
                f"Only {TargetInputProtocol.V0_GT_INPUT.value!r} is supported, got {lineage.target_protocol_version!r}.",
            )
        if lineage.target_crop_policy != TARGET_CROP_POLICY_GT_OBB_ORIENTED_ANY_VERTEX_V1:
            raise EndpointEvaluationBlockedError(
                EndpointEvaluationBlockedReason.UNSUPPORTED_TARGET_PROTOCOL,
                f"Unsupported target crop policy {lineage.target_crop_policy!r}.",
            )
        if target.target_row_id != lineage.target_row_id or target.target_id != lineage.target_id:
            raise EndpointEvaluationBlockedError(
                EndpointEvaluationBlockedReason.TARGET_IDENTITY_MISMATCH,
                "Persisted target DTO does not match endpoint lineage.",
            )
        if target.source != ORACLE_TARGET_TASK_SOURCE or not target.target_valid or not target.gt_label_valid:
            raise EndpointEvaluationBlockedError(
                EndpointEvaluationBlockedReason.TARGET_IDENTITY_MISMATCH,
                "Endpoint evaluation requires a valid Oracle-GT target row.",
            )
        if not _hash_matches(lineage.oracle_config_hash, self._oracle_config_sha256):
            raise EndpointEvaluationBlockedError(
                EndpointEvaluationBlockedReason.CONFIG_IDENTITY_MISMATCH,
                "Stored oracle configuration does not match the independent evaluator configuration.",
            )
        if not any(
            _hash_matches(lineage.candidate_config_hash, item) for item in self.config.expected_candidate_config_hashes
        ):
            raise EndpointEvaluationBlockedError(
                EndpointEvaluationBlockedReason.CONFIG_IDENTITY_MISMATCH,
                "Stored candidate configuration is not approved by the evaluator cohort.",
            )
        if not any(
            _hash_matches(lineage.rollout_config_hash, item) for item in self.config.expected_rollout_config_hashes
        ):
            raise EndpointEvaluationBlockedError(
                EndpointEvaluationBlockedReason.CONFIG_IDENTITY_MISMATCH,
                "Stored rollout configuration is not approved by the evaluator cohort.",
            )

    @staticmethod
    def _validate_pose_chain(pose_chain: StoredSelectedPoseChain) -> None:
        root = np.asarray(pose_chain.root_pose_world)
        selected = np.asarray(pose_chain.selected_poses_world_cam)
        if root.shape != (12,) or selected.ndim != 2 or selected.shape[1:] != (12,):
            raise EndpointEvaluationBlockedError(
                EndpointEvaluationBlockedReason.POSE_CHAIN_INVALID,
                f"Expected root (12,) and selected (H,12), got {root.shape} and {selected.shape}.",
            )
        if selected.shape[0] != len(pose_chain.step_row_ids) or selected.shape[0] != len(
            pose_chain.selected_candidate_row_ids
        ):
            raise EndpointEvaluationBlockedError(
                EndpointEvaluationBlockedReason.POSE_CHAIN_INVALID,
                "Selected poses, step rows, and selected candidate rows are not aligned.",
            )
        if not np.isfinite(root).all() or not np.isfinite(selected).all():
            raise EndpointEvaluationBlockedError(
                EndpointEvaluationBlockedReason.NONFINITE_GEOMETRY,
                "Stored pose chain contains non-finite geometry.",
            )
        pose_rows = np.concatenate([root.reshape(1, 12), selected.reshape(-1, 12)], axis=0)
        rotations = PoseTW(torch.as_tensor(pose_rows, dtype=torch.float64)).R.detach().cpu().numpy().reshape(-1, 3, 3)
        orthogonality = rotations @ np.swapaxes(rotations, -1, -2)
        determinants = np.linalg.det(rotations)
        if not np.allclose(orthogonality, np.eye(3), atol=1e-3, rtol=1e-3) or not np.allclose(
            determinants, 1.0, atol=1e-3, rtol=1e-3
        ):
            raise EndpointEvaluationBlockedError(
                EndpointEvaluationBlockedReason.POSE_CHAIN_INVALID,
                "Stored pose chain contains a non-rigid rotation.",
            )

    @staticmethod
    def _rebuild_target(
        sample: VinOfflineSample,
        target: StoredTarget,
        lineage: StoredEvaluationLineage,
    ) -> OracleTargetTask:
        result = OracleTargetTaskSampler(OracleTargetTaskSamplerConfig(max_targets_per_sample=None, seed=0)).sample(
            sample
        )
        matches = [
            row
            for row in result.rows
            if row.target_id == lineage.target_id
            and int(row.source_index) == int(target.source_index)
            and int(row.target_row_id) == int(lineage.target_row_id)
        ]
        if len(matches) != 1:
            raise EndpointEvaluationBlockedError(
                EndpointEvaluationBlockedReason.TARGET_NOT_FOUND,
                "Persisted Oracle-GT target is absent or ambiguous after rebuilding the source target table.",
            )
        task = matches[0]
        descriptor = task.descriptor
        checks = (
            int(descriptor.sem_id) == int(target.sem_id),
            int(task.inst_id) == int(target.inst_id),
            descriptor.class_name == target.class_name,
            np.allclose(np.asarray(descriptor.center_world), target.center_world, atol=1e-5, rtol=1e-5),
            np.allclose(np.asarray(descriptor.extents_m), target.extents, atol=1e-5, rtol=1e-5),
            np.allclose(np.asarray(descriptor.pose_world_object), target.pose_world_object, atol=1e-5, rtol=1e-5),
            task.identity_status == TargetTaskIdentityStatus.MATCHED.value,
        )
        if not all(checks):
            raise EndpointEvaluationBlockedError(
                EndpointEvaluationBlockedReason.TARGET_IDENTITY_MISMATCH,
                "Rebuilt Oracle-GT target geometry or semantic identity differs from the persisted target row.",
            )
        return task

    def _render_history(
        self,
        sample: VinOfflineSample,
        *,
        root_pose: PoseTW,
        pose_chain: StoredSelectedPoseChain,
    ) -> torch.Tensor:
        count = int(pose_chain.selected_poses_world_cam.shape[0])
        if count == 0:
            return torch.empty((0, 3), dtype=torch.float32)
        snippet = sample.efm_snippet_view
        if snippet is None:
            raise EndpointEvaluationBlockedError(
                EndpointEvaluationBlockedReason.SOURCE_NOT_FOUND,
                "Resolved source sample has no live EFM snippet.",
            )
        try:
            camera_template = snippet.get_camera("rgb").calib
        except Exception as exc:
            raise EndpointEvaluationBlockedError(
                EndpointEvaluationBlockedReason.CALIBRATION_MISSING,
                f"Source RGB calibration is unavailable: {exc}",
            ) from exc
        poses = PoseTW(torch.as_tensor(pose_chain.selected_poses_world_cam, dtype=torch.float32))
        try:
            candidates = _candidate_table_from_world_poses(
                reference_pose=root_pose,
                poses_world_cam=poses,
                camera_template=camera_template,
            )
        except Exception as exc:
            raise EndpointEvaluationBlockedError(
                EndpointEvaluationBlockedReason.CALIBRATION_MISSING,
                f"Failed to compose calibration-bearing selected candidates: {exc}",
            ) from exc
        try:
            renderer = self.config.target_scorer.depth.setup_target()
            depths = renderer.render_compact_indices(snippet, candidates, tuple(range(count)))
        except Exception as exc:
            raise EndpointEvaluationBlockedError(
                EndpointEvaluationBlockedReason.RENDER_FAILED,
                f"Failed to render the complete selected pose chain: {exc}",
            ) from exc
        if depths.depths.shape[0] != count or not bool(depths.depths_valid_mask.reshape(count, -1).any(dim=1).all()):
            raise EndpointEvaluationBlockedError(
                EndpointEvaluationBlockedReason.DEPTH_MISSING,
                "At least one selected pose has no valid independently rendered depth.",
            )
        try:
            clouds = build_candidate_pointclouds(
                snippet,
                depths,
                stride=int(self.config.target_scorer.backprojection_stride),
            )
        except Exception as exc:
            raise EndpointEvaluationBlockedError(
                EndpointEvaluationBlockedReason.BACKPROJECTION_FAILED,
                f"Selected-depth backprojection failed: {exc}",
            ) from exc
        if clouds.lengths.numel() != count or bool(torch.any(clouds.lengths <= 0).item()):
            raise EndpointEvaluationBlockedError(
                EndpointEvaluationBlockedReason.DEPTH_MISSING,
                "At least one selected pose backprojected to an empty point cloud.",
            )
        rows = [clouds.points[index, : int(clouds.lengths[index].item()), :3] for index in range(count)]
        points = torch.cat(rows, dim=0)
        if points.numel() == 0 or not bool(torch.isfinite(points).all().item()):
            raise EndpointEvaluationBlockedError(
                EndpointEvaluationBlockedReason.NONFINITE_GEOMETRY,
                "Selected-view point clouds are empty or non-finite.",
            )
        return points


def build_endpoint_audit_row(
    evaluator: IndependentEndpointEvaluator,
    *,
    unit: StoredEndpointEvaluationUnit,
    target: StoredTarget,
    audit_config: ScientificAuditConfig,
    match_identity: PolicyMatchIdentity,
    root_action_identity: StoredRootActionSetIdentity,
    unit_id: str,
    stratum_id: str,
) -> EndpointAuditRow:
    r"""Evaluate one frozen unit and attach its separated persisted comparator.

    The evaluator receives only source lineage, target identity, and the factual
    pose chain. After evaluation, this bridge computes the thesis endpoint

    $$J=(\Delta_0-\Delta_H)/(\Delta_0+\epsilon)$$

    and the distinct persisted-contract comparator

    $$G_H^{\mathrm{ind}}=(\Delta_0-\Delta_H)/\max(\Delta_0,10^{-12}).$$

    Args:
        evaluator: Independent geometry evaluator with no comparator input.
        unit: Frozen persisted endpoint unit whose comparator remains separate.
        target: Target DTO corresponding exactly to ``unit.lineage``.
        audit_config: Frozen endpoint and equivalence tolerances.
        match_identity: Frozen treatment and exact non-treatment pairing key.
        root_action_identity: Persisted step-zero action-table identity.
        unit_id: Globally unique sampled-unit identity.
        stratum_id: Predeclared sampling-stratum identity.

    Returns:
        A complete pass/fail row, or a typed blocked row when independent
        evaluation cannot be performed. Blocked units are retained rather than
        replaced or interpreted as low gain.
    """

    if root_action_identity.rollout_row_id != unit.lineage.rollout_row_id:
        raise ValueError("Root action-set identity belongs to a different rollout row.")
    if root_action_identity.budget != unit.budget:
        raise ValueError("Root action-set identity budget differs from the endpoint unit.")
    if root_action_identity.sha256 != match_identity.root_action_set_sha256:
        raise ValueError("Root action-set identity differs from the frozen policy match identity.")
    persisted_context_sha256 = persisted_pre_treatment_context_sha256(
        unit.lineage,
        target,
        root_action_identity,
    )
    if persisted_context_sha256 != match_identity.persisted_context_sha256:
        raise ValueError("Persisted pre-treatment context differs from the frozen policy match identity.")

    identity: _EndpointRowIdentity = {
        "unit_id": unit_id,
        "stratum_id": stratum_id,
        "match_identity": match_identity,
        "rollout_row_id": unit.lineage.rollout_row_id,
        "scene_id": unit.lineage.scene_id,
        "rollout_id": unit.lineage.rollout_id,
        "source_sample_key": unit.lineage.source_sample_key,
        "target_id": unit.lineage.target_id,
        "pose_chain_sha256": selected_pose_chain_sha256(unit.pose_chain),
    }
    try:
        measurement = evaluator.evaluate(
            lineage=unit.lineage,
            target=target,
            pose_chain=unit.pose_chain,
        )
        if measurement.achieved_steps != unit.achieved_steps:
            raise EndpointEvaluationBlockedError(
                EndpointEvaluationBlockedReason.POSE_CHAIN_INVALID,
                "Independent evaluator step count differs from the frozen endpoint unit.",
            )
        comparator_gain = float(unit.comparator.gain)
        if not math.isfinite(comparator_gain):
            raise EndpointEvaluationBlockedError(
                EndpointEvaluationBlockedReason.CONFIG_IDENTITY_MISMATCH,
                "Persisted endpoint comparator is non-finite.",
            )
    except EndpointEvaluationBlockedError as exc:
        return EndpointAuditRow(
            **identity,
            source_store_sha256=None,
            split_manifest_sha256=None,
            raw_assets=(),
            evaluation_status=RowEvaluationStatus.BLOCKED,
            delta_0=None,
            delta_h=None,
            endpoint_gain=None,
            comparator_gain=None,
            independent_comparator_gain=None,
            comparator_gamma=None,
            absolute_error=None,
            relative_error=None,
            equivalence_verdict=EquivalenceVerdict.BLOCKED,
            achieved_steps=None,
            budget=None,
            termination_reason=None,
            path_length_m=None,
            evaluation_cost_s=None,
            missing_reason=f"{exc.reason.value}: {exc.message}",
        )

    delta_0 = measurement.delta_0
    delta_h = measurement.delta_h
    endpoint_gain = (delta_0 - delta_h) / (delta_0 + audit_config.endpoint_epsilon)
    independent_comparator_gain = (delta_0 - delta_h) / max(delta_0, audit_config.comparator_epsilon)
    absolute_error = abs(independent_comparator_gain - comparator_gain)
    relative_error = absolute_error / max(
        abs(independent_comparator_gain),
        abs(comparator_gain),
        audit_config.comparator_epsilon,
    )
    equivalent = math.isclose(
        independent_comparator_gain,
        comparator_gain,
        rel_tol=audit_config.relative_tolerance,
        abs_tol=audit_config.absolute_tolerance,
    )
    return EndpointAuditRow(
        **identity,
        source_store_sha256=measurement.source_store_sha256,
        split_manifest_sha256=measurement.split_manifest_sha256,
        raw_assets=tuple(
            sorted(
                (NamedSha256(name=item.name, sha256=item.sha256) for item in measurement.raw_assets),
                key=lambda item: item.name,
            )
        ),
        evaluation_status=RowEvaluationStatus.COMPLETE,
        delta_0=delta_0,
        delta_h=delta_h,
        endpoint_gain=endpoint_gain,
        comparator_gain=comparator_gain,
        independent_comparator_gain=independent_comparator_gain,
        comparator_gamma=unit.comparator.gamma,
        absolute_error=absolute_error,
        relative_error=relative_error,
        equivalence_verdict=EquivalenceVerdict.PASS if equivalent else EquivalenceVerdict.FAIL,
        achieved_steps=measurement.achieved_steps,
        budget=unit.budget,
        termination_reason=unit.termination_reason,
        path_length_m=measurement.acquisition_path_length_m,
        evaluation_cost_s=measurement.evaluation_cost_s,
        missing_reason=None,
    )


def _candidate_table_from_world_poses(
    *,
    reference_pose: PoseTW,
    poses_world_cam: PoseTW,
    camera_template: CameraTW,
) -> CandidateSamplingResult:
    """Rebuild calibration-bearing candidates with generator transform semantics."""

    pose_rows = poses_world_cam.tensor().reshape(-1, 12)  # type: ignore[no-untyped-call]
    count = int(pose_rows.shape[0])
    template = camera_template.tensor()  # type: ignore[no-untyped-call]
    if template.numel() == 0:
        raise ValueError("RGB camera calibration template is empty.")
    if template.ndim == 1:
        template = template.reshape(1, -1)
    camera_rows = template[0].to(device=pose_rows.device, dtype=pose_rows.dtype).expand(count, -1).clone()
    poses_ref_cam = reference_pose.inverse().compose(poses_world_cam)
    poses_cam_ref = poses_ref_cam.inverse()
    camera_rows[:, CameraTW.T_CAM_RIG_IND] = poses_cam_ref.tensor().reshape(  # type: ignore[no-untyped-call]
        count, 12
    )
    return CandidateSamplingResult(
        views=CameraTW(camera_rows),
        reference_pose=reference_pose,
        mask_valid=torch.ones(count, device=pose_rows.device, dtype=torch.bool),
        masks={},
        shell_poses=poses_world_cam,
    )


def _geometry_asset_hashes(
    sample: VinOfflineSample,
    target_obb: ObbTW,
    target_mesh_verts: torch.Tensor,
    target_mesh_faces: torch.Tensor,
) -> tuple[EndpointRawAssetSha256, ...]:
    snippet = sample.efm_snippet_view
    assert snippet is not None and snippet.mesh_verts is not None and snippet.mesh_faces is not None
    return (
        EndpointRawAssetSha256(
            "scene_mesh",
            _tensor_bundle_sha256((snippet.mesh_verts, snippet.mesh_faces)),
        ),
        EndpointRawAssetSha256(
            "target_obb_world",
            _tensor_bundle_sha256((target_obb.tensor(),)),  # type: ignore[no-untyped-call]
        ),
        EndpointRawAssetSha256(
            "target_mesh_crop",
            _tensor_bundle_sha256((target_mesh_verts, target_mesh_faces)),
        ),
    )


def _tensor_bundle_sha256(tensors: tuple[torch.Tensor, ...]) -> str:
    digest = hashlib.sha256()
    for tensor in tensors:
        array = tensor.detach().cpu().contiguous().numpy()
        digest.update(str(array.dtype).encode("ascii"))
        digest.update(np.asarray(array.shape, dtype=np.int64).tobytes())
        digest.update(array.tobytes())
    return digest.hexdigest()


def _file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _hash_matches(left: str, right: str) -> bool:
    left_normalized = left.strip().lower()
    right_normalized = right.strip().lower()
    if len(left_normalized) not in {16, 64} or len(right_normalized) not in {16, 64}:
        return False
    if any(char not in "0123456789abcdef" for char in left_normalized + right_normalized):
        return False
    if len(left_normalized) == len(right_normalized):
        return left_normalized == right_normalized
    short, full = sorted((left_normalized, right_normalized), key=len)
    return full[:16] == short


def _pose_chain_path_length_m(pose_chain: StoredSelectedPoseChain) -> float:
    rows = np.concatenate(
        [
            np.asarray(pose_chain.root_pose_world, dtype=np.float64).reshape(1, 12),
            np.asarray(pose_chain.selected_poses_world_cam, dtype=np.float64).reshape(-1, 12),
        ],
        axis=0,
    )
    if rows.shape[0] <= 1:
        return 0.0
    centers = PoseTW(torch.as_tensor(rows, dtype=torch.float64)).t.detach().cpu().numpy().reshape(-1, 3)
    return float(np.linalg.norm(np.diff(centers, axis=0), axis=1).sum())


__all__ = [
    "EndpointEvaluationBlockedError",
    "EndpointEvaluationBlockedReason",
    "EndpointRawAssetSha256",
    "EndpointSourceRepository",
    "IndependentEndpointEvaluator",
    "IndependentEndpointMeasurement",
    "OracleGtEndpointEvaluator",
    "OracleGtEndpointEvaluatorConfig",
    "ResolvedEndpointSource",
    "VinOfflineEndpointSourceRepository",
    "build_endpoint_audit_row",
]
