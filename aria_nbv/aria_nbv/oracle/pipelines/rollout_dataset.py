"""Build standalone target-RRI rollout replay stores from VIN offline rows.

This module owns the first rollout-data generation path, not a migration of the
immutable VIN offline cache. It reads `VinOfflineDataset` samples with live
`EfmSnippetView` snippets and GT meshes attached, samples oracle target tasks,
generates fixed-count mixed candidate tables, scores valid candidates with the
target-cropped oracle, and writes a separate `rollouts.zarr` store.

The generated store must be interpretable as replay data for finite-candidate
value learning. Lineage includes source manifest hashes, split hashes,
candidate/oracle/rollout config hashes, selected target records, GT match audit
fields, candidate strategy provenance, and rollout policy identifiers. Invalid
targets or actions are skipped or masked with reason codes; they are never
encoded as low target RRI.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Protocol

import torch
from pydantic import Field, field_validator, model_validator

from ...configs import PathConfig
from ...data_handling.vin_store.dataset import VinOfflineDataset, VinOfflineDatasetConfig, VinOfflineSample
from ...oracle.target_rri import TargetRriScorerConfig
from ...oracle.target_selection import (
    ORACLE_TARGET_TASK_SOURCE,
    TARGET_INVALID_REASON_CODES,
    TARGET_INVALID_REASON_VERSION,
    OracleTargetTask,
    OracleTargetTaskSampler,
    OracleTargetTaskSamplerConfig,
    OracleTargetTaskSelectionPolicy,
    TargetTaskIdentityStatus,
)
from ...pose_generation import (
    CandidateGenerationRuntimeContext,
    CandidateMixtureViewGeneratorConfig,
)
from ...rendering import CandidateDepthRenderer, CandidateDepthRendererConfig
from ...rollouts.manifest import RolloutStoreInvocation, RolloutStoreManifestContext, collect_runtime_provenance
from ...rollouts.replay.engine import CounterfactualPoseGeneratorConfig
from ...rollouts.replay.policy import CounterfactualSelectionPolicy, RolloutPolicySpec
from ...rollouts.replay.state import CounterfactualRolloutResult
from ...rollouts.shard_manifest import (
    RolloutShardEntry,
    RolloutShardRow,
    RolloutSourceManifest,
    build_rollout_split_manifest_hash,
    read_rollout_source_manifest,
)
from ...rollouts.trace import INVALID_REASON_VERSION, PolicyLineage, RolloutLineage, SourceLineage, TargetLineage
from ...rollouts.zarr_store import (
    RolloutZarrStoreConfig,
    RolloutZarrWriteResult,
    validate_rollout_zarr_store,
    write_rollout_zarr_store,
)
from ...targets import ObservedTargetDescriptor
from ...targets.protocol import (
    TargetDescriptorProvenance,
    TargetInputProtocol,
    validate_target_protocol_admission,
)
from ...utils import BaseConfig, Console, TargetConfig, Verbosity
from ...utils.fingerprints import stable_config_hash, stable_msgspec_hash
from .evaluated_rollout import (
    EvaluatedRollout,
    EvaluatedRolloutRecord,
    OracleReplayAdapter,
    OracleReplayInvalidityError,
)


@dataclass(slots=True)
class RolloutDatasetWriterStats:
    """Counters reported by one rollout-store build.

    The counters are operational diagnostics for local smoke builds. They are
    not dataset labels; invalidity details that affect training/evaluation must
    also be represented in rollout trace masks and lineage.
    """

    samples_seen: int = 0
    """Number of VIN source rows visited by the writer."""

    samples_without_snippet_or_mesh: int = 0
    """Rows skipped because live snippet evidence or oracle mesh was absent."""

    targets_selected: int = 0
    """Target tasks admitted for rollout generation before label-validity gates."""

    targets_label_invalid: int = 0
    """Selected targets lacking an admissible oracle evaluation label."""

    target_invalid_skips: int = 0
    """Targets skipped by target-level validity requirements."""

    rollout_invalid_skips: int = 0
    """Generated roots skipped because rollout-level action checks failed."""

    rollouts_written: int = 0
    """Root-target-recipe records handed to standalone Zarr persistence."""

    skipped_reasons: dict[str, int] = field(default_factory=dict)
    """Operational skip counts keyed by stable diagnostic reason."""

    def skip(self, reason: str) -> None:
        """Increment one operational skip reason without creating a label.

        Training-relevant invalidity must still be represented by explicit
        trace masks and versioned reason codes; this counter is build telemetry
        only.
        """

        self.skipped_reasons[reason] = self.skipped_reasons.get(reason, 0) + 1


class InsufficientRootSupportError(RuntimeError):
    """Typed preflight outcome that must not create a rollout store."""

    def __init__(self, reason: str) -> None:
        self.reason = reason
        super().__init__(reason)


@dataclass(frozen=True, slots=True)
class ExplicitRolloutTarget:
    """Immutable V1 observed target consumed by one rollout writer unit."""

    sample_key: str
    actor_descriptor: ObservedTargetDescriptor
    detected_source_row: int
    gt_match_row: int
    gt_match_id: str
    oriented_iou: float
    status: str
    reason: str
    target_id: str
    protocol: TargetInputProtocol = TargetInputProtocol.V1_OBSERVED
    explicit_target_hash: str = ""

    def __post_init__(self) -> None:
        if self.protocol is not TargetInputProtocol.V1_OBSERVED:
            raise ValueError("ExplicitRolloutTarget requires protocol v1_observed.")
        if self.sample_key != self.actor_descriptor.sample_key or self.target_id != self.actor_descriptor.target_id:
            raise ValueError("Explicit target identity does not match its actor descriptor.")
        if not 0.0 <= float(self.oriented_iou) <= 1.0:
            raise ValueError("oriented_iou must be in [0, 1].")


class ExplicitRolloutTargetConfig(BaseConfig):
    """Discriminated configuration for one explicit observed target."""

    protocol: TargetInputProtocol = TargetInputProtocol.V1_OBSERVED
    sample_key: str
    actor_descriptor: ObservedTargetDescriptor
    detected_source_row: int = Field(ge=0)
    gt_match_row: int = Field(ge=0)
    gt_match_id: str
    oriented_iou: float = Field(ge=0.0, le=1.0)
    status: str = "admitted"
    reason: str = "admitted"
    target_id: str
    explicit_target_hash: str

    @model_validator(mode="after")
    def _validate_identity(self) -> "ExplicitRolloutTargetConfig":
        if self.protocol is not TargetInputProtocol.V1_OBSERVED:
            raise ValueError("explicit target protocol must be v1_observed")
        if self.status != "admitted" or self.reason != "admitted":
            raise ValueError("explicit target must be admitted with reason=admitted")
        if self.sample_key != self.actor_descriptor.sample_key or self.target_id != self.actor_descriptor.target_id:
            raise ValueError("explicit target sample/target identity mismatch")
        if not self.gt_match_id or not self.explicit_target_hash:
            raise ValueError("explicit target requires GT match id and stable hash")
        expected = stable_msgspec_hash(
            {
                "sample_key": self.sample_key,
                "target_id": self.target_id,
                "detected_source_row": self.detected_source_row,
                "gt_match_row": self.gt_match_row,
                "gt_match_id": self.gt_match_id,
                "oriented_iou": self.oriented_iou,
                "descriptor_hash": self.actor_descriptor.descriptor_hash,
            }
        )
        if self.explicit_target_hash != expected:
            raise ValueError("explicit_target_hash does not match explicit target identity")
        return self

    def setup_target(self) -> ExplicitRolloutTarget:
        """Materialize the immutable runtime DTO without sampling."""
        return ExplicitRolloutTarget(
            sample_key=self.sample_key,
            actor_descriptor=self.actor_descriptor,
            detected_source_row=self.detected_source_row,
            gt_match_row=self.gt_match_row,
            gt_match_id=self.gt_match_id,
            oriented_iou=self.oriented_iou,
            status=self.status,
            reason=self.reason,
            target_id=self.target_id,
            protocol=self.protocol,
            explicit_target_hash=self.explicit_target_hash,
        )

    setup_runtime = setup_target


class RolloutRecipeConfig(BaseConfig):
    """One rollout policy recipe materialized into the replay store.

    Recipes control both candidate-set sampling and action selection. The first
    supported policies cover random valid selection, greedy oracle selection,
    retained-beam oracle lookahead, and temperature-softmax records for rollout
    diversity.
    """

    name: str
    """Stable recipe name stored as branch schedule lineage."""

    policy: RolloutPolicySpec
    """Complete branching and action-selection policy for this recipe."""

    @staticmethod
    def default_suite() -> list["RolloutRecipeConfig"]:
        """Return deterministic two-step recipes for local evidence builds.

        The suite covers one factual path for random-valid and greedy policies
        plus two retained branches for oracle-lookahead and temperature-softmax
        policies. These recipe axes are rollout controls, not candidate-shell
        widths; every step still persists its complete generated shell.
        """

        return [
            RolloutRecipeConfig(
                name="random_valid",
                policy=RolloutPolicySpec(
                    selection_policy=CounterfactualSelectionPolicy.RANDOM_VALID,
                    horizon=2,
                    branch_factor=1,
                    seed=0,
                ),
            ),
            RolloutRecipeConfig(
                name="oracle_greedy",
                policy=RolloutPolicySpec(
                    selection_policy=CounterfactualSelectionPolicy.ORACLE_GREEDY,
                    horizon=2,
                    branch_factor=1,
                    seed=0,
                ),
            ),
            RolloutRecipeConfig(
                name="oracle_lookahead",
                policy=RolloutPolicySpec(
                    selection_policy=CounterfactualSelectionPolicy.ORACLE_GREEDY,
                    horizon=2,
                    branch_factor=2,
                    beam_width=2,
                    seed=0,
                ),
            ),
            RolloutRecipeConfig(
                name="temperature_softmax",
                policy=RolloutPolicySpec(
                    selection_policy=CounterfactualSelectionPolicy.TEMPERATURE_SOFTMAX,
                    horizon=2,
                    branch_factor=2,
                    beam_width=2,
                    selection_temperature=1.0,
                    seed=0,
                ),
            ),
        ]

    @staticmethod
    def diverse_suite() -> list["RolloutRecipeConfig"]:
        """Return the radial/backtrack rollout-diversity recipe suite.

        The suite mirrors `.configs/build_rollouts_v1_diverse.toml` and is
        intended to pair with
        `CandidateMixtureViewGeneratorConfig.radial_target_backtrack_family`.
        Sibling-diversity controls are best-effort after candidate validity
        pruning, so the recipes record the intended action-family pressure
        without changing rollout hard-mask semantics.
        """

        return [
            RolloutRecipeConfig(
                name="random_valid_diverse",
                policy=RolloutPolicySpec(
                    selection_policy=CounterfactualSelectionPolicy.RANDOM_VALID,
                    horizon=2,
                    branch_factor=3,
                    beam_width=3,
                    require_sibling_strategy_diversity=True,
                    min_sibling_distance_m=0.2,
                    min_sibling_yaw_deg=20.0,
                    min_sibling_target_bearing_deg=20.0,
                    seed=0,
                ),
            ),
            RolloutRecipeConfig(
                name="oracle_lookahead_diverse",
                policy=RolloutPolicySpec(
                    selection_policy=CounterfactualSelectionPolicy.ORACLE_GREEDY,
                    horizon=2,
                    branch_factor=3,
                    beam_width=3,
                    require_sibling_strategy_diversity=True,
                    min_sibling_distance_m=0.2,
                    min_sibling_yaw_deg=20.0,
                    min_sibling_target_bearing_deg=20.0,
                    seed=0,
                ),
            ),
            RolloutRecipeConfig(
                name="temperature_softmax_diverse",
                policy=RolloutPolicySpec(
                    selection_policy=CounterfactualSelectionPolicy.TEMPERATURE_SOFTMAX,
                    horizon=2,
                    branch_factor=3,
                    beam_width=3,
                    selection_temperature=1.25,
                    require_sibling_strategy_diversity=True,
                    min_sibling_distance_m=0.2,
                    min_sibling_yaw_deg=20.0,
                    min_sibling_target_bearing_deg=20.0,
                    stochastic_branch_factors=(2, 3),
                    stochastic_branch_probabilities=(0.5, 0.5),
                    seed=0,
                ),
            ),
        ]


class SelectedDepthRetentionConfig(BaseConfig):
    """High-resolution oracle depth retained only for selected rollout actions.

    Mesh-rendered depth supports successor-history reconstruction and audits.
    It is not actor-visible evidence and is stored in the rollout destination,
    never backfilled into the immutable VIN source cache.
    """

    enabled: bool = True
    """Persist one selected-action depth map for every materialized rollout step."""

    width_px: int = Field(default=240, ge=1)
    """Persisted selected-depth width in pixels."""

    height_px: int = Field(default=240, ge=1)
    """Persisted selected-depth height in pixels."""

    chunk_steps: int = Field(default=16, ge=1)
    """Number of selected steps per Zarr depth chunk."""

    def renderer_config(self, base: CandidateDepthRendererConfig) -> CandidateDepthRendererConfig:
        """Return a selected-only renderer config derived from the scorer renderer."""

        return base.model_copy(
            deep=True,
            update={
                "max_candidates_final": 1,
                "resolution_scale": None,
                "output_width_px": int(self.width_px),
                "output_height_px": int(self.height_px),
            },
        )


def _select_source_manifest_rows(
    manifest: RolloutSourceManifest,
    sample_keys: Sequence[str] | None,
) -> tuple[RolloutShardRow, ...]:
    """Select manifest rows in exact configured sample-key order."""

    if sample_keys is None:
        return manifest.rows
    rows_by_key = {row.sample_key: row for row in manifest.rows}
    missing = [sample_key for sample_key in sample_keys if sample_key not in rows_by_key]
    if missing:
        raise ValueError(f"sample_keys are missing from source_manifest_path: {missing!r}.")
    return tuple(rows_by_key[sample_key] for sample_key in sample_keys)


def _apply_manifest_rows(
    dataset: VinOfflineDataset,
    rows: Sequence[RolloutShardRow],
    *,
    owner: str,
) -> None:
    """Filter and order a VIN reader from validated source-row records."""

    records_by_shard_row = {(str(record.shard_id), int(record.row)): record for record in dataset._records}
    selected_records = []
    for row in rows:
        record = records_by_shard_row.get((row.source_shard_id, int(row.source_shard_row)))
        if record is None:
            raise ValueError(
                f"{owner.capitalize()} row {row.order} is not exposed by the configured "
                f"VIN source split/limit: source_shard_id={row.source_shard_id!r} "
                f"source_shard_row={row.source_shard_row}."
            )
        if not row.matches_record(record):
            raise ValueError(
                f"{owner.capitalize()} row {row.order} does not match the configured "
                "VIN source sample_index.jsonl record."
            )
        selected_records.append(record)
    dataset._records = selected_records
    dataset._record_by_pair = {(record.scene_id, record.snippet_id): record for record in selected_records}


class RolloutDatasetWriterConfig(TargetConfig["RolloutDatasetWriter"]):
    """Configuration for building standalone target-RRI rollout Zarr stores.

    The source is a strict-v7 VIN offline dataset opened in `sample` mode with
    enough live assets to rerun candidate generation and oracle scoring. The
    destination is a standalone rollout store; the source cache version is
    recorded as lineage and is not modified.
    """

    @property
    def target_type(self) -> type["RolloutDatasetWriter"]:
        """Return the concrete standalone rollout writer constructed by this config."""

        return RolloutDatasetWriter

    source: VinOfflineDatasetConfig = Field(
        default_factory=lambda: VinOfflineDatasetConfig(
            return_format="sample",
            include_efm_snippet=True,
            include_gt_mesh=True,
            load_backbone=True,
            load_candidates=False,
            load_depths=False,
            load_candidate_pcs=False,
            load_gt_obbs=True,
            load_detected_obbs=True,
            load_trajectory_metadata=True,
        )
    )
    """VIN strict-v7 source reader; must return samples with live snippet and GT mesh."""

    source_manifest_path: Path | None = None
    """Optional reviewed ordered-source manifest enforced before direct generation."""

    sample_keys: list[str] | None = None
    """Optional exact ordered sample-key subset of ``source_manifest_path``.

    Keys are applied in configured order before direct generation or shard
    planning. Missing, empty, or duplicate keys fail before dataset loading;
    the reviewed source manifest remains the provenance owner for row identity.
    """

    oracle_target_task_sampler: OracleTargetTaskSamplerConfig = Field(default_factory=OracleTargetTaskSamplerConfig)
    """Oracle GT target-task sampler used by default for rollout data generation."""

    explicit_target: ExplicitRolloutTargetConfig | None = Field(default=None, exclude=True)
    """Optional one-target V1 input; mutually exclusive with target resampling."""

    candidate_mixture: CandidateMixtureViewGeneratorConfig = Field(default_factory=CandidateMixtureViewGeneratorConfig)
    """Fixed-count mixed finite-candidate generator regenerated at every rollout step."""

    target_scorer: TargetRriScorerConfig = Field(default_factory=TargetRriScorerConfig)
    """Target-specific oracle scorer that also emits diagnostic scene RRI."""

    selected_depth: SelectedDepthRetentionConfig = Field(default_factory=SelectedDepthRetentionConfig)
    """High-resolution selected-depth persistence; separate from low-res all-candidate RRI scoring."""

    store: RolloutZarrStoreConfig = Field(
        default_factory=lambda: RolloutZarrStoreConfig(
            target_protocol_version=TargetInputProtocol.V0_GT_INPUT,
            field_retention_policy="compact_selected_heavy",
        )
    )
    """Standalone rollout Zarr destination; the VIN offline store remains unchanged."""

    recipes: list[RolloutRecipeConfig] = Field(default_factory=RolloutRecipeConfig.default_suite)
    """Rollout policies/branch schedules materialized into the replay store."""

    max_samples: int | None = Field(default=None, ge=1)
    """Optional local smoke cap on source samples."""

    max_targets_per_sample: int | None = None
    """Optional local smoke cap on selected targets rolled out per source sample."""

    log_timing: bool = False
    """Emit generation/scoring timing diagnostics for local evidence builds."""

    require_label_valid: bool = True
    """Skip selected targets without valid GT/evaluation labels when true."""

    min_valid_root_candidates: int = Field(default=3, ge=0)
    """Skip rollout roots whose materialized first step has too few valid actions."""

    verbosity: Verbosity = Field(default=Verbosity.NORMAL)
    """Console verbosity."""

    is_debug: bool = False
    """Enable debug logging in writer dependencies."""

    _coerce_verbosity = field_validator("verbosity", mode="before")(BaseConfig._coerce_verbosity)

    @model_validator(mode="after")
    def _validate_target_protocol(self) -> "RolloutDatasetWriterConfig":
        """Reject actor-visible protocol claims from the Oracle GT generator."""

        explicit = self.explicit_target
        if explicit is not None:
            validate_target_protocol_admission(
                self.store.target_protocol_version,
                target_source=self.explicit_target.actor_descriptor.source,
                descriptor_source=self.explicit_target.actor_descriptor.source,
                descriptor_provenance=TargetDescriptorProvenance.ACTOR_VISIBLE_DETECTOR,
            )
            if self.store.target_protocol_version is not TargetInputProtocol.V1_OBSERVED:
                raise ValueError("explicit_target requires store.target_protocol_version=v1_observed")
            if self.max_targets_per_sample not in (None, 1):
                raise ValueError("explicit_target is mutually exclusive with multi-target sampling.")
            if self.oracle_target_task_sampler != OracleTargetTaskSamplerConfig():
                raise ValueError("oracle_target_task_sampler is ignored for explicit targets; use defaults")
            return self
        validate_target_protocol_admission(
            self.store.target_protocol_version,
            target_source=ORACLE_TARGET_TASK_SOURCE,
            descriptor_source=ORACLE_TARGET_TASK_SOURCE,
            descriptor_provenance=TargetDescriptorProvenance.ORACLE_GT,
        )
        return self

    @field_validator("source_manifest_path", mode="before")
    @classmethod
    def _resolve_source_manifest_path(cls, value: Path | str | None) -> Path | None:
        """Resolve a configured source manifest relative to the repository root."""

        if value is None:
            return None
        return PathConfig().resolve_artifact_path(value, expected_suffix=".json", create_parent=False)

    @field_validator("sample_keys")
    @classmethod
    def _validate_sample_keys(cls, value: list[str] | None) -> list[str] | None:
        """Normalize an exact ordered sample-key selection and reject ambiguity."""

        if value is None:
            return None
        normalized = [str(sample_key).strip() for sample_key in value]
        if not normalized or any(not sample_key for sample_key in normalized):
            raise ValueError("sample_keys must contain at least one non-empty key when set.")
        if len(set(normalized)) != len(normalized):
            raise ValueError("sample_keys must be unique.")
        return normalized

    @model_validator(mode="after")
    def _validate_source_manifest_contract(self) -> "RolloutDatasetWriterConfig":
        """Require direct pilot configs to match their reviewed ordered source rows."""

        if self.source_manifest_path is None:
            if self.sample_keys is not None:
                raise ValueError("sample_keys requires source_manifest_path for fail-closed row identity validation.")
            return self
        manifest = read_rollout_source_manifest(self.source_manifest_path)
        selected_rows = self.selected_source_manifest_rows(manifest)
        expected_rows = len(selected_rows)
        if self.max_samples != expected_rows:
            raise ValueError(
                f"source_manifest_path requires max_samples to equal the selected manifest row count ({expected_rows})."
            )
        if self.source.limit != len(manifest.rows):
            raise ValueError(
                f"source_manifest_path requires source.limit to equal the manifest row count ({len(manifest.rows)})."
            )
        if self.source.split != manifest.split:
            raise ValueError(
                f"Configured source split {self.source.split!r} does not match source manifest {manifest.split!r}."
            )
        if self.source.store.store_dir.name != Path(manifest.source_store_dir).name:
            raise ValueError("Configured VIN source-store identity does not match source_manifest_path provenance.")
        expected_split_manifest_hash = build_rollout_split_manifest_hash(
            source_manifest_hash=manifest.source_manifest_hash,
            split=manifest.split,
            records=[{**row.hash_record(), "order": order} for order, row in enumerate(selected_rows)],
        )
        if self.store.split_manifest_hash != expected_split_manifest_hash:
            raise ValueError("Configured rollout split_manifest_hash does not match the selected source manifest rows.")
        return self

    def selected_source_manifest_rows(self, manifest: RolloutSourceManifest) -> tuple[RolloutShardRow, ...]:
        """Return source-manifest rows in the exact configured sample-key order.

        The full reviewed manifest remains authoritative for immutable row
        identity. When `sample_keys` is unset, its complete order is preserved.
        """

        return _select_source_manifest_rows(manifest, self.sample_keys)

    @field_validator("max_targets_per_sample")
    @classmethod
    def _validate_max_targets_per_sample(cls, value: int | None) -> int | None:
        """Preserve ``None`` as no per-sample target cap while rejecting non-positive caps."""

        if value is not None and int(value) < 1:
            raise ValueError("max_targets_per_sample must be >= 1 when set.")
        return value

    def _propagate_to_child(self, parent_field: str, child_config: BaseConfig) -> None:
        """Avoid propagating rollout Zarr ``store`` into the VIN source config."""

        excluded = {"max_targets_per_sample", parent_field, "propagated_fields", "target", "target_type"}
        if parent_field == "source":
            excluded.add("store")
        shared_fields = {
            name: value for name, value in self if name in child_config.__class__.model_fields and name not in excluded
        }
        for name, value in shared_fields.items():
            if getattr(child_config, name, None) != value:
                setattr(child_config, name, value)
                child_config.propagated_fields[name] = value


@dataclass(frozen=True, slots=True)
class _RolloutSourceLineageBuilder:
    """Build deterministic source/config lineage values for rollout records.

    The VIN offline sample index is the root-of-truth for source rows, but a
    rollout shard may be planned from a source reader exposing `split="all"`.
    Lineage therefore hashes the concrete selected row split when records are
    split-local, matching the shard manifest used by LRZ array jobs.
    """

    source_manifest_hash: str
    split_manifest_hash: str
    source_cache_version: str
    campaign_split: str = "unknown"

    @classmethod
    def from_dataset(
        cls, dataset: VinOfflineDataset, *, max_samples: int, campaign_split: str | None = None
    ) -> "_RolloutSourceLineageBuilder":
        """Hash the source manifest and ordered source rows used by a rollout shard."""

        source_manifest_hash = stable_msgspec_hash(dataset.manifest)
        records = dataset._records[:max_samples]
        split = _lineage_split(records=records, fallback=dataset.config.split)
        return cls(
            source_manifest_hash=source_manifest_hash,
            split_manifest_hash=cls.build_split_manifest_hash(
                source_manifest_hash=source_manifest_hash,
                split=split,
                records=cls.dataset_records_for_hash(dataset, limit=max_samples),
            ),
            source_cache_version=str(dataset.manifest.version),
            campaign_split=str(campaign_split or split),
        )

    @staticmethod
    def config_hash(config: BaseConfig) -> str:
        """Hash one config for rollout trace lineage."""

        return stable_config_hash(config)

    @staticmethod
    def build_split_manifest_hash(*, source_manifest_hash: str, split: str, records: list[dict[str, object]]) -> str:
        """Hash the split-local ordered source rows used for a rollout shard."""

        return build_rollout_split_manifest_hash(
            source_manifest_hash=source_manifest_hash,
            split=split,
            records=records,
        )

    @staticmethod
    def dataset_records_for_hash(dataset: VinOfflineDataset, *, limit: int) -> list[dict[str, object]]:
        """Return ordered source-row fields that define a rollout shard lineage."""

        output: list[dict[str, object]] = []
        for order, record in enumerate(dataset._records[:limit]):
            output.append(
                {
                    "order": order,
                    "sample_index": int(record.sample_index),
                    "sample_key": str(record.sample_key),
                    "scene_id": str(record.scene_id),
                    "snippet_id": str(record.snippet_id),
                    "split": str(record.split),
                    "source_shard_id": str(record.shard_id),
                    "source_shard_row": int(record.row),
                }
            )
        return output

    @staticmethod
    def mesh_version(sample: VinOfflineSample) -> str:
        """Return a compact mesh-size fingerprint for rollout lineage."""

        snippet = sample.efm_snippet_view
        if snippet is None or snippet.mesh is None:
            return "missing-mesh"
        return f"mesh-v={len(snippet.mesh.vertices)}-f={len(snippet.mesh.faces)}"


class _SplitRecord(Protocol):
    @property
    def split(self) -> str: ...


class RolloutDatasetWriter:
    """Generate target-RRI rollout records and write a standalone Zarr store.

    For each source row the writer samples geometry-valid Oracle target tasks,
    passes sanitized descriptors to candidate generation, regenerates
    candidates from updated history/budget, scores target RRI, and persists
    compact replay records. Heavy diagnostics should be retained only for
    selected actions or retained chains through the downstream Zarr policy.

    This class is the handoff point between `data_handling` and
    `pose_generation`: it reads immutable `VinOfflineSample` roots, calls the
    finite-candidate counterfactual generator, and emits evaluated rollout records
    objects that are stored independently of the VIN offline cache.
    """

    def __init__(self, config: RolloutDatasetWriterConfig) -> None:
        self.config = config
        self.console = (
            Console.with_prefix(self.__class__.__name__).set_verbosity(config.verbosity).set_debug(config.is_debug)
        )
        self.stats = RolloutDatasetWriterStats()

    def root_support_preflight(self, valid_candidates: int) -> str | None:
        """Apply the campaign root-support gate before recipe generation.

        The caller supplies the one-shot probe count; probe tensors are not
        retained by this writer.  A shortfall is a typed skip reason and must
        be handled by the shard owner without creating a store.
        """
        count = int(valid_candidates)
        minimum = int(self.config.min_valid_root_candidates)
        if count < minimum:
            reason = f"insufficient_root_support:{count}<{minimum}"
            self.stats.skip(reason)
            return reason
        return None

    def _require_campaign_recipe_completeness(self, records: Sequence[object], shard_entry: Any) -> None:
        """Reject partial multi-recipe campaign targets before store creation."""
        if (
            shard_entry is not None
            and shard_entry.campaign_binding is not None
            and len(self.config.recipes) > 1
            and len(records) != len(self.config.recipes)
        ):
            raise RuntimeError(
                "campaign rollout requires one validated record per configured recipe; "
                f"got {len(records)} of {len(self.config.recipes)}"
            )

    def run(
        self,
        *,
        invocation: RolloutStoreInvocation | None = None,
        shard_entry: RolloutShardEntry | None = None,
    ) -> RolloutZarrWriteResult:
        """Build the configured rollout store.

        In normal mode the configured source split and `max_samples` decide the
        rows. In shard mode the `RolloutShardEntry` is authoritative: source
        rows are filtered and ordered from the manifest, `max_samples` is
        ignored, and source/config hash mismatches fail before generation.
        """

        dataset = self.config.source.setup_target()
        if dataset is None:
            raise RuntimeError("VinOfflineDatasetConfig did not instantiate a dataset.")
        source_manifest = (
            None
            if self.config.source_manifest_path is None
            else read_rollout_source_manifest(self.config.source_manifest_path)
        )
        if source_manifest is not None and shard_entry is None:
            self._apply_source_manifest(dataset, source_manifest, sample_keys=self.config.sample_keys)
        if shard_entry is not None:
            self._apply_shard_manifest(dataset, shard_entry)
        explicit_config = getattr(self.config, "explicit_target", None)
        oracle_sampler = (
            None if explicit_config is not None else OracleTargetTaskSampler(self.config.oracle_target_task_sampler)
        )
        max_samples = (
            len(dataset)
            if shard_entry is not None or self.config.max_samples is None
            else min(int(self.config.max_samples), len(dataset))
        )
        source_lineage = _RolloutSourceLineageBuilder.from_dataset(
            dataset,
            max_samples=max_samples,
            campaign_split=None if shard_entry is None else shard_entry.campaign_split,
        )
        if source_manifest is not None and shard_entry is None:
            self._validate_source_manifest_lineage(
                source_lineage,
                source_manifest,
                expected_split_manifest_hash=self.config.store.split_manifest_hash,
            )
        if shard_entry is not None:
            self._validate_shard_lineage(source_lineage, shard_entry)
        records = []

        for sample_index in range(max_samples):
            sample = dataset[sample_index]
            if not isinstance(sample, VinOfflineSample):
                raise TypeError("RolloutDatasetWriter requires source.return_format='sample'.")
            self.stats.samples_seen += 1
            if sample.efm_snippet_view is None or not sample.efm_snippet_view.has_mesh:
                self.stats.samples_without_snippet_or_mesh += 1
                self.stats.skip("missing_snippet_or_mesh")
                continue
            if explicit_config is not None:
                explicit = explicit_config.setup_target()
                if explicit.sample_key != sample.sample_key:
                    continue
                target_result = _explicit_target_result(explicit)
            else:
                assert oracle_sampler is not None
                target_result = oracle_sampler.sample(sample)
            if not target_result.selected_rows:
                reason = "no_geometry_valid_oracle_target_tasks" if target_result.rows else "no_oracle_target_tasks"
                self.stats.skip(reason)
                self.console.warn(
                    f"Skipping sample scene={sample.scene_id} snippet={sample.snippet_id}: {reason}; "
                    f"source={target_result.source} warnings={target_result.warnings}",
                )
                continue
            rolled_targets_for_sample = 0
            for target_rank, target in enumerate(target_result.selected_rows):
                self.stats.targets_selected += 1
                if self.config.max_targets_per_sample is not None and rolled_targets_for_sample >= int(
                    self.config.max_targets_per_sample
                ):
                    self.stats.skip("max_targets_per_sample")
                    continue
                if self.config.require_label_valid and target.identity_status != TargetTaskIdentityStatus.MATCHED.value:
                    self.stats.targets_label_invalid += 1
                    self.stats.skip(target.identity_status)
                    continue
                target_records = self._rollout_target(
                    sample=sample,
                    target=target,
                    target_rank=target_rank,
                    source_lineage=source_lineage,
                )
                self._require_campaign_recipe_completeness(target_records, shard_entry)
                if target_records:
                    rolled_targets_for_sample += 1
                    records.extend(target_records)

        if not records:
            raise RuntimeError(f"No rollout records were generated; skipped={self.stats.skipped_reasons}")

        selected_depth_renderer_config = self.config.selected_depth.renderer_config(self.config.target_scorer.depth)
        result = write_rollout_zarr_store(
            self.config.store.store_dir,
            records,
            return_semantics=self.config.store.return_semantics,
            discount_gamma=self.config.store.discount_gamma,
            target_protocol_version=self.config.store.target_protocol_version,
            reason_code_version=self.config.store.reason_code_version,
            field_retention_policy=self.config.store.field_retention_policy,
            source_offline_store_version=source_lineage.source_cache_version,
            split_manifest_hash=source_lineage.split_manifest_hash,
            manifest_context=RolloutStoreManifestContext(
                writer_config=self.config.model_dump_jsonable(),
                invocation=invocation or RolloutStoreInvocation.programmatic(),
                runtime=collect_runtime_provenance(),
                shard=None if shard_entry is None else shard_entry.to_jsonable(),
            ),
            selected_depth_enabled=self.config.selected_depth.enabled,
            selected_depth_width_px=self.config.selected_depth.width_px,
            selected_depth_height_px=self.config.selected_depth.height_px,
            selected_depth_chunk_steps=self.config.selected_depth.chunk_steps,
            selected_depth_renderer=selected_depth_renderer_config.renderer.target_type.__name__,
            selected_depth_znear_m=selected_depth_renderer_config.renderer.znear,
            selected_depth_zfar_m=selected_depth_renderer_config.renderer.zfar,
            selected_depth_source_resolution="exact_output_size",
            q_h_chunk_states=self.config.store.q_h_chunk_states,
            target_eval_crop_max_points=self.config.store.target_eval_crop_max_points,
            target_eval_crops_enabled=self.config.store.target_eval_crops_enabled,
        )
        self.stats.rollouts_written = int(result.num_rollouts)
        validation = validate_rollout_zarr_store(result.store_dir)
        if not validation.ok:
            joined = "; ".join(validation.errors)
            raise RuntimeError(f"Rollout Zarr post-write validation failed for {result.store_dir}: {joined}")
        self.console.log(
            "Wrote rollout store: "
            f"rollouts={result.num_rollouts} steps={result.num_steps} candidates={result.num_candidates} "
            f"path={result.store_dir}",
        )
        return result

    def _apply_shard_manifest(self, dataset: VinOfflineDataset, shard_entry: RolloutShardEntry) -> None:
        """Filter a source dataset to the ordered rows owned by one shard entry."""

        shard_entry.validate()
        _apply_manifest_rows(dataset, shard_entry.rows, owner=f"rollout shard {shard_entry.shard_id!r}")

    @staticmethod
    def _apply_source_manifest(
        dataset: VinOfflineDataset,
        manifest: RolloutSourceManifest,
        *,
        sample_keys: Sequence[str] | None = None,
    ) -> None:
        """Filter a direct build to the reviewed profile-independent source rows."""

        manifest.validate()
        rows = _select_source_manifest_rows(manifest, sample_keys)
        _apply_manifest_rows(dataset, rows, owner="rollout source manifest")

    @staticmethod
    def _validate_source_manifest_lineage(
        source_lineage: _RolloutSourceLineageBuilder,
        manifest: RolloutSourceManifest,
        *,
        expected_split_manifest_hash: str,
    ) -> None:
        """Verify the direct reader still matches the reviewed source manifest."""

        if source_lineage.source_manifest_hash != manifest.source_manifest_hash:
            raise ValueError("Configured source manifest hash does not match the active VIN source store.")
        if source_lineage.source_cache_version != manifest.source_cache_version:
            raise ValueError("Configured source cache version does not match the active VIN source store.")
        if source_lineage.split_manifest_hash != expected_split_manifest_hash:
            raise ValueError("Configured ordered source rows do not match source_manifest_path.")

    @staticmethod
    def _validate_shard_lineage(
        source_lineage: _RolloutSourceLineageBuilder,
        shard_entry: RolloutShardEntry,
    ) -> None:
        """Verify that the active dataset matches the requested shard manifest entry."""

        if source_lineage.source_manifest_hash != shard_entry.source_manifest_hash:
            raise ValueError(
                f"Rollout shard {shard_entry.shard_id!r} source manifest hash mismatch: "
                f"config source={source_lineage.source_manifest_hash} manifest={shard_entry.source_manifest_hash}."
            )
        if source_lineage.source_cache_version != shard_entry.source_cache_version:
            raise ValueError(
                f"Rollout shard {shard_entry.shard_id!r} source cache version mismatch: "
                f"config source={source_lineage.source_cache_version} manifest={shard_entry.source_cache_version}."
            )
        if source_lineage.split_manifest_hash != shard_entry.split_manifest_hash:
            raise ValueError(
                f"Rollout shard {shard_entry.shard_id!r} split manifest hash mismatch: "
                f"config source={source_lineage.split_manifest_hash} manifest={shard_entry.split_manifest_hash}."
            )
        if shard_entry.campaign_split is not None and source_lineage.campaign_split != shard_entry.campaign_split:
            raise ValueError(
                f"Rollout shard {shard_entry.shard_id!r} campaign split mismatch: "
                f"config source={source_lineage.campaign_split} manifest={shard_entry.campaign_split}."
            )

    def _rollout_target(
        self,
        *,
        sample: VinOfflineSample,
        target: OracleTargetTask,
        target_rank: int,
        source_lineage: _RolloutSourceLineageBuilder,
    ) -> list[EvaluatedRolloutRecord]:
        records: list[EvaluatedRolloutRecord] = []
        runtime_context = CandidateGenerationRuntimeContext(descriptor=target.descriptor)
        scorer = self.config.target_scorer.setup_target(
            sample=sample.efm_snippet_view,
            target_sample=sample,
            target_task=target,
        )
        if scorer.invalidity is not None:
            self.stats.target_invalid_skips += 1
            self.stats.skip(f"target_scorer:{scorer.invalidity.reason.value}")
            self.console.warn(
                f"Skipping target scorer scene={sample.scene_id} snippet={sample.snippet_id} "
                f"target={target.target_id}: {scorer.invalidity.message}",
            )
            return records
        # Probe one fresh root shell solely for the hard support gate.  This is
        # deliberately candidate-generation-only: support must not pay for
        # replay scoring or rendering, and the discarded shell is never reused.
        if getattr(self.config, "min_valid_root_candidates", 0) > 0 and self.config.recipes:
            probe = self.config.candidate_mixture.setup_target().generate_from_typed_sample(
                sample.efm_snippet_view,
                runtime_context=runtime_context,
            )
            valid_count = int(probe.mask_valid.detach().cpu().to(dtype=torch.bool).sum().item())
            support_reason = self.root_support_preflight(valid_count)
            if support_reason is not None:
                self.stats.rollout_invalid_skips += 1
                raise InsufficientRootSupportError(support_reason)
        selected_depth_renderer = (
            self.config.selected_depth.renderer_config(self.config.target_scorer.depth).setup_target()
            if self.config.selected_depth.enabled
            else None
        )
        for recipe in self.config.recipes:
            score_candidates = OracleReplayAdapter(scorer)
            rollout_cfg = CounterfactualPoseGeneratorConfig(
                candidate_config=self.config.candidate_mixture,
                policy=recipe.policy,
                log_timing=self.config.log_timing,
                verbosity=self.config.verbosity,
                is_debug=self.config.is_debug,
            )
            try:
                snippet = sample.efm_snippet_view
                if snippet is None:
                    raise ValueError("Rollout generation requires an attached EFM snippet view.")
                result = rollout_cfg.setup_target().generate_from_typed_sample(
                    snippet,
                    score_candidates=score_candidates,
                    candidate_runtime_context=runtime_context,
                )
            except OracleReplayInvalidityError as exc:
                self.stats.rollout_invalid_skips += 1
                self.stats.skip(f"{recipe.name}:{exc.invalidity.reason.value}")
                self.console.warn(
                    f"Skipping rollout recipe={recipe.name} scene={sample.scene_id} snippet={sample.snippet_id} "
                    f"target={target.target_id}: {exc.invalidity.message}",
                )
                continue
            low_valid_root = self._low_valid_root_reason(result)
            if low_valid_root is not None:
                self.stats.rollout_invalid_skips += 1
                self.stats.skip(low_valid_root)
                self.console.warn(
                    f"Skipping rollout recipe={recipe.name} scene={sample.scene_id} snippet={sample.snippet_id} "
                    f"target={target.target_id}: {low_valid_root}",
                )
                continue
            evaluated = score_candidates.materialize(
                result,
                retain_target_crops=self.config.store.target_eval_crops_enabled,
            )
            if selected_depth_renderer is not None:
                self._attach_selected_depths(
                    evaluated=evaluated,
                    sample=sample,
                    renderer=selected_depth_renderer,
                )

            prefix = f"{sample.sample_index:08d}-target-{target_rank:02d}-{recipe.name}"
            records.append(
                EvaluatedRolloutRecord(
                    evaluated=evaluated,
                    rollout_id_prefix=prefix,
                    lineage=RolloutLineage(
                        source=SourceLineage(
                            scene_id=sample.scene_id,
                            snippet_id=sample.snippet_id,
                            mesh_version=source_lineage.mesh_version(sample),
                            source_cache_version=source_lineage.source_cache_version,
                            source_row_id=sample.sample_index,
                            source_sample_index=sample.sample_index,
                            source_sample_key=sample.sample_key,
                            split=sample.split,
                            campaign_split=getattr(source_lineage, "campaign_split", sample.split),
                            source_shard_id=sample.source_shard_id,
                            source_shard_row=sample.source_shard_row,
                            source_offline_store_manifest_hash=source_lineage.source_manifest_hash,
                            split_manifest_hash=source_lineage.split_manifest_hash,
                        ),
                        target=self._target_lineage(target, target_rank=target_rank),
                        policy=PolicyLineage(
                            candidate_config_hash=source_lineage.config_hash(self.config.candidate_mixture),
                            oracle_config_hash=source_lineage.config_hash(self.config.target_scorer),
                            random_seed=recipe.policy.seed,
                            rollout_config_hash=source_lineage.config_hash(rollout_cfg),
                            branch_schedule_id=recipe.name,
                            reason_code_version=INVALID_REASON_VERSION,
                            selection_rng_state_hash=(
                                f"seed-once:{recipe.policy.seed}:split-manifest:{source_lineage.split_manifest_hash}"
                            ),
                        ),
                    ),
                )
            )
        return records

    def _target_lineage(self, target: OracleTargetTask, *, target_rank: int) -> TargetLineage:
        """Encode one Oracle task into the frozen rollout target columns."""

        explicit = getattr(self.config, "explicit_target", None)
        actor = explicit.actor_descriptor if explicit is not None else None
        gt_valid = target.identity_status == TargetTaskIdentityStatus.MATCHED.value
        if gt_valid:
            primary_reason = TARGET_INVALID_REASON_CODES["VALID"]
        elif target.identity_status == TargetTaskIdentityStatus.AMBIGUOUS.value:
            primary_reason = TARGET_INVALID_REASON_CODES["TARGET_GT_AMBIGUOUS"]
        elif target.identity_status == TargetTaskIdentityStatus.INVALID_GEOMETRY.value:
            primary_reason = TARGET_INVALID_REASON_CODES["OBB_EXTENT_INVALID"]
        else:
            primary_reason = TARGET_INVALID_REASON_CODES["TARGET_GT_UNMATCHED"]
        descriptor = actor.descriptor if actor is not None and actor.descriptor is not None else target.descriptor
        return TargetLineage(
            target_row_id=target.target_row_id,
            target_id=explicit.target_id if explicit is not None else target.target_id,
            target_protocol_version=self.config.store.target_protocol_version,
            target_crop_policy=self.config.target_scorer.target_crop_policy,
            target_selection_policy=self._target_selection_policy(),
            target_selection_rank=target.selected_rank if target.selected_rank is not None else target_rank,
            target_selection_score=float("nan"),
            target_selection_probability=target.selection_probability,
            target_selection_temperature=None,
            target_source=(actor.source if actor is not None else ORACLE_TARGET_TASK_SOURCE),
            target_source_index=(explicit.detected_source_row if explicit is not None else target.source_index),
            descriptor_source=(actor.source if actor is not None else ORACLE_TARGET_TASK_SOURCE),
            descriptor_provenance=(
                TargetDescriptorProvenance.ACTOR_VISIBLE_DETECTOR.value
                if actor is not None
                else TargetDescriptorProvenance.ORACLE_GT.value
            ),
            descriptor_hash=(actor.descriptor_hash if actor is not None else None),
            explicit_target_hash=(explicit.explicit_target_hash if explicit is not None else None),
            target_sem_id=descriptor.sem_id,
            target_inst_id=target.inst_id,
            target_class_name=descriptor.class_name,
            target_confidence=target.confidence,
            target_projected_area_pixels=0.0,
            target_projected_area_fraction=0.0,
            target_semidense_support_count=0,
            target_evl_support_count=0,
            target_effective_support_count=0.0,
            target_visibility_score=0.0,
            target_support_score=0.0,
            target_deficit_score=0.0,
            target_center_world=descriptor.center_world,
            target_extents=descriptor.extents_m,
            target_pose_world_object=descriptor.pose_world_object,
            target_relative_pose_reference_object=descriptor.relative_pose_reference_object,
            target_invalid_reason_bitset=1 << primary_reason,
            target_primary_invalid_reason=primary_reason,
            target_reason_code_version=TARGET_INVALID_REASON_VERSION,
            matched_gt_target_row_id=(
                explicit.gt_match_row if explicit is not None else (target.source_index if gt_valid else None)
            ),
            matched_gt_target_id=(
                explicit.gt_match_id if explicit is not None else (target.target_id if gt_valid else None)
            ),
            gt_match_iou=(explicit.oriented_iou if explicit is not None else None),
            gt_match_score=None,
            gt_match_status=(
                explicit.status if explicit is not None else ("matched" if gt_valid else target.identity_status)
            ),
        )

    def _low_valid_root_reason(self, result: CounterfactualRolloutResult) -> str | None:
        """Return a skip reason when the root step falls below the valid-action gate."""

        threshold = int(self.config.min_valid_root_candidates)
        if threshold <= 0:
            return None
        root_counts = [
            int(trajectory.steps[0].candidates.mask_valid.detach().cpu().to(dtype=torch.bool).sum().item())
            for trajectory in result.trajectories
            if trajectory.steps
        ]
        if not root_counts:
            return "low_valid_root_candidates:missing_root_step"
        min_count = min(root_counts)
        if min_count < threshold:
            return f"low_valid_root_candidates:{min_count}<min{threshold}"
        return None

    def _attach_selected_depths(
        self,
        *,
        evaluated: EvaluatedRollout,
        sample: VinOfflineSample,
        renderer: CandidateDepthRenderer,
    ) -> None:
        """Render and attach one high-resolution selected-depth map per retained step."""

        if sample.efm_snippet_view is None:
            raise ValueError("Selected-depth persistence requires sample.efm_snippet_view.")
        for chain_id, trajectory in enumerate(evaluated.result.trajectories):
            for step in trajectory.steps:
                evaluated_step = evaluated.step(chain_id, step.step_index)
                if evaluated_step is None:
                    raise KeyError(f"Missing evaluated rollout step chain={chain_id} step={step.step_index}.")
                batch = renderer.render_compact_indices(
                    sample.efm_snippet_view,
                    step.candidates,
                    [step.selected_valid_index],
                )
                if int(batch.candidate_indices[0].detach().cpu().item()) != int(step.selected_shell_index):
                    raise RuntimeError("Selected-depth render candidate index does not match selected shell index.")
                depth = batch.depths[0].detach().cpu().to(dtype=torch.float32).clone()
                valid_mask = batch.depths_valid_mask[0].detach().cpu().to(dtype=torch.bool).clone()
                expected_shape = (int(self.config.selected_depth.height_px), int(self.config.selected_depth.width_px))
                if tuple(depth.shape) != expected_shape:
                    raise RuntimeError(
                        f"Selected-depth render shape {tuple(depth.shape)} does not match {expected_shape}."
                    )
                camera = batch.camera
                focal = camera.f.reshape(-1, 2)[0].detach().cpu().to(dtype=torch.float32)
                principal = camera.c.reshape(-1, 2)[0].detach().cpu().to(dtype=torch.float32)
                size_wh = camera.size.reshape(-1, 2)[0].detach().cpu().to(dtype=torch.float32)
                evidence = evaluated_step.evaluation.evidence
                evidence.selected_depth_m = depth
                evidence.selected_depth_valid_mask = valid_mask
                evidence.selected_depth_focal_px = (float(focal[0].item()), float(focal[1].item()))
                evidence.selected_depth_principal_point_px = (float(principal[0].item()), float(principal[1].item()))
                evidence.selected_depth_image_size_hw = (int(size_wh[1].item()), int(size_wh[0].item()))

    def _target_selection_policy(self) -> str:
        if getattr(self.config, "explicit_target", None) is not None:
            return "explicit_observed_target"
        return OracleTargetTaskSelectionPolicy.UNIFORM_WITHOUT_REPLACEMENT.value


def _lineage_split(*, records: Sequence[_SplitRecord], fallback: str) -> str:
    """Return the concrete shard split when selected records do not mix splits."""

    splits = {str(record.split) for record in records}
    return next(iter(splits)) if len(splits) == 1 else str(fallback)


__all__ = [
    "ExplicitRolloutTarget",
    "ExplicitRolloutTargetConfig",
    "RolloutDatasetWriter",
    "RolloutDatasetWriterConfig",
    "RolloutDatasetWriterStats",
    "InsufficientRootSupportError",
    "RolloutRecipeConfig",
    "SelectedDepthRetentionConfig",
]


def _explicit_target_result(target: ExplicitRolloutTarget):
    """Adapt one explicit target to the writer's existing task loop."""

    task = OracleTargetTask(
        # Oracle crop/scoring resolves this index against the privileged GT
        # table.  The detector row remains separately persisted as lineage.
        source_index=target.gt_match_row,
        target_row_id=target.detected_source_row,
        target_id=target.target_id,
        descriptor=target.actor_descriptor.descriptor,
        inst_id=target.actor_descriptor.inst_id,
        confidence=target.actor_descriptor.confidence,
        identity_status=TargetTaskIdentityStatus.MATCHED.value,
        selected_rank=0,
        selection_probability=1.0,
    )
    return type(
        "_ExplicitResult", (), {"rows": (task,), "selected_rows": (task,), "source": "explicit_v1", "warnings": ()}
    )()
