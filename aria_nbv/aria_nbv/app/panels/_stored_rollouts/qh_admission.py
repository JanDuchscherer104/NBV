"""Read-only admission inspection for the configured ``Q_H`` training corpus.

The section deliberately stops at the DataModule boundary. It constructs the
configured datasets and their actual loaders, but never constructs a Trainer,
model, run manifest, or training loop.
"""

from __future__ import annotations

import tomllib
from collections.abc import Iterable, Iterator
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol, SupportsIndex, runtime_checkable

import pandas as pd
import streamlit as st

from .session import StoredRolloutSession
from .shared import _SECTION_KEY, _info_popover

_REPO_ROOT = Path(__file__).resolve().parents[5]
_REPORT_KEY = "stored_rollouts_qh_admission"
_MATERIALIZATION_KEY = "stored_rollouts_qh_materialization"
_LOCAL_CONFIG_MODE = "Local experiment TOML path"
_REPOSITORY_CONFIG_MODE = "Repository experiment TOML"
_TEMPLATE_PATH_PLACEHOLDER = "/ABS/PATH/TO/ARIA_DSS"

_QH_INFO = r"""
This view inspects the **training projection**, not another copy of the raw
rollout-store plots. An experiment TOML constructs its configured
`QhDataModule`; the module proves stage compatibility before any sample is
admitted.

- `QhRolloutChain` is one complete, unpadded persisted chain joined to its
  actor-visible VIN snippet.
- `QhBatch` is the actual DataLoader collation result. Its leading `B` axis and
  its `S`/`N` axes can contain padding.
- `q_train_mask[S,N]` admits finite, actor-valid Oracle labels.
  `row_train_mask[S]` gates selected-transition loss rows. They are different
  contracts; invalidity is never represented as a low reward.
- A single-process preview proves eligibility and collation shape. It does not
  claim the exact rank-wise order produced after Lightning replaces samplers in
  distributed training.
"""


class _QhDataset(Protocol):
    provenance: object
    scene_ids: Iterable[object]
    q_h_horizon: int

    def __len__(self) -> int: ...

    def __getitem__(self, index: int) -> object: ...


@runtime_checkable
class _QhLoader(Protocol):
    def __iter__(self) -> Iterator[object]: ...


@runtime_checkable
class _QhDataModule(Protocol):
    train_dataset: _QhDataset | None
    val_dataset: _QhDataset | None
    test_dataset: _QhDataset | None
    batch_size: int
    num_workers: int
    pin_memory: bool
    persistent_workers: bool
    learning_contract: object
    provenance: object

    def train_dataloader(self) -> object: ...

    def val_dataloader(self) -> object: ...

    def test_dataloader(self) -> object: ...


class _DataModuleConfig(Protocol):
    def setup_target(self, *, seed: int) -> object: ...


@runtime_checkable
class _ExperimentConfig(Protocol):
    seed: int
    datamodule_config: _DataModuleConfig


class _ExperimentConfigType(Protocol):
    @classmethod
    def from_toml(cls, path: Path) -> object: ...


@dataclass(frozen=True, slots=True)
class QhStageAdmission:
    """Metadata-only admission evidence for one configured corpus stage."""

    stage: str
    dataset_length: int
    scene_ids: tuple[str, ...]
    source_store_path: str | None
    source_manifest_hash: str | None
    rollout_store_paths: tuple[str, ...]
    horizon: int
    distributed_padding_rows: int
    distributed_padding_fraction: float
    provenance: dict[str, object]

    def to_row(self) -> dict[str, object]:
        """Return one compact Streamlit table row."""

        return {
            "stage": self.stage,
            "chains": self.dataset_length,
            "scenes": len(self.scene_ids),
            "horizon": self.horizon,
            "rollout_stores": ", ".join(self.rollout_store_paths),
            "actor_store": self.source_store_path,
            "actor_manifest": self.source_manifest_hash,
            "distributed_padding_rows": self.distributed_padding_rows,
            "distributed_padding_fraction": self.distributed_padding_fraction,
        }


@dataclass(frozen=True, slots=True)
class QhAdmissionReport:
    """All-stage evidence produced by the canonical DataModule factory."""

    config_path: Path
    seed: int
    world_size: int
    stages: tuple[QhStageAdmission, ...]
    learning_contract: dict[str, object]
    datamodule_provenance: dict[str, object]
    loader_policy: dict[str, object]
    scene_disjoint: bool

    def stage(self, name: str) -> QhStageAdmission:
        """Return one configured stage or raise an actionable error."""

        for stage in self.stages:
            if stage.stage == name:
                return stage
        raise ValueError(f"Q_H experiment has no configured {name!r} dataset.")


