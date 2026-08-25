"""Immutable training and inference composition for finite-horizon Q_H."""

from __future__ import annotations

import hashlib
import importlib.metadata
import json
import math
import shutil
import sys
import uuid
from dataclasses import asdict, dataclass, is_dataclass
from enum import Enum
from pathlib import Path
from typing import Any, Literal

import pytorch_lightning as pl
import torch
from pydantic import Field

from ..data_handling.qh_data import QhDatasetConfig
from ..data_handling.qh_data.views import QhActorStateContract
from ..rollouts.inspection import oracle_headroom_evidence
from ..rollouts.qh_reader import QhDataContract
from ..rollouts.zarr_store import RolloutZarrStoreReader
from ..utils import BaseConfig, TargetConfig
from ..utils.fingerprints import stable_config_hash, stable_msgspec_hash
from ..vin.models.target_finite_horizon import (
    TargetFiniteHorizonScorer,
    TargetFiniteHorizonScorerConfig,
)
from ..vin.qh_bundle import QH_INFERENCE_BUNDLE_SCHEMA_VERSION, QhInferenceBundleRef, QhInferenceRuntime
from .lit_trainer_callbacks import TrainerCallbacksConfig
from .lit_trainer_factory import TrainerFactoryConfig
from .qh_datamodule import QhDataModule, QhLearningContract
from .qh_module import QhLightningModule, QhLightningModuleConfig
from .qh_q2_certification import (
    QhDecoderSupport,
    QhExactQ2CertificationSpec,
    QhExactQ2Certifier,
)

_MANIFEST_FILENAME = "manifest.json"
_SCORER_STATE_FILENAME = "scorer-state.pt"
_TRAINING_RECEIPT_FILENAME = "training-receipt.json"
_SELECTION_RECEIPT_FILENAME = "checkpoint-selection-receipt.json"
_IDENTITY_FIELDS = {
    "actor_state_contract",
    "actor_state_contract_hash",
    "learning_contract",
    "learning_contract_hash",
    "geometry_contract_hash",
    "datasets",
    "dataset_provenance",
    "ordered_store_manifests",
    "ordered_store_paths",
    "warm_start_parent_manifest_sha256",
    "action_mask_semantics",
    "representation_semantics",
    "seed",
}


@dataclass(frozen=True, slots=True)
class QhCheckpointSelectionSpec:
    """Closed V1 validation-checkpoint selection rule."""

    monitor: Literal["val/loss"] = "val/loss"
    """Existing admitted-row-weighted Q_H validation metric."""

    mode: Literal["min"] = "min"
    """Validation loss is minimized."""

    tie_break: Literal["earliest_optimizer_update"] = "earliest_optimizer_update"
    """An exact metric tie retains the earlier optimizer update."""

    def __post_init__(self) -> None:
        if (self.monitor, self.mode, self.tie_break) != (
            "val/loss",
            "min",
            "earliest_optimizer_update",
        ):
            raise ValueError("Q_H V1 checkpoint selection is fixed to val/loss minimization with earliest-update ties.")


@dataclass(frozen=True, slots=True)
class QhFitRequest:
    """Immutable inputs and output authority for one bounded fitted-Q run."""

    train: QhDatasetConfig
    """Training dataset over one ordered tuple of immutable rollout stores."""

    validation: QhDatasetConfig
    """Scene-disjoint validation dataset used only for checkpoint selection."""

    test: QhDatasetConfig
    """Untouched scene-disjoint held-out dataset used after fitting."""

    warm_start_from: QhInferenceBundleRef | None
    """Verified prior bundle providing scorer weights only; optimizer state is never restored."""

    checkpoint_selection: QhCheckpointSelectionSpec
    """Closed validation monitor, direction, and tie-break identity."""

    seed: int
    """Global Lightning and DataLoader seed recorded in the bundle."""

    output_bundle_dir: Path
    """New immutable destination; any existing filesystem entry is rejected."""


@dataclass(frozen=True, slots=True)
class QhFitResult:
    """Immutable bundle and receipt references emitted by one fit."""

    bundle: QhInferenceBundleRef
    """Verified reference to the published inference bundle."""

    training_receipt_path: Path
    """JSON receipt for trainer inputs, warm-start lineage, and optimizer updates."""

    training_receipt_sha256: str
    """Content digest of :attr:`training_receipt_path`."""

    checkpoint_selection_receipt_path: Path
    """JSON receipt for the selected validation checkpoint."""

    checkpoint_selection_receipt_sha256: str
    """Content digest of :attr:`checkpoint_selection_receipt_path`."""


@dataclass(frozen=True, slots=True)
class QhHeldOutEvaluationRequest:
    """Immutable request for one explicit diagnostic held-out evaluation."""

    bundle: QhInferenceBundleRef
    """Verified bundle whose scorer and frozen test identity are evaluated."""

    test: QhDatasetConfig
    """Exact test population configuration bound to the bundle manifest."""

    output_receipt_path: Path
    """New receipt destination; an existing path is rejected."""


@dataclass(frozen=True, slots=True)
class QhHeldOutEvaluationResult:
    """Immutable result of an explicit diagnostic held-out evaluation."""

    receipt_path: Path
    """Receipt containing diagnostic fitted-Q aggregates."""

    receipt_sha256: str
    """Digest of :attr:`receipt_path`."""


@dataclass(frozen=True, slots=True)
class QhExactQ2CertificationRequest:
    """Immutable request for bounded held-out learned-recursion evidence.

    Args:
        bundle: Verified scorer bundle whose frozen weights are evaluated.
        test: Exact held-out dataset configuration already bound by the bundle
            manifest; a different population is rejected.
        spec: Numeric tolerances and deterministic stratified selection bounds.
        output_receipt_path: New JSON destination; existing paths are rejected.
        device: Torch device used for scorer evaluation. Dataset census and
            materialization remain CPU-owned until each selected batch moves.
        headroom_store_dir: Optional validated rollout store from which the
            existing exact-role oracle-headroom diagnostic is summarized. This
            diagnostic is a persisted terminal-step proxy, not independent
            endpoint evaluation, and can never satisfy the longer-horizon gate.
    """

    bundle: QhInferenceBundleRef
    test: QhDatasetConfig
    spec: QhExactQ2CertificationSpec
    output_receipt_path: Path
    device: str = "cpu"
    headroom_store_dir: Path | None = None


@dataclass(frozen=True, slots=True)
class QhExactQ2CertificationResult:
    """Immutable reference to one exact-``Q_2`` certification receipt."""

    receipt_path: Path
    """JSON receipt containing bound census, row, and gate evidence."""

    receipt_sha256: str
    """Digest of :attr:`receipt_path`."""


