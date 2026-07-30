"""Run bounded local rollout campaigns over immutable source and replay shards.

The campaign control plane selects one deterministic eligible root per ASE
scene, builds each root as an independent one-row VIN store, and expands it
into scene/profile rollout shards.  Completed source stores and rollout shards
are never rewritten: progress is an append-only JSONL ledger, rollout payloads
use :func:`run_rollout_shard`, and collection growth registers validated shard
directories without copying their arrays.
"""

from __future__ import annotations

import json
import os
import shutil
import time
from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path
from typing import Any, Literal

from pydantic import Field, field_validator, model_validator

from ...configs import PathConfig
from ...data_handling.vin_store.dataset import VinOfflineDatasetConfig, VinOfflineSample
from ...data_handling.vin_store.store import VinOfflineStoreConfig
from ...pose_generation.candidate_mixture import CandidateMixtureViewGeneratorConfig
from ...rollouts.collection import RolloutCollection, RolloutShardLogicalKey
from ...rollouts.replay.policy import CounterfactualSelectionPolicy, RolloutPolicySpec
from ...utils import BaseConfig, TargetConfig
from ...utils.fingerprints import stable_config_hash
from ..target_selection import ObservedTargetTaskSamplerConfig
from .offline_vin import VinOfflineWriterConfig
from .rollout_dataset import RolloutDatasetWriterConfig, RolloutRecipeConfig
from .root_selection import (
    RankedSnippet,
    RootInventory,
    SceneRootCandidates,
    discover_ase_root_inventory,
    write_root_inventory,
)
from .shards import plan_rollout_shards, run_rollout_shard

CAMPAIGN_EVENT_VERSION = "rollout-campaign-event-v1"
"""Version of campaign progress ledger rows."""


class CampaignSourceIneligibleError(RuntimeError):
    """One source snippet has no scientifically admissible V1 target."""


class CampaignSceneExhaustedError(RuntimeError):
    """Every deterministic reserve for one scene is scientifically ineligible."""


