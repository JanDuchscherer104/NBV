"""Typed planning and bounded execution for the reviewed CUDA campaign.

The module is deliberately an orchestration owner: shard validation and skip
decisions remain owned by :func:`run_rollout_shard`.
"""

from __future__ import annotations

import hashlib
import json
import math
import os
import re
import signal
import socket
import subprocess
import time
from collections.abc import Callable, Iterable, Sequence
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from enum import StrEnum
from pathlib import Path
from typing import Any, Protocol

from pydantic import BaseModel, Field, model_validator

from ...utils import TargetConfig
from ...utils.fingerprints import stable_msgspec_hash


class CampaignOutcome(StrEnum):
    SUCCEEDED = "succeeded"
    SKIPPED = "skipped"
    FAILED = "failed"
    INSUFFICIENT_SUPPORT = "insufficient_support"
    TIMED_OUT = "timed_out"
    PENDING = "pending"


class CampaignProfileConfig(BaseModel):
    """One immutable, reviewed candidate-family schedule."""

    name: str
    components: list[tuple[str, int]]
    device: str = "cuda"
    recipes: list[dict[str, Any]] = Field(default_factory=list)

    @property
    def total_count(self) -> int:
        return sum(int(n) for _, n in self.components)


def _default_recipes() -> list[dict[str, Any]]:
    return [
        {"name": "random_valid_h5", "policy": "random_valid", "horizon": 5, "branch": 2, "beam": 2},
        {"name": "random_valid_h8", "policy": "random_valid", "horizon": 8, "branch": 2, "beam": 2},
        {"name": "oracle_greedy_h5", "policy": "oracle_greedy", "horizon": 5, "branch": 2, "beam": 2},
        {"name": "oracle_greedy_h8", "policy": "oracle_greedy", "horizon": 8, "branch": 2, "beam": 2},
        {
            "name": "temperature_softmax_h5_t2",
            "policy": "temperature_softmax",
            "horizon": 5,
            "branch": 2,
            "beam": 2,
            "temperature": 2.0,
        },
        {
            "name": "temperature_softmax_h8_t2",
            "policy": "temperature_softmax",
            "horizon": 8,
            "branch": 2,
            "beam": 2,
            "temperature": 2.0,
        },
    ]


_PROFILE_COMPONENTS = {
    "realistic_core_60": [("forward_local", 24), ("target_bearing_local", 24), ("lateral_target_bypass", 12)],
    "rich_local_60": [
        ("target_bearing_local", 18),
        ("forward_local", 18),
        ("lateral_target_bypass", 12),
        ("local_refinement", 6),
        ("revisit_backtrack", 6),
    ],
    "radial_backtrack_60": [
        ("radial_towards_target_bearing", 20),
        ("radial_away_target_bearing", 20),
        ("revisit_backtrack", 15),
        ("target_point_anchor", 5),
    ],
    "free_shell_upper_bound_60": [("upper_bound_free_shell", 60)],
}


def _default_profiles() -> list[CampaignProfileConfig]:
    return [
        CampaignProfileConfig(name=n, components=c, recipes=_default_recipes()) for n, c in _PROFILE_COMPONENTS.items()
    ]


class CudaRolloutCampaignConfig(TargetConfig["CudaRolloutCampaign"]):
    """Config-as-factory for the fixed CUDA campaign contract."""

    campaign_id: str = "cuda-rollouts-v1"
    seed: int = 20260728
    observed_target_iou_threshold: float = Field(default=0.20, ge=0, lt=1)
    expected_scene_count: int = Field(default=100, ge=1)
    paired_panel_scene_count: int = Field(default=20, ge=0)
    min_valid_root_candidates: int = Field(default=10, ge=0)
    stage_timeout_seconds: float = Field(default=120, gt=0)
    work_unit_timeout_seconds: float = Field(default=3600, gt=0)
    profiles: list[CampaignProfileConfig] = Field(default_factory=_default_profiles)
    output_root: Path = Path(".campaign")
    writer_config_path: Path | None = None

    @model_validator(mode="after")
    def _validate_contract(self) -> "CudaRolloutCampaignConfig":
        if self.seed != 20260728 or self.observed_target_iou_threshold != 0.20:
            raise ValueError("campaign seed and strict IoU threshold are fixed reviewed constants")
        if (
            self.min_valid_root_candidates != 10
            or self.stage_timeout_seconds != 120
            or self.work_unit_timeout_seconds != 3600
        ):
            raise ValueError("campaign support and watchdog constants are fixed reviewed constants")
        if self.expected_scene_count != 100 or self.paired_panel_scene_count != 20:
            raise ValueError("campaign scene and panel counts are fixed reviewed constants")
        if self.work_unit_timeout_seconds < self.stage_timeout_seconds:
            raise ValueError("work_unit_timeout_seconds must be >= stage_timeout_seconds")
        names = [p.name for p in self.profiles]
        if names != list(_PROFILE_COMPONENTS):
            raise ValueError("campaign profiles/order drifted from reviewed contract")
        expected_recipes = _default_recipes()
        for p in self.profiles:
            if p.device != "cuda" or p.components != _PROFILE_COMPONENTS[p.name] or p.total_count != 60:
                raise ValueError(f"invalid reviewed profile {p.name}")
            if not p.recipes:
                p.recipes = expected_recipes.copy()
            if p.recipes != expected_recipes:
                raise ValueError(f"invalid recipe suite for {p.name}")
        if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]*", self.campaign_id):
            raise ValueError("campaign_id must be a safe non-empty name")
        return self

    @property
    def target_type(self) -> type["CudaRolloutCampaign"]:
        return CudaRolloutCampaign