def _default_qh_trainer() -> TrainerFactoryConfig:
    return TrainerFactoryConfig(
        use_wandb=False,
        enable_validation=True,
        callbacks=TrainerCallbacksConfig(
            checkpoint_monitor="val/loss",
            checkpoint_mode="min",
            checkpoint_filename="epoch={epoch}-step={step}-val-loss={val/loss:.6f}",
            checkpoint_save_top_k=1,
            checkpoint_save_last=False,
            use_lr_monitor=False,
            use_tqdm_progress_bar=False,
            use_rich_model_summary=False,
        ),
    )


class QhExperimentConfig(TargetConfig["QhExperiment"]):
    """Compose the scorer, optimizer module, data loaders, and trainer."""

    scorer: TargetFiniteHorizonScorerConfig = Field(default_factory=TargetFiniteHorizonScorerConfig)
    """Closed production scorer configuration persisted in every bundle."""

    module: QhLightningModuleConfig
    """Optimizer and Double-Q policy; contract hashes are rebound from admitted data during fit."""

    trainer: TrainerFactoryConfig = Field(default_factory=_default_qh_trainer)
    """Bounded Lightning execution policy with V1 validation checkpointing."""

    batch_size: int = Field(default=1, gt=0)
    """Number of complete rollout chains per batch."""

    num_workers: int = Field(default=0, ge=0)
    """DataLoader worker process count."""

    pin_memory: bool = False
    """Pin collated CPU tensors before accelerator transfer."""

    persistent_workers: bool = False
    """Reuse workers between epochs when ``num_workers`` is positive."""

    objective_profile: Literal["qh_dense_valid_fitted_q_v1"] = "qh_dense_valid_fitted_q_v1"
    """Deployable fitted-Q support contract."""

    @property
    def target_type(self) -> type["QhExperiment"]:
        """Return the concrete experiment constructed by :meth:`setup_target`."""

        return QhExperiment


