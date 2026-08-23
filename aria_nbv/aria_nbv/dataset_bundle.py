"""Read-only composition evidence for VIN roots and rollout supervision stores.

This module owns the presentation-neutral training-dataset bundle boundary. A
bundle selects exactly one immutable VIN root store and an explicit tuple of
standalone rollout stores. Lightweight inspection reads manifests, indexes,
split metadata, and persisted storage evidence only;
:func:`compute_dataset_bundle_deep_statistics` is the separate opt-in array
scan. Neither path repairs, migrates, or writes a store.
"""

from __future__ import annotations

import json
from collections import Counter
from dataclasses import dataclass, fields
from pathlib import Path
from typing import Any, Literal

import msgspec
import numpy as np

from .data_handling.identifiers import compact_ase_atek_sample_id
from .data_handling.qh_data.views import (
    QhExperimentProfile,
    QhRootEvlProfile,
    QhSelectedObservationProtocol,
    validate_experiment_profile,
)
from .data_handling.vin_store.format import VinOfflineIndexRecord, VinOfflineManifest
from .data_handling.vin_store.store import OFFLINE_DATASET_VERSION, VinOfflineStoreConfig
from .data_handling.vin_store.target_inventory import TargetInventory, inspect_target_inventory
from .rollouts.inspection import (
    build_effective_streamlit_trust,
    build_manifest_facts,
    build_promotion_evidence,
    build_schema_validation,
)
from .rollouts.manifest import read_rollout_store_manifest
from .rollouts.zarr_store import ROLLOUT_ZARR_SCHEMA_VERSION, RolloutZarrStoreReader
from .utils import Stage
from .utils.fingerprints import stable_msgspec_hash

DatasetBundleVerdict = Literal["Ready", "Incomplete", "Blocked"]
"""Training-bundle readiness after the requested level of inspection."""

FindingSeverity = Literal["blocking", "incomplete", "information"]
"""Effect of one bundle finding on the aggregate readiness verdict."""


@dataclass(frozen=True, slots=True)
class DatasetBundleSelection:
    """Session-local selection of one VIN root and explicit rollout stores."""

    root_store: Path
    """Exactly one immutable VIN offline-store directory."""

    rollout_stores: tuple[Path, ...] = ()
    """Explicit rollout-store directories; order is normalized and deduplicated."""

    def __post_init__(self) -> None:
        root = Path(self.root_store).expanduser().resolve()
        rollouts = tuple(
            sorted(
                {Path(path).expanduser().resolve() for path in self.rollout_stores},
                key=lambda path: path.as_posix(),
            )
        )
        if root in rollouts:
            raise ValueError("The VIN root store cannot also be selected as a rollout store.")
        object.__setattr__(self, "root_store", root)
        object.__setattr__(self, "rollout_stores", rollouts)


@dataclass(frozen=True, slots=True)
class DatasetBundleFinding:
    """One exact readiness or provenance finding for a selected store."""

    severity: FindingSeverity
    """Whether the finding blocks, leaves evidence incomplete, or only informs."""

    code: str
    """Stable machine-readable reason code."""

    message: str
    """Concise operator-facing explanation."""

    store_path: str | None = None
    """Affected store, or ``None`` for a bundle-level finding."""

    def to_jsonable(self) -> dict[str, Any]:
        """Return a JSON-compatible finding row."""

        return {
            "severity": self.severity,
            "code": self.code,
            "message": self.message,
            "store_path": self.store_path,
        }


@dataclass(frozen=True, slots=True)
class DatasetBundleEvidence:
    """Deterministic lightweight evidence for one selected training bundle."""

    selection: DatasetBundleSelection
    """Normalized root and rollout selection."""

    verdict: DatasetBundleVerdict
    """Strict readiness verdict derived from :attr:`findings`."""

    root: dict[str, Any]
    """VIN manifest, index, split, schema, and storage summary."""

    rollouts: tuple[dict[str, Any], ...]
    """All selected rollout summaries, including incompatible stores."""

    aggregate: dict[str, Any]
    """Totals over compatible stores only; unavailable values remain ``None``."""

    topology: dict[str, Any]
    """Compact root-to-rollout dependency nodes and classified edges."""

    coral_artifacts: tuple[dict[str, Any], ...]
    """Optional CORAL binner artifacts; missing provenance never blocks readiness."""

    findings: tuple[DatasetBundleFinding, ...]
    """Ordered evidence underlying :attr:`verdict`."""

    def to_jsonable(self) -> dict[str, Any]:
        """Return the complete download-ready evidence payload."""

        return {
            "selection": {
                "root_store": self.selection.root_store.as_posix(),
                "rollout_stores": [path.as_posix() for path in self.selection.rollout_stores],
            },
            "verdict": self.verdict,
            "root": self.root,
            "rollouts": list(self.rollouts),
            "aggregate": self.aggregate,
            "topology": self.topology,
            "coral_artifacts": list(self.coral_artifacts),
            "findings": [finding.to_jsonable() for finding in self.findings],
        }


@dataclass(frozen=True, slots=True)
class QhStageReadiness:
    """Materialized readiness facts for one learning stage."""

    stage: Stage
    """Campaign/learning split represented by this row."""

    included: bool
    """Whether the stage contains chains and is configured in the DataModule."""

    chain_count: int
    """Number of complete factual rollout chains."""

    state_count: int
    """Number of realized candidate-bearing states across the stage."""

    trainable_candidate_count: int
    """Number of candidates admitted by the persisted Q_H label mask."""

    scene_ids: tuple[str, ...]
    """Ordered scene identities admitted by the stage dataset."""

    max_horizon: int
    """Largest realized chain length in the stage."""

    provenance: dict[str, object]
    """Actor and rollout identities reported by the validated dataset."""


@dataclass(frozen=True, slots=True)
class NormalizedStorageMetric:
    """One storage total normalized by an explicit factual denominator."""

    name: str
    """Stable metric name."""

    value: float | None
    """Bytes per denominator row, or ``None`` when unavailable."""

    numerator_bytes: int | None
    """Persisted storage byte total used by the ratio."""

    denominator: int | None
    """Factual row count used by the ratio."""

    unit: str
    """Human-readable ratio unit."""

    reason: str | None
    """Why the ratio is unavailable, otherwise ``None``."""