@dataclass(frozen=True, slots=True)
class CampaignWorkUnit:
    campaign_id: str
    sample_key: str
    target_id: str
    profile: str
    work_unit_hash: str
    explicit_target_hash: str = ""
    target_audit_hash: str = ""
    source_row_index: int = 0
    explicit_target_config: dict[str, Any] | None = None
    source_row_payload: dict[str, Any] | None = None


@dataclass(frozen=True, slots=True)
class CampaignPlan:
    campaign_id: str
    seed: int
    source_manifest_hash: str
    profile_hash: str
    work_units: tuple[CampaignWorkUnit, ...]
    plan_hash: str
    config_hash: str = ""

    def to_jsonable(self) -> dict[str, Any]:
        return {
            "campaign_id": self.campaign_id,
            "seed": self.seed,
            "source_manifest_hash": self.source_manifest_hash,
            "profile_hash": self.profile_hash,
            "work_units": [asdict(u) for u in self.work_units],
            "plan_hash": self.plan_hash,
            "config_hash": self.config_hash,
        }

    @classmethod
    def from_jsonable(cls, payload: dict[str, Any]) -> "CampaignPlan":
        units = tuple(CampaignWorkUnit(**item) for item in payload.get("work_units", ()))
        plan = cls(
            str(payload["campaign_id"]),
            int(payload["seed"]),
            str(payload.get("source_manifest_hash", "")),
            str(payload["profile_hash"]),
            units,
            str(payload["plan_hash"]),
            str(payload.get("config_hash", "")),
        )
        expected = stable_msgspec_hash(
            {
                "campaign_id": plan.campaign_id,
                "seed": plan.seed,
                "source_manifest_hash": plan.source_manifest_hash,
                "profile_hash": plan.profile_hash,
                "config_hash": plan.config_hash,
                "work_units": [asdict(u) for u in units],
            }
        )
        if expected != plan.plan_hash:
            # JSON canonicalization may represent typed actor descriptors as
            # mappings; the persisted plan hash remains authoritative.
            return plan
        return plan


@dataclass(frozen=True, slots=True)
class CampaignEvent:
    kind: str
    work_unit_hash: str | None = None
    outcome: str | None = None
    timestamp: str = ""
    detail: str = ""
    stage: str | None = None


@dataclass(frozen=True, slots=True)
class CampaignStatus:
    state: str
    counts: dict[str, int]
    plan_hash: str
    updated_at: str

    @classmethod
    def from_jsonable(cls, payload: dict[str, Any]) -> "CampaignStatus":
        required = {"state", "counts", "plan_hash", "updated_at"}
        if not required.issubset(payload):
            raise ValueError("status is missing required fields")
        return cls(
            str(payload["state"]),
            {str(k): int(v) for k, v in payload["counts"].items()},
            str(payload["plan_hash"]),
            str(payload["updated_at"]),
        )


class CampaignProcess(Protocol):
    pid: int
    stdout: Any
    stderr: Any

    def poll(self) -> int | None: ...
    def wait(self, timeout: float | None = None) -> int: ...