class QhExperiment:
    """Fit, publish, verify, and reconstruct immutable Q_H bundles."""

    def __init__(self, config: QhExperimentConfig) -> None:
        self.config = config

    def fit(self, request: QhFitRequest) -> QhFitResult:
        """Train from immutable stages and atomically publish one new bundle."""

        output = request.output_bundle_dir.expanduser().resolve()
        if output.exists():
            raise FileExistsError(f"Q_H output bundle directory already exists: {output}.")
        output.parent.mkdir(parents=True, exist_ok=True)
        temporary = output.parent / f".{output.name}.tmp-{uuid.uuid4().hex}"
        temporary.mkdir()
        try:
            pl.seed_everything(int(request.seed), workers=True)
            train = request.train.setup_target()
            validation = request.validation.setup_target()
            test = request.test.setup_target()
            data = QhDataModule(
                train=train,
                val=validation,
                test=test,
                batch_size=int(self.config.batch_size),
                num_workers=int(self.config.num_workers),
                pin_memory=bool(self.config.pin_memory),
                persistent_workers=bool(self.config.persistent_workers),
                seed=int(request.seed),
                experiment_profile=self.config.scorer.experiment_profile,
                objective_profile=self.config.objective_profile,
            )
            if data.learning_contract.max_horizon > self.config.scorer.max_horizon:
                raise ValueError(
                    "Q_H scorer max_horizon is smaller than the admitted dataset horizon: "
                    f"{self.config.scorer.max_horizon} < {data.learning_contract.max_horizon}."
                )

            module_config = self.config.module.model_copy(
                deep=True,
                update={
                    "root_evl_profile": train.actor_state_contract.root_evl_profile,
                    "selected_observation_protocol": train.actor_state_contract.selected_observation_protocol,
                    "experiment_profile": self.config.scorer.experiment_profile,
                    "action_mask_semantics": data.learning_contract.data_contract.action_mask_semantics,
                    "actor_state_contract_hash": data.actor_state_contract_hash,
                    "learning_contract_hash": data.learning_contract_hash,
                    "geometry_contract_hash": data.geometry_contract_hash,
                },
            )
            scorer = self.config.scorer.setup_target()
            module = QhLightningModule(module_config, scorer=scorer)
            warm_start_parent = self._warm_start_weights(
                request.warm_start_from,
                scorer=module.online_scorer,
                scorer_config=self.config.scorer,
                module_config=module_config,
                actor_state_contract_hash=data.actor_state_contract_hash,
                learning_contract_hash=data.learning_contract_hash,
                target_protocol=data.learning_contract.data_contract.target_protocol,
                action_mask_semantics=data.learning_contract.data_contract.action_mask_semantics,
                geometry_contract_hash=data.geometry_contract_hash,
            )
            if warm_start_parent is not None:
                module.target_scorer.load_state_dict(module.online_scorer.state_dict(), strict=True)
                module._freeze_target()  # noqa: SLF001 - warm starts intentionally reset target state
            trainer_config = self._trainer_config(temporary, request.checkpoint_selection)
            trainer = trainer_config.setup_target()
            trainer.fit(module, datamodule=data)
            selected_checkpoint, selected_validation_loss, selected_optimizer_updates = self._selected_checkpoint(
                temporary
            )
            selected_payload = torch.load(selected_checkpoint, map_location="cpu", weights_only=False)
            selected_state = selected_payload.get("state_dict")
            if not isinstance(selected_state, dict):
                raise ValueError("Selected Q_H Lightning checkpoint has no state_dict.")
            module.load_state_dict(selected_state, strict=True)
            if int(module.optimizer_updates.item()) != selected_optimizer_updates:
                raise ValueError("Selected Q_H checkpoint optimizer-update identity is inconsistent.")
            selection_receipt = {
                "schema_version": "qh-checkpoint-selection-receipt-v1",
                "selection": asdict(request.checkpoint_selection),
                "selected_checkpoint_sha256": _sha256_file(selected_checkpoint),
                "validation_loss_sum": float(torch.as_tensor(selected_state["validation_loss_sum"]).item()),
                "validation_row_count": int(torch.as_tensor(selected_state["validation_row_count"]).item()),
                "selected_validation_loss": selected_validation_loss,
                "optimizer_updates": selected_optimizer_updates,
            }
            selection_path = temporary / _SELECTION_RECEIPT_FILENAME
            _write_json(selection_path, selection_receipt)

            training_receipt = {
                "schema_version": "qh-training-receipt-v1",
                "seed": int(request.seed),
                "warm_start_parent_manifest_sha256": (
                    None if warm_start_parent is None else warm_start_parent.manifest_sha256
                ),
                "optimizer_updates": int(module.optimizer_updates.item()),
                "train_provenance": _jsonable(train.provenance),
                "validation_provenance": _jsonable(validation.provenance),
                "test_provenance": _jsonable(test.provenance),
                "learning_contract_hash": data.learning_contract_hash,
                "actor_state_contract_hash": data.actor_state_contract_hash,
            }
            training_path = temporary / _TRAINING_RECEIPT_FILENAME
            _write_json(training_path, training_receipt)

            manifest = self._publish_bundle(
                temporary,
                module.online_scorer,
                module_config=module_config,
                identity={
                    "actor_state_contract": train.actor_state_contract,
                    "actor_state_contract_hash": data.actor_state_contract_hash,
                    "learning_contract": data.learning_contract,
                    "learning_contract_hash": data.learning_contract_hash,
                    "geometry_contract_hash": data.geometry_contract_hash,
                    "datasets": {
                        "train": request.train,
                        "validation": request.validation,
                        "test": request.test,
                    },
                    "dataset_provenance": {
                        "train": train.provenance,
                        "validation": validation.provenance,
                        "test": test.provenance,
                    },
                    "ordered_store_manifests": {
                        "train": _ordered_store_manifest_hashes(train.provenance),
                        "validation": _ordered_store_manifest_hashes(validation.provenance),
                        "test": _ordered_store_manifest_hashes(test.provenance),
                    },
                    "ordered_store_paths": {
                        "train": request.train.rollout_store_dirs,
                        "validation": request.validation.rollout_store_dirs,
                        "test": request.test.rollout_store_dirs,
                    },
                    "warm_start_parent_manifest_sha256": (
                        None if warm_start_parent is None else warm_start_parent.manifest_sha256
                    ),
                    "action_mask_semantics": str(
                        getattr(data.learning_contract.data_contract, "action_mask_semantics", "oracle_action_mask_v1")
                    ),
                    "representation_semantics": str(
                        getattr(self.config.scorer, "representation_semantics", "root_moments_v1")
                    ),
                    "seed": int(request.seed),
                },
                artifact_hashes={
                    _TRAINING_RECEIPT_FILENAME: _sha256_file(training_path),
                    _SELECTION_RECEIPT_FILENAME: _sha256_file(selection_path),
                },
            )
            temporary.replace(output)
        except BaseException:
            shutil.rmtree(temporary, ignore_errors=True)
            raise

        bundle = QhInferenceBundleRef(
            bundle_path=output,
            schema_version=QH_INFERENCE_BUNDLE_SCHEMA_VERSION,
            manifest_sha256=str(manifest["manifest_sha256"]),
        )
        return QhFitResult(
            bundle=bundle,
            training_receipt_path=output / _TRAINING_RECEIPT_FILENAME,
            training_receipt_sha256=_sha256_file(output / _TRAINING_RECEIPT_FILENAME),
            checkpoint_selection_receipt_path=output / _SELECTION_RECEIPT_FILENAME,
            checkpoint_selection_receipt_sha256=_sha256_file(output / _SELECTION_RECEIPT_FILENAME),
        )

    def evaluate_held_out(self, request: QhHeldOutEvaluationRequest) -> QhHeldOutEvaluationResult:
        """Run explicit diagnostic fitted-Q evaluation on a bundle's frozen test population.

        This operation is intentionally separate from :meth:`fit` and does not
        provide endpoint-policy evidence; endpoint evaluation remains owned by
        the online oracle contract.
        """

        output = request.output_receipt_path.expanduser().resolve()
        if output.exists():
            raise FileExistsError(f"Q_H held-out diagnostic receipt already exists: {output}.")
        manifest = self._read_verified_manifest(request.bundle)
        expected_test = manifest["identity"]["datasets"]["test"]
        actual_test = _jsonable(request.test)
        if expected_test != actual_test:
            raise ValueError("Q_H held-out diagnostic population does not match the frozen bundle test identity.")
        test = request.test.setup_target()
        runtime = self.load_for_inference(request.bundle, device="cpu")
        module_config = QhLightningModuleConfig.model_validate(manifest["module_config"])
        module = QhLightningModule(module_config, scorer=runtime.scorer)
        module.target_scorer.load_state_dict(module.online_scorer.state_dict(), strict=True)
        data = QhDataModule(
            train=test,
            batch_size=int(self.config.batch_size),
            num_workers=int(self.config.num_workers),
            pin_memory=bool(self.config.pin_memory),
            persistent_workers=bool(self.config.persistent_workers),
            seed=int(manifest["identity"]["seed"]),
            experiment_profile=module_config.experiment_profile,
            objective_profile=self.config.objective_profile,
        )
        data.test_dataset = test
        trainer_config = self.config.trainer.model_copy(
            deep=True,
            update={
                "enable_validation": False,
                "use_wandb": False,
                "callbacks": TrainerCallbacksConfig(
                    use_model_checkpoint=False,
                    use_lr_monitor=False,
                    use_tqdm_progress_bar=False,
                    use_rich_model_summary=False,
                ),
            },
        )
        trainer_config.setup_target().test(module, datamodule=data)
        receipt = {
            "schema_version": "qh-held-out-diagnostic-receipt-v1",
            "diagnostic_only": True,
            "endpoint_policy_evidence": False,
            "bundle_manifest_sha256": request.bundle.manifest_sha256,
            "test_population_sha256": _json_payload_hash(request.test),
            "test_loss_sum": float(module.test_loss_sum.item()),
            "test_row_count": int(module.test_row_count.item()),
        }
        output.parent.mkdir(parents=True, exist_ok=True)
        _write_json(output, receipt)
        return QhHeldOutEvaluationResult(output, _sha256_file(output))

    def certify_exact_q2(self, request: QhExactQ2CertificationRequest) -> QhExactQ2CertificationResult:
        r"""Certify learned recursive ``Q_2`` targets on the frozen test corpus.

        This operation evaluates the selected bundle but does not fit it. The
        exact control replaces the learned successor value with the maximum
        persisted one-step reward at the factual successor. Consequently the
        reported discrepancy isolates the bundle's learned ``Q_1`` path inside
        the two-step recursion; it does not re-test tensor-indexing parity and
        it does not estimate endpoint-policy headroom.

        Hard-invalid rows remain excluded by the Lightning owner's
        ``selected_train_mask`` and ``successor_backup_mask``. The certifier
        never consults feasibility logits, never multiplies probability by Q,
        and never widens support beyond the frozen action/label masks.

        Args:
            request: Frozen bundle, exact test population, stratified-selection
                and tolerance contract, new output path, execution device, and
                optional diagnostic headroom store.

        Returns:
            Receipt reference whose content binds the scorer, state fusion,
            decoder, actor/source profile, learning semantics, test provenance,
            row selection, tolerances, and optional headroom diagnostic.

        Raises:
            FileExistsError: If the receipt destination already exists.
            ValueError: If bundle, dataset, device, lineage, or diagnostic store
                identity is invalid or has drifted from the frozen manifest.

        Notes:
            ``longer_horizon_gate_passed`` requires both learned-recursion
            agreement and positive independent held-out endpoint headroom. The
            optional store diagnostic explicitly declares that it is not an
            independent endpoint evaluation, so a certification receipt cannot
            promote ``h>2`` claims by itself.
        """

        output = request.output_receipt_path.expanduser().resolve()
        if output.exists():
            raise FileExistsError(f"Q_H exact-Q2 certification receipt already exists: {output}.")
        manifest = self._read_verified_manifest(request.bundle)
        expected_test = manifest["identity"]["datasets"]["test"]
        if expected_test != _jsonable(request.test):
            raise ValueError("Q_H exact-Q2 population does not match the frozen bundle test identity.")
        test = request.test.setup_target()
        identity = manifest["identity"]
        module_config = QhLightningModuleConfig.model_validate(manifest["module_config"])
        objective_profile = identity["learning_contract"].get("objective_profile")
        if objective_profile != "qh_dense_valid_fitted_q_v1":
            raise ValueError("Q_H exact-Q2 certification requires the dense-valid fitted-Q objective profile.")
        data = QhDataModule(
            train=test,
            batch_size=int(self.config.batch_size),
            num_workers=int(self.config.num_workers),
            pin_memory=bool(self.config.pin_memory),
            persistent_workers=bool(self.config.persistent_workers),
            seed=int(manifest["identity"]["seed"]),
            experiment_profile=module_config.experiment_profile,
            objective_profile=objective_profile,
        )
        if data.learning_contract_hash != identity["learning_contract_hash"]:
            raise ValueError("Q_H exact-Q2 test learning contract drifted from the bundle.")
        if data.actor_state_contract_hash != identity["actor_state_contract_hash"]:
            raise ValueError("Q_H exact-Q2 test actor-state contract drifted from the bundle.")
        if data.geometry_contract_hash != identity["geometry_contract_hash"]:
            raise ValueError("Q_H exact-Q2 test geometry contract drifted from the bundle.")
        expected_provenance = identity["dataset_provenance"]["test"]
        if _jsonable(test.provenance) != expected_provenance:
            raise ValueError("Q_H exact-Q2 test provenance drifted from the bundle.")

        device = _certification_device(request.device)
        runtime = self.load_for_inference(request.bundle, device=device)
        module = QhLightningModule(module_config, scorer=runtime.scorer)
        module.target_scorer.load_state_dict(module.online_scorer.state_dict(), strict=True)
        q2_evidence = QhExactQ2Certifier(request.spec).certify(
            module=module,
            dataset=test,
            device=device,
            ordered_store_manifest_sha256=_json_payload_hash(identity["ordered_store_manifests"]["test"]),
            decoder_support=_decoder_support(manifest["scorer_config"]),
        )
        headroom = _headroom_diagnostic(
            request.headroom_store_dir,
            threshold=float(request.spec.positive_headroom_threshold),
        )
        independent_positive_headroom = bool(
            headroom.get("independent_endpoint_evaluation", False)
            and headroom.get("positive_lookahead_headroom", False)
        )
        receipt = {
            "schema_version": "qh-exact-q2-certification-receipt-v2",
            "historical_compatibility": {
                "qh-exact-q2-certification-receipt-v1": "inspection_only_not_promotable",
            },
            "bundle_manifest_sha256": request.bundle.manifest_sha256,
            "test_population_sha256": _json_payload_hash(request.test),
            "test_provenance_sha256": _json_payload_hash(test.provenance),
            "execution_device": str(device),
            "bound_contract": {
                "scorer_config_hash": manifest["scorer_config_hash"],
                "scorer_config": manifest["scorer_config"],
                "module_config": manifest["module_config"],
                "learning_contract_hash": identity["learning_contract_hash"],
                "learning_contract": identity["learning_contract"],
                "actor_state_contract_hash": identity["actor_state_contract_hash"],
                "actor_state_contract": identity["actor_state_contract"],
                "geometry_contract_hash": identity["geometry_contract_hash"],
                "action_mask_semantics": identity["action_mask_semantics"],
                "representation_semantics": identity["representation_semantics"],
                "ordered_test_store_manifests": identity["ordered_store_manifests"]["test"],
                "ordered_test_store_paths": identity["ordered_store_paths"]["test"],
            },
            "exact_q2": q2_evidence,
            "oracle_headroom": headroom,
            "longer_horizon_gate": {
                "learned_recursion_passed": q2_evidence["learned_recursion_passed"],
                "independent_positive_headroom": independent_positive_headroom,
                "passed": bool(q2_evidence["learned_recursion_passed"] and independent_positive_headroom),
                "claim_scope": "h>2",
            },
        }
        output.parent.mkdir(parents=True, exist_ok=True)
        _write_json(output, receipt)
        return QhExactQ2CertificationResult(output, _sha256_file(output))

    @classmethod
    def load_for_inference(
        cls,
        ref: QhInferenceBundleRef,
        *,
        device: torch.device | str,
    ) -> QhInferenceRuntime:
        """Verify a bundle and return its scorer with manifest-derived identities."""

        manifest = cls._read_verified_manifest(ref)
        config = TargetFiniteHorizonScorerConfig.model_validate(manifest["scorer_config"])
        scorer = config.setup_target()
        state_path = _verified_artifact_path(ref.bundle_path, manifest, _SCORER_STATE_FILENAME)
        expected_state_hash = str(manifest["artifacts"][_SCORER_STATE_FILENAME]["sha256"])
        if _sha256_file(state_path) != expected_state_hash:
            raise ValueError("Q_H scorer-state payload hash does not match the bundle manifest.")
        state = torch.load(state_path, map_location="cpu", weights_only=True)
        scorer.load_state_dict(state, strict=True)
        scorer.validate_value_decoder_state(require_publishable=True)
        scorer.to(device=device)
        scorer.eval()
        identity = manifest["identity"]
        learning = identity["learning_contract"]["data_contract"]
        implementation = manifest["implementation"]
        return QhInferenceRuntime(
            scorer=scorer,
            bundle_manifest_sha256=str(manifest["manifest_sha256"]),
            scorer_state_sha256=expected_state_hash,
            scorer_config_hash=str(manifest["scorer_config_hash"]),
            implementation_sha256=str(implementation["package_tree_sha256"]),
            actor_state_contract_hash=str(identity["actor_state_contract_hash"]),
            learning_contract_hash=str(identity["learning_contract_hash"]),
            target_protocol=str(learning["target_protocol"]),
            candidate_config_hashes=tuple(str(item) for item in learning.get("candidate_config_hashes", [])),
            action_mask_semantics=str(identity["action_mask_semantics"]),
            representation_semantics=str(
                manifest["scorer_config"].get("representation_semantics", identity["representation_semantics"])
            ),
        )

    def _publish_bundle(
        self,
        bundle_dir: Path,
        scorer: TargetFiniteHorizonScorer,
        *,
        module_config: QhLightningModuleConfig,
        identity: dict[str, Any],
        artifact_hashes: dict[str, str] | None = None,
    ) -> dict[str, Any]:
        """Write scorer state plus one self-verifying manifest into a new directory."""

        bundle_dir = bundle_dir.expanduser().resolve()
        bundle_dir.mkdir(parents=True, exist_ok=True)
        state_path = bundle_dir / _SCORER_STATE_FILENAME
        if state_path.exists() or (bundle_dir / _MANIFEST_FILENAME).exists():
            raise FileExistsError(f"Q_H bundle payload already exists in {bundle_dir}.")
        if stable_config_hash(scorer.config, length=64) != stable_config_hash(self.config.scorer, length=64):
            raise ValueError("Q_H scorer runtime configuration does not match the experiment configuration.")
        scorer.validate_value_decoder_state(require_publishable=True)
        torch.save(scorer.state_dict(), state_path)
        artifacts = {
            _SCORER_STATE_FILENAME: {
                "path": _SCORER_STATE_FILENAME,
                "sha256": _sha256_file(state_path),
            }
        }
        for name, digest in sorted((artifact_hashes or {}).items()):
            artifacts[name] = {"path": name, "sha256": digest}
        manifest: dict[str, Any] = {
            "schema_version": QH_INFERENCE_BUNDLE_SCHEMA_VERSION,
            "scorer_type": "TargetFiniteHorizonScorer",
            "scorer_config": self.config.scorer.model_dump_jsonable(),
            "scorer_config_hash": stable_config_hash(self.config.scorer, length=64),
            "module_config": module_config.model_dump_jsonable(),
            "identity": _jsonable(identity),
            "dependencies": _bundle_dependencies(),
            "implementation": _bundle_implementation(),
            "artifacts": artifacts,
        }
        manifest["manifest_sha256"] = _manifest_hash(manifest)
        self._validate_manifest_contract(manifest)
        _verify_all_artifacts(bundle_dir, manifest)
        _write_json(bundle_dir / _MANIFEST_FILENAME, manifest)
        return manifest

    def _trainer_config(
        self,
        output: Path,
        selection: QhCheckpointSelectionSpec,
    ) -> TrainerFactoryConfig:
        callbacks = self.config.trainer.callbacks.model_copy(
            deep=True,
            update={
                "use_model_checkpoint": True,
                "checkpoint_monitor": selection.monitor,
                "checkpoint_mode": selection.mode,
                "checkpoint_dir": output / "checkpoints",
                "checkpoint_filename": "epoch={epoch}-step={step}-val-loss={val/loss:.6f}",
                "checkpoint_save_top_k": -1,
                "checkpoint_save_last": False,
            },
        )
        return self.config.trainer.model_copy(
            deep=True,
            update={
                "default_root_dir": output,
                "enable_validation": True,
                "use_wandb": False,
                "gradient_clip_val": None,
                "callbacks": callbacks,
            },
        )

    @classmethod
    def _read_verified_manifest(cls, ref: QhInferenceBundleRef) -> dict[str, Any]:
        bundle_path = ref.bundle_path.expanduser().resolve()
        if ref.schema_version != QH_INFERENCE_BUNDLE_SCHEMA_VERSION:
            raise ValueError(f"Unsupported Q_H bundle schema {ref.schema_version!r}.")
        manifest_path = bundle_path / _MANIFEST_FILENAME
        try:
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as error:
            raise ValueError(f"Cannot read Q_H bundle manifest at {manifest_path}.") from error
        if not isinstance(manifest, dict):
            raise ValueError("Q_H bundle manifest must contain one JSON object.")
        actual = _manifest_hash(manifest)
        declared = str(manifest.get("manifest_sha256", ""))
        if declared != actual or ref.manifest_sha256 != actual:
            raise ValueError("Q_H bundle manifest hash does not match its reference or contents.")
        if manifest.get("schema_version") != ref.schema_version:
            raise ValueError("Q_H bundle reference and manifest schema versions differ.")
        cls._validate_manifest_contract(manifest)
        _verify_all_artifacts(bundle_path, manifest)
        return manifest

    @classmethod
    def _warm_start_weights(
        cls,
        ref: QhInferenceBundleRef | None,
        *,
        scorer: torch.nn.Module,
        scorer_config: TargetFiniteHorizonScorerConfig,
        module_config: QhLightningModuleConfig,
        actor_state_contract_hash: str,
        learning_contract_hash: str,
        target_protocol: str,
        action_mask_semantics: str,
        geometry_contract_hash: str | None,
    ) -> QhInferenceBundleRef | None:
        """Load weights only from an exactly compatible learning identity.

        Warm starting is continuation, not representation transfer. The
        parent must therefore agree on the complete learning-contract hash in
        addition to scorer, actor, target, mask, observation, and geometry
        identities. A future cross-objective transfer policy requires its own
        versioned profile rather than weakening this fail-closed path.
        """

        if ref is None:
            return None
        manifest = cls._read_verified_manifest(ref)
        identity = manifest["identity"]
        expected = {
            "scorer_config_hash": stable_config_hash(scorer_config, length=64),
            "actor_state_contract_hash": actor_state_contract_hash,
            "learning_contract_hash": learning_contract_hash,
            "target_protocol": target_protocol,
            "action_mask_semantics": action_mask_semantics,
            "root_evl_profile": module_config.root_evl_profile,
            "selected_observation_protocol": module_config.selected_observation_protocol,
            "experiment_profile": module_config.experiment_profile,
            "geometry_contract_hash": geometry_contract_hash,
        }
        actual = {
            "scorer_config_hash": manifest["scorer_config_hash"],
            "actor_state_contract_hash": identity["actor_state_contract_hash"],
            "learning_contract_hash": identity["learning_contract_hash"],
            "target_protocol": identity["learning_contract"]["data_contract"]["target_protocol"],
            "action_mask_semantics": identity["action_mask_semantics"],
            "root_evl_profile": manifest["module_config"]["root_evl_profile"],
            "selected_observation_protocol": manifest["module_config"]["selected_observation_protocol"],
            "experiment_profile": manifest["module_config"]["experiment_profile"],
            "geometry_contract_hash": identity["geometry_contract_hash"],
        }
        mismatches = [name for name in expected if expected[name] != actual[name]]
        if mismatches:
            raise ValueError(f"Q_H warm-start bundle is incompatible with the current fit: {', '.join(mismatches)}.")
        state_path = _verified_artifact_path(ref.bundle_path, manifest, _SCORER_STATE_FILENAME)
        state = torch.load(state_path, map_location="cpu", weights_only=True)
        scorer.load_state_dict(state, strict=True)
        scorer.validate_value_decoder_state(require_publishable=True)
        return QhInferenceBundleRef(ref.bundle_path, ref.schema_version, ref.manifest_sha256)

    @staticmethod
    def _selected_checkpoint(output: Path) -> tuple[Path, float, int]:
        """Select the exact minimum validation loss, breaking ties by earliest update."""

        ranked: list[tuple[float, int, str, Path]] = []
        for path in sorted((output / "checkpoints").glob("*.ckpt")):
            try:
                payload = torch.load(path, map_location="cpu", weights_only=False)
            except Exception as error:  # noqa: BLE001
                raise ValueError(f"Q_H selection checkpoint {path.name!r} cannot be loaded.") from error
            state = payload.get("state_dict")
            if not isinstance(state, dict):
                raise ValueError(f"Q_H selection checkpoint {path.name!r} has no state_dict.")
            scalars: dict[str, float] = {}
            for field in ("validation_loss_sum", "validation_row_count", "optimizer_updates"):
                if field not in state:
                    raise ValueError(f"Q_H selection checkpoint {path.name!r} is missing {field!r}.")
                try:
                    scalars[field] = float(torch.as_tensor(state[field]).item())
                except (TypeError, ValueError, RuntimeError) as error:
                    raise ValueError(f"Q_H selection checkpoint {path.name!r} has invalid scalar {field!r}.") from error
            loss_sum = scalars["validation_loss_sum"]
            row_count_value = scalars["validation_row_count"]
            optimizer_updates_value = scalars["optimizer_updates"]
            if (
                not math.isfinite(loss_sum)
                or not math.isfinite(row_count_value)
                or not row_count_value.is_integer()
                or row_count_value < 1
                or not math.isfinite(optimizer_updates_value)
                or not optimizer_updates_value.is_integer()
                or optimizer_updates_value < 0
            ):
                raise ValueError(f"Q_H selection checkpoint {path.name!r} has invalid selection aggregates.")
            row_count = int(row_count_value)
            optimizer_updates = int(optimizer_updates_value)
            ranked.append((loss_sum / row_count, optimizer_updates, path.name, path.resolve()))
        if not ranked:
            raise RuntimeError(
                "Q_H fit produced no val/loss-selected checkpoint; refusing to publish final trainer state."
            )
        validation_loss, optimizer_updates, _name, selected = min(ranked)
        return selected, validation_loss, optimizer_updates

    @staticmethod
    def _validate_manifest_contract(manifest: dict[str, Any]) -> None:
        """Validate the closed bundle schema and cross-field identities.

        The learning contract may cover a strict subset of the scorer's
        configured horizon support, but it may never claim a horizon the
        persisted scorer cannot query. This binds the dataset horizon,
        ``H_max`` model capacity, and checkpoint manifest at load time as well
        as at fit admission.
        """

        required_manifest_fields = {
            "schema_version",
            "scorer_type",
            "scorer_config",
            "scorer_config_hash",
            "module_config",
            "identity",
            "dependencies",
            "implementation",
            "artifacts",
            "manifest_sha256",
        }
        if set(manifest) != required_manifest_fields:
            raise ValueError("Q_H bundle manifest fields do not match the closed V1 schema.")
        if manifest.get("scorer_type") != "TargetFiniteHorizonScorer":
            raise ValueError("Q_H bundle scorer_type is missing or unsupported.")
        try:
            scorer = TargetFiniteHorizonScorerConfig.model_validate(manifest["scorer_config"])
            module = QhLightningModuleConfig.model_validate(manifest["module_config"])
            identity = manifest["identity"]
            actor_payload = identity["actor_state_contract"]
            learning_payload = identity["learning_contract"]
            actor_contract = QhActorStateContract(**actor_payload)
            data_contract = QhDataContract(**learning_payload["data_contract"])
            learning_contract = QhLearningContract(
                data_contract=data_contract,
                max_horizon=int(learning_payload["max_horizon"]),
                horizon_weighting=str(learning_payload["horizon_weighting"]),
                objective_profile=learning_payload["objective_profile"],
            )
            artifacts = manifest["artifacts"]
            datasets = identity["datasets"]
            dataset_provenance = identity["dataset_provenance"]
            ordered_store_manifests = identity["ordered_store_manifests"]
            ordered_store_paths = identity["ordered_store_paths"]
        except (KeyError, TypeError, ValueError) as error:
            raise ValueError("Q_H bundle manifest is missing a required closed contract field.") from error
        if set(identity) != _IDENTITY_FIELDS:
            raise ValueError("Q_H bundle identity fields do not match the closed V1 schema.")
        if manifest["dependencies"] != _bundle_dependencies():
            raise ValueError("Q_H bundle dependency identity does not match the current runtime.")
        if manifest["implementation"] != _bundle_implementation():
            raise ValueError("Q_H bundle implementation identity does not match the current source owners.")
        if manifest.get("scorer_config_hash") != stable_config_hash(scorer, length=64):
            raise ValueError("Q_H bundle scorer_config_hash does not match scorer_config.")
        actor_hash = stable_msgspec_hash(actor_contract)
        learning_hash = stable_msgspec_hash(learning_contract)
        if identity.get("actor_state_contract_hash") != actor_hash:
            raise ValueError("Q_H bundle actor-state contract hash does not match its payload.")
        if identity.get("learning_contract_hash") != learning_hash:
            raise ValueError("Q_H bundle learning contract hash does not match its payload.")
        if module.actor_state_contract_hash != actor_hash or module.learning_contract_hash != learning_hash:
            raise ValueError("Q_H bundle module config is not bound to the manifest contracts.")
        if learning_contract.max_horizon > scorer.max_horizon:
            raise ValueError(
                "Q_H bundle learning-contract max_horizon exceeds scorer max_horizon: "
                f"{learning_contract.max_horizon} > {scorer.max_horizon}."
            )
        geometry_hash = identity.get("geometry_contract_hash")
        if module.geometry_contract_hash != geometry_hash or actor_contract.geometry_contract_hash != geometry_hash:
            raise ValueError("Q_H bundle geometry identity is inconsistent across actor, module, and manifest.")
        if (
            scorer.experiment_profile != module.experiment_profile
            or actor_contract.experiment_profile != scorer.experiment_profile
        ):
            raise ValueError("Q_H bundle scorer, module, and actor experiment profiles differ.")
        if (
            module.root_evl_profile != actor_contract.root_evl_profile
            or module.selected_observation_protocol != actor_contract.selected_observation_protocol
        ):
            raise ValueError("Q_H bundle module and actor observation profiles differ.")
        if module.privileged:
            raise ValueError("Q_H deployable bundle rejects privileged module configuration.")
        if learning_contract.objective_profile != "qh_dense_valid_fitted_q_v1":
            raise ValueError("Q_H deployable bundle requires the dense-valid fitted-Q objective.")
        if set(datasets) != {"train", "validation", "test"}:
            raise ValueError("Q_H bundle must bind train, validation, and test dataset configs.")
        if (
            set(dataset_provenance) != set(datasets)
            or set(ordered_store_manifests) != set(datasets)
            or set(ordered_store_paths) != set(datasets)
        ):
            raise ValueError("Q_H bundle dataset provenance stages are incomplete.")
        if isinstance(identity["seed"], bool) or not isinstance(identity["seed"], int):
            raise ValueError("Q_H bundle seed identity must be one integer.")
        warm_start_identity = identity["warm_start_parent_manifest_sha256"]
        if warm_start_identity is not None and (not isinstance(warm_start_identity, str) or not warm_start_identity):
            raise ValueError("Q_H warm-start parent identity must be absent or one non-empty manifest hash.")
        for field in ("action_mask_semantics", "representation_semantics"):
            if not isinstance(identity[field], str) or not identity[field]:
                raise ValueError(f"Q_H bundle {field} must be one non-empty string.")
        if identity["action_mask_semantics"] != data_contract.action_mask_semantics:
            raise ValueError("Q_H bundle action-mask semantics do not match the learning contract.")
        if identity["action_mask_semantics"] == "learned_feasibility_v1":
            raise ValueError(
                "Q_H deployable core bundles reject learned_feasibility_v1 until a separately versioned "
                "calibrated learned-only profile exists."
            )
        if identity["action_mask_semantics"] not in {
            "oracle_action_mask_v1",
            "actor_observed_action_mask_v1",
        }:
            raise ValueError("Q_H bundle action-mask semantics are unsupported.")
        if module.action_mask_semantics != identity["action_mask_semantics"]:
            raise ValueError("Q_H bundle module and identity action-mask semantics differ.")
        if identity["representation_semantics"] != scorer.representation_semantics:
            raise ValueError("Q_H bundle representation semantics do not match the scorer configuration.")
        required_artifacts = {
            _SCORER_STATE_FILENAME,
            _TRAINING_RECEIPT_FILENAME,
            _SELECTION_RECEIPT_FILENAME,
        }
        if set(artifacts) != required_artifacts:
            missing = sorted(required_artifacts - set(artifacts))
            unexpected = sorted(set(artifacts) - required_artifacts)
            raise ValueError(
                f"Q_H V1 bundle artifact set is incomplete or unknown: missing={missing}, unexpected={unexpected}."
            )
        for name, artifact in artifacts.items():
            if not isinstance(artifact, dict) or not isinstance(artifact.get("sha256"), str):
                raise ValueError(f"Q_H bundle artifact {name!r} has invalid metadata.")
            _validate_artifact_name(name, artifact.get("path"))