@dataclass(frozen=True, slots=True)
class QhCorpusReadiness:
    """Actual Q_H dataset and DataModule admission evidence for one bundle."""

    selection: DatasetBundleSelection
    """Normalized VIN root and rollout-store selection."""

    verdict: Literal["Ready", "Blocked"]
    """Whether the selected stores construct one admitted DataModule."""

    blockers: tuple[str, ...]
    """Exact fail-closed construction or validation errors."""

    stages: tuple[QhStageReadiness, ...]
    """Train, validation, and test rows in stable order."""

    contract: dict[str, object] | None
    """Homogeneous horizon-independent Q_H data contract."""

    actor_contract: dict[str, object] | None
    """Exact named actor contract used to construct every stage."""

    loader_settings: dict[str, int | bool]
    """Deterministic DataLoader settings used for admission and preview."""

    scene_disjoint: bool | None
    """Whether configured stage scene sets passed pairwise disjointness checks."""

    storage: tuple[NormalizedStorageMetric, ...]
    """Persisted bytes normalized by physical and Q_H factual denominators."""

    def to_jsonable(self) -> dict[str, object]:
        """Return presentation-neutral readiness evidence."""

        return {
            "selection": {
                "root_store": self.selection.root_store.as_posix(),
                "rollout_stores": [path.as_posix() for path in self.selection.rollout_stores],
            },
            "verdict": self.verdict,
            "blockers": list(self.blockers),
            "stages": [
                {
                    "stage": row.stage.value,
                    "included": row.included,
                    "chain_count": row.chain_count,
                    "state_count": row.state_count,
                    "trainable_candidate_count": row.trainable_candidate_count,
                    "scene_ids": list(row.scene_ids),
                    "max_horizon": row.max_horizon,
                    "provenance": _plain_value(row.provenance),
                }
                for row in self.stages
            ],
            "contract": _plain_value(self.contract),
            "actor_contract": _plain_value(self.actor_contract),
            "loader_settings": _plain_value(self.loader_settings),
            "scene_disjoint": self.scene_disjoint,
            "storage": [
                {
                    "name": metric.name,
                    "value": metric.value,
                    "numerator_bytes": metric.numerator_bytes,
                    "denominator": metric.denominator,
                    "unit": metric.unit,
                    "reason": metric.reason,
                }
                for metric in self.storage
            ],
        }


@dataclass(frozen=True, slots=True)
class QhReadinessContract:
    """Named Q_H actor/data contract required by readiness inspection."""

    experiment_profile: QhExperimentProfile
    """Closed experiment role, never inferred from a diagnostic default."""

    root_evl_profile: QhRootEvlProfile
    """Root EVL profile bound to the actor store."""

    selected_observation_protocol: QhSelectedObservationProtocol
    """Selected-observation source bound to the actor contract."""


@dataclass(frozen=True, slots=True)
class QhBatchPreview:
    """Bounded evidence from one selected chain and one actual DataLoader batch."""

    stage: Stage
    """Stage whose dataset and loader were sampled."""

    selected_chain_index: int
    """Requested zero-based dataset index."""

    selected_chain_key: dict[str, object]
    """CPU-only source identity for the directly read chain."""

    selected_chain_steps: int
    """Realized state count in the directly read chain."""

    batch_chain_keys: tuple[dict[str, object], ...]
    """CPU-only identities collated by the actual DataLoader."""

    batch_step_counts: tuple[int, ...]
    """Realized chain lengths before time-axis padding."""

    shapes: dict[str, tuple[int, ...]]
    """Principal actor and supervision tensor shapes."""

    dtypes: dict[str, str]
    """Principal actor and supervision tensor dtypes."""

    step_padding_count: int
    """False entries in the batch step mask."""

    candidate_padding_count: int
    """False entries in the materialized-candidate mask."""

    action_count: int
    """Actor-valid candidate entries in the batch."""

    trainable_candidate_count: int
    """Persisted label-supported candidate entries in the batch."""

    def to_jsonable(self) -> dict[str, object]:
        """Return JSON-compatible chain and collation evidence."""

        return {
            "stage": self.stage.value,
            "selected_chain_index": self.selected_chain_index,
            "selected_chain_key": self.selected_chain_key,
            "selected_chain_steps": self.selected_chain_steps,
            "batch_chain_keys": list(self.batch_chain_keys),
            "batch_step_counts": list(self.batch_step_counts),
            "shapes": {name: list(shape) for name, shape in self.shapes.items()},
            "dtypes": self.dtypes,
            "step_padding_count": self.step_padding_count,
            "candidate_padding_count": self.candidate_padding_count,
            "action_count": self.action_count,
            "trainable_candidate_count": self.trainable_candidate_count,
        }


def build_qh_corpus_readiness(
    selection: DatasetBundleSelection,
    *,
    contract: QhReadinessContract,
    batch_size: int = 1,
    seed: int = 0,
) -> QhCorpusReadiness:
    """Construct and inspect the real stage datasets and Q_H DataModule.

    The call is intentionally explicit and potentially expensive: it validates
    selected stores, joins every admitted rollout source to the immutable VIN
    actor store, scans factual chains for realized support counts, and then
    crosses the production DataModule admission seam. It never creates a model,
    Trainer, writer, or mutable store handle.
    """

    loader_settings = {
        "batch_size": batch_size,
        "num_workers": 0,
        "pin_memory": False,
        "persistent_workers": False,
        "seed": seed,
    }
    if batch_size < 1:
        return _blocked_qh_readiness(selection, loader_settings, "Q_H batch_size must be positive.")
    light = build_dataset_bundle_summary(selection, validate_rollouts=False)
    blocking = tuple(finding.message for finding in light.findings if finding.severity == "blocking")
    if blocking:
        return _blocked_qh_readiness(selection, loader_settings, *blocking)
    if not selection.rollout_stores:
        return _blocked_qh_readiness(selection, loader_settings, "Select at least one rollout store.")

    promotion_blockers = _qh_promotion_blockers(selection)
    if promotion_blockers:
        return _blocked_qh_readiness(selection, loader_settings, *promotion_blockers)

    try:
        datasets, data_module = _build_qh_data_module(selection, contract=contract, batch_size=batch_size, seed=seed)
        stage_rows = tuple(_qh_stage_readiness(stage, datasets.get(stage)) for stage in _QH_STAGES)
    except Exception as exc:
        return _blocked_qh_readiness(selection, loader_settings, f"{type(exc).__name__}: {exc}")

    data_contract = {
        field.name: getattr(data_module.train_dataset.contract, field.name)
        for field in fields(data_module.train_dataset.contract)
    }
    storage = _normalized_qh_storage(light, stage_rows)
    return QhCorpusReadiness(
        selection=selection,
        verdict="Ready",
        blockers=(),
        stages=stage_rows,
        contract=data_contract,
        actor_contract={
            "experiment_profile": data_module.train_dataset.actor_state_contract.experiment_profile,
            "root_evl_profile": data_module.train_dataset.actor_state_contract.root_evl_profile,
            "selected_observation_protocol": data_module.train_dataset.actor_state_contract.selected_observation_protocol,
            "actor_manifest_hash": data_module.actor_state_contract_hash,
        },
        loader_settings=loader_settings,
        scene_disjoint=True,
        storage=storage,
    )