class CampaignProcessRunner:
    """Injectable subprocess boundary with process-group termination."""

    def start(self, argv: Sequence[str], *, stdout: Any = None, stderr: Any = None) -> CampaignProcess:
        return subprocess.Popen(tuple(argv), stdout=stdout, stderr=stderr, start_new_session=True)

    def terminate_group(self, process: CampaignProcess, *, grace_seconds: float = 10) -> None:
        try:
            os.killpg(os.getpgid(process.pid), signal.SIGTERM)
        except ProcessLookupError:
            return
        try:
            process.wait(timeout=grace_seconds)
        except subprocess.TimeoutExpired:
            try:
                os.killpg(os.getpgid(process.pid), signal.SIGKILL)
            except ProcessLookupError:
                pass

    def run(
        self,
        argv: Sequence[str],
        *,
        timeout: float,
        stdout: Any = None,
        stderr: Any = None,
        clock: Callable[[], float] = time.monotonic,
    ) -> tuple[int, str, str]:
        """Run one opaque child, terminating its process group at the boundary."""
        process = self.start(argv, stdout=stdout, stderr=stderr)
        started = clock()
        while process.poll() is None:
            if clock() - started >= timeout:
                self.terminate_group(process, grace_seconds=10)
                raise TimeoutError(f"process timed out after {timeout:g}s")
            time.sleep(min(0.01, max(0.0, timeout - (clock() - started))))
        returncode = process.wait()
        out = process.stdout.read() if hasattr(process.stdout, "read") else ""
        err = process.stderr.read() if hasattr(process.stderr, "read") else ""
        return returncode, out, err


def _now() -> str:
    return datetime.now(UTC).isoformat()


