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
import shutil
import signal
import socket
import subprocess
import sys
import time
from collections.abc import Callable, Iterable, Sequence
from dataclasses import asdict, dataclass, replace
from datetime import UTC, datetime
from enum import StrEnum
from pathlib import Path
from typing import Any, ClassVar, Protocol

from pydantic import BaseModel, Field, model_validator

from ...utils import TargetConfig
from ...utils.fingerprints import stable_config_hash, stable_msgspec_hash

CAMPAIGN_PLAN_SCHEMA_VERSION = "campaign-plan-v3"
CAMPAIGN_ADMISSION_AUDIT_SCHEMA_VERSION = "campaign-admission-audit-v2"
GENERATION_REVISION_SCHEMA_VERSION = "campaign-generation-revision-v1"


@dataclass(frozen=True, slots=True)
class GenerationRevision:
    """Reproducibility identity required before campaign planning/output."""

    contract_revision: str
    clean_commit: str
    head_tree: str
    uv_lock_sha256: str
    content_bundle_hash: str
    revision_hash: str

    def to_jsonable(self) -> dict[str, str]:
        return {"schema_version": GENERATION_REVISION_SCHEMA_VERSION, **asdict(self)}


def current_generation_revision(
    *, repo_root: Path | None = None, contract_revision: str = "g003-v1"
) -> GenerationRevision:
    """Capture clean Git and reviewed-generator content identity."""

    root = repo_root
    if root is None:
        root = Path(subprocess.check_output(["git", "rev-parse", "--show-toplevel"], text=True).strip())
    status = subprocess.check_output(
        ["git", "status", "--porcelain", "--untracked-files=all"], cwd=root, text=True
    ).strip()
    if status:
        raise ValueError("campaign generation revision requires a clean worktree")
    commit = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=root, text=True).strip()
    tree = subprocess.check_output(["git", "rev-parse", "HEAD^{tree}"], cwd=root, text=True).strip()
    lock = root / "aria_nbv" / "uv.lock"
    if not lock.is_file():
        raise ValueError("campaign generation revision requires aria_nbv/uv.lock")
    lock_hash = hashlib.sha256(lock.read_bytes()).hexdigest()
    bundle_roots = (
        root / "aria_nbv" / "aria_nbv" / "oracle" / "pipelines",
        root / "aria_nbv" / "aria_nbv" / "rollouts",
        root / "aria_nbv" / "aria_nbv" / "pose_generation",
    )
    files = sorted(path for bundle_root in bundle_roots for path in bundle_root.rglob("*.py"))
    if not files:
        raise ValueError("campaign reviewed-generator content bundle is empty")
    bundle = hashlib.sha256()
    for path in files:
        bundle.update(path.relative_to(root).as_posix().encode())
        bundle.update(path.read_bytes())
    content_hash = bundle.hexdigest()
    revision_hash = stable_msgspec_hash(
        {
            "contract_revision": contract_revision,
            "clean_commit": commit,
            "head_tree": tree,
            "uv_lock_sha256": lock_hash,
            "content_bundle_hash": content_hash,
        }
    )
    return GenerationRevision(contract_revision, commit, tree, lock_hash, content_hash, revision_hash)


class CampaignOutcome(StrEnum):
    SUCCEEDED = "succeeded"
    SKIPPED = "skipped"
    FAILED = "failed"
    INSUFFICIENT_SUPPORT = "insufficient_support"
    TIMED_OUT = "timed_out"
    PENDING = "pending"
    BLOCKED = "blocked"
    CONFLICTED = "conflicted"


class CampaignMode(StrEnum):
    """Explicit campaign plan shape; generic replay modes stay elsewhere."""

    BROAD = "broad"
    PILOT = "pilot"


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
        # Campaign generation is intentionally myopic: the generic replay
        # engine still supports planning, but this campaign owns one frozen
        # H=8 temperature-softmax recipe per target.
        {"name": "temperature_softmax_h8", "policy": "temperature_softmax", "horizon": 8, "branch": 1, "beam": 1},
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
    mode: CampaignMode = CampaignMode.BROAD
    frozen_profile: str = "realistic_core_60"
    pilot_scene_count: int = Field(default=5, ge=1)
    temperatures: tuple[float, ...] = (0.5, 1.0, 2.0, 4.0)
    seed: int = 20260728
    observed_target_iou_threshold: float = Field(default=0.20, ge=0, lt=1)
    expected_scene_count: int = Field(default=100, ge=1)
    paired_panel_scene_count: int = Field(default=20, ge=0)
    min_valid_root_candidates: int = Field(default=15, ge=0)
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
            self.min_valid_root_candidates != 15
            or self.stage_timeout_seconds != 120
            or self.work_unit_timeout_seconds != 3600
        ):
            raise ValueError("campaign support and watchdog constants are fixed reviewed constants")
        if self.expected_scene_count != 100 or self.paired_panel_scene_count != 20:
            raise ValueError("campaign scene and panel counts are fixed reviewed constants")
        if self.mode not in {CampaignMode.BROAD, CampaignMode.PILOT}:
            raise ValueError("campaign mode must be broad or pilot")
        if self.frozen_profile not in _PROFILE_COMPONENTS:
            raise ValueError("campaign frozen_profile is unknown")
        if tuple(self.temperatures) != (0.5, 1.0, 2.0, 4.0):
            raise ValueError("campaign temperatures are fixed reviewed constants")
        if self.work_unit_timeout_seconds < self.stage_timeout_seconds:
            raise ValueError("work_unit_timeout_seconds must be >= stage_timeout_seconds")
        names = [p.name for p in self.profiles]
        if names != list(_PROFILE_COMPONENTS):
            raise ValueError("campaign profiles/order drifted from reviewed contract")
        expected_recipes = _default_recipes()
        for p in self.profiles:
            if p.device != "cuda" or p.components != _PROFILE_COMPONENTS[p.name] or p.total_count != 60:
                raise ValueError(f"invalid reviewed profile {p.name}")
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
    profile_hash: str = ""
    config_hash: str = ""
    source_identity_hash: str = ""
    writer_config_hash: str = ""
    temperature: float = 0.5
    temperatures: tuple[float, ...] = (0.5,)
    scene_split: str = "train"
    seed_lineage: dict[str, int] | None = None
    campaign_split: str = "train"
    generation_revision_hash: str = ""


def derive_campaign_seed(*parts: object) -> int:
    """Derive a stable 32-bit seed from the campaign seed lineage parts."""

    payload = json.dumps(parts, sort_keys=True, separators=(",", ":"), default=str).encode()
    return int.from_bytes(hashlib.sha256(payload).digest()[:4], "big")


def _work_unit_identity(unit: CampaignWorkUnit, *, seed: int) -> str:
    payload = {
        "campaign_id": unit.campaign_id,
        "seed": seed,
        "source_identity_hash": unit.source_identity_hash,
        "sample_key": unit.sample_key,
        "target_id": unit.target_id,
        "explicit_target_hash": unit.explicit_target_hash,
        "target_audit_hash": unit.target_audit_hash,
        "profile": unit.profile,
        "profile_hash": unit.profile_hash,
        "config_hash": unit.config_hash,
        "writer_config_hash": unit.writer_config_hash,
        "temperatures": unit.temperatures,
        "scene_split": unit.scene_split,
        "campaign_split": unit.campaign_split,
        "generation_revision_hash": unit.generation_revision_hash,
    }
    return stable_msgspec_hash(json.loads(json.dumps(payload, sort_keys=True, default=str)))


def _jsonable_audit_rows(rows: Sequence[Any]) -> list[dict[str, Any]]:
    """Normalize audit rows once for hashing and immutable persistence."""
    return [
        json.loads(
            json.dumps(
                row
                if isinstance(row, dict)
                else row.model_dump(mode="json")
                if hasattr(row, "model_dump")
                else vars(row),
                sort_keys=True,
                default=str,
            )
        )
        for row in rows
    ]


@dataclass(frozen=True, slots=True)
class CampaignPlan:
    campaign_id: str
    seed: int
    source_manifest_hash: str
    profile_hash: str
    work_units: tuple[CampaignWorkUnit, ...]
    plan_hash: str
    config_hash: str = ""
    writer_config_hash: str = ""
    admission_audit_hash: str = ""
    admission_counts: dict[str, int] | None = None
    admission_reason_counts: dict[str, int] | None = None
    generation_revision: GenerationRevision | None = None
    zero_admission_scene_ids: tuple[str, ...] = ()
    zero_admission_scene_count: int = 0

    def to_jsonable(self) -> dict[str, Any]:
        return {
            "schema_version": CAMPAIGN_PLAN_SCHEMA_VERSION,
            "campaign_id": self.campaign_id,
            "seed": self.seed,
            "source_manifest_hash": self.source_manifest_hash,
            "profile_hash": self.profile_hash,
            "work_units": [asdict(u) for u in self.work_units],
            "plan_hash": self.plan_hash,
            "config_hash": self.config_hash,
            "writer_config_hash": self.writer_config_hash,
            "admission_audit_hash": self.admission_audit_hash,
            "admission_counts": self.admission_counts or {},
            "admission_reason_counts": self.admission_reason_counts or {},
            "generation_revision": None if self.generation_revision is None else self.generation_revision.to_jsonable(),
            "zero_admission_scene_ids": list(self.zero_admission_scene_ids),
            "zero_admission_scene_count": self.zero_admission_scene_count,
        }

    @classmethod
    def from_jsonable(cls, payload: dict[str, Any]) -> "CampaignPlan":
        if payload.get("schema_version") != CAMPAIGN_PLAN_SCHEMA_VERSION:
            raise ValueError("unsupported campaign plan schema version; regenerate the plan")
        revision_payload = payload.get("generation_revision")
        if not isinstance(revision_payload, dict) or not revision_payload.get("revision_hash"):
            raise ValueError("campaign plan requires generation revision identity")
        units = tuple(
            CampaignWorkUnit(
                **{
                    **item,
                    "temperatures": tuple(item.get("temperatures", (item.get("temperature", 0.5),))),
                }
            )
            for item in payload.get("work_units", ())
        )
        plan = cls(
            str(payload["campaign_id"]),
            int(payload["seed"]),
            str(payload.get("source_manifest_hash", "")),
            str(payload["profile_hash"]),
            units,
            str(payload["plan_hash"]),
            str(payload.get("config_hash", "")),
            str(payload.get("writer_config_hash", "")),
            str(payload.get("admission_audit_hash", "")),
            payload.get("admission_counts") or {},
            payload.get("admission_reason_counts") or {},
            None
            if payload.get("generation_revision") is None
            else GenerationRevision(
                **{
                    k: str(payload["generation_revision"][k])
                    for k in (
                        "contract_revision",
                        "clean_commit",
                        "head_tree",
                        "uv_lock_sha256",
                        "content_bundle_hash",
                        "revision_hash",
                    )
                }
            ),
            tuple(str(value) for value in payload.get("zero_admission_scene_ids", ())),
            int(payload.get("zero_admission_scene_count", len(payload.get("zero_admission_scene_ids", ())))),
        )
        expected_payload = {
            "schema_version": CAMPAIGN_PLAN_SCHEMA_VERSION,
            "campaign_id": plan.campaign_id,
            "seed": plan.seed,
            "source_manifest_hash": plan.source_manifest_hash,
            "profile_hash": plan.profile_hash,
            "config_hash": plan.config_hash,
            "writer_config_hash": plan.writer_config_hash,
            "admission_audit_hash": plan.admission_audit_hash,
            "admission_counts": plan.admission_counts or {},
            "admission_reason_counts": plan.admission_reason_counts or {},
            "generation_revision": None if plan.generation_revision is None else plan.generation_revision.to_jsonable(),
            "zero_admission_scene_ids": list(plan.zero_admission_scene_ids),
            "zero_admission_scene_count": plan.zero_admission_scene_count,
            "work_units": [asdict(u) for u in units],
        }
        expected = stable_msgspec_hash(json.loads(json.dumps(expected_payload, sort_keys=True, default=str)))
        if expected != plan.plan_hash:
            raise ValueError("plan hash mismatch")
        for unit in units:
            if _work_unit_identity(unit, seed=plan.seed) != unit.work_unit_hash:
                raise ValueError("work-unit hash mismatch")
        return plan


@dataclass(frozen=True, slots=True)
class CampaignEvent:
    kind: str
    work_unit_hash: str | None = None
    outcome: str | None = None
    timestamp: str = ""
    detail: str = ""
    stage: str | None = None
    plan_hash: str | None = None
    config_hash: str | None = None
    source_identity_hash: str | None = None
    target_id: str | None = None
    profile: str | None = None
    profile_hash: str | None = None
    writer_config_hash: str | None = None
    source_manifest_hash: str | None = None
    elapsed_seconds: float | None = None
    schema_version: str = "campaign-event-v1"
    pid: int | None = None
    process_group: int | None = None
    tmux_session: str | None = None
    timeout_disposition: str | None = None
    stderr_tail: str | None = None
    campaign_id: str | None = None