def _qh_promotion_blockers(selection: DatasetBundleSelection) -> tuple[str, ...]:
    """Return fail-closed trust errors for promoted rollout stores.

    Legacy V0 stores without promotion markers remain compatible with the
    existing Q_H contract. Once a store advertises promotion through either
    marker, however, both typed promotion evidence and canonical schema
    validation must agree before dataset construction is admitted. Root and
    rollout provenance remain validated independently by the lightweight
    bundle summary above.
    """

    blockers: list[str] = []
    for store in selection.rollout_stores:
        marker_present = (store / "_SUCCESS.json").exists() or (store / "_owner.json").exists()
        if not marker_present:
            # V0/non-promoted stores intentionally have no promotion trust
            # contract; their existing lineage/provenance checks above remain
            # the compatibility boundary.
            continue
        try:
            reader = RolloutZarrStoreReader(store)
            manifest_facts = build_manifest_facts(reader)
            promotion = build_promotion_evidence(reader, manifest_payload=manifest_facts.payload)
        except Exception as exc:
            blockers.append(f"Q_H rollout trust could not be evaluated for {store.name}: {type(exc).__name__}: {exc}")
            continue
        try:
            schema = build_schema_validation(reader)
            trust = build_effective_streamlit_trust(schema, promotion)
        except Exception as exc:
            blockers.append(f"Q_H promoted rollout validation failed for {store.name}: {type(exc).__name__}: {exc}")
            continue
        if not trust.ok:
            detail = "; ".join(trust.errors[:3]) or "unknown trust error"
            blockers.append(f"Q_H promoted rollout {store.name} is not trusted: {detail}")
    return tuple(blockers)


def preview_qh_batch(
    selection: DatasetBundleSelection,
    *,
    contract: QhReadinessContract,
    stage: Stage | str = Stage.TRAIN,
    chain_index: int = 0,
    batch_size: int = 1,
    seed: int = 0,
) -> QhBatchPreview:
    """Read one selected chain and collate one batch through the real loader."""

    normalized_stage = Stage.from_str(stage) if isinstance(stage, str) else stage
    datasets, data_module = _build_qh_data_module(selection, contract=contract, batch_size=batch_size, seed=seed)
    dataset = datasets.get(normalized_stage)
    if dataset is None:
        raise ValueError(f"Q_H stage {normalized_stage.value!r} contains no chains.")
    chain = dataset[chain_index]
    loader = {
        Stage.TRAIN: data_module.train_dataloader,
        Stage.VAL: data_module.val_dataloader,
        Stage.TEST: data_module.test_dataloader,
    }[normalized_stage]()
    if isinstance(loader, list):
        raise ValueError(f"Q_H stage {normalized_stage.value!r} is not configured.")
    batch = next(iter(loader))
    tensors = {
        "candidate_pose_relative_root": batch.actor.candidate_pose_relative_root,
        "candidate_mask": batch.actor.candidate_mask,
        "action_mask": batch.actor.action_mask,
        "horizon_remaining": batch.actor.horizon_remaining,
        "step_mask": batch.actor.step_mask,
        "label_mask": batch.supervision.label_mask,
        "candidate_reward": batch.supervision.candidate_reward,
    }
    return QhBatchPreview(
        stage=normalized_stage,
        selected_chain_index=chain_index,
        selected_chain_key=_qh_key_row(chain.key),
        selected_chain_steps=chain.num_steps,
        batch_chain_keys=tuple(_qh_key_row(key) for key in batch.keys),
        batch_step_counts=tuple(int(value) for value in batch.num_steps.tolist()),
        shapes={name: tuple(int(axis) for axis in tensor.shape) for name, tensor in tensors.items()},
        dtypes={name: str(tensor.dtype) for name, tensor in tensors.items()},
        step_padding_count=int((~batch.actor.step_mask).sum().item()),
        candidate_padding_count=int((~batch.actor.candidate_mask).sum().item()),
        action_count=int(batch.actor.action_mask.sum().item()),
        trainable_candidate_count=int(batch.supervision.label_mask.sum().item()),
    )


_QH_STAGES = (Stage.TRAIN, Stage.VAL, Stage.TEST)


def _build_qh_data_module(
    selection: DatasetBundleSelection,
    *,
    contract: QhReadinessContract,
    batch_size: int,
    seed: int,
) -> tuple[dict[Stage, Any], Any]:
    """Construct non-empty stage datasets and the production DataModule."""

    from .data_handling.qh_data import QhDatasetConfig
    from .lightning.qh_datamodule import QhDataModule

    validate_experiment_profile(
        contract.experiment_profile,
        root_evl_profile=contract.root_evl_profile,
        selected_observation_protocol=contract.selected_observation_protocol,
        privileged=contract.experiment_profile == "qh_cfplus_gt_depth_v1",
    )
    datasets: dict[Stage, Any] = {}
    actor = VinOfflineStoreConfig(store_dir=selection.root_store)
    for stage in _QH_STAGES:
        dataset = QhDatasetConfig(
            rollout_store_dirs=selection.rollout_stores,
            actor=actor,
            split=stage,
            root_evl_profile=contract.root_evl_profile,
            selected_observation_protocol=contract.selected_observation_protocol,
            experiment_profile=contract.experiment_profile,
        ).setup_target()
        if len(dataset):
            datasets[stage] = dataset
    train = datasets.get(Stage.TRAIN)
    if train is None:
        raise ValueError("Q_H training stage must contain at least one chain.")
    data_module = QhDataModule(
        train=train,
        val=datasets.get(Stage.VAL),
        test=datasets.get(Stage.TEST),
        batch_size=batch_size,
        num_workers=0,
        pin_memory=False,
        persistent_workers=False,
        seed=seed,
        experiment_profile=contract.experiment_profile,
    )
    actor_contract = data_module.train_dataset.actor_state_contract
    if (
        actor_contract.experiment_profile != contract.experiment_profile
        or actor_contract.root_evl_profile != contract.root_evl_profile
        or actor_contract.selected_observation_protocol != contract.selected_observation_protocol
    ):
        raise ValueError("Q_H actor-state contract does not match the requested named readiness contract.")
    return datasets, data_module