@dataclass(frozen=True, slots=True)
class QhAdmissionRuntime:
    """Admission report paired with its already validated DataModule."""

    report: QhAdmissionReport
    datamodule: _QhDataModule


@dataclass(frozen=True, slots=True)
class QhStageMaterialization:
    """Exactly one dataset item and the first batch from one actual stage loader."""

    stage: str
    dataset_index: int
    chain: object
    batch: object


@dataclass(frozen=True, slots=True)
class _PreflightState:
    key: tuple[Path, int]
    runtime: QhAdmissionRuntime


@dataclass(frozen=True, slots=True)
class _MaterializationState:
    key: tuple[Path, str, int]
    materialization: QhStageMaterialization


def _selected_preflight(value: object, *, key: tuple[Path, int]) -> QhAdmissionRuntime | None:
    if not isinstance(value, _PreflightState) or value.key != key:
        return None
    return value.runtime


def _selected_materialization(
    value: object,
    *,
    key: tuple[Path, str, int],
) -> QhStageMaterialization | None:
    if not isinstance(value, _MaterializationState) or value.key != key:
        return None
    return value.materialization


def discover_qh_experiment_configs(repo_root: Path = _REPO_ROOT) -> tuple[Path, ...]:
    """Return canonical explicit ``train_qh_*.toml`` experiment configs."""

    config_dir = repo_root.expanduser().resolve() / ".configs"
    return tuple(sorted(path.resolve() for path in config_dir.rglob("train_qh_*.toml") if path.is_file()))


def build_qh_admission_report(
    config_path: Path,
    *,
    world_size: int = 1,
    repo_root: Path = _REPO_ROOT,
) -> QhAdmissionRuntime:
    """Construct only the configured DataModule and summarize every stage."""

    canonical = _admit_config_path(config_path, repo_root=repo_root)
    _reject_template_config(canonical)
    if world_size < 1:
        raise ValueError("Distributed world size must be positive.")
    config_type = _load_qh_experiment_config_type()
    config = _require_experiment_config(config_type.from_toml(canonical))
    datamodule = _require_qh_datamodule(config.datamodule_config.setup_target(seed=config.seed))

    stages: list[QhStageAdmission] = []
    for name, dataset in _configured_datasets(datamodule):
        provenance = _mapping_copy(getattr(dataset, "provenance", {}))
        rollout = _mapping_copy(provenance.get("rollout", {}))
        actor = _mapping_copy(provenance.get("actor", {}))
        length = len(dataset)
        padding = (-length) % world_size
        emitted = length + padding
        stages.append(
            QhStageAdmission(
                stage=name,
                dataset_length=length,
                scene_ids=tuple(sorted(str(scene) for scene in getattr(dataset, "scene_ids", ()))),
                source_store_path=_optional_text(actor.get("store_path")),
                source_manifest_hash=_optional_text(actor.get("manifest_hash")),
                rollout_store_paths=_rollout_store_paths(rollout),
                horizon=int(dataset.q_h_horizon),
                distributed_padding_rows=padding,
                distributed_padding_fraction=0.0 if emitted == 0 else padding / emitted,
                provenance=provenance,
            )
        )
    if not stages:
        raise ValueError("Q_H DataModule did not expose any configured corpus stage.")

    scene_disjoint = _scenes_are_disjoint(stages)
    if not scene_disjoint:
        raise ValueError("Q_H configured corpus stages are not scene-disjoint.")
    report = QhAdmissionReport(
        config_path=canonical,
        seed=int(config.seed),
        world_size=world_size,
        stages=tuple(stages),
        learning_contract=_mapping_copy(getattr(datamodule, "learning_contract", {})),
        datamodule_provenance=_mapping_copy(getattr(datamodule, "provenance", {})),
        loader_policy={
            "batch_size_per_rank": int(datamodule.batch_size),
            "num_workers": int(datamodule.num_workers),
            "pin_memory": bool(datamodule.pin_memory),
            "persistent_workers": bool(datamodule.persistent_workers),
            "train_shuffle": True,
            "validation_test_shuffle": False,
            "lightning_distributed_sampler_eligible": True,
            "preview_exact_rank_order": False,
        },
        scene_disjoint=True,
    )
    return QhAdmissionRuntime(report=report, datamodule=datamodule)


