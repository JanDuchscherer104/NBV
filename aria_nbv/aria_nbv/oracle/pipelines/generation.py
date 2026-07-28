"""Typed admission and synchronous execution for local dataset generation.

This module is the non-UI boundary between config files and the existing VIN
offline and rollout writers. Streamlit selects a config reference and renders
the returned plan; TOML parsing, Pydantic defaults, writer construction, and
destination safety remain here and in the concrete config/writer owners.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
from typing import TYPE_CHECKING, Any, cast

from ...rollouts.manifest import RolloutStoreInvocation
from ...utils.config_paths import resolve_config_toml_path
from .offline_vin import VinOfflineWriter, VinOfflineWriterConfig
from .progress import GenerationProgress, ProgressCallback
from .rollout_dataset import RolloutDatasetWriter, RolloutDatasetWriterConfig

if TYPE_CHECKING:
    from ...rollouts.zarr_store import RolloutZarrWriteResult


class GenerationKind(StrEnum):
    """Dataset artifact families supported by the local generation console."""

    VIN_OFFLINE = "vin_offline"
    ROLLOUTS = "rollouts"


@dataclass(frozen=True, slots=True)
class GenerationConfigRef:
    """One typed generation config discovered below `.configs/generation`."""

    kind: GenerationKind
    """Writer family that owns TOML validation and execution."""

    path: Path
    """Absolute config path passed to the typed config loader."""

    label: str
    """Config-root-relative label displayed by Streamlit."""


@dataclass(frozen=True, slots=True)
class GenerationPlan:
    """Validated effective config and destination-safety preflight."""

    kind: GenerationKind
    """Selected VIN-offline or rollout writer family."""

    config_path: Path
    """Absolute TOML path that produced `config`."""

    config: VinOfflineWriterConfig | RolloutDatasetWriterConfig
    """Fully validated config with TOML values layered over model defaults."""

    source: Path | None
    """Existing VIN source store for rollout generation, when applicable."""

    destination: Path
    """Resolved output store path owned by the writer."""

    max_samples: int | None
    """Configured local sample bound; `None` means the config does not cap it."""

    effective_config: dict[str, Any]
    """JSON-safe resolved config displayed read-only in the UI."""

    blockers: tuple[str, ...]
    """Safety failures that disable generation before writer construction."""

    requires_overwrite_confirmation: bool
    """Whether the config explicitly allows replacing an existing VIN store."""


@dataclass(frozen=True, slots=True)
class GenerationResult:
    """Small completion report returned without reopening the generated store."""

    kind: GenerationKind
    """Writer family that completed."""

    destination: Path
    """Generated store path."""

    summary: dict[str, Any]
    """Writer-returned counts suitable for status display."""


class GenerationBlockedError(RuntimeError):
    """Raised when local generation violates its preflight safety boundary."""


_CONFIG_TYPES: dict[GenerationKind, type[VinOfflineWriterConfig] | type[RolloutDatasetWriterConfig]] = {
    GenerationKind.VIN_OFFLINE: VinOfflineWriterConfig,
    GenerationKind.ROLLOUTS: RolloutDatasetWriterConfig,
}

_GENERATION_DIRECTORIES = {
    GenerationKind.VIN_OFFLINE: Path("generation/vin"),
    GenerationKind.ROLLOUTS: Path("generation/rollouts"),
}

_CLI_OWNED_ROLLOUT_GROUPS = frozenset({"campaigns", "templates"})


def discover_generation_configs(config_root: str | Path) -> tuple[GenerationConfigRef, ...]:
    """Discover only writer configs admitted by the generation directory contract."""

    root = Path(config_root).expanduser().resolve()
    refs: list[GenerationConfigRef] = []
    for kind, relative_dir in _GENERATION_DIRECTORIES.items():
        directory = root / relative_dir
        if not directory.is_dir():
            continue
        refs.extend(
            GenerationConfigRef(kind=kind, path=path.resolve(), label=path.relative_to(root).as_posix())
            for path in directory.rglob("*.toml")
            if path.is_file()
        )
    return tuple(sorted(refs, key=lambda ref: ref.label))


def load_generation_plan(config_path: str | Path, kind: GenerationKind) -> GenerationPlan:
    """Load one typed config and derive a mutation-free local preflight."""

    resolved = resolve_config_toml_path(config_path)
    config = _CONFIG_TYPES[kind].from_toml(resolved)
    destination = Path(config.store.store_dir).expanduser().resolve()
    rollout_config = cast("RolloutDatasetWriterConfig", config)
    vin_config = cast("VinOfflineWriterConfig", config)
    source = None
    if kind is GenerationKind.ROLLOUTS:
        source = Path(rollout_config.source.store.store_dir).expanduser().resolve()
    blockers: list[str] = []
    requires_overwrite_confirmation = False
    max_samples = getattr(config, "max_samples", None)
    if max_samples is None:
        blockers.append("Local generation requires a finite max_samples value in the TOML config.")
    if kind is GenerationKind.ROLLOUTS and _rollout_group(resolved) in _CLI_OWNED_ROLLOUT_GROUPS:
        blockers.append("Campaign and template rollout configs are CLI/Slurm-owned and cannot run in Streamlit.")
    if source is not None and not source.exists():
        blockers.append(f"VIN source store does not exist: {source}")
    if destination.exists():
        if kind is GenerationKind.ROLLOUTS:
            blockers.append(f"Rollout destination already exists: {destination}")
        elif bool(vin_config.overwrite):
            requires_overwrite_confirmation = True
        else:
            blockers.append(f"VIN offline destination already exists and overwrite is disabled: {destination}")
    return GenerationPlan(
        kind=kind,
        config_path=resolved,
        config=config,
        source=source,
        destination=destination,
        max_samples=max_samples,
        effective_config=config.model_dump_jsonable(),
        blockers=tuple(blockers),
        requires_overwrite_confirmation=requires_overwrite_confirmation,
    )


def run_generation(
    plan: GenerationPlan,
    *,
    progress: ProgressCallback | None = None,
    allow_overwrite: bool = False,
) -> GenerationResult:
    """Run one validated local generation plan synchronously.

    The function never starts a background process or remote campaign. Writer
    exceptions propagate after a final failed progress event so Streamlit and
    CLI callers share the same failure semantics.
    """

    if plan.blockers:
        raise GenerationBlockedError("; ".join(plan.blockers))
    if plan.requires_overwrite_confirmation and not allow_overwrite:
        raise GenerationBlockedError("Explicit overwrite confirmation is required for the existing VIN store.")

    _emit(
        progress, GenerationProgress(stage="preparing", completed=0, total=plan.max_samples, message="Preparing writer")
    )
    try:
        target = plan.config.setup_target()
        if target is None:
            raise RuntimeError(f"{type(plan.config).__name__}.setup_target() returned None.")
        raw_result: object
        if plan.kind is GenerationKind.ROLLOUTS:
            invocation = RolloutStoreInvocation.from_config(config_path=plan.config_path)
            rollout_target = cast("RolloutDatasetWriter", target)
            raw_result = rollout_target.run(progress=progress, invocation=invocation)
        else:
            vin_target = cast("VinOfflineWriter", target)
            raw_result = vin_target.run(progress=progress)
    except Exception as exc:
        _emit(
            progress,
            GenerationProgress(
                stage="failed",
                completed=0,
                total=plan.max_samples,
                message=f"Generation failed: {type(exc).__name__}: {exc}",
            ),
        )
        raise

    summary = _result_summary(plan.kind, raw_result)
    completed = int(summary.get("num_samples", summary.get("num_rollouts", 0)))
    _emit(
        progress,
        GenerationProgress(
            stage="complete",
            completed=completed,
            total=plan.max_samples,
            message=f"Generation complete: {plan.destination}",
        ),
    )
    return GenerationResult(kind=plan.kind, destination=plan.destination, summary=summary)


def _result_summary(kind: GenerationKind, result: object) -> dict[str, Any]:
    if kind is GenerationKind.VIN_OFFLINE:
        return dict(getattr(result, "stats", {}))
    rollout_result = cast("RolloutZarrWriteResult", result)
    return {
        "num_rollouts": int(rollout_result.num_rollouts),
        "num_steps": int(rollout_result.num_steps),
        "num_candidates": int(rollout_result.num_candidates),
    }


def _emit(progress: ProgressCallback | None, event: GenerationProgress) -> None:
    if progress is not None:
        progress(event)


def _rollout_group(path: Path) -> str | None:
    """Return the directory owning a rollout profile below `generation/rollouts`."""

    parts = path.parts
    for index in range(len(parts) - 2):
        if parts[index : index + 2] == ("generation", "rollouts"):
            return parts[index + 2]
    return None


__all__ = [
    "GenerationBlockedError",
    "GenerationConfigRef",
    "GenerationKind",
    "GenerationPlan",
    "GenerationResult",
    "discover_generation_configs",
    "load_generation_plan",
    "run_generation",
]