def _qh_stage_readiness(stage: Stage, dataset: Any | None) -> QhStageReadiness:
    """Inspect one configured dataset through its public chain interface."""

    if dataset is None:
        return QhStageReadiness(stage, False, 0, 0, 0, (), 0, {})
    state_count = 0
    trainable_candidate_count = 0
    realized_max_horizon = 0
    for index in range(len(dataset)):
        chain = dataset[index]
        state_count += chain.num_steps
        trainable_candidate_count += int(chain.supervision.label_mask.sum().item())
        realized_max_horizon = max(realized_max_horizon, chain.num_steps)
    return QhStageReadiness(
        stage=stage,
        included=True,
        chain_count=len(dataset),
        state_count=state_count,
        trainable_candidate_count=trainable_candidate_count,
        scene_ids=tuple(sorted(dataset.scenes)),
        max_horizon=realized_max_horizon,
        provenance=_plain_value(dataset.provenance),
    )


def _normalized_qh_storage(
    light: DatasetBundleEvidence,
    stages: tuple[QhStageReadiness, ...],
) -> tuple[NormalizedStorageMetric, ...]:
    """Normalize persisted storage totals by explicit factual row counts."""

    chain_count = sum(stage.chain_count for stage in stages)
    state_count = sum(stage.state_count for stage in stages)
    trainable_count = sum(stage.trainable_candidate_count for stage in stages)
    return (
        _storage_metric(
            "root_bytes_per_sample",
            light.root.get("storage_bytes"),
            light.root.get("sample_count"),
            "bytes / physical sample",
        ),
        _storage_metric(
            "rollout_bytes_per_chain",
            light.aggregate.get("rollout_storage_bytes"),
            chain_count,
            "bytes / factual Q_H chain",
        ),
        _storage_metric(
            "rollout_bytes_per_state",
            light.aggregate.get("rollout_storage_bytes"),
            state_count,
            "bytes / factual Q_H state",
        ),
        _storage_metric(
            "rollout_bytes_per_trainable_candidate",
            light.aggregate.get("rollout_storage_bytes"),
            trainable_count,
            "bytes / trainable Q_H candidate",
        ),
    )


def _storage_metric(
    name: str,
    numerator: Any,
    denominator: Any,
    unit: str,
) -> NormalizedStorageMetric:
    """Build one ratio without fabricating missing or zero denominators."""

    if not isinstance(numerator, int) or numerator < 0:
        return NormalizedStorageMetric(
            name, None, None, denominator if isinstance(denominator, int) else None, unit, "storage_bytes_unavailable"
        )
    if not isinstance(denominator, int) or denominator <= 0:
        return NormalizedStorageMetric(
            name,
            None,
            numerator,
            denominator if isinstance(denominator, int) else None,
            unit,
            "denominator_unavailable",
        )
    return NormalizedStorageMetric(name, numerator / denominator, numerator, denominator, unit, None)


def _blocked_qh_readiness(
    selection: DatasetBundleSelection,
    loader_settings: dict[str, int | bool],
    *blockers: str,
) -> QhCorpusReadiness:
    """Return a fail-closed readiness result without partial admission claims."""

    return QhCorpusReadiness(
        selection=selection,
        verdict="Blocked",
        blockers=tuple(blockers),
        stages=(),
        contract=None,
        actor_contract=None,
        loader_settings=loader_settings,
        scene_disjoint=None,
        storage=(),
    )


def _qh_key_row(key: Any) -> dict[str, object]:
    """Project one CPU-only chain key into a presentation-neutral row."""

    return {
        "store_index": int(key.store_index),
        "rollout_row_id": int(key.rollout_row_id),
        "source_sample_index": int(key.source_sample_index),
        "scene_id": str(key.scene_id),
        "target_row_id": int(key.target_row_id),
    }


def _plain_value(value: Any) -> Any:
    """Convert paths, stages, dataclasses, and containers into JSON values."""

    if isinstance(value, Stage):
        return value.value
    if isinstance(value, Path):
        return value.as_posix()
    if isinstance(value, dict):
        return {str(key): _plain_value(item) for key, item in value.items()}
    if isinstance(value, list | tuple | set | frozenset):
        return [_plain_value(item) for item in value]
    if hasattr(value, "__dataclass_fields__"):
        return {field.name: _plain_value(getattr(value, field.name)) for field in fields(value)}
    return value


def build_dataset_bundle_summary(
    selection: DatasetBundleSelection,
    *,
    coral_artifact_roots: tuple[Path, ...] = (),
    validate_rollouts: bool = False,
) -> DatasetBundleEvidence:
    """Inspect one root-plus-rollout bundle without scanning analytic arrays.

    Args:
        selection: Session-local bundle selection.
        coral_artifact_roots: Files or directories searched for fitted
            ``rri_binner*.json`` artifacts.
        validate_rollouts: Run each rollout store's full read-only validator.
            When false, selected compatible stores keep the verdict
            ``Incomplete`` until validation is explicitly requested.

    Returns:
        Download-ready bundle evidence. Incompatible rollout stores remain in
        ``rollouts`` but are excluded from ``aggregate`` training totals.
    """

    findings: list[DatasetBundleFinding] = []
    root, root_records = _root_summary(selection.root_store, findings=findings)
    root_usable = not any(
        finding.severity == "blocking" and finding.store_path == selection.root_store.as_posix() for finding in findings
    )
    root_hash = root.get("manifest_hash")
    rollout_rows = tuple(
        _rollout_summary(
            path,
            root_hash=root_hash if isinstance(root_hash, str) else None,
            root_records=root_records,
            root_usable=root_usable,
            validate=validate_rollouts,
            findings=findings,
        )
        for path in selection.rollout_stores
    )
    if not rollout_rows:
        findings.append(
            DatasetBundleFinding(
                "incomplete",
                "no_rollout_supervision_selected",
                "No rollout supervision store is selected for the Q_H training bundle.",
            )
        )

    aggregate = _aggregate_summary(root, rollout_rows)
    topology = _bundle_topology(selection.root_store, rollout_rows)
    coral = tuple(_catalog_coral_artifacts(coral_artifact_roots))
    verdict = _verdict(findings)
    return DatasetBundleEvidence(selection, verdict, root, rollout_rows, aggregate, topology, coral, tuple(findings))