def materialize_qh_stage(
    runtime: QhAdmissionRuntime,
    *,
    stage: str,
    dataset_index: int,
) -> QhStageMaterialization:
    """Read one selected chain and only the first actual loader batch."""

    stage_report = runtime.report.stage(stage)
    if not 0 <= dataset_index < stage_report.dataset_length:
        raise IndexError(
            f"Q_H {stage} dataset index {dataset_index} is outside [0, {stage_report.dataset_length - 1}]."
        )
    datasets = dict(_configured_datasets(runtime.datamodule))
    dataset = datasets[stage]
    chain = dataset[dataset_index]
    loader = _stage_loader(runtime.datamodule, stage)
    batch = next(iter(loader))
    return QhStageMaterialization(stage=stage, dataset_index=dataset_index, chain=chain, batch=batch)


def _load_qh_experiment_config_type() -> type[_ExperimentConfigType]:
    """Import the heavy Lightning/QH config only inside an explicit action."""

    from ....lightning.qh_experiment import QhExperimentConfig

    return QhExperimentConfig


def _admit_config_path(config_path: Path, *, repo_root: Path) -> Path:
    """Resolve one explicit readable TOML without narrowing it to checked-in examples.

    The admission view is a local, read-only diagnostic surface. A copied
    machine-local experiment config is therefore a first-class input: it is
    where concrete rollout and VIN-store mounts belong. Repository configs are
    merely convenient examples, not a safe substitute for those local paths.
    """

    raw_path = config_path.expanduser()
    canonical = (repo_root / raw_path).resolve() if not raw_path.is_absolute() else raw_path.resolve()
    if canonical.suffix.lower() != ".toml":
        raise ValueError(f"Q_H experiment config must be a .toml file, got {canonical}.")
    if not canonical.is_file():
        raise FileNotFoundError(f"Q_H experiment TOML does not exist or is not a file: {canonical}.")
    return canonical


def _reject_template_config(config_path: Path) -> None:
    """Fail early when a checked-in template still carries a fake data mount."""

    if fields := _template_placeholder_fields(config_path):
        formatted_fields = ", ".join(fields)
        raise ValueError(
            "Q_H experiment TOML contains template placeholders at "
            f"{formatted_fields}. Copy it to a local path and replace the rollout-store, VIN-store, and output "
            "paths before preflight."
        )


def _template_placeholder_fields(config_path: Path) -> tuple[str, ...]:
    """Return exact TOML fields that still contain the checked-in mount placeholder."""

    payload = tomllib.loads(config_path.read_text(encoding="utf-8"))
    fields: list[str] = []

    def _visit(value: object, *, path: str) -> None:
        if isinstance(value, str):
            if _TEMPLATE_PATH_PLACEHOLDER in value:
                fields.append(path)
            return
        if isinstance(value, dict):
            for key, item in value.items():
                _visit(item, path=f"{path}.{key}" if path else str(key))
            return
        if isinstance(value, list):
            for index, item in enumerate(value):
                _visit(item, path=f"{path}[{index}]")

    _visit(payload, path="")
    return tuple(fields)


def _require_qh_datamodule(value: object) -> _QhDataModule:
    if not isinstance(value, _QhDataModule):
        raise TypeError("Q_H DataModule factory returned an incompatible runtime object.")
    return value


def _require_experiment_config(value: object) -> _ExperimentConfig:
    if not isinstance(value, _ExperimentConfig):
        raise TypeError("Q_H experiment TOML produced an incompatible config object.")
    return value


def _configured_datasets(datamodule: _QhDataModule) -> tuple[tuple[str, _QhDataset], ...]:
    stages: list[tuple[str, _QhDataset]] = []
    for name, dataset in (
        ("train", datamodule.train_dataset),
        ("val", datamodule.val_dataset),
        ("test", datamodule.test_dataset),
    ):
        if dataset is not None:
            stages.append((name, dataset))
    return tuple(stages)


def _stage_loader(datamodule: _QhDataModule, stage: str) -> _QhLoader:
    if stage == "train":
        loader = datamodule.train_dataloader()
    elif stage == "val":
        loader = datamodule.val_dataloader()
    elif stage == "test":
        loader = datamodule.test_dataloader()
    else:
        raise ValueError(f"Q_H experiment has no configured {stage!r} loader.")
    if isinstance(loader, list):
        if len(loader) != 1:
            raise ValueError(f"Q_H {stage} loader must resolve to exactly one DataLoader.")
        loader = loader[0]
    if not isinstance(loader, _QhLoader):
        raise TypeError(f"Q_H {stage} loader is not iterable.")
    return loader


def _scenes_are_disjoint(stages: list[QhStageAdmission]) -> bool:
    for index, left in enumerate(stages):
        left_scenes = set(left.scene_ids)
        for right in stages[index + 1 :]:
            if left_scenes.intersection(right.scene_ids):
                return False
    return True


def _mapping_copy(value: object) -> dict[str, object]:
    return dict(value) if isinstance(value, dict) else {}