@dataclass(frozen=True, slots=True)
class CampaignWorkerResult:
    """Immutable, plan-bound result emitted by a campaign worker."""

    campaign_id: str
    config_hash: str
    plan_hash: str
    work_unit_hash: str
    source_identity_hash: str
    target_id: str
    profile: str
    profile_hash: str
    generation_revision_hash: str
    outcome: str
    validated: bool = False
    reason: str | None = None
    leaf_evidence: dict[str, Any] | None = None

    def to_jsonable(self) -> dict[str, Any]:
        """Return the complete worker contract without mutable aliases."""
        return asdict(self)

    @classmethod
    def from_jsonable(
        cls,
        payload: dict[str, Any],
        *,
        campaign_id: str,
        config_hash: str,
        plan_hash: str,
        unit: CampaignWorkUnit,
    ) -> "CampaignWorkerResult":
        """Validate one worker result against its immutable plan unit."""
        required = {
            "campaign_id",
            "config_hash",
            "plan_hash",
            "work_unit_hash",
            "source_identity_hash",
            "target_id",
            "profile",
            "profile_hash",
            "generation_revision_hash",
            "outcome",
        }
        if not required.issubset(payload):
            raise ValueError("worker result is missing immutable identity bindings")
        bindings = {
            "campaign_id": campaign_id,
            "config_hash": config_hash,
            "plan_hash": plan_hash,
            "work_unit_hash": unit.work_unit_hash,
            "source_identity_hash": unit.source_identity_hash,
            "target_id": unit.target_id,
            "profile": unit.profile,
            "profile_hash": unit.profile_hash,
            "generation_revision_hash": unit.generation_revision_hash,
        }
        for field, expected in bindings.items():
            if str(payload.get(field, "")) != str(expected):
                raise ValueError(f"worker result {field} binding mismatch")
        outcome = str(payload["outcome"])
        if outcome not in {"succeeded", "skipped", "insufficient_support"}:
            raise ValueError("worker result has unsupported outcome")
        validated = payload.get("validated") is True
        evidence = payload.get("leaf_evidence")
        if outcome in {"succeeded", "skipped"} and (not validated or not isinstance(evidence, dict)):
            raise ValueError("successful worker result requires validated leaf evidence")
        if outcome == "insufficient_support" and (validated or evidence not in (None, {})):
            raise ValueError("insufficient-support result cannot claim validated leaf evidence")
        return cls(
            **{field: str(payload[field]) for field in bindings},
            outcome=outcome,
            validated=validated,
            reason=None if payload.get("reason") is None else str(payload["reason"]),
            leaf_evidence=None if evidence is None else dict(evidence),
        )


@dataclass(frozen=True, slots=True)
class CampaignStatus:
    state: str
    counts: dict[str, int]
    plan_hash: str
    updated_at: str
    current_work_unit: str | None = None
    current_target_id: str | None = None
    current_profile: str | None = None
    current_stage: str | None = None
    elapsed_seconds: float = 0.0
    latest_failure_reason: str | None = None
    schema_version: str = "campaign-status-v2"
    campaign_id: str = ""
    config_hash: str = ""
    smoke_evidence_hash: str = ""
    smoke_evidence_summary: dict[str, Any] | None = None
    last_work_unit: str | None = None
    started_at: str | None = None
    finished_at: str | None = None
    bounded_error: str | None = None
    last_timeout: dict[str, Any] | None = None
    active_pid: int | None = None
    active_process_group: int | None = None
    active_started_at: str | None = None

    _VALID_STATES: ClassVar[frozenset[str]] = frozenset(
        {
            "not_started",
            "planned",
            "preflight_passed",
            "smoke_passed",
            "running",
            "completed",
            "completed_with_failures",
            "blocked",
            "conflicted",
        }
    )
    _COUNT_KEYS: ClassVar[frozenset[str]] = frozenset(outcome.value for outcome in CampaignOutcome)

    @classmethod
    def from_jsonable(cls, payload: dict[str, Any]) -> "CampaignStatus":
        required = {"state", "counts", "plan_hash", "updated_at"}
        if not required.issubset(payload):
            raise ValueError("status is missing required fields")
        if payload.get("schema_version", "campaign-status-v1") not in {"campaign-status-v1", "campaign-status-v2"}:
            raise ValueError("unsupported campaign status schema version")
        state = str(payload["state"])
        if state not in cls._VALID_STATES:
            raise ValueError("unsupported campaign status state")
        counts = payload["counts"]
        if not isinstance(counts, dict) or any(not isinstance(v, int) or v < 0 for v in counts.values()):
            raise ValueError("campaign status counts must be non-negative integers")
        if not cls._COUNT_KEYS.issubset(counts):
            raise ValueError("campaign status counts must include every outcome")
        if state in {"completed", "completed_with_failures"} and counts[CampaignOutcome.PENDING.value] != 0:
            raise ValueError("terminal campaign status cannot retain pending work")
        failures = counts[CampaignOutcome.FAILED.value] + counts[CampaignOutcome.TIMED_OUT.value]
        if state == "completed" and failures:
            raise ValueError("completed campaign status cannot contain failures")
        if state == "completed_with_failures" and not failures:
            raise ValueError("completed_with_failures requires failure evidence")
        current_work_unit = payload.get("current_work_unit")
        if state != "running" and current_work_unit is not None:
            raise ValueError("only running status may expose a current work unit")
        if any(payload.get(key) is not None for key in ("active_pid", "active_process_group", "active_started_at")):
            if current_work_unit is None:
                raise ValueError("active process identity requires a current work unit")
        return cls(
            state,
            {str(k): int(v) for k, v in counts.items()},
            str(payload["plan_hash"]),
            str(payload["updated_at"]),
            current_work_unit,
            payload.get("current_target_id"),
            payload.get("current_profile"),
            payload.get("current_stage"),
            float(payload.get("elapsed_seconds", 0.0)),
            payload.get("latest_failure_reason"),
            str(payload.get("schema_version", "campaign-status-v1")),
            str(payload.get("campaign_id", "")),
            str(payload.get("config_hash", "")),
            str(payload.get("smoke_evidence_hash", "")),
            payload.get("smoke_evidence_summary"),
            payload.get("last_work_unit"),
            payload.get("started_at"),
            payload.get("finished_at"),
            payload.get("bounded_error"),
            payload.get("last_timeout"),
            payload.get("active_pid"),
            payload.get("active_process_group"),
            payload.get("active_started_at"),
        )


def validate_cuda_contract(value: Any) -> None:
    """Reject CPU or mixed-device nested configs before any output is created."""
    devices: list[str] = []
    seen: set[int] = set()

    def visit(obj: Any) -> None:
        if id(obj) in seen:
            return
        seen.add(id(obj))
        if isinstance(obj, str) and (obj.lower() == "cpu" or obj.lower().startswith("cuda")):
            devices.append(obj.lower())
        elif type(obj).__name__ == "device":
            value = str(obj).lower()
            if not value.startswith("cuda"):
                raise RuntimeError(f"CUDA campaign rejects device={value!r}")
            devices.append(value)
        elif isinstance(obj, dict):
            for _key, item in obj.items():
                key_name = str(_key).lower()
                if (
                    key_name in {"device", "map_location"}
                    and isinstance(item, str)
                    and not item.lower().startswith("cuda")
                ):
                    raise RuntimeError(f"CUDA campaign rejects {key_name}={item!r} at {_key}")
                if key_name == "collision_backend" and str(item).lower() != "pytorch3d":
                    raise RuntimeError(f"CUDA campaign requires collision_backend='pytorch3d' at {_key}")
                # Traverse every nested model: source, renderer, scorer, and
                # retained-depth configs may each carry an independent device.
                visit(item)
        elif isinstance(obj, (list, tuple, set)):
            for item in obj:
                visit(item)
        elif hasattr(obj, "model_dump"):
            visit(obj.model_dump(mode="python"))
        elif hasattr(obj, "__dict__"):
            for _key, item in vars(obj).items():
                visit(item)

    visit(value)
    if any(device == "cpu" or device.startswith("cuda:") and device != "cuda:0" for device in devices):
        raise RuntimeError("CUDA campaign rejects CPU or mixed-device nested configuration")


class CampaignProcess(Protocol):
    pid: int
    stdout: Any
    stderr: Any

    def poll(self) -> int | None: ...
    def wait(self, timeout: float | None = None) -> int: ...
    def communicate(self, timeout: float | None = None) -> tuple[Any, Any]: ...


class CampaignTimeoutError(TimeoutError):
    """Bounded child timeout carrying reproducible process evidence."""

    def __init__(
        self,
        message: str,
        *,
        pid: int,
        process_group: int | None,
        elapsed_seconds: float,
        stderr_tail: str = "",
        disposition: str = "term-grace-kill",
        tmux_session: str | None = None,
    ) -> None:
        super().__init__(message)
        self.pid, self.process_group = pid, process_group
        self.elapsed_seconds, self.stderr_tail = elapsed_seconds, stderr_tail[-2000:]
        self.disposition, self.tmux_session = disposition, tmux_session


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
        on_started: Callable[[int, int | None], None] | None = None,
        clock: Callable[[], float] = time.monotonic,
    ) -> tuple[int, str, str]:
        """Run one opaque child while draining pipes and enforcing its watchdog."""
        process = self.start(argv, stdout=stdout, stderr=stderr)
        try:
            process_group = os.getpgid(process.pid)
        except ProcessLookupError:
            process_group = None
        if on_started is not None:
            try:
                on_started(process.pid, process_group)
            except Exception:
                self.terminate_group(process)
                raise
        started = clock()
        try:
            out, err = process.communicate(timeout=timeout)
        except subprocess.TimeoutExpired:
            elapsed = clock() - started
            try:
                process_group = os.getpgid(process.pid)
            except ProcessLookupError:
                process_group = None
            if process_group is not None:
                try:
                    os.killpg(process_group, signal.SIGTERM)
                except ProcessLookupError:
                    pass
            disposition = "term-grace"
            try:
                out, err = process.communicate(timeout=10)
            except subprocess.TimeoutExpired:
                disposition = "term-grace-kill"
                if process_group is not None:
                    try:
                        os.killpg(process_group, signal.SIGKILL)
                    except ProcessLookupError:
                        pass
                out, err = process.communicate()
            if isinstance(err, bytes):
                err = err.decode(errors="replace")
            raise CampaignTimeoutError(
                f"process timed out after {timeout:g}s",
                pid=process.pid,
                process_group=process_group,
                elapsed_seconds=elapsed,
                stderr_tail=err or "",
                disposition=disposition,
            ) from None
        return process.returncode, out or "", err or ""

    def run_stage(
        self, argv: Sequence[str], *, timeout: float = 120, stdout: Any = None, stderr: Any = None
    ) -> tuple[int, str, str]:
        """Run a bounded setup/render stage using the same process-group policy."""
        return self.run(argv, timeout=timeout, stdout=stdout, stderr=stderr)