def _jsonable(value: Any) -> Any:
    if isinstance(value, BaseConfig):
        return value.model_dump_jsonable()
    if is_dataclass(value) and not isinstance(value, type):
        return _jsonable(asdict(value))
    if isinstance(value, dict):
        return {str(key): _jsonable(item) for key, item in value.items()}
    if isinstance(value, (list, tuple, set, frozenset)):
        return [_jsonable(item) for item in value]
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, torch.Tensor):
        return value.detach().cpu().tolist()
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    return repr(value)


def _ordered_store_manifest_hashes(provenance: dict[str, object]) -> list[str]:
    """Return rollout manifest hashes in the reader's canonical store order."""

    rollout = provenance.get("rollout")
    if not isinstance(rollout, dict):
        return []
    stores = rollout.get("stores")
    if not isinstance(stores, list):
        return []
    hashes: list[str] = []
    for index, store in enumerate(stores):
        if not isinstance(store, dict) or not isinstance(store.get("manifest_sha256"), str):
            raise ValueError(f"Q_H dataset provenance store {index} has no manifest_sha256.")
        hashes.append(str(store["manifest_sha256"]))
    return hashes


def _validate_artifact_name(name: str, raw_path: object) -> str:
    if not isinstance(raw_path, str) or not raw_path:
        raise ValueError(f"Q_H bundle artifact {name!r} has no relative payload path.")
    path = Path(raw_path)
    if path.is_absolute() or path.name != raw_path or raw_path in {".", ".."}:
        raise ValueError(f"Q_H bundle artifact {name!r} path must be one contained filename.")
    if name != raw_path:
        raise ValueError(f"Q_H bundle artifact key {name!r} must equal its payload filename.")
    return raw_path