def compute_dataset_bundle_deep_statistics(selection: DatasetBundleSelection) -> dict[str, Any]:
    """Scan compatible rollout arrays for distributions and unique target tasks.

    Compatibility is re-evaluated from lightweight lineage first. Blocked
    stores are reported but excluded. The scan reads candidate, step, rollout,
    source, target, and dictionary arrays only and never changes store state.

    Returns:
        JSON-compatible per-store and aggregate statistics. Root target
        opportunities remain unavailable because counting them requires a
        separate source-backed GT-OBB scan, not a rollout-array proxy.
    """

    light = build_dataset_bundle_summary(selection, validate_rollouts=False)
    root_target_inventory = inspect_target_inventory(selection.root_store)
    root_target_scan = _legacy_gt_target_opportunities(root_target_inventory)
    stores: list[dict[str, Any]] = []
    unique_targets: set[tuple[str, int, str]] = set()
    q_train_total = 0
    finite_rri_total = 0
    eligible_store_count = 0
    scanned_store_count = 0
    failed_store_count = 0
    for row in light.rollouts:
        if not bool(row["included_in_training_totals"]):
            stores.append({"path": row["path"], "included": False, "reason": "lineage_or_schema_blocked"})
            continue
        eligible_store_count += 1
        path = Path(str(row["path"]))
        try:
            reader = RolloutZarrStoreReader(path)
            q_train = _required_array(reader, "candidates/q_train_mask", np.bool_)
            target_rri = _required_array(reader, "candidates/target_rri", np.float64)
            target_root_gain = _required_array(reader, "candidates/target_root_gain", np.float64)
            valid_per_step = _required_array(reader, "steps/num_valid_candidates", np.float64)
            horizons = _required_array(reader, "rollouts/horizon", np.float64)
            store_targets = _unique_target_tasks(reader, source_hash=str(row["source_manifest_hash"]))
        except Exception as exc:
            stores.append(
                {
                    "path": path.as_posix(),
                    "included": False,
                    "error": f"{type(exc).__name__}: {exc}",
                }
            )
            failed_store_count += 1
            continue
        q_count = int(np.count_nonzero(q_train))
        finite_rri = int(np.count_nonzero(np.isfinite(target_rri)))
        q_train_total += q_count
        finite_rri_total += finite_rri
        unique_targets.update(store_targets)
        scanned_store_count += 1
        stores.append(
            {
                "path": path.as_posix(),
                "included": True,
                "q_h_trainable_candidates": q_count,
                "finite_target_rri_candidates": finite_rri,
                "unique_target_tasks": len(store_targets),
                "target_rri": _distribution(target_rri),
                "target_root_gain": _distribution(target_root_gain),
                "valid_fanout": _distribution(valid_per_step),
                "horizon": _distribution(horizons),
            }
        )
    deep_status = _deep_scan_status(
        eligible_store_count=eligible_store_count,
        scanned_store_count=scanned_store_count,
        failed_store_count=failed_store_count,
    )
    counts_available = scanned_store_count > 0
    return {
        "selection": {
            "root_store": selection.root_store.as_posix(),
            "rollout_stores": [path.as_posix() for path in selection.rollout_stores],
        },
        "stores": stores,
        "root_target_inventory": root_target_inventory.to_jsonable(),
        "root_gt_obb_target_opportunities": root_target_scan,
        "aggregate": {
            "root_gt_obb_target_opportunities": root_target_scan["target_opportunity_count"],
            "root_gt_obb_target_opportunities_status": (
                "available" if root_target_scan["available"] else str(root_target_scan["reason"])
            ),
            "deep_rollout_scan_status": deep_status,
            "eligible_rollout_store_count": eligible_store_count,
            "scanned_rollout_store_count": scanned_store_count,
            "failed_rollout_store_count": failed_store_count,
            "persisted_rollout_unique_target_tasks": len(unique_targets) if counts_available else None,
            "persisted_rollout_unique_target_tasks_status": deep_status,
            "q_h_trainable_candidates": q_train_total if counts_available else None,
            "q_h_trainable_candidates_status": deep_status,
            "finite_target_rri_candidates": finite_rri_total if counts_available else None,
            "finite_target_rri_candidates_status": deep_status,
        },
    }


def scan_root_gt_obb_target_opportunities(root_store: Path | str) -> dict[str, Any]:
    """Count materialized finite, non-padding GT-OBB rows in a VIN root store.

    This opt-in scan reads only persisted ``gt.obbs`` numeric blocks. It never
    falls back to raw ATEK snippets. Counts represent GT label/evaluation OBB
    rows available as potential target evidence, not actor-visible proposals,
    selector-admitted target tasks, or trainable rollout targets.

    Args:
        root_store: Immutable VIN offline-store directory.

    Returns:
        JSON-compatible availability, total, and per-sample/scene/split counts.
        An unavailable result includes an exact reason and no inferred count.
    """

    return _legacy_gt_target_opportunities(inspect_target_inventory(root_store))


def _legacy_gt_target_opportunities(inventory: TargetInventory) -> dict[str, Any]:
    """Project canonical target inventory into the historical GT-only shape."""

    gt = inventory.gt
    if not gt.available:
        reason = gt.reason.replace("gt.obbs", "gt_obb") if gt.reason is not None else None
        return {
            "path": inventory.path,
            "available": False,
            "reason": reason,
            "semantic_role": "gt_obb_label_evaluation_target_opportunities",
            "target_opportunity_count": None,
            "sample_count": None,
            "scene_counts": {},
            "split_counts": {},
            "per_sample": [],
        }
    return {
        "path": inventory.path,
        "available": True,
        "reason": None,
        "semantic_role": "gt_obb_label_evaluation_target_opportunities",
        "target_opportunity_count": gt.row_count,
        "sample_count": len(gt.sample_counts),
        "scene_counts": dict(gt.scene_counts),
        "split_counts": dict(gt.split_counts),
        "per_sample": [
            {
                "sample_index": sample.sample_index,
                "sample_key": sample.sample_key,
                "scene_id": sample.scene_id,
                "snippet_id": sample.snippet_id,
                "split": sample.split,
                "gt_obb_target_opportunities": sample.count,
            }
            for sample in gt.sample_rows
        ],
    }