def _optional_text(value: object) -> str | None:
    return None if value in (None, "") else str(value)


def _rollout_store_paths(provenance: dict[str, object]) -> tuple[str, ...]:
    stores = provenance.get("stores")
    if isinstance(stores, list):
        paths = tuple(
            str(entry["path"]) for entry in stores if isinstance(entry, dict) and entry.get("path") not in (None, "")
        )
        if paths:
            return paths
    for key in ("store_path", "store_dir", "path"):
        if value := _optional_text(provenance.get(key)):
            return (value,)
    source = provenance.get("source")
    if isinstance(source, dict):
        return _rollout_store_paths(source)
    return ()


def _carry_lineage_to_inspect(
    lineage: object,
    *,
    session: StoredRolloutSession,
    rollout_store_paths: tuple[str, ...],
) -> str | None:
    """Carry compatible persisted identities into Inspect & Rerun state."""

    if len(rollout_store_paths) != 1:
        return "The QH stage must identify exactly one rollout store; raw-inspector handoff was not applied."
    configured_store = Path(rollout_store_paths[0]).expanduser().resolve()
    if session.store_path.expanduser().resolve() != configured_store:
        return "The QH stage references a different rollout store; raw-inspector handoff was not applied."
    rollout_id = getattr(lineage, "rollout_row_id", None)
    if rollout_id is None:
        return "The materialized chain has no rollout_row_id lineage; raw-inspector handoff was not applied."
    if not isinstance(rollout_id, SupportsIndex):
        return "The materialized chain has invalid rollout_row_id lineage; raw-inspector handoff was not applied."
    rollout_id = int(rollout_id)
    st.session_state["stored_rollout_id"] = rollout_id
    steps = session.steps(rollout_row_id=rollout_id)
    first_step = next((row.get("step_row_id") for row in steps if row.get("step_row_id") is not None), None)
    if isinstance(first_step, SupportsIndex):
        st.session_state["stored_step_id"] = int(first_step)
    st.session_state[_SECTION_KEY] = "Inspect & Rerun"
    return None


def _render_runtime_topology(value: object, *, root_name: str) -> None:
    from ....dataset_topology import build_runtime_topology
    from ....dataset_topology.rendering import render_topology_snapshot

    topology = build_runtime_topology(value, root_name=root_name)
    render_topology_snapshot(snapshot=topology)


def _render_report(report: QhAdmissionReport) -> None:
    columns = st.columns(4)
    columns[0].metric("Configured stages", len(report.stages))
    columns[1].metric("Seed", report.seed)
    columns[2].metric("Preview world size", report.world_size)
    columns[3].metric("Scene-disjoint", "yes" if report.scene_disjoint else "no")
    st.dataframe(pd.DataFrame(stage.to_row() for stage in report.stages), hide_index=True, width="stretch")
    with st.expander("DataModule contract and provenance"):
        st.markdown("**Loader policy**")
        st.json(report.loader_policy)
        st.markdown("**Learning contract**")
        st.json(report.learning_contract)
        st.markdown("**All-stage provenance**")
        st.json(report.datamodule_provenance)