class CudaRolloutCampaign:
    """Plan and execute one campaign serially through the shard leaf."""

    _STATUS_TRANSITIONS: ClassVar[dict[str, frozenset[str]]] = {
        "not_started": frozenset({"not_started", "planned"}),
        "planned": frozenset({"planned", "preflight_passed", "blocked", "conflicted"}),
        "preflight_passed": frozenset({"preflight_passed", "smoke_passed", "blocked", "conflicted"}),
        "smoke_passed": frozenset({"smoke_passed", "running", "blocked", "conflicted"}),
        "running": frozenset({"running", "blocked", "conflicted", "completed", "completed_with_failures"}),
        "blocked": frozenset({"blocked", "running"}),
        "conflicted": frozenset({"conflicted"}),
        "completed": frozenset({"completed"}),
        "completed_with_failures": frozenset({"completed_with_failures"}),
    }

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

    @staticmethod
    def _disk_usage_path(path: Path) -> Path:
        """Return the nearest existing ancestor without creating output state."""
        candidate = path
        while not candidate.exists() and candidate != candidate.parent:
            candidate = candidate.parent
        return candidate

    def plan(
        self, source_rows: Iterable[Any], *, source_manifest_hash: str = "", writer_config_hash: str = ""
    ) -> CampaignPlan:
        rows = list(source_rows)
        if not source_manifest_hash:
            raise ValueError("source_manifest_hash is required and must be non-empty")
        generation_revision = current_generation_revision()

        def val(row: Any, key: str) -> Any:
            if hasattr(row, key):
                return getattr(row, key)
            return row.get(key, "") if hasattr(row, "get") else ""

        def is_strictly_eligible(row: Any) -> bool:
            if val(row, "admitted") is not True:
                return False
            iou = val(row, "oriented_iou")
            try:
                return (
                    iou not in ("", None)
                    and math.isfinite(float(iou))
                    and float(iou) > self.config.observed_target_iou_threshold
                )
            except (TypeError, ValueError):
                return False

        if not rows or any(not str(val(r, "scene_id")) for r in rows):
            raise ValueError("source rows require non-empty scene_id")
        invalid_admissions = [row for row in rows if val(row, "admitted") is True and not is_strictly_eligible(row)]
        if invalid_admissions:
            raise ValueError("admitted source rows require finite oriented_iou strictly above the threshold")
        scenes = sorted({str(val(row, "scene_id")) for row in rows})
        identities = [
            (str(val(r, "scene_id")), str(val(r, "sample_key")), str(val(r, "target_id") or val(r, "task_id")))
            for r in rows
        ]
        if len(set(identities)) != len(identities):
            raise ValueError("duplicate scene/sample/target identity in source manifest")
        if len(scenes) != self.config.expected_scene_count:
            raise ValueError(f"expected {self.config.expected_scene_count} scenes, found {len(scenes)}")
        mode = CampaignMode(self.config.mode)
        profiles = (
            self.config.profiles[:2]
            if mode is CampaignMode.PILOT
            else [next(p for p in self.config.profiles if p.name == self.config.frozen_profile)]
        )
        split_order = sorted(
            scenes,
            key=lambda s: (
                hashlib.sha256(json.dumps([self.config.seed, "split", s], separators=(",", ":")).encode()).hexdigest(),
                s,
            ),
        )
        split_by_scene = {
            scene: (
                "train"
                if index < math.ceil(len(scenes) * 0.8)
                else "validation"
                if index < math.ceil(len(scenes) * 0.9)
                else "test"
            )
            for index, scene in enumerate(split_order)
        }
        eligible_rows = [
            row for row in rows if is_strictly_eligible(row) and split_by_scene[str(val(row, "scene_id"))] == "train"
        ]
        pilot_order = sorted(
            eligible_rows,
            key=lambda row: (
                hashlib.sha256(
                    json.dumps(
                        [self.config.seed, "pilot", val(row, "sample_key"), val(row, "target_id")],
                        separators=(",", ":"),
                    ).encode()
                ).hexdigest(),
                str(val(row, "sample_key")),
                str(val(row, "target_id")),
            ),
        )
        pilot_rows: list[Any] = []
        pilot_scenes: set[str] = set()
        for row in pilot_order:
            scene = str(val(row, "scene_id"))
            if scene not in pilot_scenes:
                pilot_rows.append(row)
                pilot_scenes.add(scene)
            if len(pilot_rows) == self.config.pilot_scene_count:
                break
        if len(pilot_rows) < self.config.pilot_scene_count:
            for row in pilot_order:
                if row not in pilot_rows:
                    pilot_rows.append(row)
                if len(pilot_rows) == self.config.pilot_scene_count:
                    break
        pilot_target_keys = {
            (str(val(row, "sample_key")), str(val(row, "target_id") or val(row, "task_id"))) for row in pilot_rows
        }
        units: list[CampaignWorkUnit] = []
        eligible_index = 0
        for row_index, row in enumerate(rows):
            sample = str(val(row, "sample_key"))
            target = str(val(row, "target_id") or val(row, "task_id"))
            if not sample:
                raise ValueError("source rows require sample_key")
            scene = str(val(row, "scene_id"))
            iou = val(row, "oriented_iou")
            if not is_strictly_eligible(row):
                continue
            if not target:
                raise ValueError("admitted source rows require target_id")
            explicit_payload = val(row, "explicit_target_config")
            if not explicit_payload:
                raise ValueError("admitted campaign rows require full explicit_target_config")
            try:
                from .rollout_dataset import ExplicitRolloutTargetConfig

                explicit_payload = ExplicitRolloutTargetConfig.model_validate(explicit_payload).model_dump(mode="json")
            except (ImportError, TypeError, ValueError) as exc:
                raise ValueError("malformed explicit_target_config in admitted campaign row") from exc
            reasons = [val(row, key) for key in ("reason", "admission_reason") if val(row, key) not in ("", None)]
            if not reasons or any(str(reason).lower() != "admitted" for reason in reasons):
                raise ValueError("campaign admission reason must be admitted")
            counts = [
                val(row, key)
                for key in ("gt_match_count", "qualified_gt_match_count")
                if val(row, key) not in ("", None)
            ]
            if not counts or any(int(count) != 1 for count in counts):
                raise ValueError("campaign admission requires exactly one GT match")
            if (
                str(explicit_payload.get("sample_key", sample)) != sample
                or str(explicit_payload.get("target_id", target)) != target
            ):
                raise ValueError("explicit target identity does not match source row")
            payload_iou = explicit_payload.get("oriented_iou")
            if payload_iou is not None and float(payload_iou) != float(iou):
                raise ValueError("explicit target IoU does not match source row")
            for field in ("gt_match_row", "gt_match_id"):
                row_value = val(row, field)
                payload_value = explicit_payload.get(field)
                if row_value not in ("", None) and payload_value != row_value:
                    raise ValueError(f"explicit target {field} does not match source row")
            row_hash = val(row, "explicit_target_hash")
            payload_hash = explicit_payload.get("explicit_target_hash", "")
            if row_hash not in ("", None) and payload_hash != row_hash:
                raise ValueError("explicit target hash does not match source row")
            if not str(
                val(row, "explicit_target_hash")
                or (explicit_payload.get("explicit_target_hash", "") if isinstance(explicit_payload, dict) else "")
            ):
                raise ValueError("admitted campaign rows require explicit_target_hash")
            selected = profiles
            if mode is CampaignMode.PILOT:
                if (sample, target) not in pilot_target_keys:
                    continue
            for profile in selected:
                temperatures = (
                    self.config.temperatures
                    if mode is CampaignMode.PILOT
                    else (self.config.temperatures[eligible_index % len(self.config.temperatures)],)
                )
                temperature = temperatures[0]
                payload = [
                    self.config.campaign_id,
                    sample,
                    target,
                    profile.name,
                    str(val(row, "explicit_target_hash")),
                    self.config.seed,
                    stable_msgspec_hash(profile.model_dump()),
                    temperatures,
                    split_by_scene[scene],
                ]
                units.append(
                    CampaignWorkUnit(
                        campaign_id=self.config.campaign_id,
                        sample_key=sample,
                        target_id=target,
                        profile=profile.name,
                        work_unit_hash=stable_msgspec_hash(payload),
                        explicit_target_hash=str(val(row, "explicit_target_hash")),
                        target_audit_hash=stable_msgspec_hash(
                            {
                                "explicit": explicit_payload
                                or {"scene_id": scene, "target_id": target, "oriented_iou": iou},
                                "admission_reason": reasons,
                                "gt_match_count": val(row, "gt_match_count")
                                or val(row, "qualified_gt_match_count")
                                or 1,
                            }
                        ),
                        source_row_index=row_index,
                        explicit_target_config=explicit_payload,
                        source_row_payload={
                            **{
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
                                    "source_manifest_hash",
                                    "campaign_split",
                                )
                                if val(row, k) not in ("", None)
                            },
                            "campaign_split": split_by_scene[scene],
                        },
                        temperature=temperature,
                        temperatures=tuple(temperatures),
                        scene_split=split_by_scene[scene],
                        seed_lineage={
                            "unit": derive_campaign_seed(self.config.seed, "unit", sample, target, profile.name),
                            "recipe": derive_campaign_seed(self.config.seed, "recipe", sample, target, profile.name),
                        },
                        campaign_split=split_by_scene[scene],
                    )
                )
            eligible_index += 1
        profile_hash = stable_msgspec_hash([p.model_dump() for p in profiles])
        config_hash = stable_msgspec_hash(self.config.model_dump_jsonable())
        from dataclasses import replace

        units = [
            replace(
                unit,
                profile_hash=stable_msgspec_hash(next(p.model_dump() for p in profiles if p.name == unit.profile)),
                config_hash=config_hash,
                writer_config_hash=writer_config_hash,
                source_identity_hash=stable_msgspec_hash(
                    {
                        "source_manifest_hash": source_manifest_hash,
                        "row": unit.source_row_payload or unit.source_row_index,
                    }
                ),
                generation_revision_hash=generation_revision.revision_hash,
            )
            for unit in units
        ]
        units = [replace(unit, work_unit_hash=_work_unit_identity(unit, seed=self.config.seed)) for unit in units]
        admission_counts = {
            "admitted": sum(1 for row in rows if val(row, "admitted") is True),
            "rejected": sum(1 for row in rows if val(row, "admitted") is not True),
        }
        reason_counts: dict[str, int] = {}
        for row in rows:
            reason = str(
                val(row, "reason")
                or val(row, "admission_reason")
                or ("admitted" if val(row, "admitted") is True else "unspecified")
            )
            reason_counts[reason] = reason_counts.get(reason, 0) + 1
        audit_rows = _jsonable_audit_rows(rows)
        admission_audit_hash = stable_msgspec_hash(audit_rows)
        payload = {
            "schema_version": CAMPAIGN_PLAN_SCHEMA_VERSION,
            "campaign_id": self.config.campaign_id,
            "seed": self.config.seed,
            "source_manifest_hash": source_manifest_hash,
            "profile_hash": profile_hash,
            "config_hash": config_hash,
            "writer_config_hash": writer_config_hash,
            "admission_audit_hash": admission_audit_hash,
            "admission_counts": admission_counts,
            "admission_reason_counts": reason_counts,
            "generation_revision": generation_revision.to_jsonable(),
            "zero_admission_scene_ids": sorted(
                scene
                for scene in scenes
                if not any(is_strictly_eligible(row) and str(val(row, "scene_id")) == scene for row in rows)
            ),
            "zero_admission_scene_count": sum(
                1
                for scene in scenes
                if not any(is_strictly_eligible(row) and str(val(row, "scene_id")) == scene for row in rows)
            ),
            "work_units": [asdict(u) for u in units],
        }
        plan_hash = stable_msgspec_hash(json.loads(json.dumps(payload, sort_keys=True, default=str)))
        return CampaignPlan(
            self.config.campaign_id,
            self.config.seed,
            source_manifest_hash,
            profile_hash,
            tuple(units),
            plan_hash,
            config_hash,
            writer_config_hash,
            admission_audit_hash,
            admission_counts,
            reason_counts,
            generation_revision,
            tuple(payload["zero_admission_scene_ids"]),
            int(payload["zero_admission_scene_count"]),
        )

    def audit_source_manifest(self, writer_config: Any, source_manifest: Any) -> list[dict[str, Any]]:
        """Enumerate every observed target and attach privileged admission evidence."""
        from ...targets.selection import observed_target_descriptors
        from ..target_selection import OracleTargetTaskSampler, match_observed_target_descriptors
        from .rollout_dataset import ExplicitRolloutTargetConfig, RolloutDatasetWriter

        # Admission reads persisted target geometry and trajectory pose only.
        # Loading raw EFM snippets, meshes, or backbone tensors would replay
        # the expensive source pipeline for every reviewed row without
        # contributing to observed/GT target matching.
        audit_source = writer_config.source
        if hasattr(audit_source, "model_copy"):
            audit_source = audit_source.model_copy(
                update={
                    "include_efm_snippet": False,
                    "include_gt_mesh": False,
                    "load_backbone": False,
                    "load_candidates": False,
                    "load_depths": False,
                    "load_candidate_pcs": False,
                }
            )
        dataset = audit_source.setup_target()
        if dataset is None:
            raise RuntimeError("campaign source audit requires a VIN offline dataset")
        RolloutDatasetWriter._apply_source_manifest(
            dataset,
            source_manifest,
            sample_keys=writer_config.sample_keys,
        )
        source_rows = writer_config.selected_source_manifest_rows(source_manifest)
        if len(dataset) != len(source_rows):
            raise ValueError("campaign source audit dataset/manifest row count mismatch")
        sampler = OracleTargetTaskSampler(writer_config.oracle_target_task_sampler)
        source_lineage = {
            key: value
            for key in ("source_manifest_hash", "source_cache_version", "source_store_dir")
            if (value := getattr(source_manifest, key, None)) not in (None, "")
        }
        audited: list[dict[str, Any]] = []
        for source_row, sample in zip(source_rows, dataset, strict=True):
            if str(sample.sample_key) != source_row.sample_key:
                raise ValueError("campaign source audit sample identity mismatch")
            observed = observed_target_descriptors(sample)
            gt_rows = sampler.sample(sample).rows
            matches = match_observed_target_descriptors(
                observed,
                list(gt_rows),
                threshold=self.config.observed_target_iou_threshold,
            )
            if not matches:
                audited.append(
                    {
                        **source_row.to_jsonable(),
                        **source_lineage,
                        "target_id": "",
                        "observed_target_count": len(observed),
                        "gt_match_count": 0,
                        "qualified_gt_match_count": 0,
                        "admitted": False,
                        "reason": "excluded_no_observed_target" if not observed else "excluded_no_gt_match",
                    }
                )
            for match in matches:
                actor = match.descriptor
                row = {
                    **source_row.to_jsonable(),
                    **source_lineage,
                    "target_id": actor.target_id,
                    "detected_source_row": actor.source_row,
                    "gt_match_row": match.gt_match_row,
                    "gt_match_id": match.gt_match_id,
                    "gt_match_count": match.qualified_gt_match_count,
                    "qualified_gt_match_count": match.qualified_gt_match_count,
                    "oriented_iou": match.oriented_iou,
                    "admitted": match.admitted,
                    "reason": match.reason.value,
                    "descriptor_hash": actor.descriptor_hash,
                }
                if match.admitted:
                    if actor.descriptor is None or match.gt_match_row is None or match.gt_match_id is None:
                        raise ValueError("admitted target is missing descriptor or GT audit identity")
                    identity = {
                        "sample_key": actor.sample_key,
                        "target_id": actor.target_id,
                        "detected_source_row": actor.source_row,
                        "gt_match_row": match.gt_match_row,
                        "gt_match_id": match.gt_match_id,
                        "oriented_iou": match.oriented_iou,
                        "descriptor_hash": actor.descriptor_hash,
                    }
                    explicit_hash = stable_msgspec_hash(identity)
                    explicit = ExplicitRolloutTargetConfig.model_validate(
                        {
                            **{key: value for key, value in identity.items() if key != "descriptor_hash"},
                            "actor_descriptor": actor,
                            "status": "admitted",
                            "reason": "admitted",
                            "explicit_target_hash": explicit_hash,
                        }
                    )
                    row["explicit_target_hash"] = explicit_hash
                    row["explicit_target_config"] = explicit.model_dump(mode="json")
                audited.append(row)
        return audited

    def write_admission_audit(
        self,
        rows: Sequence[dict[str, Any]],
        *,
        source_manifest_hash: str,
        expected_hash: str,
        path: Path | None = None,
    ) -> Path:
        """Persist the complete immutable target-admission audit before plan publication."""
        audit_rows = _jsonable_audit_rows(rows)
        audit_hash = stable_msgspec_hash(audit_rows)
        if audit_hash != expected_hash:
            raise ValueError("admission audit hash does not match campaign plan")
        target = path or (self.config.output_root / "admission-audit.json")
        payload = {
            "schema_version": CAMPAIGN_ADMISSION_AUDIT_SCHEMA_VERSION,
            "campaign_id": self.config.campaign_id,
            "source_manifest_hash": source_manifest_hash,
            "admission_audit_hash": audit_hash,
            "rows": audit_rows,
        }
        encoded = json.dumps(payload, sort_keys=True, indent=2) + "\n"
        target.parent.mkdir(parents=True, exist_ok=True)
        if target.exists() and target.read_text(encoding="utf-8") != encoded:
            raise ValueError("canonical admission audit already exists with different content")
        if not target.exists():
            tmp = target.with_name(f".{target.name}.tmp-{os.getpid()}")
            tmp.write_text(encoded, encoding="utf-8")
            os.replace(tmp, target)
        return target

    def preflight(
        self,
        cuda_probe: Callable[[], Any] | None = None,
        *,
        nested_configs: Iterable[Any] = (),
        plan_path: Path | None = None,
        writer_config_path: Path | None = None,
    ) -> Any:
        # This gate intentionally runs before plan/status/evidence writes in
        # production entry points.  Nested writer and renderer configs are
        # part of the CUDA contract, not optional leaf hints.
        validate_cuda_contract(self.config)
        for nested in nested_configs:
            validate_cuda_contract(nested)
        output_root = self.config.output_root
        if output_root.exists() and not output_root.is_dir():
            raise RuntimeError("campaign output_root exists but is not a directory")
        writable_parent = self._disk_usage_path(output_root)
        if not writable_parent.is_dir() or not os.access(writable_parent, os.W_OK):
            raise RuntimeError("campaign output_root has no writable existing ancestor")
        if shutil.disk_usage(writable_parent).free <= 0:
            raise RuntimeError("campaign output filesystem reports no free space")
        result = cuda_probe() if cuda_probe else None
        if cuda_probe:
            validate_cuda_contract(result)
            if result is False or getattr(result, "ok", True) is False:
                raise RuntimeError("CUDA preflight failed")
            if isinstance(result, dict):
                if not result.get("cuda_available") or not result.get("pytorch3d_available"):
                    raise RuntimeError("CUDA preflight probe must prove cuda_available and PyTorch3D availability")
            elif hasattr(result, "cuda_available") or hasattr(result, "pytorch3d_available"):
                if not getattr(result, "cuda_available", False) or not getattr(result, "pytorch3d_available", False):
                    raise RuntimeError("CUDA preflight probe must prove cuda_available and PyTorch3D availability")
            else:
                raise RuntimeError(
                    "CUDA preflight probe must explicitly prove cuda_available and PyTorch3D availability"
                )
            return result
        try:
            import pytorch3d  # noqa: F401 - availability is a hard contract
            import torch
        except ImportError as exc:
            raise RuntimeError("CUDA campaign requires PyTorch and PyTorch3D before writes") from exc

        if not torch.cuda.is_available():
            raise RuntimeError("CUDA is required for campaign execution")
        # The actual rasterizer operation runs in the named watchdog child
        # below; keep the parent gate to cheap availability checks only.
        # Keep the two heavyweight gates in separate, named subprocesses.  In
        # particular, do not use an empty ``python -c pass`` placeholder: the
        # child must execute the repository-owned internal probe mode and is
        # subject to the same process-group watchdog as every other stage.
        python = os.environ.get("PYTHON", sys.executable)
        for stage_name in ("cuda-rasterizer-preflight", "source-target-preflight"):
            stage_argv = [python, "-m", "aria_nbv.oracle.pipelines.cli", "--internal-preflight", stage_name]
            if plan_path is not None:
                stage_argv.extend(("--plan-path", str(plan_path)))
            if writer_config_path is not None:
                stage_argv.extend(("--writer-config-path", str(writer_config_path)))
            stage_argv.extend(("--expected-scene-count", str(self.config.expected_scene_count)))
            self.run_preflight_stage(
                tuple(stage_argv),
                stage_name=stage_name,
            )
        return {
            "ok": True,
            "cuda_available": True,
            "pytorch3d_available": True,
            "device": torch.cuda.get_device_name(0),
        }

    def run_preflight_stage(
        self, argv: Sequence[str], *, plan: CampaignPlan | None = None, stage_name: str = "preflight"
    ) -> tuple[int, str, str]:
        """Run the named 120-second setup stage through the process-group watchdog."""
        result = self.process_runner.run_stage(
            argv,
            timeout=self.config.stage_timeout_seconds,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        if plan is not None:
            self.append_event(
                self._event(
                    plan,
                    "preflight_stage_completed" if result[0] == 0 else "preflight_stage_failed",
                    stage=stage_name,
                    detail=(result[2] or result[1])[-2000:],
                )
            )
        if result[0] != 0:
            raw_detail = result[2] or result[1] or f"preflight stage exited {result[0]}"
            if isinstance(raw_detail, bytes):
                raw_detail = raw_detail.decode(errors="replace")
            detail = raw_detail.strip()
            # Internal probes run with normal Python exception reporting.  The
            # public CLI should expose the terminal reason, not embed a child
            # traceback inside Click's validation error.
            terminal_line = detail.splitlines()[-1] if detail else f"preflight stage exited {result[0]}"
            if ": " in terminal_line:
                exception_name, message = terminal_line.split(": ", 1)
                if exception_name.endswith(("Error", "Exception")):
                    terminal_line = message
            raise RuntimeError(terminal_line)
        return result

    def smoke(
        self,
        plan: CampaignPlan,
        *,
        config_path: Path | None = None,
        plan_path: Path | None = None,
    ) -> Any:
        unit = self._smoke_unit(plan)
        if config_path is None or plan_path is None:
            raise ValueError("production smoke requires canonical config_path and plan_path")
        argv = self.worker_argv(plan_path, unit, config_path=config_path)
        argv = tuple(plan.plan_hash if value == "PLAN_HASH" else value for value in argv)
        code, stdout, stderr = self.process_runner.run(
            argv, timeout=self.config.work_unit_timeout_seconds, stdout=subprocess.PIPE, stderr=subprocess.PIPE
        )
        if code:
            raise RuntimeError((stderr or stdout or f"worker exited {code}")[-2000:])
        try:
            result = self.parse_worker_result(stdout, plan, unit).to_jsonable()
        except (TypeError, ValueError, json.JSONDecodeError) as exc:
            raise RuntimeError("worker did not emit typed validated JSON") from exc
        if result.get("outcome") != CampaignOutcome.SUCCEEDED.value or result.get("validated") is not True:
            raise RuntimeError("smoke evidence requires a structured succeeded+validated worker result")
        evidence = {
            "campaign_id": self.config.campaign_id,
            "plan_hash": plan.plan_hash,
            "work_unit_hash": unit.work_unit_hash,
            "config_hash": plan.config_hash,
            "result": result,
        }
        (self.config.output_root / "smoke-evidence.json").parent.mkdir(parents=True, exist_ok=True)
        (self.config.output_root / "smoke-evidence.json").write_text(json.dumps(evidence, sort_keys=True) + "\n")
        return result

    @staticmethod
    def parse_worker_json(payload: str | bytes | dict[str, Any]) -> dict[str, Any]:
        """Parse worker JSON and preserve skipped as a distinct outcome."""
        if isinstance(payload, bytes):
            payload = payload.decode(errors="replace")
        if isinstance(payload, str):
            candidates = [line.strip() for line in payload.splitlines() if line.strip()]
            value = None
            for candidate in reversed(candidates):
                try:
                    value = json.loads(candidate)
                except json.JSONDecodeError:
                    continue
                break
            if value is None:
                raise ValueError("worker output contains no JSON result")
        else:
            value = payload
        if not isinstance(value, dict) or value.get("outcome") not in {"succeeded", "skipped", "insufficient_support"}:
            raise ValueError("worker JSON requires succeeded, skipped, or insufficient_support outcome")
        if value["outcome"] == "succeeded" and not value.get("validated"):
            raise ValueError("succeeded worker result requires validated evidence")
        return value

    def parse_worker_result(
        self, payload: str | bytes | dict[str, Any], plan: CampaignPlan, unit: CampaignWorkUnit
    ) -> CampaignWorkerResult:
        """Parse and strictly bind a subprocess worker result to its unit."""
        value = self.parse_worker_json(payload)
        return CampaignWorkerResult.from_jsonable(
            value,
            campaign_id=self.config.campaign_id,
            config_hash=plan.config_hash,
            plan_hash=plan.plan_hash,
            unit=unit,
        )

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
        result = evidence.get("result")
        unit = self._smoke_unit(plan)
        if not isinstance(result, dict):
            raise RuntimeError("smoke evidence result must be a typed worker result")
        try:
            typed_result = self.parse_worker_result(result, plan, unit)
        except ValueError as exc:
            raise RuntimeError("smoke evidence result identity is invalid") from exc
        if typed_result.outcome != CampaignOutcome.SUCCEEDED.value or not typed_result.validated:
            raise RuntimeError("smoke evidence result must be succeeded and validated")
        if evidence.get("work_unit_hash") != unit.work_unit_hash:
            raise RuntimeError("smoke evidence work-unit identity mismatch")
        for key in ("plan_hash", "work_unit_hash", "config_hash"):
            if key in result and result[key] != (
                plan.plan_hash
                if key == "plan_hash"
                else unit.work_unit_hash
                if key == "work_unit_hash"
                else plan.config_hash
            ):
                raise RuntimeError(f"smoke evidence {key} mismatch")
        return evidence

    def _smoke_unit(self, plan: CampaignPlan) -> CampaignWorkUnit:
        """Return the first deterministically planned unit used for smoke proof."""
        if not plan.work_units:
            raise ValueError("plan has no work units")
        unit = plan.work_units[0]
        if plan.campaign_id != self.config.campaign_id or unit.campaign_id != plan.campaign_id:
            raise ValueError("smoke unit campaign identity does not match the plan")
        if _work_unit_identity(unit, seed=plan.seed) != unit.work_unit_hash:
            raise ValueError("smoke unit hash does not match the plan")
        if unit.profile not in {profile.name for profile in self.config.profiles}:
            raise ValueError("smoke unit profile is not in the reviewed campaign config")
        if unit.config_hash != plan.config_hash:
            raise ValueError("smoke unit config binding does not match the plan")
        if unit.writer_config_hash != plan.writer_config_hash:
            raise ValueError("smoke unit writer binding does not match the plan")
        return unit

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
        binding = getattr(shard_entry, "campaign_binding", None)
        if binding is not None:
            expected = {
                "campaign_id": unit.campaign_id,
                "work_unit_hash": unit.work_unit_hash,
                "target_id": unit.target_id,
                "profile_hash": unit.profile_hash,
                "explicit_target_hash": unit.explicit_target_hash,
                "generation_revision_hash": unit.generation_revision_hash,
            }
            if any(getattr(binding, field, None) != value for field, value in expected.items()):
                raise ValueError("campaign work unit does not match shard campaign binding")
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
        if hasattr(shard_entry, "rows"):
            rows = tuple(shard_entry.rows)
            if len(rows) != 1 or getattr(rows[0], "sample_key", None) != unit.sample_key:
                raise ValueError("campaign work unit must bind exactly one matching source row")
        if hasattr(cfg, "sample_keys"):
            # Each campaign work unit is exactly one immutable source row.
            source_manifest_path = getattr(cfg, "source_manifest_path", None)
            if source_manifest_path is not None:
                from ...rollouts.shard_manifest import read_rollout_source_manifest

                manifest_keys = {row.sample_key for row in read_rollout_source_manifest(source_manifest_path).rows}
                if unit.sample_key not in manifest_keys:
                    raise ValueError("campaign work unit sample is absent from the canonical source manifest")
                cfg = cfg.model_copy(
                    update={
                        "sample_keys": [unit.sample_key],
                        "max_samples": 1,
                    }
                )
            else:
                # Legacy in-memory adapters have no manifest to constrain;
                # production configs always carry one and take the strict path.
                cfg = cfg.model_copy(update={"sample_keys": None})
        if explicit_target is not None and unit.explicit_target_config is not None:
            from .rollout_dataset import ExplicitRolloutTargetConfig

            canonical_override = ExplicitRolloutTargetConfig.model_validate(explicit_target).model_dump(mode="json")
            canonical_unit = ExplicitRolloutTargetConfig.model_validate(unit.explicit_target_config).model_dump(
                mode="json"
            )
            if canonical_override != canonical_unit:
                raise ValueError("explicit target override does not match immutable work-unit target")
        target_payload = unit.explicit_target_config if explicit_target is None else explicit_target
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
                    "min_valid_root_candidates": 15,
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
                component_type = type(mixture.components[0]) if mixture.components else None
                from ...pose_generation.candidate_mixture import CandidateMixtureViewGeneratorConfig

                typed_components = CandidateMixtureViewGeneratorConfig.reviewed_component_templates(
                    profile.components,
                    existing_components=list(mixture.components),
                )
                mixture.components = (
                    [component_type.model_validate(component.model_dump()) for component in typed_components]
                    if component_type
                    else typed_components
                )
            from ...rollouts.replay.policy import CounterfactualSelectionPolicy, RolloutPolicySpec
            from .rollout_dataset import RolloutRecipeConfig

            temperatures = tuple(unit.temperatures or (unit.temperature,))
            cfg = cfg.model_copy(
                update={
                    "recipes": [
                        RolloutRecipeConfig(
                            name=f"{recipe['name']}_t{temperature:g}",
                            policy=RolloutPolicySpec(
                                selection_policy=CounterfactualSelectionPolicy(recipe["policy"]),
                                horizon=recipe["horizon"],
                                branch_factor=recipe["branch"],
                                beam_width=recipe["beam"],
                                selection_temperature=temperature,
                                seed=(unit.seed_lineage or {}).get("recipe", self.config.seed),
                            ),
                        )
                        for temperature in temperatures
                        for recipe in profile.recipes
                    ]
                }
            )
        if hasattr(shard_entry, "split_manifest_hash") and hasattr(cfg, "store"):
            cfg = cfg.model_copy(
                update={"store": cfg.store.model_copy(update={"split_manifest_hash": shard_entry.split_manifest_hash})}
            )
        if hasattr(cfg, "model_dump"):
            cfg = type(cfg).model_validate({**cfg.model_dump(), "explicit_target": target_payload})
        # Canonical source/split/writer lineage is mandatory for production
        # shard entries.  Legacy unit tests may adapt a config without a real
        # shard envelope; those remain an in-memory construction seam only.
        if (
            hasattr(shard_entry, "rows")
            and getattr(cfg, "source_manifest_path", None) is not None
            and Path(cfg.source_manifest_path).exists()
        ):
            from .shards import plan_rollout_shards

            planned_entries = plan_rollout_shards(cfg, rows_per_shard=1)
            planned_entries = [entry for entry in planned_entries if entry.rows[0].sample_key == unit.sample_key]
            if len(planned_entries) != 1:
                raise ValueError("campaign work unit must plan exactly one canonical source row")
            shard_entry = planned_entries[0]
            if not shard_entry.rows or shard_entry.rows[0].sample_key != unit.sample_key:
                raise ValueError("campaign source row does not match canonical VIN manifest")
            if getattr(shard_entry, "writer_config_hash", "") != stable_config_hash(cfg):
                raise ValueError("campaign writer config hash does not match canonical shard lineage")
        binding = RolloutShardCampaignBinding(
            campaign_id=self.config.campaign_id,
            plan_hash=plan_hash
            or (unit.explicit_target_config.get("plan_hash", "") if unit.explicit_target_config else ""),
            work_unit_hash=unit.work_unit_hash,
            target_id=unit.target_id,
            profile_hash=profile_hash
            or (unit.explicit_target_config.get("profile_hash", "") if unit.explicit_target_config else ""),
            explicit_target_hash=unit.explicit_target_hash,
            generation_revision_hash=unit.generation_revision_hash,
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
        from ...rollouts.shard_manifest import (
            RolloutShardCampaignBinding,
            RolloutShardEntry,
            RolloutShardRow,
            build_rollout_split_manifest_hash,
        )

        if not unit.profile_hash:
            raise ValueError("work unit requires profile_hash identity")
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
            campaign_split=unit.campaign_split,
        )
        source_lineage_hash = str(source.get("source_manifest_hash", ""))
        if not source_lineage_hash:
            raise ValueError("work unit requires VIN source_manifest_hash lineage")
        entry = RolloutShardEntry(
            shard_id=f"shard-{unit.source_row_index:06d}",
            split=row.split,
            rows=(row,),
            writer_config_hash="",
            source_manifest_hash=source_lineage_hash,
            source_cache_version=str(source.get("source_cache_version", "campaign-v1")),
            split_manifest_hash=build_rollout_split_manifest_hash(
                source_manifest_hash=source_lineage_hash,
                split=row.split,
                records=[row.hash_record()],
            ),
            source_store_dir=str(source.get("source_store_dir", "")),
            campaign_binding=RolloutShardCampaignBinding(
                campaign_id=plan.campaign_id,
                plan_hash=plan.plan_hash,
                work_unit_hash=unit.work_unit_hash,
                target_id=unit.target_id,
                profile_hash=unit.profile_hash,
                explicit_target_hash=unit.explicit_target_hash,
                generation_revision_hash=plan.generation_revision.revision_hash if plan.generation_revision else "",
            ),
            campaign_split=unit.campaign_split,
            generation_revision_hash=plan.generation_revision.revision_hash if plan.generation_revision else "",
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
            sys.executable,
            "-m",
            "aria_nbv.oracle.pipelines.cli",
            "--campaign",
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
        plan_path: Path | None = None,
        config_path: Path | None = None,
        cuda_probe: Callable[[], Any] | None = None,
        nested_configs: Iterable[Any] = (),
        current_writer_config_hash: str = "",
        max_new_units: int | None = None,
        time_budget_seconds: float | None = None,
        free_disk_floor_gb: float | None = None,
    ) -> list[Any]:
        """Run a claimed campaign and always release its claim."""
        if plan is None:
            raise ValueError("an immutable CampaignPlan is required")
        if plan.campaign_id != self.config.campaign_id or any(
            unit.campaign_id != plan.campaign_id for unit in plan.work_units
        ):
            raise ValueError("campaign plan/unit identity does not match configured campaign")
        if plan.generation_revision is None:
            raise ValueError("campaign plan requires generation revision identity")
        current_revision = current_generation_revision()
        if current_revision.revision_hash != plan.generation_revision.revision_hash:
            raise ValueError("campaign generation revision does not match the plan")
        current_config_hash = stable_msgspec_hash(self.config.model_dump_jsonable())
        if plan.config_hash and plan.config_hash != current_config_hash:
            raise ValueError("campaign config hash does not match plan")
        if plan.writer_config_hash and plan.writer_config_hash != current_writer_config_hash:
            raise ValueError("writer config hash does not match plan")
        if max_new_units is not None and not 1 <= max_new_units <= 100:
            raise ValueError("max_new_units must be between 1 and 100")
        if time_budget_seconds is not None and time_budget_seconds <= 0:
            raise ValueError("time_budget_seconds must be positive")
        if free_disk_floor_gb is not None and free_disk_floor_gb <= 0:
            raise ValueError("free_disk_floor_gb must be positive")
        if free_disk_floor_gb is not None:
            free_bytes = shutil.disk_usage(self._disk_usage_path(self.config.output_root)).free
            if free_bytes < free_disk_floor_gb * 1024**3:
                raise RuntimeError("free disk floor is not satisfied")
        prior_results = self._resumable_event_results(plan)
        prior_events = self.read_events(plan=plan)
        prior_progress = self._validate_event_lifecycle(prior_events, plan)
        prior_state = next(iter(prior_progress["allowed_states"]))
        if prior_events and prior_state == "not_started":
            raise ValueError("incomplete planning event prefix")
        resuming_campaign = any(event.kind in {"campaign_started", "campaign_resumed"} for event in prior_events)
        # Exclusive ownership precedes every status/event mutation so a
        # competing start cannot clobber the active campaign's evidence.
        claim = self.acquire_claim(plan)
        try:
            self.preflight(
                cuda_probe,
                nested_configs=nested_configs,
                plan_path=plan_path,
                writer_config_path=self.config.writer_config_path,
            )
            if not resuming_campaign and prior_state not in {"preflight_passed", "smoke_passed"}:
                self.append_event(self._event(plan, "preflight_passed"))
                self.write_status(self.status(plan, prior_results, stage="preflight_passed"))
            self.smoke_evidence(plan)
            if not resuming_campaign and prior_state != "smoke_passed":
                self.append_event(self._event(plan, "smoke_passed"))
                self.write_status(self.status(plan, prior_results, stage="smoke_passed"))
            return self._run_claimed(
                plan,
                plan_path=plan_path,
                config_path=config_path,
                claim=claim,
                max_new_units=max_new_units,
                time_budget_seconds=time_budget_seconds,
                free_disk_floor_gb=free_disk_floor_gb,
            )
        finally:
            self.release_claim(plan, claim_hash=claim["claim_hash"])

    def _run_claimed(
        self,
        plan: CampaignPlan,
        *,
        plan_path: Path | None = None,
        config_path: Path | None = None,
        claim: dict[str, Any],
        max_new_units: int | None = None,
        time_budget_seconds: float | None = None,
        free_disk_floor_gb: float | None = None,
    ) -> list[Any]:
        if plan is None:
            raise ValueError("an immutable CampaignPlan is required")
        results_by_unit: dict[str, Any] = {
            result["work_unit_hash"]: result for result in self._resumable_event_results(plan)
        }

        def ordered_results() -> list[Any]:
            return [
                results_by_unit[unit.work_unit_hash]
                for unit in plan.work_units
                if unit.work_unit_hash in results_by_unit
            ]

        results = ordered_results()
        started_at = self.clock()
        started_at_iso = self.utc_now().isoformat()
        new_units = 0
        blocked = False
        last_timeout: dict[str, Any] | None = None
        prior_events = self.read_events(plan=plan)
        attempt_kind = (
            "campaign_resumed"
            if any(event.kind in {"campaign_started", "campaign_resumed"} for event in prior_events)
            else "campaign_started"
        )
        self.append_event(self._event(plan, attempt_kind))
        self.write_status(self.status(plan, results, stage="running", started_at=started_at_iso))
        for unit in plan.work_units:
            if unit.work_unit_hash in results_by_unit:
                continue
            reason = None
            if max_new_units is not None and new_units >= max_new_units:
                reason = "max_new_units reached"
            elif time_budget_seconds is not None and self.clock() - started_at >= time_budget_seconds:
                reason = "time budget exhausted"
            elif (
                free_disk_floor_gb is not None
                and shutil.disk_usage(self._disk_usage_path(self.config.output_root)).free
                < free_disk_floor_gb * 1024**3
            ):
                reason = "free disk floor reached"
            if reason:
                blocked = True
                self.append_event(
                    self._event(plan, "campaign_blocked", outcome=CampaignOutcome.BLOCKED.value, detail=reason)
                )
                self.write_status(
                    self.status(
                        plan,
                        results,
                        stage=CampaignOutcome.BLOCKED.value,
                        elapsed_seconds=self.clock() - started_at,
                        bounded_error=reason,
                        last_timeout=last_timeout,
                        started_at=started_at_iso,
                    )
                )
                break
            self.append_event(self._event(plan, "target_profile", unit=unit, stage=unit.profile))
            self.write_status(
                self.status(
                    plan,
                    results,
                    current_unit=unit,
                    stage=unit.profile,
                    elapsed_seconds=self.clock() - started_at,
                    last_timeout=last_timeout,
                    started_at=started_at_iso,
                )
            )
            self.append_event(self._event(plan, "root_preflight", unit=unit, stage="preflight"))
            self.write_status(
                self.status(
                    plan,
                    results,
                    current_unit=unit,
                    stage="preflight",
                    elapsed_seconds=self.clock() - started_at,
                    last_timeout=last_timeout,
                    started_at=started_at_iso,
                )
            )
            try:
                started = self._event(plan, "unit_started", unit=unit, stage="worker")
                self.append_event(started)
                self.write_status(
                    self.status(
                        plan,
                        results,
                        current_unit=unit,
                        stage="worker",
                        elapsed_seconds=self.clock() - started_at,
                        last_timeout=last_timeout,
                        started_at=started_at_iso,
                        active_started_at=started.timestamp,
                    )
                )
                self.append_event(self._event(plan, "recipe_worker", unit=unit, stage=unit.profile))
                argv = self.worker_argv(
                    plan_path or (self.config.output_root / "plan.json"), unit, config_path=config_path
                )
                argv = tuple(plan.plan_hash if x == "PLAN_HASH" else x for x in argv)
                returncode, stdout, stderr = self.process_runner.run(
                    argv,
                    timeout=self.config.work_unit_timeout_seconds,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    on_started=self._child_started_callback(
                        plan,
                        results,
                        unit,
                        started_at=started_at,
                        started_at_iso=started_at_iso,
                        last_timeout=last_timeout,
                    ),
                )
                if returncode:
                    raise RuntimeError((stderr or stdout or f"worker exited {returncode}")[-2000:])
                result = self.parse_worker_result(stdout, plan, unit).to_jsonable()
                outcome = (
                    result.get("outcome", CampaignOutcome.SUCCEEDED.value)
                    if isinstance(result, dict)
                    else CampaignOutcome.SUCCEEDED.value
                )
                if outcome != CampaignOutcome.SKIPPED.value:
                    new_units += 1
                elapsed = self.clock() - started_at
                if outcome in {CampaignOutcome.SUCCEEDED.value, CampaignOutcome.SKIPPED.value}:
                    self._require_validated_terminal_shard(plan, unit)
                if outcome == CampaignOutcome.INSUFFICIENT_SUPPORT.value:
                    detail = str(result.get("reason", "")) if isinstance(result, dict) else ""
                    self.append_event(
                        self._event(
                            plan,
                            "root_preflight_insufficient",
                            unit=unit,
                            outcome=outcome,
                            detail=detail,
                            stage="preflight",
                            elapsed_seconds=elapsed,
                        )
                    )
                    self.write_status(
                        self.status(
                            plan,
                            results,
                            current_unit=unit,
                            stage="preflight",
                            elapsed_seconds=elapsed,
                            last_timeout=last_timeout,
                            started_at=started_at_iso,
                        )
                    )
                elif outcome in {CampaignOutcome.SUCCEEDED.value, CampaignOutcome.SKIPPED.value}:
                    self.append_event(
                        self._event(
                            plan,
                            "root_preflight_completed",
                            unit=unit,
                            outcome=outcome,
                            stage="preflight",
                            elapsed_seconds=elapsed,
                        )
                    )
                    self.write_status(
                        self.status(
                            plan,
                            results,
                            current_unit=unit,
                            stage="preflight",
                            elapsed_seconds=elapsed,
                            last_timeout=last_timeout,
                            started_at=started_at_iso,
                        )
                    )
                    self.append_event(
                        self._event(
                            plan,
                            "recipe_stage_completed",
                            unit=unit,
                            outcome=outcome,
                            stage=unit.profile,
                            elapsed_seconds=elapsed,
                        )
                    )
                    self.write_status(
                        self.status(
                            plan,
                            results,
                            current_unit=unit,
                            stage=unit.profile,
                            elapsed_seconds=elapsed,
                            last_timeout=last_timeout,
                            started_at=started_at_iso,
                        )
                    )
                    self.append_event(
                        self._event(
                            plan,
                            "unit_validated_skip" if outcome == CampaignOutcome.SKIPPED.value else "unit_promoted",
                            unit=unit,
                            outcome=outcome,
                            stage="promotion",
                            elapsed_seconds=elapsed,
                        )
                    )
                    self.write_status(
                        self.status(
                            plan,
                            results,
                            current_unit=unit,
                            stage="promotion",
                            elapsed_seconds=elapsed,
                            last_timeout=last_timeout,
                            started_at=started_at_iso,
                        )
                    )
                if isinstance(result, dict):
                    result = {**result, "work_unit_hash": unit.work_unit_hash}
                results_by_unit[unit.work_unit_hash] = result
                results = ordered_results()
                self.append_event(
                    self._event(
                        plan,
                        "unit_" + str(outcome),
                        unit=unit,
                        outcome=str(outcome),
                        detail=str(result.get("reason", "")) if isinstance(result, dict) else "",
                        elapsed_seconds=elapsed,
                    )
                )
            except Exception as exc:  # record-and-continue is intentional
                quarantine_path = self.quarantine_staging(unit) if isinstance(exc, TimeoutError) else None
                outcome = (
                    CampaignOutcome.TIMED_OUT.value if isinstance(exc, TimeoutError) else CampaignOutcome.FAILED.value
                )
                result = {"outcome": outcome, "error": str(exc)[-2000:], "work_unit_hash": unit.work_unit_hash}
                results_by_unit[unit.work_unit_hash] = result
                results = ordered_results()
                if isinstance(exc, CampaignTimeoutError):
                    last_timeout = {
                        "work_unit_hash": unit.work_unit_hash,
                        "stage": "worker",
                        "pid": exc.pid,
                        "process_group": exc.process_group,
                        "tmux_session": exc.tmux_session
                        or (claim.get("tmux_session") if isinstance(claim, dict) else None),
                        "disposition": exc.disposition,
                        "stderr_tail": exc.stderr_tail,
                        "elapsed_seconds": exc.elapsed_seconds,
                    }
                self.append_event(
                    self._event(
                        plan,
                        "unit_" + outcome,
                        unit=unit,
                        outcome=outcome,
                        detail=(
                            str(exc)[-1500:] + f" quarantine={quarantine_path}"
                            if isinstance(exc, TimeoutError)
                            else str(exc)[-2000:]
                        ),
                        elapsed_seconds=self.clock() - started_at,
                        pid=getattr(exc, "pid", None),
                        process_group=getattr(exc, "process_group", None),
                        tmux_session=claim.get("tmux_session") if isinstance(claim, dict) else None,
                        timeout_disposition=getattr(exc, "disposition", None),
                        stderr_tail=getattr(exc, "stderr_tail", None),
                    )
                )
            self.write_status(
                replace(
                    self.status(
                        plan,
                        results,
                        current_unit=unit,
                        stage=str(outcome),
                        elapsed_seconds=self.clock() - started_at,
                        last_timeout=last_timeout,
                        started_at=started_at_iso,
                    ),
                    state="running",
                )
            )
        if not blocked:
            self.append_event(self._event(plan, "campaign_finished"))
            self.write_status(
                self.status(
                    plan,
                    results,
                    stage="terminal",
                    last_timeout=last_timeout,
                    started_at=started_at_iso,
                    finished_at=self.utc_now().isoformat(),
                )
            )
        return results

    def _resumable_event_results(self, plan: CampaignPlan) -> list[dict[str, str]]:
        """Rebuild plan-ordered terminal outcomes or reject a finished ledger."""
        events = self.read_events(plan=plan)
        if not events:
            return []
        progress = self._validate_event_lifecycle(events, plan)
        outcomes = progress["terminal_outcomes"]
        resumable_outcomes = {
            outcome
            for outcome in outcomes.values()
            if outcome not in {CampaignOutcome.SUCCEEDED.value, CampaignOutcome.SKIPPED.value}
        }
        if progress["allowed_states"] <= {"completed", "completed_with_failures"} and not resumable_outcomes:
            raise ValueError("completed campaign cannot be resumed")
        for unit in plan.work_units:
            if outcomes.get(unit.work_unit_hash) in {
                CampaignOutcome.SUCCEEDED.value,
                CampaignOutcome.SKIPPED.value,
            }:
                self._require_validated_terminal_shard(plan, unit)
        return [
            {"outcome": outcomes[unit.work_unit_hash], "work_unit_hash": unit.work_unit_hash}
            for unit in plan.work_units
            if outcomes.get(unit.work_unit_hash) in {CampaignOutcome.SUCCEEDED.value, CampaignOutcome.SKIPPED.value}
        ]

    def _event(
        self,
        plan: CampaignPlan,
        kind: str,
        *,
        unit: CampaignWorkUnit | None = None,
        outcome: str | None = None,
        detail: str = "",
        stage: str | None = None,
        elapsed_seconds: float | None = None,
        pid: int | None = None,
        process_group: int | None = None,
        tmux_session: str | None = None,
        timeout_disposition: str | None = None,
        stderr_tail: str | None = None,
    ) -> CampaignEvent:
        """Build a fully bound progress event for a plan or work unit."""
        return CampaignEvent(
            kind=kind,
            work_unit_hash=unit.work_unit_hash if unit else None,
            outcome=outcome,
            timestamp=self.utc_now().isoformat(),
            detail=detail,
            stage=stage,
            plan_hash=plan.plan_hash,
            config_hash=plan.config_hash,
            source_identity_hash=unit.source_identity_hash if unit else None,
            target_id=unit.target_id if unit else None,
            profile=unit.profile if unit else None,
            profile_hash=unit.profile_hash if unit else plan.profile_hash,
            writer_config_hash=plan.writer_config_hash,
            source_manifest_hash=plan.source_manifest_hash,
            elapsed_seconds=elapsed_seconds,
            pid=pid,
            process_group=process_group,
            tmux_session=tmux_session,
            timeout_disposition=timeout_disposition,
            stderr_tail=stderr_tail,
            campaign_id=self.config.campaign_id,
        )

    def quarantine_staging(self, unit: CampaignWorkUnit) -> Path | None:
        """Atomically quarantine a timed-out unit's known staging directory."""
        from .shards import quarantine_rollout_staging

        staging = self.config.output_root / "tmp" / unit.work_unit_hash
        return quarantine_rollout_staging(staging, self.config.output_root / "quarantine")

    def status(
        self,
        plan: CampaignPlan,
        results: Sequence[Any] = (),
        *,
        current_unit: CampaignWorkUnit | None = None,
        stage: str | None = None,
        elapsed_seconds: float = 0.0,
        bounded_error: str | None = None,
        last_timeout: dict[str, Any] | None = None,
        active_pid: int | None = None,
        active_process_group: int | None = None,
        active_started_at: str | None = None,
        started_at: str | None = None,
        finished_at: str | None = None,
        last_unit: CampaignWorkUnit | None = None,
    ) -> CampaignStatus:
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
        terminal_outcomes = {"succeeded", "skipped", "failed", "timed_out", "insufficient_support", "conflicted"}
        terminal = sum(
            1
            for result in results
            if (
                result.value
                if isinstance(result, CampaignOutcome)
                else result.get("outcome")
                if isinstance(result, dict)
                else "succeeded"
            )
            in terminal_outcomes
        )
        state = "not_started" if not results else ("completed" if terminal >= len(plan.work_units) else "running")
        if stage in {"planned", "preflight_passed", "smoke_passed"}:
            state = stage
        elif stage in {"running", "worker", "preflight", "promotion"} or stage in {
            p.name for p in self.config.profiles
        }:
            state = "running"
        elif stage in {CampaignOutcome.BLOCKED.value, CampaignOutcome.CONFLICTED.value}:
            state = stage
        elif stage == "terminal":
            state = (
                "completed_with_failures"
                if any(counts[k] for k in (CampaignOutcome.FAILED.value, CampaignOutcome.TIMED_OUT.value))
                else "completed"
            )
        counts["pending"] = max(0, len(plan.work_units) - terminal)
        if stage in {CampaignOutcome.BLOCKED.value, CampaignOutcome.CONFLICTED.value}:
            counts[stage] = counts.get(stage, 0) + 1
        if (
            any(counts[k] for k in (CampaignOutcome.FAILED.value, CampaignOutcome.TIMED_OUT.value))
            and state == "completed"
        ):
            state = "completed_with_failures"
        latest_failure = (
            next(
                (
                    str(result.get("error") or result.get("reason"))
                    for result in reversed(results)
                    if (
                        isinstance(result, dict)
                        and result.get("outcome") in {"failed", "timed_out", "insufficient_support"}
                        and (result.get("error") or result.get("reason"))
                    )
                ),
                None,
            )
            or bounded_error
        )
        smoke_hash = ""
        smoke_summary = None
        smoke_path = self.config.output_root / "smoke-evidence.json"
        if smoke_path.exists():
            try:
                smoke_raw = smoke_path.read_bytes()
                smoke_hash = hashlib.sha256(smoke_raw).hexdigest()
                smoke_payload = json.loads(smoke_raw)
                smoke_result = smoke_payload.get("result")
                if isinstance(smoke_result, dict):
                    smoke_summary = {"outcome": smoke_result.get("outcome"), "validated": smoke_result.get("validated")}
            except (OSError, ValueError, json.JSONDecodeError):
                smoke_summary = {"outcome": "invalid", "validated": False}
                latest_failure = latest_failure or "invalid_smoke_evidence"
        active = stage in {"running", "worker", "preflight", "promotion", *[p.name for p in self.config.profiles]}
        if stage in {CampaignOutcome.BLOCKED.value, CampaignOutcome.CONFLICTED.value, "terminal"}:
            active = False
        retained_last = last_unit or self._persisted_last_unit(plan)
        if not active and current_unit is not None:
            retained_last = current_unit
        return CampaignStatus(
            state,
            counts,
            plan.plan_hash,
            self.utc_now().isoformat(),
            current_unit.work_unit_hash if current_unit and active else None,
            current_unit.target_id if current_unit and active else None,
            current_unit.profile if current_unit and active else None,
            stage,
            float(elapsed_seconds),
            latest_failure,
            campaign_id=self.config.campaign_id,
            config_hash=plan.config_hash,
            last_work_unit=retained_last.work_unit_hash if retained_last else None,
            bounded_error=bounded_error,
            smoke_evidence_hash=smoke_hash,
            smoke_evidence_summary=smoke_summary,
            last_timeout=last_timeout,
            active_pid=active_pid,
            active_process_group=active_process_group,
            active_started_at=active_started_at,
            started_at=started_at,
            finished_at=finished_at,
        )

    def _persisted_last_unit(self, plan: CampaignPlan) -> CampaignWorkUnit | None:
        """Read only the prior typed terminal identity for status continuity."""
        target = self.config.output_root / "status.json"
        if not target.exists():
            return None
        try:
            previous = CampaignStatus.from_jsonable(json.loads(target.read_text(encoding="utf-8")))
        except (OSError, TypeError, ValueError, json.JSONDecodeError):
            return None
        if previous.plan_hash not in {"", plan.plan_hash}:
            return None
        return next((unit for unit in plan.work_units if unit.work_unit_hash == previous.last_work_unit), None)

    def _child_started_callback(
        self,
        plan: CampaignPlan,
        results: Sequence[Any],
        unit: CampaignWorkUnit,
        *,
        started_at: float,
        started_at_iso: str,
        last_timeout: dict[str, Any] | None,
    ) -> Callable[[int, int | None], None]:
        """Persist child identity immediately after subprocess creation."""

        def callback(pid: int, process_group: int | None) -> None:
            started = self._event(
                plan,
                "unit_started",
                unit=unit,
                stage="worker",
                pid=pid,
                process_group=process_group,
            )
            self.append_event(started)
            self.write_status(
                self.status(
                    plan,
                    results,
                    current_unit=unit,
                    stage="worker",
                    elapsed_seconds=self.clock() - started_at,
                    last_timeout=last_timeout,
                    started_at=started_at_iso,
                    active_pid=pid,
                    active_process_group=process_group,
                    active_started_at=started.timestamp,
                )
            )

        return callback

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
    def claim_is_stale(
        path: Path,
        *,
        tmux_probe: Callable[[str], bool] | None = None,
        pid_probe: Callable[[int], bool] | None = None,
        process_group_probe: Callable[[int], bool] | None = None,
        owner_probe: Callable[[str], bool] | None = None,
    ) -> bool:
        """Diagnose a vanished local owner without deleting its evidence."""
        if not path.exists():
            return False
        try:
            payload = json.loads(path.read_text())
            if payload.get("hostname") and payload["hostname"] != socket.gethostname():
                return True
            if payload.get("tmux_session"):
                probe = tmux_probe or (
                    lambda session: (
                        subprocess.run(("tmux", "has-session", "-t", session), capture_output=True).returncode == 0
                    )
                )
                if probe(str(payload["tmux_session"])):
                    return False
                return True
            pid = int(payload["pid"])
            alive = (pid_probe or (lambda p: os.kill(p, 0) is None))(pid)
            if not alive:
                return True
            if (
                payload.get("process_group")
                and process_group_probe is not None
                and not process_group_probe(int(payload["process_group"]))
            ):
                return True
            if payload.get("owner") and owner_probe is not None and not owner_probe(str(payload["owner"])):
                return True
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
        if not target.exists():
            tmp = target.with_name(f".{target.name}.tmp-{os.getpid()}")
            tmp.write_text(encoded, encoding="utf-8")
            os.replace(tmp, target)
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
            os.fsync(f.fileno())
        return target

    def read_events(self, path: Path | None = None, plan: CampaignPlan | None = None) -> list[CampaignEvent]:
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
                if index == len(lines) - 1 and not target.read_bytes().endswith(b"\n"):
                    break
                raise ValueError(f"malformed event line {index + 1}") from exc
            if not isinstance(payload, dict):
                raise ValueError(f"campaign event line {index + 1} must be a JSON object")
            allowed = set(CampaignEvent.__dataclass_fields__)
            is_legacy = "schema_version" not in payload
            if payload.get("schema_version", "campaign-event-v1") != "campaign-event-v1":
                raise ValueError(f"unsupported campaign event schema version at line {index + 1}")
            event = CampaignEvent(**{key: value for key, value in payload.items() if key in allowed})
            if not is_legacy and (not event.campaign_id or not event.plan_hash or not event.config_hash):
                raise ValueError("campaign event v1 requires campaign, plan, and config identity")
            if event.campaign_id and event.campaign_id != self.config.campaign_id:
                raise ValueError("campaign event campaign_id mismatch")
            current_config_hash = stable_msgspec_hash(self.config.model_dump_jsonable())
            if event.config_hash and event.config_hash != current_config_hash:
                raise ValueError("campaign event config_hash mismatch")
            if plan is not None and (
                (event.plan_hash and event.plan_hash != plan.plan_hash)
                or (event.config_hash and event.config_hash != plan.config_hash)
            ):
                raise ValueError("campaign event identity mismatch")
            if plan is not None:
                if event.writer_config_hash != plan.writer_config_hash:
                    raise ValueError("campaign event writer_config_hash mismatch")
                if event.source_manifest_hash != plan.source_manifest_hash:
                    raise ValueError("campaign event source_manifest_hash mismatch")
                if event.work_unit_hash is not None:
                    unit = next(
                        (item for item in plan.work_units if item.work_unit_hash == event.work_unit_hash),
                        None,
                    )
                    if unit is None:
                        raise ValueError("campaign event references unknown work unit")
                    bindings = {
                        "source_identity_hash": unit.source_identity_hash,
                        "target_id": unit.target_id,
                        "profile": unit.profile,
                        "profile_hash": unit.profile_hash,
                    }
                    for field, expected in bindings.items():
                        if getattr(event, field) != expected:
                            raise ValueError(f"campaign event {field} mismatch")
            events.append(event)
        return events

    def read_status(self, path: Path | None = None, plan: CampaignPlan | None = None) -> CampaignStatus:
        target = path or (self.config.output_root / "status.json")
        if not target.exists():
            if plan is not None:
                try:
                    events = self.read_events(plan=plan)
                    if events:
                        status = self._rebuild_status_from_events(events, plan)
                        self._cross_check_status_evidence(status, plan)
                        return status
                except (OSError, json.JSONDecodeError, TypeError, ValueError) as exc:
                    raise ValueError("invalid campaign status") from exc
            return CampaignStatus("not_started", {o.value: 0 for o in CampaignOutcome}, "", self.utc_now().isoformat())
        try:
            status = CampaignStatus.from_jsonable(json.loads(target.read_text(encoding="utf-8")))
            if status.campaign_id and status.campaign_id != self.config.campaign_id:
                raise ValueError("campaign status campaign_id mismatch")
            if (
                status.schema_version == "campaign-status-v2"
                and status.plan_hash
                and (not status.campaign_id or not status.config_hash)
            ):
                raise ValueError("campaign status v2 requires campaign and config identity")
            current_config_hash = stable_msgspec_hash(self.config.model_dump_jsonable())
            if status.schema_version == "campaign-status-v2" and status.config_hash:
                if status.config_hash != current_config_hash:
                    raise ValueError("campaign status config_hash mismatch")
            if plan is not None and (
                (status.plan_hash and status.plan_hash != plan.plan_hash)
                or (status.config_hash and status.config_hash != plan.config_hash)
            ):
                raise ValueError("campaign status plan identity mismatch")
            if plan is not None:
                known_units = {unit.work_unit_hash for unit in plan.work_units}
                if status.current_work_unit is not None and status.current_work_unit not in known_units:
                    raise ValueError("campaign status references unknown current work unit")
                if status.last_work_unit is not None and status.last_work_unit not in known_units:
                    raise ValueError("campaign status references unknown last work unit")
                self._cross_check_status_evidence(status, plan)
            return status
        except (OSError, json.JSONDecodeError, TypeError, ValueError) as exc:
            raise ValueError("invalid campaign status") from exc

    def _cross_check_status_evidence(self, status: CampaignStatus, plan: CampaignPlan) -> None:
        """Reject stale or divergent status when canonical progress exists."""
        events = self.read_events(plan=plan)
        if not events:
            expected = self.status(plan)
            projected_fields = (
                "current_work_unit",
                "current_target_id",
                "current_profile",
                "current_stage",
                "latest_failure_reason",
                "last_work_unit",
                "started_at",
                "finished_at",
                "bounded_error",
                "last_timeout",
                "active_pid",
                "active_process_group",
                "active_started_at",
            )
            if (
                status.state != "not_started"
                or status.counts != expected.counts
                or status.elapsed_seconds != 0.0
                or any(getattr(status, field) is not None for field in projected_fields)
            ):
                raise ValueError("campaign status lacks canonical event evidence")
            return
        progress = self._validate_event_lifecycle(events, plan)
        if status.state in {"completed", "completed_with_failures"} and not any(
            event.kind == "campaign_finished" for event in events
        ):
            raise ValueError("terminal status lacks campaign_finished evidence")
        if status.state == "running" and not any(event.kind == "campaign_started" for event in events):
            raise ValueError("running status lacks campaign_started evidence")
        latest = progress["terminal_outcomes"]
        counts = {outcome.value: 0 for outcome in CampaignOutcome}
        for outcome in latest.values():
            counts[outcome] = counts.get(outcome, 0) + 1
        counts["pending"] = max(0, len(plan.work_units) - len(latest))
        if progress["blocked"] and status.state == "blocked":
            counts[CampaignOutcome.BLOCKED.value] = 1
        for key, value in counts.items():
            if int(status.counts.get(key, 0)) != value:
                raise ValueError("campaign status diverges from canonical events")
        if status.state not in progress["allowed_states"]:
            raise ValueError("campaign status state diverges from canonical events")
        if status.current_work_unit != progress["current_work_unit"]:
            raise ValueError("campaign status current work unit diverges from canonical events")
        if status.last_work_unit != progress["last_work_unit"]:
            raise ValueError("campaign status last work unit diverges from canonical events")
        evidence_fields = (
            "current_target_id",
            "current_profile",
            "current_stage",
            "active_pid",
            "active_process_group",
            "active_started_at",
        )
        if any(getattr(status, field) != progress[field] for field in evidence_fields):
            raise ValueError("campaign status active projection diverges from canonical events")
        for work_unit_hash, outcome in latest.items():
            unit = next((item for item in plan.work_units if item.work_unit_hash == work_unit_hash), None)
            if unit is None:
                raise ValueError("event references unknown work unit")
            if outcome not in {CampaignOutcome.SUCCEEDED.value, CampaignOutcome.SKIPPED.value}:
                continue
            self._require_validated_terminal_shard(plan, unit)

    def _rebuild_status_from_events(self, events: Sequence[CampaignEvent], plan: CampaignPlan) -> CampaignStatus:
        """Rebuild the persisted read model when its canonical projection is missing."""
        progress = self._validate_event_lifecycle(events, plan)
        if len(progress["allowed_states"]) != 1:
            raise ValueError("canonical events do not identify one campaign state")
        state = next(iter(progress["allowed_states"]))
        if state == "not_started":
            raise ValueError("canonical events do not prove a started campaign state")
        outcomes = progress["terminal_outcomes"]
        results = [
            {"outcome": outcomes[unit.work_unit_hash], "work_unit_hash": unit.work_unit_hash}
            for unit in plan.work_units
            if unit.work_unit_hash in outcomes
        ]
        current_unit = next(
            (unit for unit in plan.work_units if unit.work_unit_hash == progress["current_work_unit"]),
            None,
        )
        last_unit = next(
            (unit for unit in plan.work_units if unit.work_unit_hash == progress["last_work_unit"]),
            None,
        )
        stage = progress["current_stage"]
        started_at = next(
            (event.timestamp for event in events if event.kind == "campaign_started"),
            None,
        )
        finished_at = next(
            (event.timestamp for event in reversed(events) if event.kind == "campaign_finished"),
            None,
        )
        rebuilt = self.status(
            plan,
            results,
            current_unit=current_unit,
            stage=stage,
            last_unit=last_unit,
            active_pid=progress["active_pid"],
            active_process_group=progress["active_process_group"],
            active_started_at=progress["active_started_at"],
            started_at=started_at,
            finished_at=finished_at,
        )
        return replace(rebuilt, updated_at=events[-1].timestamp or rebuilt.updated_at)

    def _require_validated_terminal_shard(self, plan: CampaignPlan, unit: CampaignWorkUnit) -> dict[str, Any]:
        """Return the plan-bound promoted shard or reject terminal success/skip."""
        from .shards import read_validated_completed_shard

        try:
            effective_writer, effective_entry = self._effective_writer_and_shard_entry(plan, unit)
            evidence = read_validated_completed_shard(
                self.config.output_root / "shards" / unit.work_unit_hash,
                shard_entry=effective_entry,
                writer_config_hash=(
                    plan.writer_config_hash if effective_writer is None else stable_config_hash(effective_writer)
                ),
            )
        except (OSError, TypeError, ValueError, KeyError) as exc:
            raise ValueError("terminal success/skip lacks validated shard evidence") from exc
        if evidence is None:
            raise ValueError("terminal success/skip lacks validated shard evidence")
        return evidence

    def _effective_writer_config_hash(self, plan: CampaignPlan, unit: CampaignWorkUnit) -> str:
        """Derive the per-unit writer digest bound by the campaign adapter.

        The plan digest identifies the unbound base writer. Promoted shards are
        bound after source, target, profile, recipe, and split adaptation, so
        terminal validation must compare the effective adapted configuration.
        """
        writer_path = getattr(self.config, "writer_config_path", None)
        if writer_path is None:
            return plan.writer_config_hash
        writer, _ = self._effective_writer_and_shard_entry(plan, unit)
        return stable_config_hash(writer)

    def _effective_writer_and_shard_entry(self, plan: CampaignPlan, unit: CampaignWorkUnit) -> tuple[Any, Any]:
        """Adapt the writer and canonical shard entry as one validation unit."""
        writer_path = getattr(self.config, "writer_config_path", None)
        if writer_path is None:
            return (None, self.shard_entry_for_unit(plan, unit))
        path = Path(writer_path)
        if not path.is_absolute():
            candidates = (Path.cwd() / path, Path(__file__).resolve().parents[4] / path)
            path = next((candidate for candidate in candidates if candidate.exists()), path)
        if not path.exists():
            raise ValueError(f"campaign writer config is missing: {path}")
        from .rollout_dataset import RolloutDatasetWriterConfig

        base_writer = RolloutDatasetWriterConfig.from_toml(path)
        adapted, adapted_entry = self.adapt_work_unit(
            unit,
            writer_config=base_writer,
            shard_entry=self.shard_entry_for_unit(plan, unit),
            plan_hash=plan.plan_hash,
            profile_hash=unit.profile_hash,
        )
        return adapted, adapted_entry

    @staticmethod
    def _validate_event_lifecycle(events: Sequence[CampaignEvent], plan: CampaignPlan) -> dict[str, Any]:
        """Validate the ordered event stream and return its canonical progress."""
        run_state = "prefix"
        pre_run_state = "not_started"
        finished = False
        saw_source_selection = False
        saw_plan_ready = False
        current_work_unit: str | None = None
        current_target_id: str | None = None
        current_profile: str | None = None
        current_stage: str | None = None
        last_work_unit: str | None = None
        active_pid: int | None = None
        active_process_group: int | None = None
        active_started_at: str | None = None
        unit_phases: dict[str, str] = {}
        terminal_outcomes: dict[str, str] = {}
        terminal_kinds = {
            "unit_succeeded",
            "unit_skipped",
            "unit_failed",
            "unit_timed_out",
            "unit_insufficient_support",
            "unit_blocked",
            "unit_conflicted",
        }
        known_units = {unit.work_unit_hash for unit in plan.work_units}
        for event in events:
            if finished and event.kind != "campaign_resumed":
                raise ValueError("events follow campaign_finished")
            if event.work_unit_hash is not None and event.work_unit_hash not in known_units:
                raise ValueError("event references unknown work unit")
            if event.kind == "source_selection":
                if run_state != "prefix" or saw_source_selection or saw_plan_ready or event.work_unit_hash:
                    raise ValueError("invalid source_selection transition")
                saw_source_selection = True
                continue
            if event.kind == "plan_ready":
                if run_state != "prefix" or not saw_source_selection or saw_plan_ready or event.work_unit_hash:
                    raise ValueError("invalid plan_ready transition")
                saw_plan_ready = True
                pre_run_state = "planned"
                current_stage = "planned"
                continue
            if event.kind == "preflight_passed":
                if (
                    run_state != "prefix"
                    or event.work_unit_hash is not None
                    or not saw_source_selection
                    or not saw_plan_ready
                    or pre_run_state != "planned"
                ):
                    raise ValueError("invalid preflight_passed transition")
                pre_run_state = "preflight_passed"
                current_stage = "preflight_passed"
                continue
            if event.kind == "smoke_passed":
                if run_state != "prefix" or event.work_unit_hash is not None or pre_run_state != "preflight_passed":
                    raise ValueError("invalid smoke_passed transition")
                pre_run_state = "smoke_passed"
                current_stage = "smoke_passed"
                continue
            if event.kind == "campaign_started":
                if run_state not in {"prefix", "blocked"}:
                    raise ValueError("duplicate campaign_started event")
                if run_state == "prefix" and pre_run_state != "smoke_passed":
                    raise ValueError("incomplete planning event prefix")
                run_state = "running"
                current_work_unit = None
                current_target_id = None
                current_profile = None
                current_stage = "running"
                active_pid = None
                active_process_group = None
                active_started_at = None
                unit_phases = {}
                continue
            if event.kind == "campaign_resumed":
                retryable = {
                    outcome
                    for outcome in terminal_outcomes.values()
                    if outcome not in {CampaignOutcome.SUCCEEDED.value, CampaignOutcome.SKIPPED.value}
                }
                if (
                    run_state not in {"running", "blocked", "finished"}
                    or event.work_unit_hash is not None
                    or (run_state == "finished" and not retryable)
                ):
                    raise ValueError("invalid campaign_resumed transition")
                terminal_outcomes = {
                    work_unit_hash: outcome
                    for work_unit_hash, outcome in terminal_outcomes.items()
                    if outcome in {CampaignOutcome.SUCCEEDED.value, CampaignOutcome.SKIPPED.value}
                }
                current_work_unit = None
                current_target_id = None
                current_profile = None
                current_stage = "running"
                active_pid = None
                active_process_group = None
                active_started_at = None
                unit_phases = dict.fromkeys(terminal_outcomes, "terminal")
                run_state = "running"
                finished = False
                continue
            if event.kind == "campaign_finished":
                if run_state != "running" or current_work_unit is not None:
                    raise ValueError("invalid campaign_finished transition")
                if set(terminal_outcomes) != known_units:
                    raise ValueError("campaign_finished precedes terminal work units")
                run_state = "finished"
                finished = True
                current_stage = "terminal"
                continue
            if run_state != "running":
                raise ValueError("event precedes campaign_started")
            if event.kind == "campaign_blocked":
                if current_work_unit is not None or event.work_unit_hash is not None:
                    raise ValueError("campaign_blocked while a work unit is active")
                run_state = "blocked"
                current_stage = CampaignOutcome.BLOCKED.value
                continue
            unit_hash = event.work_unit_hash
            if unit_hash is None:
                if event.kind in {"preflight_stage_completed", "preflight_stage_failed"}:
                    continue
                raise ValueError("work-unit event lacks work-unit identity")
            phase = unit_phases.get(unit_hash)
            if event.kind == "target_profile":
                if current_work_unit is not None or unit_hash in terminal_outcomes:
                    raise ValueError("target_profile overlaps an active work unit")
                current_work_unit = unit_hash
                current_target_id = event.target_id
                current_profile = event.profile
                current_stage = event.stage
                unit_phases[unit_hash] = "target_profile"
            elif event.kind == "root_preflight":
                if current_work_unit != unit_hash or phase != "target_profile":
                    raise ValueError("invalid root_preflight transition")
                unit_phases[unit_hash] = "root_preflight"
                current_stage = event.stage
            elif event.kind == "unit_started":
                if current_work_unit != unit_hash or phase != "root_preflight":
                    raise ValueError("invalid unit_started transition")
                unit_phases[unit_hash] = "unit_started"
                current_stage = event.stage
                active_pid = event.pid
                active_process_group = event.process_group
                active_started_at = event.timestamp
            elif event.kind == "recipe_worker":
                if current_work_unit != unit_hash or phase != "unit_started":
                    raise ValueError("invalid recipe_worker transition")
                unit_phases[unit_hash] = "recipe_worker"
                current_stage = "worker"
            elif event.kind in {"root_preflight_completed", "root_preflight_insufficient"}:
                if current_work_unit != unit_hash or phase not in {"unit_started", "recipe_worker"}:
                    raise ValueError(f"invalid {event.kind} transition")
                allowed_outcomes = (
                    {CampaignOutcome.INSUFFICIENT_SUPPORT.value}
                    if event.kind == "root_preflight_insufficient"
                    else {CampaignOutcome.SUCCEEDED.value, CampaignOutcome.SKIPPED.value}
                )
                if event.outcome not in allowed_outcomes:
                    raise ValueError(f"invalid {event.kind} outcome")
                unit_phases[unit_hash] = event.kind
                current_stage = event.stage
                active_pid = None
                active_process_group = None
                active_started_at = None
            elif event.kind == "recipe_stage_completed":
                if current_work_unit != unit_hash or phase != "root_preflight_completed":
                    raise ValueError("invalid recipe_stage_completed transition")
                unit_phases[unit_hash] = "recipe_stage_completed"
                current_stage = event.stage
            elif event.kind in {"unit_promoted", "unit_validated_skip"}:
                expected_outcome = (
                    CampaignOutcome.SUCCEEDED.value if event.kind == "unit_promoted" else CampaignOutcome.SKIPPED.value
                )
                if (
                    current_work_unit != unit_hash
                    or phase != "recipe_stage_completed"
                    or event.outcome != expected_outcome
                ):
                    raise ValueError(f"invalid {event.kind} transition")
                unit_phases[unit_hash] = event.kind
                current_stage = event.stage
            elif event.kind in terminal_kinds:
                expected_outcome = event.kind.removeprefix("unit_")
                valid_phase = {
                    CampaignOutcome.SUCCEEDED.value: "unit_promoted",
                    CampaignOutcome.SKIPPED.value: "unit_validated_skip",
                    CampaignOutcome.INSUFFICIENT_SUPPORT.value: "root_preflight_insufficient",
                }.get(expected_outcome)
                if (
                    current_work_unit != unit_hash
                    or unit_hash in terminal_outcomes
                    or event.outcome != expected_outcome
                    or (valid_phase is not None and phase != valid_phase)
                    or (valid_phase is None and phase not in {"root_preflight", "unit_started", "recipe_worker"})
                ):
                    raise ValueError("invalid unit terminal transition")
                terminal_outcomes[unit_hash] = expected_outcome
                last_work_unit = unit_hash
                current_work_unit = None
                current_target_id = None
                current_profile = None
                current_stage = expected_outcome
                active_pid = None
                active_process_group = None
                active_started_at = None
                unit_phases[unit_hash] = "terminal"
            else:
                raise ValueError(f"unsupported campaign event kind: {event.kind}")
        if run_state == "finished":
            has_failures = any(
                outcome in {CampaignOutcome.FAILED.value, CampaignOutcome.TIMED_OUT.value}
                for outcome in terminal_outcomes.values()
            )
            allowed_states = {"completed_with_failures" if has_failures else "completed"}
        elif run_state == "blocked":
            allowed_states = {"blocked"}
        elif run_state == "running":
            allowed_states = {"running"}
        elif pre_run_state != "not_started":
            allowed_states = {pre_run_state}
        else:
            allowed_states = {"not_started"}
        return {
            "allowed_states": allowed_states,
            "blocked": run_state == "blocked",
            "current_work_unit": current_work_unit,
            "current_target_id": current_target_id,
            "current_profile": current_profile,
            "current_stage": current_stage,
            "last_work_unit": last_work_unit,
            "active_pid": active_pid,
            "active_process_group": active_process_group,
            "active_started_at": active_started_at,
            "terminal_outcomes": terminal_outcomes,
        }

    def progress_summary(self, plan: CampaignPlan | None = None) -> dict[str, Any]:
        """Presentation-free status/events read model for CLI and UI adapters."""
        if plan is None:
            plan_path = self.config.output_root / "plan.json"
            if plan_path.exists():
                plan = self.load_plan(plan_path)
        status = self.read_status(plan=plan)
        payload = asdict(status)
        if status.state == "running" and status.started_at:
            try:
                started = datetime.fromisoformat(status.started_at)
                payload["elapsed_seconds"] = max(0.0, (self.utc_now() - started).total_seconds())
            except ValueError:
                pass
        payload["campaign_id"] = self.config.campaign_id
        raw = status.counts
        completed = int(raw.get("succeeded", 0)) + int(raw.get("skipped", 0))
        payload["counts"] = {
            "completed": completed,
            "failed": int(raw.get("failed", 0)) + int(raw.get("timed_out", 0)),
            "insufficient": int(raw.get("insufficient_support", 0)),
            "pending": (
                len(plan.work_units)
                if plan is not None and status.state == "not_started"
                else int(raw.get("pending", max(0, (len(plan.work_units) if plan else completed) - completed)))
            ),
        }
        if plan is not None and status.plan_hash and status.plan_hash != plan.plan_hash:
            payload["latest_failure_reason"] = "stale_status_plan_hash"
        artifacts: list[dict[str, Any]] = []
        shards_root = self.config.output_root / "shards"
        if shards_root.is_dir() and plan is not None:
            from .shards import read_validated_completed_shard

            for unit in plan.work_units:
                try:
                    effective_writer, entry = self._effective_writer_and_shard_entry(plan, unit)
                    effective_writer_hash = (
                        plan.writer_config_hash if effective_writer is None else stable_config_hash(effective_writer)
                    )
                    entry = replace(entry, writer_config_hash=effective_writer_hash)
                except (TypeError, ValueError, KeyError):
                    continue
                path = shards_root / unit.work_unit_hash
                evidence = read_validated_completed_shard(
                    path, shard_entry=entry, writer_config_hash=effective_writer_hash
                )
                if evidence is None:
                    continue
                binding = entry.campaign_binding.to_jsonable() if entry.campaign_binding else {}
                artifacts.append(
                    {
                        "work_unit_hash": unit.work_unit_hash,
                        "store_path": evidence["store_path"],
                        "owner_evidence_path": str((path / "_owner.json").resolve()),
                        "success_evidence_path": str((path / "_SUCCESS.json").resolve()),
                        "owner_sha256": evidence["success_evidence"].get("owner_sha256", ""),
                        "rollout_manifest_sha256": evidence["success_evidence"].get("rollout_manifest_sha256", ""),
                        "validation": evidence["validation"],
                        "campaign_binding": binding,
                        "campaign_id": self.config.campaign_id,
                        "config_hash": plan.config_hash,
                        "plan_hash": plan.plan_hash,
                        "target_id": unit.target_id,
                        "profile": unit.profile,
                        "profile_hash": unit.profile_hash,
                        "source_identity_hash": unit.source_identity_hash,
                        "split_manifest_hash": entry.split_manifest_hash,
                        "campaign_writer_config_hash": plan.writer_config_hash,
                        "effective_writer_config_hash": evidence["owner_evidence"].get("writer_config_hash", ""),
                        "campaign_source_manifest_hash": plan.source_manifest_hash,
                        "shard_source_manifest_hash": evidence["owner_evidence"].get("source_manifest_hash", ""),
                        "outcome": "succeeded",
                    }
                )
        payload["validated_artifacts"] = artifacts
        return payload

    def write_status(self, status: CampaignStatus, path: Path | None = None) -> Path:
        target = path or (self.config.output_root / "status.json")
        event_path = target.with_name("progress.jsonl")
        previous: CampaignStatus | None = None
        if target.exists():
            try:
                previous = CampaignStatus.from_jsonable(json.loads(target.read_text(encoding="utf-8")))
            except (OSError, TypeError, ValueError, json.JSONDecodeError) as exc:
                raise ValueError("existing campaign status is invalid") from exc

        canonical_state: str | None = None
        events = self.read_events(event_path)
        for event in events:
            if (
                (event.campaign_id and event.campaign_id != status.campaign_id)
                or (event.plan_hash and event.plan_hash != status.plan_hash)
                or (event.config_hash and event.config_hash != status.config_hash)
            ):
                raise ValueError("campaign status transition diverges from canonical event identity")
            if event.kind == "plan_ready":
                canonical_state = "planned"
            elif event.kind in {"preflight_passed", "smoke_passed"}:
                canonical_state = event.kind
            elif event.kind == "campaign_started":
                canonical_state = "running"
            elif event.kind == "campaign_resumed":
                canonical_state = "running"
            elif event.kind == "campaign_blocked":
                canonical_state = "blocked"

        prior_state = previous.state if previous is not None else canonical_state or "not_started"
        if prior_state in {"planned", "preflight_passed", "smoke_passed"} and canonical_state in {
            "planned",
            "preflight_passed",
            "smoke_passed",
        }:
            order = {"planned": 0, "preflight_passed": 1, "smoke_passed": 2}
            prior_state = max((prior_state, canonical_state), key=order.__getitem__)
        elif canonical_state in {"running", "blocked"}:
            prior_state = canonical_state
        required_event_kinds = {
            "planned": {"plan_ready"},
            "running": {"campaign_started", "campaign_resumed"},
            "blocked": {"campaign_blocked"},
            "conflicted": {"unit_conflicted"},
            "completed": {"campaign_finished"},
            "completed_with_failures": {"campaign_finished"},
        }
        if required := required_event_kinds.get(status.state):
            if not any(event.kind in required for event in events):
                raise ValueError(f"{status.state} campaign status transition requires canonical event evidence")
        if status.state not in self._STATUS_TRANSITIONS[prior_state]:
            raise ValueError(f"invalid campaign status transition: {prior_state} -> {status.state}")

        if status.state in {"preflight_passed", "smoke_passed"} and canonical_state != status.state:
            if not status.campaign_id or not status.plan_hash or not status.config_hash:
                raise ValueError("pre-run campaign status transition requires campaign, plan, and config identity")
            if not events:
                raise ValueError("pre-run campaign status transition requires canonical plan event evidence")
            binding_event = events[-1]
            self.append_event(
                CampaignEvent(
                    status.state,
                    timestamp=status.updated_at,
                    plan_hash=status.plan_hash,
                    config_hash=status.config_hash,
                    writer_config_hash=binding_event.writer_config_hash,
                    source_manifest_hash=binding_event.source_manifest_hash,
                    campaign_id=status.campaign_id,
                ),
                event_path,
            )
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
    "CampaignTimeoutError",
    "CampaignStatus",
    "CampaignWorkUnit",
    "CudaRolloutCampaign",
    "CudaRolloutCampaignConfig",
]