def _root_summary(
    store: Path,
    *,
    findings: list[DatasetBundleFinding],
) -> tuple[dict[str, Any], tuple[VinOfflineIndexRecord, ...]]:
    try:
        manifest = VinOfflineManifest.read(store / "manifest.json")
        records = tuple(VinOfflineIndexRecord.read_many(store / "sample_index.jsonl"))
    except (OSError, ValueError, TypeError, msgspec.MsgspecError) as exc:
        findings.append(
            DatasetBundleFinding(
                "blocking",
                "root_store_unreadable",
                f"VIN root manifest or sample index is unreadable: {type(exc).__name__}: {exc}",
                store.as_posix(),
            )
        )
        return {
            "path": store.as_posix(),
            "manifest_hash": None,
            "schema_version": None,
            "sample_count": None,
            "scene_count": None,
            "snippet_count": None,
            "split_counts": {},
            "storage_bytes": None,
            "storage_status": "unavailable_root_manifest_unreadable",
            "root_target_opportunities": None,
            "root_target_opportunities_status": "unavailable",
        }, ()

    if manifest.version != OFFLINE_DATASET_VERSION:
        findings.append(
            DatasetBundleFinding(
                "blocking",
                "root_schema_stale",
                f"VIN root schema {manifest.version} does not match {OFFLINE_DATASET_VERSION}.",
                store.as_posix(),
            )
        )
    _validate_root_records(store, manifest, records, findings=findings)
    split_counts = dict(sorted(Counter(record.split for record in records).items()))
    storage_bytes = _persisted_storage_bytes(manifest.stats, manifest.provenance)
    return {
        "path": store.as_posix(),
        "manifest_hash": stable_msgspec_hash(manifest),
        "schema_version": manifest.version,
        "created_at": manifest.created_at,
        "sample_count": len(records),
        "scene_count": len({record.scene_id for record in records}),
        "snippet_count": len({record.snippet_id for record in records}),
        "split_counts": split_counts,
        "storage_bytes": storage_bytes,
        "storage_status": "persisted_manifest_evidence" if storage_bytes is not None else "not_persisted_in_manifest",
        "materialized_blocks": msgspec.to_builtins(manifest.materialized_blocks),
        "manifest_stats": dict(manifest.stats),
        "root_target_opportunities": None,
        "root_target_opportunities_status": "requires_source_backed_gt_obb_scan",
    }, records


def _validate_root_records(
    store: Path,
    manifest: VinOfflineManifest,
    records: tuple[VinOfflineIndexRecord, ...],
    *,
    findings: list[DatasetBundleFinding],
) -> None:
    indices = [record.sample_index for record in records]
    keys = [record.sample_key for record in records]
    if len(set(indices)) != len(indices) or len(set(keys)) != len(keys):
        findings.append(
            DatasetBundleFinding(
                "blocking",
                "root_index_not_unique",
                "VIN root sample indices and sample keys must each be unique.",
                store.as_posix(),
            )
        )
    expected_samples = manifest.stats.get("num_samples")
    if isinstance(expected_samples, int) and expected_samples != len(records):
        findings.append(
            DatasetBundleFinding(
                "blocking",
                "root_manifest_index_count_mismatch",
                f"VIN manifest reports {expected_samples} samples but index contains {len(records)}.",
                store.as_posix(),
            )
        )
    for split in sorted({record.split for record in records}):
        split_path = store / "splits" / f"{split}.npy"
        try:
            persisted = np.asarray(np.load(split_path, allow_pickle=False), dtype=np.int64).reshape(-1)
        except (OSError, ValueError) as exc:
            findings.append(
                DatasetBundleFinding(
                    "blocking",
                    "root_split_unreadable",
                    f"VIN split {split!r} is unreadable: {type(exc).__name__}: {exc}",
                    store.as_posix(),
                )
            )
            continue
        expected = np.asarray([record.sample_index for record in records if record.split == split], dtype=np.int64)
        if not np.array_equal(np.sort(persisted), np.sort(expected)):
            findings.append(
                DatasetBundleFinding(
                    "blocking",
                    "root_split_membership_mismatch",
                    f"VIN split {split!r} does not match sample-index membership.",
                    store.as_posix(),
                )
            )


def _rollout_summary(
    store: Path,
    *,
    root_hash: str | None,
    root_records: tuple[VinOfflineIndexRecord, ...],
    root_usable: bool,
    validate: bool,
    findings: list[DatasetBundleFinding],
) -> dict[str, Any]:
    blockers_before = sum(
        finding.severity == "blocking" and finding.store_path == store.as_posix() for finding in findings
    )
    try:
        manifest = read_rollout_store_manifest(store)
    except Exception as exc:
        findings.append(
            DatasetBundleFinding(
                "blocking",
                "rollout_store_unreadable",
                f"Rollout manifest is unreadable: {type(exc).__name__}: {exc}",
                store.as_posix(),
            )
        )
        return _unreadable_rollout_row(store)

    schema = manifest.get("schema_version")
    if schema != ROLLOUT_ZARR_SCHEMA_VERSION:
        findings.append(
            DatasetBundleFinding(
                "blocking",
                "rollout_schema_stale",
                f"Rollout schema {schema!r} does not match {ROLLOUT_ZARR_SCHEMA_VERSION!r}.",
                store.as_posix(),
            )
        )
    config_hashes = manifest.get("config_hashes") if isinstance(manifest.get("config_hashes"), dict) else {}
    source_hashes = _string_values(config_hashes.get("source_manifest"))
    source_hash = source_hashes[0] if len(source_hashes) == 1 else None
    if root_hash is None or source_hash != root_hash:
        findings.append(
            DatasetBundleFinding(
                "blocking",
                "source_manifest_hash_mismatch",
                "Rollout lineage does not resolve uniquely to the selected VIN manifest hash.",
                store.as_posix(),
            )
        )
    coverage = manifest.get("source_coverage") if isinstance(manifest.get("source_coverage"), dict) else {}
    source_rows = coverage.get("sources") if isinstance(coverage, dict) else None
    source_rows = source_rows if isinstance(source_rows, list) else []
    if not source_rows:
        findings.append(
            DatasetBundleFinding(
                "blocking",
                "source_rows_missing",
                "Rollout manifest does not expose persisted source-row identities.",
                store.as_posix(),
            )
        )
    elif not _source_rows_match_root(source_rows, root_records):
        findings.append(
            DatasetBundleFinding(
                "blocking",
                "source_split_identity_mismatch",
                "At least one rollout source row does not uniquely match its VIN sample index, key, and split identity.",
                store.as_posix(),
            )
        )

    validation_status = "not_run"
    if validate:
        try:
            result = RolloutZarrStoreReader(store).validate()
        except Exception as exc:
            findings.append(
                DatasetBundleFinding(
                    "blocking",
                    "rollout_validation_failed",
                    f"Rollout validation raised {type(exc).__name__}: {exc}",
                    store.as_posix(),
                )
            )
            validation_status = "failed"
        else:
            validation_status = "ok" if result.ok else "failed"
            if not result.ok:
                findings.append(
                    DatasetBundleFinding(
                        "blocking",
                        "rollout_validation_failed",
                        "; ".join(str(error) for error in result.errors[:3]),
                        store.as_posix(),
                    )
                )
    else:
        findings.append(
            DatasetBundleFinding(
                "incomplete",
                "rollout_validation_not_run",
                "Full read-only rollout validation has not been run.",
                store.as_posix(),
            )
        )

    counts = manifest.get("counts") if isinstance(manifest.get("counts"), dict) else {}
    root_attrs = manifest.get("root_attrs") if isinstance(manifest.get("root_attrs"), dict) else {}
    generation = manifest.get("generation") if isinstance(manifest.get("generation"), dict) else {}
    writer_config = generation.get("writer_config") if isinstance(generation.get("writer_config"), dict) else {}
    invocation = generation.get("invocation") if isinstance(generation.get("invocation"), dict) else {}
    recipes = writer_config.get("recipes") if isinstance(writer_config.get("recipes"), list) else []
    blockers_after = sum(
        finding.severity == "blocking" and finding.store_path == store.as_posix() for finding in findings
    )
    included = root_usable and blockers_after == blockers_before
    storage_bytes = _persisted_storage_bytes(manifest, root_attrs, generation)
    return {
        "path": store.as_posix(),
        "schema_version": schema,
        "manifest_version": manifest.get("manifest_version"),
        "profile": writer_config.get("profile")
        or writer_config.get("recipe_profile")
        or writer_config.get("name")
        or _config_stem(invocation.get("config_path")),
        "policies": sorted(
            {
                str(recipe["selection_policy"])
                for recipe in recipes
                if isinstance(recipe, dict) and recipe.get("selection_policy") not in (None, "")
            }
        ),
        "horizons": sorted(
            {
                int(recipe["horizon"])
                for recipe in recipes
                if isinstance(recipe, dict) and isinstance(recipe.get("horizon"), int)
            }
        ),
        "source_manifest_hash": source_hash,
        "split_manifest_hashes": _string_values(config_hashes.get("split_manifest")),
        "source_splits": dict(coverage.get("split_counts", {})) if isinstance(coverage, dict) else {},
        "source_sample_count": len(source_rows),
        "source_sample_identities": [
            [source_hash, int(row["source_sample_index"])]
            for row in source_rows
            if isinstance(row, dict) and isinstance(row.get("source_sample_index"), int)
        ],
        "counts": {str(key): int(value) for key, value in counts.items() if isinstance(value, int)},
        "horizon": root_attrs.get("q_h_horizon"),
        "storage_bytes": storage_bytes,
        "storage_status": "persisted_manifest_evidence" if storage_bytes is not None else "not_persisted_in_manifest",
        "validation_status": validation_status,
        "included_in_training_totals": included,
    }