def _default_recipes() -> list[RolloutRecipeConfig]:
    """Return the mandatory realistic rollout recipe suite."""

    return [
        RolloutRecipeConfig(
            name="random_valid_h1_s0",
            policy=RolloutPolicySpec(
                selection_policy=CounterfactualSelectionPolicy.RANDOM_VALID,
                horizon=1,
                branch_factor=1,
                seed=0,
            ),
        ),
        RolloutRecipeConfig(
            name="farthest_history_h1",
            policy=RolloutPolicySpec(
                selection_policy=CounterfactualSelectionPolicy.FARTHEST_FROM_HISTORY,
                horizon=1,
                branch_factor=1,
                seed=0,
            ),
        ),
        RolloutRecipeConfig(
            name="oracle_greedy_h1",
            policy=RolloutPolicySpec(
                selection_policy=CounterfactualSelectionPolicy.ORACLE_GREEDY,
                horizon=1,
                branch_factor=1,
                seed=0,
            ),
        ),
        RolloutRecipeConfig(
            name="oracle_lookahead_h2",
            policy=RolloutPolicySpec(
                selection_policy=CounterfactualSelectionPolicy.ORACLE_GREEDY,
                horizon=2,
                branch_factor=2,
                beam_width=2,
                seed=0,
            ),
        ),
        RolloutRecipeConfig(
            name="temperature_h2_t10_s0",
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


def _radial_backtrack_60() -> CandidateMixtureViewGeneratorConfig:
    """Return the radial/backtrack preset normalized to 60 candidates."""

    config = CandidateMixtureViewGeneratorConfig.radial_target_backtrack_family()
    counts = (20, 20, 15, 5)
    return config.model_copy(
        update={
            "components": [
                component.model_copy(update={"count": count})
                for component, count in zip(config.components, counts, strict=True)
            ]
        }
    )


class CampaignRuntimeConfig(BaseConfig):
    """Bound one local campaign invocation without changing scientific axes."""

    max_new_shards: int | None = Field(default=None, ge=1)
    """Maximum freshly completed rollout shards; skipped shards do not count."""

    stop_after_minutes: float | None = Field(default=None, gt=0.0)
    """Optional wall-clock budget checked between immutable work units."""

    keep_free_disk_gib: float = Field(default=75.0, ge=0.0)
    """Minimum free local disk space required before starting another unit."""

    max_failed_units: int = Field(default=3, ge=1)
    """Maximum rollout-unit failures before aborting the invocation."""


class CandidateProfileConfig(BaseConfig):
    """Named candidate family and the rollout recipes paired within its shard."""

    candidate_mixture: CandidateMixtureViewGeneratorConfig = Field(default_factory=CandidateMixtureViewGeneratorConfig)
    """Finite candidate generator; main campaign profiles must contain exactly 60 rows."""

    recipes: list[RolloutRecipeConfig] = Field(default_factory=_default_recipes)
    """Policy, horizon, branching, and seed recipes persisted in this profile shard."""

    @model_validator(mode="after")
    def _validate_profile(self) -> "CandidateProfileConfig":
        if self.candidate_mixture.total_count != 60:
            raise ValueError("Campaign candidate profiles must each contain exactly 60 candidates.")
        if not self.recipes:
            raise ValueError("Campaign candidate profiles require at least one rollout recipe.")
        names = [recipe.name for recipe in self.recipes]
        if len(set(names)) != len(names):
            raise ValueError("Campaign rollout recipe names must be unique within a profile.")
        return self


def _default_profiles() -> dict[str, CandidateProfileConfig]:
    """Return the coverage-spine and three challenger profile defaults."""

    return {
        "realistic_core_60": CandidateProfileConfig(),
        "rich_local_60": CandidateProfileConfig(
            candidate_mixture=CandidateMixtureViewGeneratorConfig.rich_local_five_family()
        ),
        "radial_backtrack_60": CandidateProfileConfig(candidate_mixture=_radial_backtrack_60()),
        "free_shell_upper_bound_60": CandidateProfileConfig(
            candidate_mixture=CandidateMixtureViewGeneratorConfig.upper_bound_free_shell(count=60)
        ),
    }


class RolloutCampaignConfig(TargetConfig["RolloutCampaign"]):
    """Central configuration for a resumable local 100-scene rollout campaign."""

    @property
    def target_type(self) -> type["RolloutCampaign"]:
        """Return the local campaign runtime type."""

        return RolloutCampaign

    campaign_id: str = "ase-v1-local-100scene"
    """Stable collection and progress identity shared by resumed invocations."""

    seed: int = 20260728
    """Root ranking, panel assignment, and challenger balancing seed."""

    expected_scene_count: int = Field(default=100, ge=1)
    """Exact GT-mesh scene coverage required before any source build starts."""

    ase_efm_dir: Path = Path(".data/ase_efm")
    """Local root containing one ATEK EFM shard directory per scene."""

    ase_meshes_dir: Path = Path(".data/ase_meshes")
    """Local root containing one ``scene_ply_<scene>.ply`` GT mesh per scene."""

    output_root: Path = Path(".data/offline_cache/rollout_campaign_v1_local_100scene")
    """Local owner for one-row source stores, rollout shards, and attempt evidence."""

    evidence_dir: Path = Path(".configs/evidence/rollouts/local_100scene")
    """Directory containing root inventory, progress JSONL, and status snapshots."""

    collection_dir: Path = Path(".data/offline_cache/rollout_collection_v1_local_100scene")
    """Append-only collection control-plane directory for validated rollout shards."""

    source_writer: VinOfflineWriterConfig = Field(default_factory=VinOfflineWriterConfig)
    """Base one-row VIN source build; scene, snippet, shard, and output are derived per attempt."""

    writer: RolloutDatasetWriterConfig = Field(default_factory=RolloutDatasetWriterConfig)
    """Base rollout writer; source, target sampler, profile, recipes, and output are derived per unit."""

    target_sampler: ObservedTargetTaskSamplerConfig = Field(default_factory=ObservedTargetTaskSamplerConfig)
    """V1 observed-to-GT IoU matcher; ``None`` target cap admits every match."""

    profiles: dict[str, CandidateProfileConfig] = Field(default_factory=_default_profiles)
    """Complete candidate and recipe family map owned by the campaign TOML."""

    realistic_profile: str = "realistic_core_60"
    """Coverage-spine profile assigned to every admitted source root."""

    challenger_profiles: tuple[str, ...] = (
        "rich_local_60",
        "radial_backtrack_60",
        "free_shell_upper_bound_60",
    )
    """Profiles assigned in deterministic balanced scene order."""

    paired_panel_scene_count: int = Field(default=20, ge=0)
    """Stable scene count receiving every profile for paired family comparison."""

    runtime: CampaignRuntimeConfig = Field(default_factory=CampaignRuntimeConfig)
    """Local stopping and resource limits checked between immutable units."""

    @field_validator(
        "ase_efm_dir",
        "ase_meshes_dir",
        "output_root",
        "evidence_dir",
        "collection_dir",
        mode="before",
    )
    @classmethod
    def _resolve_repo_path(cls, value: Path | str) -> Path:
        """Resolve campaign paths against the repository root, not the shell CWD."""

        return PathConfig().resolve_under_root(value)

    @model_validator(mode="after")
    def _validate_campaign(self) -> "RolloutCampaignConfig":
        if not self.campaign_id.strip():
            raise ValueError("campaign_id must be non-empty.")
        required_names = {self.realistic_profile, *self.challenger_profiles}
        missing = sorted(required_names.difference(self.profiles))
        if missing:
            raise ValueError(f"Campaign profile assignment references missing profiles: {missing}.")
        if len(set(self.challenger_profiles)) != len(self.challenger_profiles):
            raise ValueError("challenger_profiles must be unique.")
        if not self.challenger_profiles:
            raise ValueError("Campaign requires at least one challenger profile.")
        if self.realistic_profile in self.challenger_profiles:
            raise ValueError("realistic_profile must not also be a challenger profile.")
        if self.paired_panel_scene_count > self.expected_scene_count:
            raise ValueError("paired_panel_scene_count cannot exceed expected_scene_count.")
        if self.target_sampler.max_targets_per_sample is not None:
            raise ValueError("The local coverage campaign must admit every IoU-matched target.")
        if self.writer.max_targets_per_sample is not None:
            raise ValueError("The rollout writer target cap must be None for all-target generation.")
        if not self.source_writer.include_gt_obbs or not self.source_writer.include_detected_obbs:
            raise ValueError("Campaign source stores must persist both GT and detected OBB blocks.")
        if not self.source_writer.include_trajectory_metadata:
            raise ValueError("Campaign source stores must persist trajectory metadata.")
        if not self.source_writer.include_backbone:
            raise ValueError("Campaign source stores require actor-visible backbone detections.")
        return self

    @property
    def root_inventory_path(self) -> Path:
        """Return the deterministic root/reserve evidence path."""

        return self.evidence_dir / "root_inventory.json"

    @property
    def progress_path(self) -> Path:
        """Return the append-only campaign event ledger path."""

        return self.evidence_dir / "progress.jsonl"

    @property
    def status_path(self) -> Path:
        """Return the atomically regenerated campaign status path."""

        return self.evidence_dir / "status.json"


@dataclass(frozen=True, slots=True)
class CampaignSourceSelection:
    """Validated one-row VIN source chosen for one scene after reserve fallback."""

    scene_id: str
    """ASE scene identifier."""

    candidate: RankedSnippet
    """Selected deterministic snippet candidate."""

    store_dir: Path
    """Immutable one-row VIN store containing required V1 evidence."""

    split: str
    """Persisted scene-level split for rollout lineage."""

    target_ids: tuple[str, ...]
    """Every V1 observed target admitted by the configured IoU matcher."""


@dataclass(frozen=True, slots=True)
class RolloutCampaignRunResult:
    """Bounded invocation result with durable artifact paths and shard counts."""

    reason: Literal["complete", "incomplete", "max_new_shards", "time_limit", "disk_limit", "failure_limit"]
    """Reason the invocation stopped between immutable units."""

    new_shards: int
    """Number of rollout shards freshly completed during this invocation."""

    skipped_shards: int
    """Number of already validated shards reused during this invocation."""

    failed_shards: int
    """Number of rollout units whose fresh attempt raised an exception."""

    failed_scenes: int
    """Number of scenes whose deterministic reserves had no admissible V1 target."""

    progress_path: Path
    """Append-only JSONL event ledger."""

    status_path: Path
    """Latest atomically written status summary."""


class RolloutCampaign:
    """Execute deterministic local source selection and immutable rollout units."""

    def __init__(self, config: RolloutCampaignConfig) -> None:
        self.config = config
        self._started = 0.0

    def paired_panel_scene_ids(self, inventory: RootInventory) -> tuple[str, ...]:
        """Return the stable scene subset receiving all candidate profiles."""

        ranked = sorted(
            (scene.scene_id for scene in inventory.scenes),
            key=lambda scene_id: (_digest(self.config.seed, "panel", scene_id), scene_id),
        )
        return tuple(ranked[: self.config.paired_panel_scene_count])

    def planned_profiles_by_scene(self, inventory: RootInventory) -> dict[str, tuple[str, ...]]:
        """Expand balanced challenger and paired-panel assignments deterministically."""

        panel = set(self.paired_panel_scene_ids(inventory))
        challenger_order = sorted(
            (scene.scene_id for scene in inventory.scenes),
            key=lambda scene_id: (_digest(self.config.seed, "challenger", scene_id), scene_id),
        )
        challenger_by_scene = {
            scene_id: self.config.challenger_profiles[index % len(self.config.challenger_profiles)]
            for index, scene_id in enumerate(challenger_order)
        }
        assignments: dict[str, tuple[str, ...]] = {}
        profile_order = tuple(self.config.profiles)
        for scene in inventory.scenes:
            selected = {self.config.realistic_profile, challenger_by_scene[scene.scene_id]}
            if scene.scene_id in panel:
                selected.update(profile_order)
            assignments[scene.scene_id] = tuple(name for name in profile_order if name in selected)
        return assignments

    def run(self) -> RolloutCampaignRunResult:
        """Run or resume the campaign until completion or a configured local bound.

        Source failures advance to the next deterministic reserve. Rollout
        failures are recorded and the invocation continues with other units;
        a later invocation receives a fresh temp attempt path. Bounds are
        checked only between units, so finalized shards are never partial.
        """

        self._started = time.monotonic()
        self._prepare_paths()
        inventory = discover_ase_root_inventory(
            ase_efm_dir=self.config.ase_efm_dir,
            ase_meshes_dir=self.config.ase_meshes_dir,
            seed=self.config.seed,
            expected_scene_count=self.config.expected_scene_count,
        )
        write_root_inventory(self.config.root_inventory_path, inventory, repo_root=Path.cwd())
        assignments = self.planned_profiles_by_scene(inventory)
        new_shards = skipped_shards = failed_shards = failed_scenes = 0
        stop_reason: Literal[
            "complete", "incomplete", "max_new_shards", "time_limit", "disk_limit", "failure_limit"
        ] = "complete"

        for scene in inventory.scenes:
            stop_reason = self._stop_reason(new_shards)
            if stop_reason != "complete":
                break
            try:
                source = self._select_source(scene)
            except CampaignSceneExhaustedError as exc:
                failed_scenes += 1
                self._event(
                    "scene_exhausted",
                    scene_id=scene.scene_id,
                    error=f"{type(exc).__name__}: {exc}",
                )
                continue
            except Exception as exc:
                self._event(
                    "source_failed",
                    scene_id=scene.scene_id,
                    error=f"{type(exc).__name__}: {exc}",
                )
                raise
            for profile_name in assignments[scene.scene_id]:
                stop_reason = self._stop_reason(new_shards)
                if stop_reason != "complete":
                    break
                try:
                    skipped = self._run_profile_shard(source, profile_name=profile_name)
                    if skipped:
                        skipped_shards += 1
                    else:
                        new_shards += 1
                except Exception as exc:
                    failed_shards += 1
                    self._event(
                        "rollout_failed",
                        scene_id=scene.scene_id,
                        sample_key=source.candidate.sample_key,
                        profile=profile_name,
                        error=f"{type(exc).__name__}: {exc}",
                    )
                    if failed_shards >= self.config.runtime.max_failed_units:
                        stop_reason = "failure_limit"
                        break
            if stop_reason != "complete":
                break

        if stop_reason == "complete" and (failed_scenes or failed_shards):
            stop_reason = "incomplete"

        result = RolloutCampaignRunResult(
            reason=stop_reason,
            new_shards=new_shards,
            skipped_shards=skipped_shards,
            failed_shards=failed_shards,
            failed_scenes=failed_scenes,
            progress_path=self.config.progress_path.resolve(),
            status_path=self.config.status_path.resolve(),
        )
        self._write_status(result, inventory=inventory, assignments=assignments)
        return result

    def _prepare_paths(self) -> None:
        self.config.output_root.mkdir(parents=True, exist_ok=True)
        self.config.evidence_dir.mkdir(parents=True, exist_ok=True)
        self.config.collection_dir.mkdir(parents=True, exist_ok=True)

    def _select_source(self, scene: SceneRootCandidates) -> CampaignSourceSelection:
        accepted = self._accepted_source_event(scene.scene_id)
        if accepted is not None:
            try:
                return self._validate_source_event(scene, accepted)
            except CampaignSourceIneligibleError as exc:
                self._event("source_cache_invalid", scene_id=scene.scene_id, error=f"{type(exc).__name__}: {exc}")

        rejected = {
            str(event.get("sample_key"))
            for event in self._events()
            if event.get("event") == "source_rejected" and event.get("scene_id") == scene.scene_id
        }
        for candidate in scene.candidates:
            if candidate.sample_key in rejected:
                continue
            try:
                return self._build_and_validate_source(scene, candidate)
            except CampaignSourceIneligibleError as exc:
                self._event(
                    "source_rejected",
                    scene_id=scene.scene_id,
                    sample_key=candidate.sample_key,
                    error=f"{type(exc).__name__}: {exc}",
                )
        raise CampaignSceneExhaustedError(
            f"Scene {scene.scene_id!r} has no reserve snippet with an admitted V1 target."
        )

    def _build_and_validate_source(
        self,
        scene: SceneRootCandidates,
        candidate: RankedSnippet,
    ) -> CampaignSourceSelection:
        attempt_root = self._fresh_attempt_dir(
            self.config.output_root / "sources" / scene.scene_id, candidate.rank_digest
        )
        store_dir = attempt_root / "store"
        source_config = self.config.source_writer.model_copy(deep=True)
        source_config.store = source_config.store.model_copy(update={"store_dir": store_dir})
        source_config.dataset = source_config.dataset.model_copy(
            update={
                "scene_ids": [scene.scene_id],
                "snippet_ids": [candidate.sample_key],
                "snippet_key_filter": [candidate.sample_key],
                "tar_urls": [candidate.shard_path.as_posix()],
                "scene_to_mesh": {scene.scene_id: scene.mesh_path},
                "wds_shuffle": False,
                "wds_repeat": False,
                "load_meshes": True,
                "require_mesh": True,
            }
        )
        source_config.max_samples = 1
        source_config.samples_per_shard = 1
        source_config.overwrite = False
        source_config.include_depths = False
        source_config.include_pointclouds = False
        source_config.include_diagnostic_payloads = False
        writer = source_config.setup_target()
        if writer is None:
            raise RuntimeError("VinOfflineWriterConfig did not instantiate a writer.")
        manifest = writer.run()
        if bool(manifest.stats.get("interrupted", False)):
            self._event(
                "source_interrupted",
                scene_id=scene.scene_id,
                sample_key=candidate.sample_key,
                store_dir=store_dir.resolve().as_posix(),
            )
            raise KeyboardInterrupt
        selection = self._open_source_selection(scene, candidate, store_dir)
        self._event(
            "source_selected",
            scene_id=scene.scene_id,
            sample_key=candidate.sample_key,
            rank_digest=candidate.rank_digest,
            store_dir=store_dir.resolve().as_posix(),
            split=selection.split,
            target_ids=list(selection.target_ids),
        )
        return selection

    def _open_source_selection(
        self,
        scene: SceneRootCandidates,
        candidate: RankedSnippet,
        store_dir: Path,
    ) -> CampaignSourceSelection:
        source = VinOfflineDatasetConfig(
            store=VinOfflineStoreConfig(store_dir=store_dir),
            split=None,
            limit=1,
            include_efm_snippet=True,
            include_gt_mesh=True,
            load_backbone=True,
            load_candidates=False,
            load_depths=False,
            load_candidate_pcs=False,
            load_gt_obbs=True,
            load_detected_obbs=True,
            load_trajectory_metadata=True,
            return_format="sample",
        )
        dataset = source.setup_target()
        if dataset is None or len(dataset) != 1:
            raise RuntimeError(
                f"Expected one VIN source row in {store_dir}; found {0 if dataset is None else len(dataset)}."
            )
        sample = dataset[0]
        if not isinstance(sample, VinOfflineSample):
            raise TypeError("Campaign VIN source reader did not return VinOfflineSample.")
        if sample.efm_snippet_view is None or sample.efm_snippet_view.mesh is None:
            raise RuntimeError("Campaign source row is missing its live EFM snippet or GT mesh.")
        if sample.gt_obbs is None or sample.detected_obbs is None or sample.trajectory is None:
            raise RuntimeError("Campaign source row is missing GT OBB, detected OBB, or trajectory evidence.")
        matching = self.config.target_sampler.setup_target()
        if matching is None:
            raise RuntimeError("ObservedTargetTaskSamplerConfig did not instantiate a sampler.")
        target_result = matching.sample(sample)
        target_ids = tuple(row.target_id for row in target_result.selected_rows)
        if not target_ids:
            raise CampaignSourceIneligibleError("V1 observed-to-GT matching admitted no target.")
        return CampaignSourceSelection(
            scene_id=scene.scene_id,
            candidate=candidate,
            store_dir=store_dir.resolve(),
            split=str(sample.split),
            target_ids=target_ids,
        )

    def _validate_source_event(
        self,
        scene: SceneRootCandidates,
        event: dict[str, Any],
    ) -> CampaignSourceSelection:
        sample_key = str(event["sample_key"])
        candidate = next(candidate for candidate in scene.candidates if candidate.sample_key == sample_key)
        return self._open_source_selection(scene, candidate, Path(str(event["store_dir"])))

    def _run_profile_shard(self, source: CampaignSourceSelection, *, profile_name: str) -> bool:
        profile = self.config.profiles[profile_name]
        final_dir = self.config.output_root / "rollouts" / source.scene_id / profile_name / "shard-000000"
        writer_config = self._derive_writer_config(source, profile=profile, final_dir=final_dir)
        entries = plan_rollout_shards(writer_config, rows_per_shard=1)
        if len(entries) != 1:
            raise RuntimeError(
                f"Expected exactly one rollout shard for scene {source.scene_id}; planned {len(entries)}."
            )
        entry = entries[0]
        temp_dir = self._fresh_temp_path(final_dir)
        result = run_rollout_shard(
            writer_config,
            shard_entry=entry,
            output_tmp=temp_dir,
            output_final=final_dir,
        )
        recipe_group = stable_config_hash(profile, length=16)
        logical_key = RolloutShardLogicalKey(
            campaign_id=self.config.campaign_id,
            split=entry.split,
            source_sample_key=entry.rows[0].sample_key,
            target_id="all-admitted-targets",
            candidate_profile=profile_name,
            recipe_group=recipe_group,
            seed_group=f"campaign-seed-{self.config.seed}",
        )
        RolloutCollection(self.config.collection_dir).register_shard(final_dir, logical_key=logical_key)
        self._event(
            "rollout_skipped" if result.skipped else "rollout_succeeded",
            scene_id=source.scene_id,
            sample_key=source.candidate.sample_key,
            profile=profile_name,
            final_dir=final_dir.resolve().as_posix(),
            target_ids=list(source.target_ids),
            recipe_group=recipe_group,
        )
        return result.skipped

    def _derive_writer_config(
        self,
        source: CampaignSourceSelection,
        *,
        profile: CandidateProfileConfig,
        final_dir: Path,
    ) -> RolloutDatasetWriterConfig:
        source_reader = VinOfflineDatasetConfig(
            store=VinOfflineStoreConfig(store_dir=source.store_dir),
            split=None,
            limit=1,
            include_efm_snippet=True,
            include_gt_mesh=True,
            load_backbone=True,
            load_candidates=False,
            load_depths=False,
            load_candidate_pcs=False,
            load_gt_obbs=True,
            load_detected_obbs=True,
            load_trajectory_metadata=True,
            return_format="sample",
        )
        rollout_store = self.config.writer.store.__class__.model_validate(
            {
                **self.config.writer.store.model_dump(),
                "store_dir": final_dir,
                "target_protocol_version": "v1_observed",
            }
        )
        updates: dict[str, Any] = {
            "source": source_reader,
            "source_manifest_path": None,
            "sample_keys": None,
            "candidate_mixture": profile.candidate_mixture,
            "recipes": profile.recipes,
            "max_samples": 1,
            "max_targets_per_sample": None,
            "store": rollout_store,
        }
        sampler_fields = (
            "observed_target_task_sampler",
            "target_task_sampler",
            "oracle_target_task_sampler",
        )
        sampler_field = next(
            (name for name in sampler_fields if name in RolloutDatasetWriterConfig.model_fields),
            None,
        )
        if sampler_field is None:
            raise RuntimeError("RolloutDatasetWriterConfig has no target-task sampler field.")
        updates[sampler_field] = self.config.target_sampler
        try:
            return RolloutDatasetWriterConfig.model_validate({**self.config.writer.model_dump(), **updates})
        except Exception as exc:
            raise RuntimeError(
                "RolloutDatasetWriterConfig does not yet admit the V1 observed target sampler integration."
            ) from exc

    def _stop_reason(
        self,
        new_shards: int,
    ) -> Literal["complete", "max_new_shards", "time_limit", "disk_limit"]:
        runtime = self.config.runtime
        if runtime.max_new_shards is not None and new_shards >= runtime.max_new_shards:
            return "max_new_shards"
        if runtime.stop_after_minutes is not None:
            elapsed_minutes = (time.monotonic() - self._started) / 60.0
            if elapsed_minutes >= runtime.stop_after_minutes:
                return "time_limit"
        free_gib = _free_disk_gib(self.config.output_root)
        if free_gib < runtime.keep_free_disk_gib:
            return "disk_limit"
        return "complete"

    def _accepted_source_event(self, scene_id: str) -> dict[str, Any] | None:
        matches = [
            event
            for event in self._events()
            if event.get("event") == "source_selected" and event.get("scene_id") == scene_id
        ]
        return matches[-1] if matches else None

    def _events(self) -> list[dict[str, Any]]:
        try:
            lines = self.config.progress_path.read_text(encoding="utf-8").splitlines()
        except FileNotFoundError:
            return []
        return [json.loads(line) for line in lines if line.strip()]

    def _event(self, event: str, **payload: Any) -> None:
        row = {
            "version": CAMPAIGN_EVENT_VERSION,
            "campaign_id": self.config.campaign_id,
            "event": event,
            "time_unix_s": time.time(),
            **payload,
        }
        self.config.progress_path.parent.mkdir(parents=True, exist_ok=True)
        with self.config.progress_path.open("a", encoding="utf-8") as stream:
            stream.write(json.dumps(row, sort_keys=True) + "\n")
            stream.flush()
            os.fsync(stream.fileno())
        self._write_live_status()

    def _write_live_status(self) -> None:
        """Atomically summarize durable events after every lifecycle transition."""

        event_counts: dict[str, int] = {}
        for event in self._events():
            name = str(event.get("event", "unknown"))
            event_counts[name] = event_counts.get(name, 0) + 1
        _write_json_atomic(
            self.config.status_path,
            {
                "version": "rollout-campaign-status-v1",
                "campaign_id": self.config.campaign_id,
                "config_hash": stable_config_hash(self.config),
                "state": "running",
                "event_counts": dict(sorted(event_counts.items())),
                "collection_dir": self.config.collection_dir.resolve().as_posix(),
            },
        )

    def _write_status(
        self,
        result: RolloutCampaignRunResult,
        *,
        inventory: RootInventory,
        assignments: dict[str, tuple[str, ...]],
    ) -> None:
        events = self._events()
        event_counts: dict[str, int] = {}
        for event in events:
            name = str(event.get("event", "unknown"))
            event_counts[name] = event_counts.get(name, 0) + 1
        payload = {
            "version": "rollout-campaign-status-v1",
            "campaign_id": self.config.campaign_id,
            "config_hash": stable_config_hash(self.config),
            "reason": result.reason,
            "invocation": {
                "new_shards": result.new_shards,
                "skipped_shards": result.skipped_shards,
                "failed_shards": result.failed_shards,
                "failed_scenes": result.failed_scenes,
            },
            "planned": {
                "scenes": len(inventory.scenes),
                "scene_profiles": sum(len(names) for names in assignments.values()),
            },
            "event_counts": dict(sorted(event_counts.items())),
            "collection_dir": self.config.collection_dir.resolve().as_posix(),
        }
        _write_json_atomic(self.config.status_path, payload)

    @staticmethod
    def _fresh_attempt_dir(parent: Path, identity: str) -> Path:
        parent.mkdir(parents=True, exist_ok=True)
        index = 0
        while True:
            candidate = parent / f"{identity[:12]}-attempt-{index:04d}"
            if not candidate.exists() and not candidate.with_name(f"{candidate.name}.tmp").exists():
                candidate.mkdir(parents=True)
                return candidate
            index += 1

    @staticmethod
    def _fresh_temp_path(final_dir: Path) -> Path:
        final_dir.parent.mkdir(parents=True, exist_ok=True)
        index = 0
        while True:
            candidate = final_dir.parent / f".{final_dir.name}.attempt-{index:04d}.tmp"
            if not candidate.exists():
                return candidate
            index += 1


def _digest(seed: int, namespace: str, value: str) -> str:
    """Return a deterministic assignment digest."""

    return sha256(f"{seed}:{namespace}:{value}".encode()).hexdigest()


def _free_disk_gib(path: Path) -> float:
    """Return free GiB at the nearest existing parent of ``path``."""

    probe = path.expanduser().resolve()
    while not probe.exists() and probe != probe.parent:
        probe = probe.parent
    return float(shutil.disk_usage(probe).free) / float(1024**3)


def _write_json_atomic(path: Path, payload: dict[str, Any]) -> None:
    """Write one JSON object by atomic replacement."""

    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_name(f".{path.name}.tmp")
    temp.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    os.replace(temp, path)


__all__ = [
    "CAMPAIGN_EVENT_VERSION",
    "CampaignRuntimeConfig",
    "CampaignSceneExhaustedError",
    "CampaignSourceSelection",
    "CampaignSourceIneligibleError",
    "CandidateProfileConfig",
    "RolloutCampaign",
    "RolloutCampaignConfig",
    "RolloutCampaignRunResult",
]
