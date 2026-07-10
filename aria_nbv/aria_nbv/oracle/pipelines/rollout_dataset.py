"""Build standalone target-RRI rollout replay stores from VIN offline rows.

This writer is the first rollout-data generation path, not a migration of the
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

from dataclasses import dataclass, field

import torch
from pydantic import Field, field_validator

from ...data_handling._target_selection import (
    TARGET_INVALID_REASON_CODES,
    TARGET_INVALID_REASON_VERSION,
    OracleTargetTaskRow,
    OracleTargetTaskSampler,
    OracleTargetTaskSamplerConfig,
    TargetCandidateRow,
    TargetTaskIdentityStatus,
)
from ...data_handling.offline.dataset import VinOfflineDataset, VinOfflineDatasetConfig, VinOfflineSample
from ...pose_generation import (
    CandidateGenerationRuntimeContext,
    CandidateMixtureViewGeneratorConfig,
)
from ...rendering import CandidateDepthRenderer, CandidateDepthRendererConfig
from ...rollouts.counterfactuals import (
    CounterfactualPoseGeneratorConfig,
    CounterfactualRolloutResult,
    CounterfactualSelectionPolicy,
)
from ...rollouts.manifest import RolloutStoreInvocation, RolloutStoreManifestContext, collect_runtime_provenance
from ...rollouts.shard_manifest import RolloutShardEntry
from ...rollouts.target_counterfactuals import CounterfactualTargetOracleRriScorerConfig, TargetRriInvalidError
from ...rollouts.trace import INVALID_REASON_VERSION, RolloutLineage, RolloutZarrRecord
from ...rollouts.zarr_store import (
    RolloutZarrStoreConfig,
    RolloutZarrWriteResult,
    validate_rollout_zarr_store,
    write_rollout_zarr_store,
)
from ...utils import BaseConfig, Console, TargetConfig, Verbosity
from ...utils.fingerprints import stable_config_hash, stable_msgspec_hash


@dataclass(slots=True)
class RolloutDatasetWriterStats:
    """Counters reported by one rollout-store build.

    The counters are operational diagnostics for local smoke builds. They are
    not dataset labels; invalidity details that affect training/evaluation must
    also be represented in rollout trace masks and lineage.
    """

    samples_seen: int = 0
    samples_without_snippet_or_mesh: int = 0
    targets_selected: int = 0
    targets_label_invalid: int = 0
    target_invalid_skips: int = 0
    rollout_invalid_skips: int = 0
    rollouts_written: int = 0
    skipped_reasons: dict[str, int] = field(default_factory=dict)

    def skip(self, reason: str) -> None:
        """Increment a named skip/failure counter."""

        self.skipped_reasons[reason] = self.skipped_reasons.get(reason, 0) + 1


class RolloutRecipeConfig(BaseConfig):
    """One rollout policy recipe materialized into the replay store.

    Recipes control both candidate-set sampling and action selection. The first
    supported policies cover random valid selection, greedy oracle selection,
    retained-beam oracle lookahead, and temperature-softmax records for rollout
    diversity.
    """

    name: str
    """Stable recipe name stored as branch schedule lineage."""

    selection_policy: CounterfactualSelectionPolicy
    """Action-selection policy used inside the rollout tree."""

    horizon: int = Field(default=2, ge=1)
    """Maximum number of rollout steps."""

    branch_factor: int = Field(default=1, ge=1)
    """Number of actions sampled/expanded per non-terminal step."""

    beam_width: int | None = Field(default=None, ge=1)
    """Retained beam width; ``None`` keeps the generator default."""

    branch_factor_schedule: list[int] | None = None
    """Optional deterministic per-step branch counts; last entry repeats."""

    stochastic_branch_factors: list[int] | None = None
    """Optional seeded branch-count choices sampled per expanded rollout node."""

    stochastic_branch_probabilities: list[float] | None = None
    """Optional probabilities aligned with ``stochastic_branch_factors``."""

    selection_temperature: float = Field(default=1.0, gt=0.0)
    """Softmax temperature for stochastic selection policies."""

    min_history_distance_m: float = Field(default=0.0, ge=0.0)
    """Minimum distance from previously selected poses during rollout selection."""

    min_sibling_distance_m: float = Field(default=0.0, ge=0.0)
    """Minimum distance between sibling branches expanded from one rollout node."""

    min_sibling_yaw_deg: float = Field(default=0.0, ge=0.0)
    """Minimum yaw separation between sibling branches expanded from one node."""

    min_sibling_target_bearing_deg: float = Field(default=0.0, ge=0.0)
    """Minimum target-bearing separation between sibling branches."""

    require_sibling_strategy_diversity: bool = False
    """Require sibling branches to use distinct candidate strategy families when possible."""

    seed: int | None = 0
    """Recipe-local random seed for candidate/action sampling."""

    @staticmethod
    def default_suite() -> list["RolloutRecipeConfig"]:
        """Return the default smoke recipe suite."""

        return [
            RolloutRecipeConfig(
                name="random_valid",
                selection_policy=CounterfactualSelectionPolicy.RANDOM_VALID,
                horizon=2,
                branch_factor=1,
                seed=0,
            ),
            RolloutRecipeConfig(
                name="oracle_greedy",
                selection_policy=CounterfactualSelectionPolicy.ORACLE_GREEDY,
                horizon=2,
                branch_factor=1,
                seed=0,
            ),
            RolloutRecipeConfig(
                name="oracle_lookahead",
                selection_policy=CounterfactualSelectionPolicy.ORACLE_GREEDY,
                horizon=2,
                branch_factor=2,
                beam_width=2,
                seed=0,
            ),
            RolloutRecipeConfig(
                name="temperature_softmax",
                selection_policy=CounterfactualSelectionPolicy.TEMPERATURE_SOFTMAX,
                horizon=2,
                branch_factor=2,
                beam_width=2,
                selection_temperature=1.0,
                seed=0,
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
            RolloutRecipeConfig(
                name="oracle_lookahead_diverse",
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
            RolloutRecipeConfig(
                name="temperature_softmax_diverse",
                selection_policy=CounterfactualSelectionPolicy.TEMPERATURE_SOFTMAX,
                horizon=2,
                branch_factor=3,
                beam_width=3,
                selection_temperature=1.25,
                require_sibling_strategy_diversity=True,
                min_sibling_distance_m=0.2,
                min_sibling_yaw_deg=20.0,
                min_sibling_target_bearing_deg=20.0,
                stochastic_branch_factors=[2, 3],
                stochastic_branch_probabilities=[0.5, 0.5],
                seed=0,
            ),
        ]


class SelectedDepthRetentionConfig(BaseConfig):
    """High-resolution selected-action depth retention for rollout stores."""

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


class RolloutDatasetWriterConfig(TargetConfig["RolloutDatasetWriter"]):
    """Configuration for building standalone target-RRI rollout Zarr stores.

    The source is a strict-v7 VIN offline dataset opened in `sample` mode with
    enough live assets to rerun candidate generation and oracle scoring. The
    destination is a standalone rollout store; the source cache version is
    recorded as lineage and is not modified.
    """

    @property
    def target_type(self) -> type["RolloutDatasetWriter"]:
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

    oracle_target_task_sampler: OracleTargetTaskSamplerConfig = Field(default_factory=OracleTargetTaskSamplerConfig)
    """Oracle GT target-task sampler used by default for rollout data generation."""

    candidate_mixture: CandidateMixtureViewGeneratorConfig = Field(default_factory=CandidateMixtureViewGeneratorConfig)
    """Fixed-count mixed finite-candidate generator regenerated at every rollout step."""

    target_scorer: CounterfactualTargetOracleRriScorerConfig = Field(
        default_factory=CounterfactualTargetOracleRriScorerConfig
    )
    """Target-specific oracle scorer that also emits diagnostic scene RRI."""

    selected_depth: SelectedDepthRetentionConfig = Field(default_factory=SelectedDepthRetentionConfig)
    """High-resolution selected-depth persistence; separate from low-res all-candidate RRI scoring."""

    store: RolloutZarrStoreConfig = Field(
        default_factory=lambda: RolloutZarrStoreConfig(
            target_protocol_version="v1_observed",
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

    @classmethod
    def from_dataset(cls, dataset: VinOfflineDataset, *, max_samples: int) -> "_RolloutSourceLineageBuilder":
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
        )

    @staticmethod
    def config_hash(config: BaseConfig) -> str:
        """Hash one config for rollout trace lineage."""

        return stable_config_hash(config)

    @staticmethod
    def build_split_manifest_hash(*, source_manifest_hash: str, split: str, records: list[dict[str, object]]) -> str:
        """Hash the split-local ordered source rows used for a rollout shard."""

        payload = {
            "source_manifest_hash": source_manifest_hash,
            "split": split,
            "records": records,
        }
        return stable_msgspec_hash(payload)

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


@dataclass(frozen=True, slots=True)
class _RolloutTargetSelectionResult:
    """Target rows selected for rollout generation plus source diagnostics."""

    rows: tuple[TargetCandidateRow, ...]
    selected_rows: tuple[TargetCandidateRow, ...]
    source: str | None
    warnings: tuple[str, ...] = ()
    empty_reason: str = "no_target_tasks"


class RolloutDatasetWriter:
    """Generate target-RRI rollout records and write a standalone Zarr store.

    For each source row the writer selects V1 actor-visible targets, validates
    GT/evaluation matches when required, regenerates candidates at each rollout
    step from updated history/budget, scores candidates by target RRI, and
    persists compact replay records. Heavy diagnostics should be retained only
    for selected actions or retained chains through the downstream Zarr policy.

    This class is the handoff point between `data_handling` and
    `pose_generation`: it reads immutable `VinOfflineSample` roots, calls the
    finite-candidate counterfactual generator, and emits `RolloutZarrRecord`
    objects that are stored independently of the VIN offline cache.
    """

    def __init__(self, config: RolloutDatasetWriterConfig) -> None:
        self.config = config
        self.console = (
            Console.with_prefix(self.__class__.__name__).set_verbosity(config.verbosity).set_debug(config.is_debug)
        )
        self.stats = RolloutDatasetWriterStats()

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
        if shard_entry is not None:
            self._apply_shard_manifest(dataset, shard_entry)
        oracle_sampler = OracleTargetTaskSampler(self.config.oracle_target_task_sampler)
        max_samples = (
            len(dataset)
            if shard_entry is not None or self.config.max_samples is None
            else min(int(self.config.max_samples), len(dataset))
        )
        source_lineage = _RolloutSourceLineageBuilder.from_dataset(dataset, max_samples=max_samples)
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
            target_result = self._select_targets(sample, oracle_sampler=oracle_sampler)
            if not target_result.selected_rows:
                reason = target_result.empty_reason
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
                if self.config.require_label_valid and not target.gt_label_valid:
                    self.stats.targets_label_invalid += 1
                    self.stats.skip(str(target.gt_match_status))
                    continue
                target_records = self._rollout_target(
                    sample=sample,
                    target=target,
                    target_rank=target_rank,
                    source_lineage=source_lineage,
                )
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
        records_by_shard_row = {(str(record.shard_id), int(record.row)): record for record in dataset._records}
        selected_records = []
        for row in shard_entry.rows:
            record = records_by_shard_row.get((row.source_shard_id, int(row.source_shard_row)))
            if record is None:
                raise ValueError(
                    f"Rollout shard {shard_entry.shard_id!r} row {row.order} is not exposed by the configured "
                    f"VIN source split/limit: source_shard_id={row.source_shard_id!r} "
                    f"source_shard_row={row.source_shard_row}."
                )
            if not row.matches_record(record):
                raise ValueError(
                    f"Rollout shard {shard_entry.shard_id!r} row {row.order} does not match the configured "
                    "VIN source sample_index.jsonl record."
                )
            selected_records.append(record)
        dataset._records = selected_records
        dataset._record_by_pair = {(record.scene_id, record.snippet_id): record for record in selected_records}

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

    def _rollout_target(
        self,
        *,
        sample: VinOfflineSample,
        target: TargetCandidateRow,
        target_rank: int,
        source_lineage: _RolloutSourceLineageBuilder,
    ) -> list[RolloutZarrRecord]:
        records: list[RolloutZarrRecord] = []
        runtime_context = CandidateGenerationRuntimeContext(
            target_center_world=torch.tensor(target.center_world, dtype=torch.float32),
            target_id=target.target_id,
        )
        try:
            scorer = self.config.target_scorer.setup_target(
                sample=sample.efm_snippet_view,
                target_sample=sample,
                target_row=target,
            )
        except TargetRriInvalidError as exc:
            self.stats.target_invalid_skips += 1
            self.stats.skip(f"target_scorer:{exc.__class__.__name__}")
            self.console.warn(
                f"Skipping target scorer scene={sample.scene_id} snippet={sample.snippet_id} "
                f"target={target.target_id}: {exc}",
            )
            return records
        selected_depth_renderer = (
            self.config.selected_depth.renderer_config(self.config.target_scorer.depth).setup_target()
            if self.config.selected_depth.enabled
            else None
        )
        for recipe in self.config.recipes:
            rollout_cfg = CounterfactualPoseGeneratorConfig(
                candidate_config=self.config.candidate_mixture,
                horizon=recipe.horizon,
                branch_factor=recipe.branch_factor,
                beam_width=recipe.beam_width,
                branch_factor_schedule=recipe.branch_factor_schedule,
                stochastic_branch_factors=recipe.stochastic_branch_factors,
                stochastic_branch_probabilities=recipe.stochastic_branch_probabilities,
                selection_policy=recipe.selection_policy,
                selection_temperature=recipe.selection_temperature,
                branch_schedule_id=recipe.name,
                min_history_distance_m=recipe.min_history_distance_m,
                min_sibling_distance_m=recipe.min_sibling_distance_m,
                min_sibling_yaw_deg=recipe.min_sibling_yaw_deg,
                min_sibling_target_bearing_deg=recipe.min_sibling_target_bearing_deg,
                require_sibling_strategy_diversity=recipe.require_sibling_strategy_diversity,
                seed=recipe.seed,
                log_timing=self.config.log_timing,
                verbosity=self.config.verbosity,
                is_debug=self.config.is_debug,
            )
            try:
                result = rollout_cfg.setup_target().generate_from_typed_sample(
                    sample.efm_snippet_view,
                    score_candidates=scorer,
                    candidate_runtime_context=runtime_context,
                )
            except TargetRriInvalidError as exc:
                self.stats.rollout_invalid_skips += 1
                self.stats.skip(f"{recipe.name}:{exc.__class__.__name__}")
                self.console.warn(
                    f"Skipping rollout recipe={recipe.name} scene={sample.scene_id} snippet={sample.snippet_id} "
                    f"target={target.target_id}: {exc}",
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
            if selected_depth_renderer is not None:
                self._attach_selected_depths(
                    result=result,
                    sample=sample,
                    renderer=selected_depth_renderer,
                )

            prefix = f"{sample.sample_index:08d}-target-{target_rank:02d}-{recipe.name}"
            records.append(
                RolloutZarrRecord(
                    result=result,
                    rollout_id_prefix=prefix,
                    lineage=RolloutLineage(
                        scene_id=sample.scene_id,
                        snippet_id=sample.snippet_id,
                        mesh_version=source_lineage.mesh_version(sample),
                        candidate_config_hash=source_lineage.config_hash(self.config.candidate_mixture),
                        oracle_config_hash=source_lineage.config_hash(self.config.target_scorer),
                        random_seed=recipe.seed,
                        source_cache_version=source_lineage.source_cache_version,
                        source_row_id=sample.sample_index,
                        source_sample_index=sample.sample_index,
                        source_sample_key=sample.sample_key,
                        split=sample.split,
                        source_shard_id=sample.source_shard_id,
                        source_shard_row=sample.source_shard_row,
                        source_offline_store_manifest_hash=source_lineage.source_manifest_hash,
                        split_manifest_hash=source_lineage.split_manifest_hash,
                        rollout_config_hash=source_lineage.config_hash(rollout_cfg),
                        branch_schedule_id=recipe.name,
                        target_row_id=target.target_row_id,
                        target_id=target.target_id,
                        target_protocol_version=self.config.store.target_protocol_version,
                        target_crop_policy=self.config.target_scorer.target_crop_policy,
                        reason_code_version=INVALID_REASON_VERSION,
                        selection_rng_state_hash=(
                            f"seed-once:{recipe.seed}:split-manifest:{source_lineage.split_manifest_hash}"
                        ),
                        target_selection_policy=self._target_selection_policy(),
                        target_selection_rank=target.selected_rank if target.selected_rank is not None else target_rank,
                        target_selection_score=target.score,
                        target_selection_probability=target.selection_probability,
                        target_selection_temperature=self._target_selection_temperature(),
                        target_source=target.source,
                        target_source_index=target.source_index,
                        target_sem_id=target.sem_id,
                        target_inst_id=target.inst_id,
                        target_class_name=target.class_name,
                        target_confidence=target.confidence,
                        target_projected_area_pixels=target.projected_area_pixels,
                        target_projected_area_fraction=target.projected_area_fraction,
                        target_semidense_support_count=target.semidense_support_count,
                        target_evl_support_count=target.evl_support_count,
                        target_effective_support_count=target.effective_support_count,
                        target_visibility_score=target.visibility_score,
                        target_support_score=target.support_score,
                        target_deficit_score=target.deficit_score,
                        target_center_world=target.center_world,
                        target_extents=target.extents,
                        target_pose_world_object=target.pose_world_object,
                        target_relative_pose_reference_object=target.relative_pose_reference_object,
                        target_invalid_reason_bitset=target.invalid_reason_bitset,
                        target_primary_invalid_reason=target.primary_invalid_reason,
                        target_reason_code_version=TARGET_INVALID_REASON_VERSION,
                        matched_gt_target_row_id=target.gt_target_row_id,
                        matched_gt_target_id=target.gt_target_id,
                        gt_match_iou=target.gt_match_iou,
                        gt_match_score=target.gt_match_score,
                        gt_match_status=target.gt_match_status,
                    ),
                )
            )
        return records

    def _select_targets(
        self,
        sample: VinOfflineSample,
        *,
        oracle_sampler: OracleTargetTaskSampler,
    ) -> _RolloutTargetSelectionResult:
        """Return rollout-ready target rows from oracle target-task sampling."""

        result = oracle_sampler.sample(sample)
        selected = tuple(_oracle_target_task_to_candidate_row(row) for row in result.selected_rows)
        reason = "no_identity_valid_oracle_target_tasks" if result.rows else "no_oracle_target_tasks"
        return _RolloutTargetSelectionResult(
            rows=tuple(_oracle_target_task_to_candidate_row(row) for row in result.rows),
            selected_rows=selected,
            source=result.source,
            warnings=result.warnings,
            empty_reason=reason,
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
        result: CounterfactualRolloutResult,
        sample: VinOfflineSample,
        renderer: CandidateDepthRenderer,
    ) -> None:
        """Render and attach one high-resolution selected-depth map per retained step."""

        if sample.efm_snippet_view is None:
            raise ValueError("Selected-depth persistence requires sample.efm_snippet_view.")
        for trajectory in result.trajectories:
            for step in trajectory.steps:
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
                step.selected_depth_m = depth
                step.selected_depth_valid_mask = valid_mask
                step.selected_depth_focal_px = (float(focal[0].item()), float(focal[1].item()))
                step.selected_depth_principal_point_px = (float(principal[0].item()), float(principal[1].item()))
                step.selected_depth_image_size_hw = (int(size_wh[1].item()), int(size_wh[0].item()))

    def _target_selection_temperature(self) -> float | None:
        return None

    def _target_selection_policy(self) -> str:
        return "oracle_identity_valid_uniform"


def _lineage_split(*, records: list[object], fallback: str) -> str:
    """Return the concrete shard split when selected records do not mix splits."""

    splits = {str(record.split) for record in records}
    return next(iter(splits)) if len(splits) == 1 else str(fallback)


def _oracle_target_task_to_candidate_row(row: OracleTargetTaskRow) -> TargetCandidateRow:
    """Adapt an oracle GT target-task row to the rollout target lineage DTO."""

    reason_bitset, primary_reason = _oracle_target_invalidity(row)
    gt_valid = row.identity_status == TargetTaskIdentityStatus.MATCHED.value
    return TargetCandidateRow(
        scene_id=row.scene_id,
        snippet_id=row.snippet_id,
        source=row.source,
        source_index=row.source_index,
        target_row_id=row.target_row_id,
        target_id=row.target_id,
        sem_id=row.sem_id,
        inst_id=row.inst_id,
        class_name=row.class_name,
        confidence=row.confidence,
        center_world=row.center_world,
        extents=row.extents,
        pose_world_object=row.pose_world_object,
        relative_pose_reference_object=row.relative_pose_reference_object,
        projected_area_pixels=row.projected_area_pixels,
        projected_area_fraction=row.projected_area_fraction,
        semidense_support_count=row.semidense_support_count,
        evl_support_count=row.evl_support_count,
        effective_support_count=row.effective_support_count,
        visibility_score=1.0,
        support_score=1.0,
        deficit_score=0.0,
        score=float(row.identity_iou) if row.identity_iou is not None else float("nan"),
        eligible=gt_valid,
        invalid_reason_bitset=reason_bitset,
        primary_invalid_reason=primary_reason,
        selected_rank=row.selected_rank,
        selection_probability=row.selection_probability,
        gt_label_valid=gt_valid,
        gt_target_row_id=row.source_index if gt_valid else None,
        gt_target_id=row.target_id if gt_valid else None,
        gt_match_iou=row.identity_iou,
        gt_match_score=row.identity_iou,
        gt_match_status="matched" if gt_valid else row.identity_status,
    )


def _oracle_target_invalidity(row: OracleTargetTaskRow) -> tuple[int, int]:
    if row.identity_status == TargetTaskIdentityStatus.MATCHED.value:
        return 1 << TARGET_INVALID_REASON_CODES["VALID"], TARGET_INVALID_REASON_CODES["VALID"]
    if row.identity_status == TargetTaskIdentityStatus.AMBIGUOUS.value:
        reason = TARGET_INVALID_REASON_CODES["TARGET_GT_AMBIGUOUS"]
    elif row.identity_status == TargetTaskIdentityStatus.INVALID_GEOMETRY.value:
        reason = TARGET_INVALID_REASON_CODES["OBB_EXTENT_INVALID"]
    else:
        reason = TARGET_INVALID_REASON_CODES["TARGET_GT_UNMATCHED"]
    return 1 << reason, reason


__all__ = [
    "RolloutDatasetWriter",
    "RolloutDatasetWriterConfig",
    "RolloutDatasetWriterStats",
    "RolloutRecipeConfig",
    "SelectedDepthRetentionConfig",
]