def render(session: StoredRolloutSession) -> None:
    """Render explicit-config preflight and bounded chain/batch inspection."""

    st.subheader("QH Training Admission")
    _info_popover("What this validates", _QH_INFO)
    configs = discover_qh_experiment_configs()
    source_mode = st.radio(
        "QH experiment TOML source",
        (_REPOSITORY_CONFIG_MODE, _LOCAL_CONFIG_MODE),
        horizontal=True,
        key="stored_rollouts_qh_config_mode",
        help=(
            "Repository configs are examples or checked-in experiments. Use a local TOML for concrete "
            "rollout and VIN-store mounts on this machine."
        ),
    )
    if source_mode == _REPOSITORY_CONFIG_MODE:
        if not configs:
            st.info("No repository `train_qh_*.toml` configs were found below `.configs`. Choose a local TOML path.")
            config_path = None
        else:
            config_path = st.selectbox(
                "Repository QH experiment TOML",
                configs,
                format_func=lambda path: path.relative_to(_REPO_ROOT).as_posix(),
                key="stored_rollouts_qh_config",
            )
    else:
        local_path = st.text_input(
            "Local QH experiment TOML path",
            placeholder="/absolute/path/to/train_qh_local.toml",
            key="stored_rollouts_qh_local_config",
            help="An absolute path is recommended. Relative paths are resolved from the ARIA-NBV repository root.",
        )
        config_path = None if not local_path.strip() else Path(local_path.strip())

    template_fields: tuple[str, ...] = ()
    if config_path is not None:
        try:
            resolved_config_path = _admit_config_path(config_path, repo_root=_REPO_ROOT)
        except (OSError, ValueError) as exc:
            resolved_config_path = None
            st.error(f"QH experiment TOML is unavailable: {type(exc).__name__}: {exc}")
        else:
            try:
                config_text = resolved_config_path.read_text(encoding="utf-8")
                template_fields = _template_placeholder_fields(resolved_config_path)
            except (OSError, tomllib.TOMLDecodeError) as exc:
                resolved_config_path = None
                st.error(f"QH experiment TOML is not valid TOML: {type(exc).__name__}: {exc}")
            else:
                with st.expander("TOML configuration", expanded=False):
                    st.code(config_text, language="toml")
                if template_fields:
                    st.warning(
                        "This TOML is a path template, not a runnable local experiment. Copy it outside the repository, "
                        "replace these fields with this machine's concrete paths, then select that local TOML: "
                        + ", ".join(template_fields)
                    )
    else:
        resolved_config_path = None

    world_size = int(
        st.number_input(
            "Distributed world size for padding estimate",
            min_value=1,
            value=1,
            step=1,
            help="Eligibility estimate only; this preview does not initialize distributed training.",
        )
    )
    preflight_key = (resolved_config_path, world_size) if resolved_config_path is not None else None
    if st.button(
        "Preflight configured stages",
        type="primary",
        disabled=resolved_config_path is None or bool(template_fields),
    ):
        try:
            if resolved_config_path is None:
                raise ValueError("Select a readable Q_H experiment TOML before preflight.")
            built_runtime = build_qh_admission_report(resolved_config_path, world_size=world_size)
            st.session_state[_REPORT_KEY] = _PreflightState(key=preflight_key, runtime=built_runtime)
            st.session_state.pop(_MATERIALIZATION_KEY, None)
        except Exception as exc:
            st.session_state.pop(_REPORT_KEY, None)
            st.session_state.pop(_MATERIALIZATION_KEY, None)
            st.error(f"QH admission failed closed: {type(exc).__name__}: {exc}")

    runtime = (
        None if preflight_key is None else _selected_preflight(st.session_state.get(_REPORT_KEY), key=preflight_key)
    )
    if runtime is None:
        st.caption("Preflight constructs only the configured DataModule; no Trainer or training loop is created.")
        return
    _render_report(runtime.report)

    stage_names = [stage.stage for stage in runtime.report.stages]
    stage_name = st.selectbox("Stage to materialize", stage_names, key="stored_rollouts_qh_stage")
    stage_report = runtime.report.stage(stage_name)
    dataset_index = int(
        st.number_input(
            "Chain dataset index",
            min_value=0,
            max_value=max(stage_report.dataset_length - 1, 0),
            value=0,
            step=1,
            key=f"stored_rollouts_qh_index:{stage_name}",
        )
    )
    materialization_key = (runtime.report.config_path, stage_name, dataset_index)
    if st.button("Load one chain and first actual batch"):
        try:
            st.session_state[_MATERIALIZATION_KEY] = _MaterializationState(
                key=materialization_key,
                materialization=materialize_qh_stage(
                    runtime,
                    stage=stage_name,
                    dataset_index=dataset_index,
                ),
            )
        except Exception as exc:
            st.session_state.pop(_MATERIALIZATION_KEY, None)
            st.error(f"QH sample materialization failed closed: {type(exc).__name__}: {exc}")

    materialized = _selected_materialization(
        st.session_state.get(_MATERIALIZATION_KEY),
        key=materialization_key,
    )
    if materialized is None:
        return
    st.caption(
        "The chain is unpadded dataset evidence. The batch is the first result from the actual stage DataLoader; "
        "its B/S/N dimensions may include collation padding."
    )
    chain_tab, batch_tab = st.tabs(["QhRolloutChain", "QhBatch"])
    with chain_tab:
        _render_runtime_topology(materialized.chain, root_name="chain")
    with batch_tab:
        _render_runtime_topology(materialized.batch, root_name="batch")

    lineage = getattr(materialized.chain, "lineage", None)
    if lineage is not None and st.button("Inspect this rollout in raw store"):
        error = _carry_lineage_to_inspect(
            lineage,
            session=session,
            rollout_store_paths=stage_report.rollout_store_paths,
        )
        if error is not None:
            st.warning(error)


__all__ = [
    "QhAdmissionReport",
    "QhAdmissionRuntime",
    "QhStageAdmission",
    "QhStageMaterialization",
    "build_qh_admission_report",
    "discover_qh_experiment_configs",
    "materialize_qh_stage",
    "render",
]