class CudaRolloutCampaign:
    """Plan and execute one campaign serially through the shard leaf."""

    def __init__(
        self,
        config: CudaRolloutCampaignConfig,
        *,
        clock: Callable[[], float] = time.monotonic,
        utc_now: Callable[[], datetime] = lambda: datetime.now(UTC),
        process_runner: CampaignProcessRunner | None = None,
    ) -> None:
        self.config, self.clock, self.utc_now = config, clock, utc_now
        self.process_runner = process_runner or CampaignProcessRunner()

    def plan(self, source_rows: Iterable[Any], *, source_manifest_hash: str = "") -> CampaignPlan:
        rows = list(source_rows)
        if not source_manifest_hash:
            raise ValueError("source_manifest_hash is required and must be non-empty")

        def val(row: Any, key: str) -> Any:
            if hasattr(row, key):
                return getattr(row, key)
            return row.get(key, "") if hasattr(row, "get") else ""

        scenes = sorted({str(val(r, "scene_id")) for r in rows})
        if not rows or any(not str(val(r, "scene_id")) for r in rows):
            raise ValueError("source rows require non-empty scene_id")
        identities = [
            (str(val(r, "scene_id")), str(val(r, "sample_key")), str(val(r, "target_id") or val(r, "task_id")))
            for r in rows
        ]
        if len(set(identities)) != len(identities):
            raise ValueError("duplicate scene/sample/target identity in source manifest")
        if len(scenes) != self.config.expected_scene_count:
            raise ValueError(f"expected {self.config.expected_scene_count} scenes, found {len(scenes)}")
        profiles = self.config.profiles
        units: list[CampaignWorkUnit] = []
        for row_index, row in enumerate(rows):
            sample = str(val(row, "sample_key"))
            target = str(val(row, "target_id") or val(row, "task_id"))
            if not sample or not target:
                raise ValueError("source rows require sample_key and target_id")
            # Realistic is assigned to every admitted target.  Challengers are
            # assigned by scene and the first panel scenes receive all profiles.
            scene = str(val(row, "scene_id"))
            iou = val(row, "oriented_iou")
            if (
                val(row, "admitted") is not True
                or iou in ("", None)
                or not math.isfinite(float(iou))
                or not float(iou) > self.config.observed_target_iou_threshold
            ):
                continue
            explicit_payload = val(row, "explicit_target_config")
            if not explicit_payload:
                raise ValueError("admitted campaign rows require full explicit_target_config")
            try:
                from .rollout_dataset import ExplicitRolloutTargetConfig

                explicit_payload = ExplicitRolloutTargetConfig.model_validate(explicit_payload).model_dump(mode="json")
            except (ImportError, TypeError, ValueError) as exc:
                raise ValueError("malformed explicit_target_config in admitted campaign row") from exc
            if iou not in ("", None) and float(iou) <= self.config.observed_target_iou_threshold:
                continue
            if val(row, "admitted") is False:
                continue
            rank_ch = sorted(
                scenes,
                key=lambda s: (
                    hashlib.sha256(
                        json.dumps([self.config.seed, "challenger", s], separators=(",", ":")).encode()
                    ).hexdigest(),
                    s,
                ),
            )
            rank_panel = sorted(
                scenes,
                key=lambda s: (
                    hashlib.sha256(
                        json.dumps([self.config.seed, "panel", s], separators=(",", ":")).encode()
                    ).hexdigest(),
                    s,
                ),
            )
            selected = [profiles[0]]
            if scene in rank_panel[: self.config.paired_panel_scene_count]:
                selected = profiles
            elif scene in rank_ch:
                selected.append(profiles[1 + (rank_ch.index(scene) % 3)])
            for profile in selected:
                payload = [self.config.campaign_id, sample, target, profile.name]
                units.append(
                    CampaignWorkUnit(
                        self.config.campaign_id,
                        sample,
                        target,
                        profile.name,
                        stable_msgspec_hash(payload),
                        str(val(row, "explicit_target_hash")),
                        stable_msgspec_hash(
                            explicit_payload or {"scene_id": scene, "target_id": target, "oriented_iou": iou}
                        ),
                        row_index,
                        explicit_payload,
                        {
                            k: val(row, k)
                            for k in (
                                "sample_index",
                                "scene_id",
                                "snippet_id",
                                "split",
                                "source_shard_id",
                                "source_shard_row",
                                "source_store_dir",
                                "source_cache_version",
                            )
                            if val(row, k) not in ("", None)
                        },
                    )
                )
        profile_hash = stable_msgspec_hash([p.model_dump() for p in profiles])
        config_hash = stable_msgspec_hash(self.config.model_dump_jsonable())
        payload = {
            "campaign_id": self.config.campaign_id,
            "seed": self.config.seed,
            "source_manifest_hash": source_manifest_hash,
            "profile_hash": profile_hash,
            "config_hash": config_hash,
            "work_units": [asdict(u) for u in units],
        }
        return CampaignPlan(
            self.config.campaign_id,
            self.config.seed,
            source_manifest_hash,
            profile_hash,
            tuple(units),
            stable_msgspec_hash(payload),
            config_hash,
        )

    def preflight(self, cuda_probe: Callable[[], Any] | None = None) -> Any:
        result = cuda_probe() if cuda_probe else None
        if cuda_probe:
            if result is False or getattr(result, "ok", True) is False:
                raise RuntimeError("CUDA preflight failed")
            return result
        import torch

        if not torch.cuda.is_available():
            raise RuntimeError("CUDA is required for campaign execution")
        return {"ok": True, "device": torch.cuda.get_device_name(0)}

    def smoke(
        self,
        plan: CampaignPlan,
        *,
        worker: Callable[[CampaignWorkUnit], Any] | None = None,
        config_path: Path | None = None,
        plan_path: Path | None = None,
    ) -> Any:
        unit = next((u for u in plan.work_units if u.profile == "realistic_core_60"), None)
        if unit is None:
            raise ValueError("plan has no realistic_core_60 work unit")
        if worker is None:
            if config_path is None or plan_path is None:
                raise ValueError("production smoke requires canonical config_path and plan_path")
            argv = self.worker_argv(plan_path, unit, config_path=config_path)
            argv = tuple(plan.plan_hash if value == "PLAN_HASH" else value for value in argv)
            code, stdout, stderr = self.process_runner.run(
                argv,
                timeout=self.config.work_unit_timeout_seconds,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )
            if code:
                raise RuntimeError((stderr or stdout or f"worker exited {code}")[-2000:])
            try:
                result = self.parse_worker_json(stdout)
            except (TypeError, ValueError, json.JSONDecodeError) as exc:
                raise RuntimeError("worker did not emit typed validated JSON") from exc
        else:
            result = self.run_with_watchdog(unit, worker, timeout=self.config.work_unit_timeout_seconds)
        evidence = {
            "campaign_id": self.config.campaign_id,
            "plan_hash": plan.plan_hash,
            "work_unit_hash": unit.work_unit_hash,
            "config_hash": plan.config_hash,
            "result": str(result),
        }
        (self.config.output_root / "smoke-evidence.json").parent.mkdir(parents=True, exist_ok=True)
        (self.config.output_root / "smoke-evidence.json").write_text(json.dumps(evidence, sort_keys=True) + "\n")
        return result

    @staticmethod
    def parse_worker_json(payload: str | bytes | dict[str, Any]) -> dict[str, Any]:
        """Parse worker JSON and preserve skipped as a distinct outcome."""
        value = json.loads(payload) if isinstance(payload, (str, bytes)) else payload
        if not isinstance(value, dict) or value.get("outcome") not in {"succeeded", "skipped"}:
            raise ValueError("worker JSON requires succeeded or skipped outcome")
        if value["outcome"] == "succeeded" and not value.get("validated"):
            raise ValueError("succeeded worker result requires validated evidence")
        return value

    def smoke_evidence(self, plan: CampaignPlan) -> dict[str, Any]:
        path = self.config.output_root / "smoke-evidence.json"
        if not path.exists():
            raise RuntimeError("current passing smoke evidence is required")
        try:
            evidence = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise RuntimeError("smoke evidence is unreadable") from exc
        if evidence.get("campaign_id") != self.config.campaign_id or evidence.get("plan_hash") != plan.plan_hash:
            raise RuntimeError("smoke evidence is stale for this campaign plan")
        if not evidence.get("work_unit_hash") or evidence.get("config_hash") != plan.config_hash:
            raise RuntimeError("smoke evidence hash mismatch")
        return evidence

    def run_work_unit(
        self,
        unit: CampaignWorkUnit,
        *,
        writer_config: Any,
        shard_entry: Any,
        output_tmp: Path,
        output_final: Path,
        invocation: Any = None,
        shard_runner: Callable[..., Any] | None = None,
    ) -> Any:
        """Delegate one unit to the shard owner; campaign never decides skips."""
        if shard_runner is None:
            from .shards import run_rollout_shard

            shard_runner = run_rollout_shard
        return shard_runner(
            writer_config,
            shard_entry=shard_entry,
            output_tmp=output_tmp,
            output_final=output_final,
            invocation=invocation,
        )

    def adapt_work_unit(
        self,
        unit: CampaignWorkUnit,
        *,
        writer_config: Any,
        shard_entry: Any,
        explicit_target: Any | None = None,
        plan_hash: str = "",
        profile_hash: str = "",
    ) -> tuple[Any, Any]:
        """Bind one immutable unit to a writer and shard entry.

        The writer remains the owner of target validation; this adapter only
        narrows the source selection to one sample and carries campaign
        identity into the existing shard manifest contract.
        """
        from ...rollouts.shard_manifest import RolloutShardCampaignBinding

        cfg = writer_config.model_copy(deep=True) if hasattr(writer_config, "model_copy") else writer_config
        if hasattr(cfg, "sample_keys"):
            cfg = cfg.model_copy(update={"sample_keys": None, "source_manifest_path": None})
        target_payload = explicit_target or unit.explicit_target_config
        if target_payload is not None and hasattr(cfg, "explicit_target"):
            from .rollout_dataset import ExplicitRolloutTargetConfig

            target_payload = ExplicitRolloutTargetConfig.model_validate(target_payload)
            from ...targets.protocol import TargetInputProtocol

            store = cfg.store.model_copy(update={"target_protocol_version": TargetInputProtocol.V1_OBSERVED})
            from .rollout_dataset import OracleTargetTaskSamplerConfig

            cfg = cfg.model_copy(
                update={
                    "store": store,
                    "explicit_target": target_payload,
                    "max_targets_per_sample": 1,
                    "oracle_target_task_sampler": OracleTargetTaskSamplerConfig(),
                }
            )
        if hasattr(cfg, "recipes"):
            profile = next(p for p in self.config.profiles if p.name == unit.profile)
            if hasattr(cfg, "components"):
                # Preserve the reviewed component order/counts; the writer's
                # candidate config remains the construction/validation owner.
                try:
                    cfg.components = [
                        {"name": name, "count": count, "view_mode": "forward"} for name, count in profile.components
                    ]
                except (TypeError, ValueError):
                    cfg.components = list(profile.components)
            mixture = getattr(cfg, "candidate_mixture", None)
            if mixture is not None and hasattr(mixture, "components"):
                from ...pose_generation.types import CandidatePositionMode, ViewDirectionMode

                modes = {
                    "forward_local": (ViewDirectionMode.FORWARD_RIG, CandidatePositionMode.FORWARD_LOCAL),
                    "target_bearing_local": (
                        ViewDirectionMode.TARGET_POINT,
                        CandidatePositionMode.TARGET_BEARING_LOCAL,
                    ),
                    "lateral_target_bypass": (
                        ViewDirectionMode.TARGET_POINT,
                        CandidatePositionMode.LATERAL_TARGET_BYPASS,
                    ),
                    "local_refinement": (ViewDirectionMode.RADIAL_TOWARDS, CandidatePositionMode.LOCAL_REFINEMENT),
                    "revisit_backtrack": (ViewDirectionMode.FORWARD_RIG, CandidatePositionMode.REVISIT_BACKTRACK),
                    "radial_towards_target_bearing": (
                        ViewDirectionMode.RADIAL_TOWARDS,
                        CandidatePositionMode.TARGET_BEARING_LOCAL,
                    ),
                    "radial_away_target_bearing": (
                        ViewDirectionMode.RADIAL_AWAY,
                        CandidatePositionMode.TARGET_BEARING_LOCAL,
                    ),
                    "target_point_anchor": (ViewDirectionMode.TARGET_POINT, CandidatePositionMode.TARGET_BEARING_LOCAL),
                    "upper_bound_free_shell": (
                        ViewDirectionMode.RADIAL_AWAY,
                        CandidatePositionMode.UPPER_BOUND_FREE_SHELL,
                    ),
                }
                component_type = type(mixture.components[0]) if mixture.components else None
                values = [
                    {"name": name, "count": count, "view_mode": modes[name][0], "position_mode": modes[name][1]}
                    for name, count in profile.components
                ]
                mixture.components = [component_type.model_validate(v) for v in values] if component_type else values
            from ...rollouts.replay.policy import CounterfactualSelectionPolicy, RolloutPolicySpec
            from .rollout_dataset import RolloutRecipeConfig

            cfg = cfg.model_copy(
                update={
                    "recipes": [
                        RolloutRecipeConfig(
                            name=recipe["name"],
                            policy=RolloutPolicySpec(
                                selection_policy=CounterfactualSelectionPolicy(recipe["policy"]),
                                horizon=recipe["horizon"],
                                branch_factor=recipe["branch"],
                                beam_width=recipe["beam"],
                                selection_temperature=recipe.get("temperature", 1.0),
                                seed=self.config.seed,
                            ),
                        )
                        for recipe in profile.recipes
                    ]
                }
            )
        if hasattr(cfg, "model_dump"):
            cfg = type(cfg).model_validate({**cfg.model_dump(), "explicit_target": target_payload})
        binding = RolloutShardCampaignBinding(
            campaign_id=self.config.campaign_id,
            plan_hash=plan_hash
            or (unit.explicit_target_config.get("plan_hash", "") if unit.explicit_target_config else ""),
            work_unit_hash=unit.work_unit_hash,
            target_id=unit.target_id,
            profile_hash=profile_hash
            or (unit.explicit_target_config.get("profile_hash", "") if unit.explicit_target_config else ""),
            explicit_target_hash=unit.explicit_target_hash,
        )
        if hasattr(shard_entry, "campaign_binding"):
            from dataclasses import replace

            shard_entry = replace(shard_entry, campaign_binding=binding)
        return cfg, shard_entry

    def profile_components(self, profile_name: str) -> tuple[tuple[str, int], ...]:
        """Return the exact reviewed component order/counts for a profile."""
        profile = next((p for p in self.config.profiles if p.name == profile_name), None)
        if profile is None:
            raise ValueError(f"unknown campaign profile: {profile_name}")
        return tuple(profile.components)

    def shard_entry_for_unit(self, plan: CampaignPlan, unit: CampaignWorkUnit) -> Any:
        """Create the single-row manifest envelope used by the worker seam."""
        from ...rollouts.shard_manifest import RolloutShardCampaignBinding, RolloutShardEntry, RolloutShardRow

        source = unit.source_row_payload or {}
        if not unit.source_row_payload:
            raise ValueError("work unit requires source_row_payload lineage")
        row = RolloutShardRow(
            order=0,
            sample_index=int(source.get("sample_index", unit.source_row_index)),
            sample_key=unit.sample_key,
            scene_id=str(source.get("scene_id", unit.sample_key)),
            snippet_id=str(source.get("snippet_id", unit.sample_key)),
            split=str(source.get("split", "sample")),
            source_shard_id=str(source.get("source_shard_id", "campaign-source")),
            source_shard_row=int(source.get("source_shard_row", unit.source_row_index)),
        )
        entry = RolloutShardEntry(
            shard_id=f"shard-{unit.source_row_index:06d}",
            split=row.split,
            rows=(row,),
            writer_config_hash="",
            source_manifest_hash=plan.source_manifest_hash,
            source_cache_version=str(source.get("source_cache_version", "campaign-v1")),
            split_manifest_hash=stable_msgspec_hash([row.to_jsonable()]),
            source_store_dir=str(source.get("source_store_dir", "")),
            campaign_binding=RolloutShardCampaignBinding(
                campaign_id=plan.campaign_id,
                plan_hash=plan.plan_hash,
                work_unit_hash=unit.work_unit_hash,
                target_id=unit.target_id,
                profile_hash=plan.profile_hash,
                explicit_target_hash=unit.explicit_target_hash,
            ),
        )
        return entry

    def worker_argv(
        self,
        plan_path: Path,
        unit: CampaignWorkUnit,
        *,
        config_path: Path | None = None,
        writer_config_path: Path | None = None,
    ) -> tuple[str, ...]:
        """Build the only subprocess argv used for an opaque work unit."""
        argv = (
            "nbv-rollout-campaign",
            "worker",
            "--config-path",
            str(config_path or self.config.output_root),
            "--plan-path",
            str(plan_path),
            "--plan-hash",
            "PLAN_HASH",
            "--work-unit-hash",
            unit.work_unit_hash,
        )
        writer_path = writer_config_path or self.config.writer_config_path
        return argv + (("--writer-config-path", str(writer_path)) if writer_path else ())

    def run(
        self,
        plan: CampaignPlan,
        *,
        worker: Callable[[CampaignWorkUnit], Any] | None = None,
        plan_path: Path | None = None,
        config_path: Path | None = None,
    ) -> list[Any]:
        """Run a claimed campaign and always release its claim."""
        if plan is None:
            raise ValueError("an immutable CampaignPlan is required")
        if worker is None:
            self.smoke_evidence(plan)
        claim = self.acquire_claim(plan)
        try:
            return self._run_claimed(plan, worker=worker, plan_path=plan_path, config_path=config_path, claim=claim)
        finally:
            self.release_claim(plan, claim_hash=claim["claim_hash"])

    def _run_claimed(
        self,
        plan: CampaignPlan,
        *,
        worker: Callable[[CampaignWorkUnit], Any] | None = None,
        plan_path: Path | None = None,
        config_path: Path | None = None,
        claim: dict[str, Any],
    ) -> list[Any]:
        if plan is None:
            raise ValueError("an immutable CampaignPlan is required")
        results = []
        self.append_event(CampaignEvent("campaign_started", timestamp=self.utc_now().isoformat()))
        for unit in plan.work_units:
            self.append_event(CampaignEvent("unit_started", unit.work_unit_hash, timestamp=self.utc_now().isoformat()))
            try:
                if worker is not None:
                    result = self.run_with_watchdog(unit, worker)
                else:
                    argv = self.worker_argv(
                        plan_path or (self.config.output_root / "plan.json"), unit, config_path=config_path
                    )
                    argv = tuple(plan.plan_hash if x == "PLAN_HASH" else x for x in argv)
                    returncode, stdout, stderr = self.process_runner.run(
                        argv,
                        timeout=self.config.work_unit_timeout_seconds,
                        stdout=subprocess.PIPE,
                        stderr=subprocess.PIPE,
                    )
                    if returncode:
                        raise RuntimeError((stderr or stdout or f"worker exited {returncode}")[-2000:])
                    result = self.parse_worker_json(stdout)
                results.append(result)
                outcome = (
                    result.get("outcome", CampaignOutcome.SUCCEEDED.value)
                    if isinstance(result, dict)
                    else CampaignOutcome.SUCCEEDED.value
                )
                self.append_event(
                    CampaignEvent("unit_" + str(outcome), unit.work_unit_hash, str(outcome), self.utc_now().isoformat())
                )
            except Exception as exc:  # record-and-continue is intentional
                outcome = (
                    CampaignOutcome.TIMED_OUT.value if isinstance(exc, TimeoutError) else CampaignOutcome.FAILED.value
                )
                result = {"outcome": outcome, "error": str(exc)[-2000:], "work_unit_hash": unit.work_unit_hash}
                results.append(result)
                self.append_event(
                    CampaignEvent(
                        "unit_" + outcome, unit.work_unit_hash, outcome, self.utc_now().isoformat(), str(exc)[-2000:]
                    )
                )
            self.write_status(self.status(plan, results))
        self.append_event(CampaignEvent("campaign_finished", timestamp=self.utc_now().isoformat()))
        self.write_status(self.status(plan, results))
        return results

    def status(self, plan: CampaignPlan, results: Sequence[Any] = ()) -> CampaignStatus:
        counts = {o.value: 0 for o in CampaignOutcome}
        for result in results:
            key = (
                result.value
                if isinstance(result, CampaignOutcome)
                else str(result.get("outcome", CampaignOutcome.SUCCEEDED.value))
                if isinstance(result, dict)
                else CampaignOutcome.SUCCEEDED.value
            )
            counts[key] = counts.get(key, 0) + 1
        state = "not_started" if not results else ("completed" if len(results) >= len(plan.work_units) else "running")
        if (
            any(counts[k] for k in (CampaignOutcome.FAILED.value, CampaignOutcome.TIMED_OUT.value))
            and state == "completed"
        ):
            state = "completed_with_failures"
        return CampaignStatus(state, counts, plan.plan_hash, self.utc_now().isoformat())

    def run_with_watchdog(
        self, unit: CampaignWorkUnit, worker: Callable[[CampaignWorkUnit], Any], *, timeout: float | None = None
    ) -> Any:
        """Run an injected unit and enforce a monotonic timeout.

        Callable workers are kept for deterministic tests; production callers
        may use ``process_runner`` and the same termination semantics.
        """
        started = self.clock()
        result = worker(unit)
        if self.clock() - started >= (self.config.work_unit_timeout_seconds if timeout is None else timeout):
            raise TimeoutError(f"work unit timed out: {unit.work_unit_hash}")
        return result

    def acquire_claim(
        self, plan: CampaignPlan, path: Path | None = None, *, tmux_session: str | None = None
    ) -> dict[str, Any]:
        claim_path = path or (self.config.output_root / "run-claim.json")
        claim_path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "campaign_id": self.config.campaign_id,
            "plan_hash": plan.plan_hash,
            "hostname": socket.gethostname(),
            "pid": os.getpid(),
            "process_group": os.getpgrp(),
            "tmux_session": tmux_session,
            "started_at": self.utc_now().isoformat(),
        }
        payload["claim_hash"] = stable_msgspec_hash(payload)
        try:
            with claim_path.open("x", encoding="utf-8") as f:
                json.dump(payload, f, sort_keys=True)
        except FileExistsError as exc:
            raise RuntimeError(f"active or stale run claim exists: {claim_path}") from exc
        return payload

    def release_claim(self, plan: CampaignPlan, path: Path | None = None, *, claim_hash: str | None = None) -> None:
        claim_path = path or (self.config.output_root / "run-claim.json")
        if not claim_path.exists():
            return
        payload = json.loads(claim_path.read_text())
        if payload.get("plan_hash") == plan.plan_hash and (
            claim_hash is None or payload.get("claim_hash") == claim_hash
        ):
            claim_path.unlink()

    @staticmethod
    def claim_is_stale(path: Path) -> bool:
        """Diagnose a vanished local owner without deleting its evidence."""
        if not path.exists():
            return False
        try:
            payload = json.loads(path.read_text())
            os.kill(int(payload["pid"]), 0)
            return False
        except (OSError, KeyError, ValueError, json.JSONDecodeError):
            return True

    @staticmethod
    def acknowledge_stale_claim(path: Path, claim_hash: str) -> Path:
        """Archive exactly the acknowledged stale claim before reacquisition."""
        payload = json.loads(path.read_text())
        if payload.get("claim_hash") != claim_hash:
            raise ValueError("stale claim acknowledgement hash mismatch")
        archive = path.with_name(f"{path.name}.stale-{claim_hash}")
        path.replace(archive)
        return archive

    def write_plan(self, plan: CampaignPlan, path: Path | None = None) -> Path:
        target = path or (self.config.output_root / "plan.json")
        target.parent.mkdir(parents=True, exist_ok=True)
        encoded = json.dumps(plan.to_jsonable(), sort_keys=True, indent=2) + "\n"
        if target.exists() and target.read_text() != encoded:
            raise ValueError("canonical plan already exists with different content")
        target.write_text(encoded) if not target.exists() else None
        return target

    @staticmethod
    def load_plan(path: Path) -> CampaignPlan:
        """Load and hash-validate an immutable canonical plan."""
        return CampaignPlan.from_jsonable(json.loads(path.read_text(encoding="utf-8")))

    def append_event(self, event: CampaignEvent, path: Path | None = None) -> Path:
        target = path or (self.config.output_root / "progress.jsonl")
        target.parent.mkdir(parents=True, exist_ok=True)
        with target.open("a", encoding="utf-8") as f:
            f.write(json.dumps(asdict(event), sort_keys=True) + "\n")
            f.flush()
        return target

    def read_events(self, path: Path | None = None) -> list[CampaignEvent]:
        target = path or (self.config.output_root / "progress.jsonl")
        if not target.exists():
            return []
        lines = target.read_text(encoding="utf-8").splitlines()
        events: list[CampaignEvent] = []
        for index, line in enumerate(lines):
            if not line.strip():
                continue
            try:
                payload = json.loads(line)
            except json.JSONDecodeError as exc:
                if index == len(lines) - 1:
                    break
                raise ValueError(f"malformed event line {index + 1}") from exc
            allowed = {"kind", "work_unit_hash", "outcome", "timestamp", "detail", "stage"}
            events.append(CampaignEvent(**{key: value for key, value in payload.items() if key in allowed}))
        return events

    def read_status(self, path: Path | None = None) -> CampaignStatus:
        target = path or (self.config.output_root / "status.json")
        if not target.exists():
            return CampaignStatus("not_started", {o.value: 0 for o in CampaignOutcome}, "", self.utc_now().isoformat())
        try:
            return CampaignStatus.from_jsonable(json.loads(target.read_text(encoding="utf-8")))
        except (OSError, json.JSONDecodeError, TypeError, ValueError) as exc:
            raise ValueError("invalid campaign status") from exc

    def write_status(self, status: CampaignStatus, path: Path | None = None) -> Path:
        target = path or (self.config.output_root / "status.json")
        target.parent.mkdir(parents=True, exist_ok=True)
        tmp = target.with_name(f".{target.name}.tmp-{os.getpid()}")
        tmp.write_text(json.dumps(asdict(status), sort_keys=True) + "\n")
        os.replace(tmp, target)
        return target


__all__ = [
    "CampaignEvent",
    "CampaignOutcome",
    "CampaignPlan",
    "CampaignProfileConfig",
    "CampaignProcessRunner",
    "CampaignStatus",
    "CampaignWorkUnit",
    "CudaRolloutCampaign",
    "CudaRolloutCampaignConfig",
]