def _source_rows_match_root(rows: list[Any], records: tuple[VinOfflineIndexRecord, ...]) -> bool:
    by_index: dict[int, list[VinOfflineIndexRecord]] = {}
    by_key: dict[str, list[VinOfflineIndexRecord]] = {}
    for record in records:
        by_index.setdefault(record.sample_index, []).append(record)
        by_key.setdefault(_canonical_key(record.sample_key), []).append(record)
    for row in rows:
        if not isinstance(row, dict):
            return False
        sample_index = row.get("source_sample_index")
        sample_key = _canonical_key(row.get("source_sample_key"))
        if not isinstance(sample_index, int) or not sample_key:
            return False
        matches = by_index.get(int(sample_index), [])
        key_matches = by_key.get(sample_key, [])
        matches = [record for record in matches if record in key_matches]
        matches = [record for record in matches if _source_identity_matches(row, record)]
        if len(matches) != 1:
            return False
    return True


def _source_identity_matches(row: dict[str, Any], record: VinOfflineIndexRecord) -> bool:
    snippet = row.get("snippet_id")
    if snippet is not None and _canonical_key(snippet) != _canonical_key(record.snippet_id):
        return False
    comparisons = (
        (row.get("scene_id"), record.scene_id),
        (row.get("split"), record.split),
        (row.get("source_shard_id"), record.shard_id),
        (row.get("source_shard_row"), record.row),
    )
    return all(expected is None or str(expected) == str(actual) for expected, actual in comparisons)


def _canonical_key(value: Any) -> str:
    if value in (None, ""):
        return ""
    return compact_ase_atek_sample_id(str(value)).rsplit("::", maxsplit=1)[-1]


def _aggregate_summary(root: dict[str, Any], rollouts: tuple[dict[str, Any], ...]) -> dict[str, Any]:
    included = [row for row in rollouts if bool(row.get("included_in_training_totals"))]
    counts = Counter()
    source_identities: set[tuple[str, int]] = set()
    for row in included:
        counts.update(row.get("counts", {}))
        source_identities.update(
            (str(identity[0]), int(identity[1]))
            for identity in row.get("source_sample_identities", [])
            if isinstance(identity, list | tuple) and len(identity) == 2
        )
    rollout_storage = _complete_storage_total(included)
    combined_storage = _complete_storage_total([root, *included])
    return {
        "root_sample_count": root.get("sample_count"),
        "root_scene_count": root.get("scene_count"),
        "root_snippet_count": root.get("snippet_count"),
        "root_split_counts": root.get("split_counts", {}),
        "compatible_rollout_store_count": len(included),
        "selected_rollout_store_count": len(rollouts),
        "rollout_count": int(counts.get("rollouts", 0)),
        "step_count": int(counts.get("steps", 0)),
        "candidate_count": int(counts.get("candidates", 0)),
        "deduplicated_source_sample_count": len(source_identities),
        "root_target_opportunities": root.get("root_target_opportunities"),
        "persisted_rollout_target_rows": int(counts.get("targets", 0)),
        "persisted_rollout_targets": None,
        "persisted_rollout_targets_status": "requires_deep_target_identity_scan",
        "q_h_trainable_candidates": None,
        "q_h_trainable_candidates_status": "requires_deep_candidate_scan",
        "rollout_storage_bytes": rollout_storage,
        "rollout_storage_status": "persisted_manifest_evidence"
        if rollout_storage is not None
        else "not_persisted_for_every_included_rollout",
        "storage_bytes": combined_storage,
        "storage_status": "persisted_manifest_evidence"
        if combined_storage is not None
        else "not_persisted_for_complete_bundle",
    }


def _bundle_topology(root: Path, rollouts: tuple[dict[str, Any], ...]) -> dict[str, Any]:
    root_id = f"vin:{root.as_posix()}"
    nodes = [{"node_id": root_id, "label": root.name, "kind": "VIN root store"}]
    edges: list[dict[str, Any]] = []
    for row in rollouts:
        path = Path(str(row["path"]))
        node_id = f"rollout:{path.as_posix()}"
        nodes.append({"node_id": node_id, "label": path.name, "kind": "rollout supervision store"})
        edges.append(
            {
                "source": root_id,
                "target": node_id,
                "relation": "provides root observations for",
                "resolution": "resolved pointer" if row.get("included_in_training_totals") else "blocked",
                "evidence": row.get("source_manifest_hash"),
            }
        )
    return {"nodes": nodes, "edges": edges}