def _verified_artifact_path(bundle_path: Path, manifest: dict[str, Any], name: str) -> Path:
    artifacts = manifest.get("artifacts")
    if not isinstance(artifacts, dict) or not isinstance(artifacts.get(name), dict):
        raise ValueError(f"Q_H bundle manifest has no required artifact {name!r}.")
    raw_path = _validate_artifact_name(name, artifacts[name].get("path"))
    root = bundle_path.expanduser().resolve()
    path = (root / raw_path).resolve()
    if path.parent != root:
        raise ValueError(f"Q_H bundle artifact {name!r} escapes the bundle directory.")
    return path


def _verify_all_artifacts(bundle_path: Path, manifest: dict[str, Any]) -> None:
    """Verify every closed-schema artifact before loading any bundle payload."""

    artifacts = manifest["artifacts"]
    for name, artifact in artifacts.items():
        path = _verified_artifact_path(bundle_path, manifest, name)
        if _sha256_file(path) != str(artifact["sha256"]):
            raise ValueError(f"Q_H bundle artifact {name!r} hash does not match the manifest.")


def _bundle_dependencies() -> dict[str, str]:
    """Return the exact runtime identity admitted by the V1 bundle schema."""

    return {
        "python": f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}",
        "torch": str(torch.__version__),
        "pytorch_lightning": importlib.metadata.version("pytorch-lightning"),
    }


def _bundle_implementation() -> dict[str, str]:
    """Return one deterministic digest over the importable ``aria_nbv`` tree."""

    package = Path(__file__).resolve().parents[1]
    return {"package_tree_sha256": _package_tree_digest(package)}


def _package_tree_digest(package: Path) -> str:
    """Hash sorted Python paths and raw bytes below one package root."""

    digest = hashlib.sha256()
    for path in sorted(package.rglob("*.py")):
        relative = path.relative_to(package).as_posix().encode("utf-8")
        digest.update(relative)
        digest.update(b"\0")
        try:
            digest.update(path.read_bytes())
        except OSError as error:
            raise ValueError(f"Cannot hash implementation source {path}.") from error
        digest.update(b"\0")
    return digest.hexdigest()


def _manifest_hash(manifest: dict[str, Any]) -> str:
    payload = {key: value for key, value in manifest.items() if key != "manifest_sha256"}
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _json_payload_hash(value: Any) -> str:
    """Hash one JSON-safe contract payload with canonical ordering."""

    encoded = json.dumps(_jsonable(value), sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _certification_device(value: str) -> torch.device:
    """Resolve one explicit certification device and fail closed on CUDA drift."""

    try:
        device = torch.device(value)
    except (RuntimeError, ValueError) as error:
        raise ValueError(f"Q_H exact-Q2 certification received invalid device {value!r}.") from error
    if device.type not in {"cpu", "cuda"}:
        raise ValueError("Q_H exact-Q2 certification supports only CPU or CUDA devices.")
    if device.type == "cuda" and not torch.cuda.is_available():
        raise ValueError("Q_H exact-Q2 certification requested CUDA, but CUDA is unavailable.")
    return device


def _decoder_support(scorer_config: object) -> QhDecoderSupport | None:
    """Extract fixed CORAL support from the verified scorer configuration."""

    if not isinstance(scorer_config, dict):
        raise ValueError("Q_H exact-Q2 scorer configuration is malformed.")
    decoder = scorer_config.get("value_decoder")
    if not isinstance(decoder, dict) or not isinstance(decoder.get("kind"), str):
        raise ValueError("Q_H exact-Q2 value-decoder configuration is malformed.")
    kind = str(decoder["kind"])
    if kind == "regression":
        return None
    if kind != "coral":
        raise ValueError(f"Q_H exact-Q2 received unsupported value decoder {kind!r}.")
    edges = decoder.get("bin_edges")
    values = decoder.get("bin_values")
    if not isinstance(edges, list) or not isinstance(values, list) or not edges or not values:
        raise ValueError("Q_H exact-Q2 CORAL support is incomplete.")
    return QhDecoderSupport(
        kind="coral",
        lower_representative=float(values[0]),
        upper_representative=float(values[-1]),
        lower_edge=float(edges[0]),
        upper_edge=float(edges[-1]),
    )


def _headroom_diagnostic(store_dir: Path | None, *, threshold: float) -> dict[str, object]:
    """Summarize the existing exact-role terminal-step headroom diagnostic.

    The rollout inspection owner explicitly labels this evidence as a proxy and
    records ``independent_endpoint_evaluation=False``. This adapter preserves
    that boundary, binds the validated store manifest, and reports whether any
    exact-role ``delta_look`` contrast is positive without promoting the proxy
    to the independent held-out endpoint evidence required for ``h>2``.
    """

    if store_dir is None:
        return {
            "available": False,
            "reason": "no_headroom_store_supplied",
            "independent_endpoint_evaluation": False,
            "positive_lookahead_headroom": False,
        }
    reader = RolloutZarrStoreReader(store_dir)
    validation = reader.validate(validate_selected_depth_payload=False)
    if not validation.ok:
        raise ValueError(f"Q_H exact-Q2 headroom store validation failed: {validation.errors}.")
    evidence = oracle_headroom_evidence(reader, threshold=threshold)
    included = [
        row
        for row in evidence["contrast_rows"]
        if row.get("contrast") == "delta_look" and row.get("status") == "included"
    ]
    values = [float(row["value"]) for row in included if row.get("value") is not None]
    manifest = reader.manifest()
    root_attrs = manifest.get("root_attrs")
    root_attrs = root_attrs if isinstance(root_attrs, dict) else {}
    return {
        "available": True,
        "evidence_status": evidence["evidence_status"],
        "metric_source": evidence["metric_source"],
        "endpoint_kind": evidence["endpoint_kind"],
        "independent_endpoint_evaluation": evidence["independent_endpoint_evaluation"],
        "positive_lookahead_headroom": any(value > threshold for value in values),
        "positive_threshold": threshold,
        "included_delta_look_count": len(values),
        "delta_look_values": values,
        "summary_rows": evidence["summary_rows"],
        "store": {
            "path": str(validation.store_dir),
            "manifest_sha256": root_attrs.get("manifest_sha256"),
            "num_rollouts": validation.num_rollouts,
            "num_steps": validation.num_steps,
            "num_candidates": validation.num_candidates,
        },
        "full_evidence_sha256": _json_payload_hash(evidence),
    }


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    try:
        with path.open("rb") as handle:
            for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                digest.update(chunk)
    except OSError as error:
        raise ValueError(f"Cannot hash required Q_H bundle artifact {path}.") from error
    return digest.hexdigest()


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.write_text(json.dumps(_jsonable(payload), sort_keys=True, indent=2) + "\n", encoding="utf-8")


__all__ = [
    "QH_INFERENCE_BUNDLE_SCHEMA_VERSION",
    "QhCheckpointSelectionSpec",
    "QhExperiment",
    "QhExperimentConfig",
    "QhExactQ2CertificationRequest",
    "QhExactQ2CertificationResult",
    "QhExactQ2CertificationSpec",
    "QhFitRequest",
    "QhFitResult",
    "QhHeldOutEvaluationRequest",
    "QhHeldOutEvaluationResult",
    "QhInferenceBundleRef",
    "QhInferenceRuntime",
]