def _catalog_coral_artifacts(roots: tuple[Path, ...]) -> list[dict[str, Any]]:
    paths: set[Path] = set()
    for raw_root in roots:
        root = Path(raw_root).expanduser().resolve()
        if root.is_file():
            paths.add(root)
        elif root.exists():
            paths.update(root.rglob("rri_binner*.json"))
    rows: list[dict[str, Any]] = []
    for path in sorted(paths, key=lambda item: item.as_posix()):
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError, TypeError):
            continue
        if not isinstance(payload, dict) or not isinstance(payload.get("num_classes"), int):
            continue
        fit_path = _fit_data_path(path)
        provenance = payload.get("provenance")
        rows.append(
            {
                "path": path.as_posix(),
                "num_classes": int(payload["num_classes"]),
                "edge_count": len(payload.get("edges", [])) if isinstance(payload.get("edges"), list) else None,
                "class_counts": payload.get("bin_counts"),
                "fit_data_path": fit_path.as_posix() if fit_path is not None else None,
                "fit_data_available": fit_path is not None,
                "provenance": provenance if isinstance(provenance, dict | str) else "unavailable",
                "config_references": payload.get("config_references", [])
                if isinstance(payload.get("config_references", []), list)
                else [],
                "size_bytes": path.stat().st_size,
                "mtime_unix": path.stat().st_mtime,
            }
        )
    return rows


def _fit_data_path(path: Path) -> Path | None:
    candidates = (
        path.with_name(f"{path.stem}_fit_data.pt"),
        path.with_name(f"{path.stem}.fit_data.pt"),
        path.with_name(f"{path.stem}-fit-data.pt"),
    )
    return next((candidate for candidate in candidates if candidate.is_file()), None)


def _unique_target_tasks(reader: RolloutZarrStoreReader, *, source_hash: str) -> set[tuple[str, int, str]]:
    rollout_sources = _required_array(reader, "rollouts/source_row_id", np.int64)
    rollout_targets = _required_array(reader, "rollouts/target_row_id", np.int64)
    source_row_ids = _required_array(reader, "sources/source_row_id", np.int64)
    source_sample_indices = _required_array(reader, "sources/sample_index", np.int64)
    target_row_ids = _required_array(reader, "targets/target_row_id", np.int64)
    target_ids = _decoded_dictionary_values(reader, "targets/target_id", "target")
    source_by_id = dict(zip(source_row_ids.tolist(), source_sample_indices.tolist(), strict=True))
    target_by_id = dict(zip(target_row_ids.tolist(), target_ids, strict=True))
    return {
        (source_hash, int(source_by_id[int(source_row)]), str(target_by_id[int(target_row)]))
        for source_row, target_row in zip(rollout_sources.tolist(), rollout_targets.tolist(), strict=True)
    }


def _decoded_dictionary_values(reader: RolloutZarrStoreReader, array_path: str, dictionary: str) -> list[str]:
    ids = _required_array(reader, array_path, np.int64)
    raw = np.asarray(reader.array(f"dictionaries/{dictionary}"), dtype=np.uint8).tobytes()
    values = json.loads(raw.decode("utf-8"))
    return [str(values[int(index)]) if 0 <= int(index) < len(values) else "" for index in ids.tolist()]


def _required_array(reader: RolloutZarrStoreReader, path: str, dtype: Any) -> np.ndarray:
    return np.asarray(reader.array(path), dtype=dtype).reshape(-1)


def _distribution(values: np.ndarray) -> dict[str, float | int | None]:
    finite = np.asarray(values, dtype=np.float64).reshape(-1)
    finite = finite[np.isfinite(finite)]
    if finite.size == 0:
        return {"count": 0, "minimum": None, "median": None, "mean": None, "maximum": None}
    return {
        "count": int(finite.size),
        "minimum": float(np.min(finite)),
        "median": float(np.median(finite)),
        "mean": float(np.mean(finite)),
        "maximum": float(np.max(finite)),
    }


def _persisted_storage_bytes(*payloads: Any) -> int | None:
    """Return an exact byte total only when persisted metadata provides one."""

    for payload in payloads:
        if not isinstance(payload, dict):
            continue
        for key in ("storage_bytes", "total_bytes", "size_bytes"):
            value = payload.get(key)
            if isinstance(value, int) and value >= 0:
                return value
        storage = payload.get("storage")
        if isinstance(storage, dict):
            value = storage.get("total_bytes")
            if isinstance(value, int) and value >= 0:
                return value
    return None


def _complete_storage_total(rows: list[dict[str, Any]]) -> int | None:
    """Sum storage evidence only when every contributing row is known."""

    values = [row.get("storage_bytes") for row in rows]
    if any(not isinstance(value, int) or value < 0 for value in values):
        return None
    return sum(values)


def _deep_scan_status(
    *,
    eligible_store_count: int,
    scanned_store_count: int,
    failed_store_count: int,
) -> Literal["available", "partial", "unavailable"]:
    """Classify whether aggregate rollout-array denominators are complete."""

    if eligible_store_count == 0 or scanned_store_count == 0:
        return "unavailable"
    if failed_store_count:
        return "partial"
    return "available"


def _string_values(value: Any) -> list[str]:
    if isinstance(value, list | tuple | set):
        return [str(item) for item in value]
    if value in (None, ""):
        return []
    return [str(value)]


def _config_stem(value: Any) -> str | None:
    if value in (None, ""):
        return None
    return Path(str(value)).stem


def _unreadable_rollout_row(store: Path) -> dict[str, Any]:
    return {
        "path": store.as_posix(),
        "schema_version": None,
        "manifest_version": None,
        "profile": None,
        "policies": [],
        "horizons": [],
        "source_manifest_hash": None,
        "split_manifest_hashes": [],
        "source_splits": {},
        "source_sample_count": 0,
        "source_sample_identities": [],
        "counts": {},
        "horizon": None,
        "storage_bytes": None,
        "storage_status": "unavailable_rollout_manifest_unreadable",
        "validation_status": "failed",
        "included_in_training_totals": False,
    }


def _verdict(findings: list[DatasetBundleFinding]) -> DatasetBundleVerdict:
    if any(finding.severity == "blocking" for finding in findings):
        return "Blocked"
    if any(finding.severity == "incomplete" for finding in findings):
        return "Incomplete"
    return "Ready"


__all__ = [
    "DatasetBundleEvidence",
    "DatasetBundleFinding",
    "DatasetBundleSelection",
    "DatasetBundleVerdict",
    "NormalizedStorageMetric",
    "QhBatchPreview",
    "QhCorpusReadiness",
    "QhReadinessContract",
    "QhStageReadiness",
    "build_dataset_bundle_summary",
    "build_qh_corpus_readiness",
    "compute_dataset_bundle_deep_statistics",
    "preview_qh_batch",
    "scan_root_gt_obb_target_opportunities",
]
