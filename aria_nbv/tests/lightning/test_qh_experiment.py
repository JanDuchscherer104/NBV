"""Immutable Q_H experiment and inference-bundle contracts."""

# ruff: noqa: S101

from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from dataclasses import FrozenInstanceError, replace
from pathlib import Path
from types import SimpleNamespace

import pytest
import torch

import aria_nbv.lightning.qh_experiment as qh_experiment_module
from aria_nbv.data_handling.qh_data.views import QhActorStateContract
from aria_nbv.lightning.lit_trainer_factory import TrainerFactoryConfig
from aria_nbv.lightning.qh_datamodule import QhLearningContract
from aria_nbv.lightning.qh_experiment import (
    QH_INFERENCE_BUNDLE_SCHEMA_VERSION,
    QhCheckpointSelectionSpec,
    QhExactQ2CertificationRequest,
    QhExactQ2CertificationSpec,
    QhExperiment,
    QhExperimentConfig,
    QhFitRequest,
    QhHeldOutEvaluationRequest,
    QhInferenceBundleRef,
    _headroom_diagnostic,
    _manifest_hash,
)
from aria_nbv.lightning.qh_module import QhLightningModuleConfig
from aria_nbv.rollouts.qh_reader import QhDataContract
from aria_nbv.utils.fingerprints import stable_config_hash, stable_msgspec_hash
from aria_nbv.vin.models.target_finite_horizon import TargetFiniteHorizonScorerConfig
from aria_nbv.vin.modules.qh_history_encoders import QhCausalTransformerHistoryEncoderConfig
from aria_nbv.vin.modules.qh_state_fusion import QhIndependentMlpStateFusionConfig
from aria_nbv.vin.modules.qh_value_decoders import (
    QhCoralValueDecoderConfig,
    QhLegacyFixedCoralSupport,
    QhPredeclaredPhysicalCoralSupport,
)
from tests.data_handling.test_qh import _chain
from tests.lightning.test_qh_module import _ChainDataset
from tests.vin.test_target_finite_horizon import _actor


def _experiment() -> QhExperiment:
    config = QhExperimentConfig(
        scorer=TargetFiniteHorizonScorerConfig(
            hidden_dim=32,
            dropout=0.0,
            max_horizon=4,
        ),
        module=QhLightningModuleConfig(
            actor_state_contract_hash="bound-during-fit",
            learning_contract_hash="bound-during-fit",
            lr_scheduler=None,
        ),
    )
    return config.setup_target()


def _coral_experiment() -> QhExperiment:
    """Return the same experiment contract with a fixed three-class Q support."""

    config = QhExperimentConfig(
        scorer=TargetFiniteHorizonScorerConfig(
            hidden_dim=32,
            dropout=0.0,
            max_horizon=4,
            value_decoder=QhCoralValueDecoderConfig(
                support=QhPredeclaredPhysicalCoralSupport.create(
                    source_population_digest="population-v1",
                    ordered_input_digest="physical-rule-inputs-v1",
                    physical_rule="symmetric-root-gain-support-v1",
                    bin_edges=(-0.5, 0.5),
                    bin_values=(-1.0, 0.0, 1.0),
                ),
                preinit_bias=False,
            ),
        ),
        module=QhLightningModuleConfig(
            actor_state_contract_hash="bound-during-fit",
            learning_contract_hash="bound-during-fit",
            lr_scheduler=None,
        ),
    )
    return config.setup_target()


def _a0_experiment() -> QhExperiment:
    """Return the regression experiment with identical-feature A0 fusion."""

    base = _experiment().config
    scorer = base.scorer.model_copy(
        deep=True,
        update={"state_fusion": QhIndependentMlpStateFusionConfig()},
    )
    return base.model_copy(deep=True, update={"scorer": scorer}).setup_target()


def test_headroom_diagnostic_accepts_any_positive_included_cohort(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class _Reader:
        def __init__(self, store_dir: Path) -> None:
            self.store_dir = store_dir

        def validate(self, *, validate_selected_depth_payload: bool) -> SimpleNamespace:
            assert validate_selected_depth_payload is False
            return SimpleNamespace(
                ok=True,
                errors=(),
                store_dir=self.store_dir,
                num_rollouts=2,
                num_steps=4,
                num_candidates=12,
            )

        def manifest(self) -> dict[str, object]:
            return {"root_attrs": {"manifest_sha256": "manifest"}}

    evidence = {
        "evidence_status": "diagnostic_only",
        "metric_source": "oracle",
        "endpoint_kind": "terminal_proxy",
        "independent_endpoint_evaluation": False,
        "contrast_rows": [
            {"contrast": "delta_look", "status": "included", "value": 0.25},
            {"contrast": "delta_look", "status": "included", "value": -0.10},
        ],
        "summary_rows": [],
    }
    monkeypatch.setattr(qh_experiment_module, "RolloutZarrStoreReader", _Reader)
    monkeypatch.setattr(
        qh_experiment_module,
        "oracle_headroom_evidence",
        lambda _reader, *, threshold: evidence,
    )

    diagnostic = _headroom_diagnostic(tmp_path / "headroom.zarr", threshold=0.0)

    assert diagnostic["positive_lookahead_headroom"] is True
    assert diagnostic["delta_look_values"] == [0.25, -0.10]


def _h1_experiment() -> QhExperiment:
    """Return the regression experiment with ordered causal pose history."""

    base = _experiment().config
    scorer = base.scorer.model_copy(
        deep=True,
        update={
            "history_encoder": QhCausalTransformerHistoryEncoderConfig(
                attention_heads=4,
                layers=1,
                feedforward_multiplier=2,
            ),
        },
    )
    return base.model_copy(deep=True, update={"scorer": scorer}).setup_target()


def _bundle(tmp_path) -> tuple[QhExperiment, QhInferenceBundleRef]:
    experiment = _experiment()
    module_config, identity = _publish_contracts(experiment)
    bundle_dir = tmp_path / "bundle"
    bundle_dir.mkdir()
    manifest = experiment._publish_bundle(  # noqa: SLF001
        bundle_dir,
        experiment.config.scorer.setup_target(),
        module_config=module_config,
        identity=identity,
        artifact_hashes=_stub_artifacts(bundle_dir),
    )
    return experiment, QhInferenceBundleRef(
        bundle_path=bundle_dir,
        schema_version=QH_INFERENCE_BUNDLE_SCHEMA_VERSION,
        manifest_sha256=manifest["manifest_sha256"],
    )


def test_qh_bundle_round_trip_preserves_values_and_ranking(tmp_path) -> None:
    torch.manual_seed(17)
    experiment = _experiment()
    scorer = experiment.config.scorer.setup_target().eval()
    actor = _actor()
    expected = scorer(actor)
    expected_rank = expected.conditional_q.masked_fill(~actor.action_mask, -torch.inf).argmax(dim=-1)
    bundle_dir = tmp_path / "bundle"
    bundle_dir.mkdir()
    module_config, identity = _publish_contracts(experiment)
    manifest = experiment._publish_bundle(  # noqa: SLF001
        bundle_dir,
        scorer,
        module_config=module_config,
        identity=identity,
        artifact_hashes=_stub_artifacts(bundle_dir),
    )
    del scorer
    ref = QhInferenceBundleRef(
        bundle_path=bundle_dir,
        schema_version=QH_INFERENCE_BUNDLE_SCHEMA_VERSION,
        manifest_sha256=manifest["manifest_sha256"],
    )

    runtime = QhExperiment.load_for_inference(ref, device="cpu")
    actual = runtime.scorer(actor)

    assert runtime.scorer.training is False
    assert runtime.scorer_state_sha256 == manifest["artifacts"]["scorer-state.pt"]["sha256"]
    assert runtime.representation_semantics == "root_moments_v1"
    assert runtime.trained_horizons == (1, 2)
    assert torch.equal(actual.conditional_q, expected.conditional_q)
    assert torch.equal(actual.feasibility_logits, expected.feasibility_logits)
    assert torch.equal(
        actual.conditional_q.masked_fill(~actor.action_mask, -torch.inf).argmax(dim=-1),
        expected_rank,
    )

    probe = subprocess.run(
        [
            sys.executable,
            "-c",
            (
                "from pathlib import Path; import torch; "
                "from aria_nbv.lightning.qh_experiment import QhExperiment, QhInferenceBundleRef; "
                "from tests.vin.test_target_finite_horizon import _actor; "
                f"ref=QhInferenceBundleRef(Path({str(bundle_dir)!r}), {ref.schema_version!r}, {ref.manifest_sha256!r}); "
                "actor=_actor(); runtime=QhExperiment.load_for_inference(ref, device='cpu'); "
                "output=runtime.scorer(actor); "
                "print(output.conditional_q.masked_fill(~actor.action_mask, -torch.inf).argmax(dim=-1).tolist())"
            ),
        ],
        check=True,
        capture_output=True,
        cwd=Path(__file__).parents[2],
        text=True,
    )
    assert probe.stdout.strip() == str(expected_rank.tolist())


def test_qh_coral_bundle_round_trip_preserves_support_thresholds_and_ranking(tmp_path) -> None:
    torch.manual_seed(19)
    experiment = _coral_experiment()
    scorer = experiment.config.scorer.setup_target().eval()
    actor = _actor()
    expected = scorer(actor)
    expected_rank = expected.conditional_q.masked_fill(~actor.action_mask, -torch.inf).argmax(dim=-1)
    bundle_dir = tmp_path / "coral-bundle"
    bundle_dir.mkdir()
    module_config, identity = _publish_contracts(experiment)
    manifest = experiment._publish_bundle(  # noqa: SLF001
        bundle_dir,
        scorer,
        module_config=module_config,
        identity=identity,
        artifact_hashes=_stub_artifacts(bundle_dir),
    )
    ref = QhInferenceBundleRef(
        bundle_path=bundle_dir,
        schema_version=QH_INFERENCE_BUNDLE_SCHEMA_VERSION,
        manifest_sha256=manifest["manifest_sha256"],
    )

    runtime = QhExperiment.load_for_inference(ref, device="cpu")
    actual = runtime.scorer(actor)

    decoder_manifest = manifest["scorer_config"]["value_decoder"]
    assert decoder_manifest["kind"] == "coral"
    assert decoder_manifest["preinit_bias"] is False
    assert decoder_manifest["support"]["provenance_kind"] == "predeclared_physical_v1"
    assert decoder_manifest["support"]["split_role"] == "not_applicable_predeclared"
    assert decoder_manifest["support"]["physical_rule"] == "symmetric-root-gain-support-v1"
    assert decoder_manifest["support"]["bin_edges"] == [-0.5, 0.5]
    assert decoder_manifest["support"]["bin_values"] == [-1.0, 0.0, 1.0]
    assert len(decoder_manifest["support"]["artifact_digest"]) == 64
    assert expected.value_auxiliary is not None
    assert actual.value_auxiliary is not None
    assert torch.equal(actual.conditional_q, expected.conditional_q)
    assert torch.equal(actual.value_auxiliary.logits, expected.value_auxiliary.logits)
    assert torch.equal(actual.value_auxiliary.bin_edges, expected.value_auxiliary.bin_edges)
    assert torch.equal(
        actual.conditional_q.masked_fill(~actor.action_mask, -torch.inf).argmax(dim=-1),
        expected_rank,
    )


def test_qh_a0_bundle_round_trip_preserves_fusion_identity_and_values(tmp_path) -> None:
    torch.manual_seed(23)
    experiment = _a0_experiment()
    scorer = experiment.config.scorer.setup_target().eval()
    actor = _actor()
    expected = scorer(actor)
    bundle_dir = tmp_path / "a0-bundle"
    bundle_dir.mkdir()
    module_config, identity = _publish_contracts(experiment)
    manifest = experiment._publish_bundle(  # noqa: SLF001
        bundle_dir,
        scorer,
        module_config=module_config,
        identity=identity,
        artifact_hashes=_stub_artifacts(bundle_dir),
    )
    ref = QhInferenceBundleRef(
        bundle_path=bundle_dir,
        schema_version=QH_INFERENCE_BUNDLE_SCHEMA_VERSION,
        manifest_sha256=manifest["manifest_sha256"],
    )

    runtime = QhExperiment.load_for_inference(ref, device="cpu")
    actual = runtime.scorer(actor)

    assert manifest["scorer_config"]["state_fusion"] == {"kind": "independent_mlp"}
    assert torch.equal(actual.conditional_q, expected.conditional_q)
    assert torch.equal(actual.feasibility_logits, expected.feasibility_logits)


def test_qh_h1_bundle_round_trip_preserves_history_identity_and_values(tmp_path) -> None:
    """The deployable manifest and strict state load preserve the H1 carrier."""

    torch.manual_seed(29)
    experiment = _h1_experiment()
    scorer = experiment.config.scorer.setup_target().eval()
    actor = _actor(steps=4)
    expected = scorer(actor)
    bundle_dir = tmp_path / "h1-bundle"
    bundle_dir.mkdir()
    module_config, identity = _publish_contracts(experiment)
    manifest = experiment._publish_bundle(  # noqa: SLF001
        bundle_dir,
        scorer,
        module_config=module_config,
        identity=identity,
        artifact_hashes=_stub_artifacts(bundle_dir),
    )
    ref = QhInferenceBundleRef(
        bundle_path=bundle_dir,
        schema_version=QH_INFERENCE_BUNDLE_SCHEMA_VERSION,
        manifest_sha256=manifest["manifest_sha256"],
    )

    runtime = QhExperiment.load_for_inference(ref, device="cpu")
    actual = runtime.scorer(actor)

    assert manifest["scorer_config"]["history_encoder"] == {
        "kind": "causal_transformer_v1",
        "attention_heads": 4,
        "layers": 1,
        "feedforward_multiplier": 2,
    }
    assert isinstance(runtime.scorer.config.history_encoder, QhCausalTransformerHistoryEncoderConfig)
    assert stable_config_hash(runtime.scorer.config, length=64) == manifest["scorer_config_hash"]
    assert torch.equal(actual.conditional_q, expected.conditional_q)
    assert torch.equal(actual.feasibility_logits, expected.feasibility_logits)


@pytest.mark.parametrize(
    ("field", "replacement", "message"),
    [
        ("bin_edges", [-0.25, 0.75], "bin edges"),
        ("bin_values", [-2.0, 0.0, 2.0], "bin values"),
    ],
)
def test_qh_coral_bundle_rejects_manifest_support_drift_with_unchanged_state(
    tmp_path,
    field: str,
    replacement: list[float],
    message: str,
) -> None:
    experiment = _coral_experiment()
    module_config, identity = _publish_contracts(experiment)
    bundle_dir = tmp_path / "coral-bundle"
    bundle_dir.mkdir()
    manifest = experiment._publish_bundle(  # noqa: SLF001
        bundle_dir,
        experiment.config.scorer.setup_target(),
        module_config=module_config,
        identity=identity,
        artifact_hashes=_stub_artifacts(bundle_dir),
    )
    current_support = experiment.config.scorer.value_decoder.support
    assert isinstance(current_support, QhPredeclaredPhysicalCoralSupport)
    replacement_support = QhPredeclaredPhysicalCoralSupport.create(
        source_population_digest=current_support.source_population_digest,
        ordered_input_digest=current_support.ordered_input_digest,
        physical_rule=current_support.physical_rule,
        bin_edges=tuple(replacement) if field == "bin_edges" else current_support.bin_edges,
        bin_values=tuple(replacement) if field == "bin_values" else current_support.bin_values,
    )
    manifest["scorer_config"]["value_decoder"]["support"] = replacement_support.model_dump_jsonable()
    scorer_config = TargetFiniteHorizonScorerConfig.model_validate(manifest["scorer_config"])
    manifest["scorer_config_hash"] = stable_config_hash(scorer_config, length=64)
    manifest["manifest_sha256"] = _manifest_hash(manifest)
    (bundle_dir / "manifest.json").write_text(
        json.dumps(manifest, sort_keys=True, indent=2) + "\n",
        encoding="utf-8",
    )
    tampered_ref = QhInferenceBundleRef(
        bundle_path=bundle_dir,
        schema_version=QH_INFERENCE_BUNDLE_SCHEMA_VERSION,
        manifest_sha256=manifest["manifest_sha256"],
    )

    with pytest.raises(ValueError, match=message):
        QhExperiment.load_for_inference(tampered_ref, device="cpu")


def test_qh_bundle_rejects_legacy_coral_support_without_provenance(tmp_path) -> None:
    base = _experiment()
    config = base.config.model_copy(
        deep=True,
        update={
            "scorer": base.config.scorer.model_copy(
                deep=True,
                update={
                    "value_decoder": QhCoralValueDecoderConfig(
                        support=QhLegacyFixedCoralSupport(
                            bin_edges=(-0.5, 0.5),
                            bin_values=(-1.0, 0.0, 1.0),
                        )
                    )
                },
            )
        },
    )
    experiment = config.setup_target()
    module_config, identity = _publish_contracts(experiment)
    bundle_dir = tmp_path / "legacy-coral-bundle"
    bundle_dir.mkdir()

    with pytest.raises(ValueError, match="inspection-only"):
        experiment._publish_bundle(  # noqa: SLF001
            bundle_dir,
            experiment.config.scorer.setup_target(),
            module_config=module_config,
            identity=identity,
            artifact_hashes=_stub_artifacts(bundle_dir),
        )


def test_qh_bundle_detects_manifest_and_state_mutation(tmp_path) -> None:
    _experiment_instance, ref = _bundle(tmp_path)
    manifest_path = ref.bundle_path / "manifest.json"
    original = manifest_path.read_text(encoding="utf-8")
    manifest_path.write_text(original.replace("qh_cf0_v1", "qh_cfplus_gt_depth_v1", 1), encoding="utf-8")
    with pytest.raises(ValueError, match="manifest hash"):
        QhExperiment.load_for_inference(ref, device="cpu")

    manifest_path.write_text(original, encoding="utf-8")
    state_path = ref.bundle_path / "scorer-state.pt"
    state_path.write_bytes(state_path.read_bytes() + b"tamper")
    with pytest.raises(ValueError, match="artifact 'scorer-state.pt' hash"):
        QhExperiment.load_for_inference(ref, device="cpu")


def test_qh_bundle_rejects_consistent_cfplus_tamper_without_privileged_marker(tmp_path) -> None:
    """Deployability follows the profile itself, not a bypassable bool."""

    _experiment_instance, ref = _bundle(tmp_path)
    manifest_path = ref.bundle_path / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    geometry_hash = "tampered-cfplus-geometry"
    manifest["scorer_config"]["experiment_profile"] = "qh_cfplus_gt_depth_v1"
    scorer_config = TargetFiniteHorizonScorerConfig.model_validate(manifest["scorer_config"])
    manifest["scorer_config_hash"] = stable_config_hash(scorer_config, length=64)
    manifest["module_config"].update(
        {
            "experiment_profile": "qh_cfplus_gt_depth_v1",
            "selected_observation_protocol": "cf_gt",
            "privileged": False,
            "geometry_contract_hash": geometry_hash,
        }
    )
    actor_payload = manifest["identity"]["actor_state_contract"]
    actor_payload.update(
        {
            "experiment_profile": "qh_cfplus_gt_depth_v1",
            "selected_observation_protocol": "cf_gt",
            "geometry_contract_hash": geometry_hash,
        }
    )
    actor_contract = QhActorStateContract(**actor_payload)
    actor_hash = stable_msgspec_hash(actor_contract)
    manifest["identity"]["actor_state_contract_hash"] = actor_hash
    manifest["identity"]["geometry_contract_hash"] = geometry_hash
    manifest["module_config"]["actor_state_contract_hash"] = actor_hash
    manifest["manifest_sha256"] = _manifest_hash(manifest)
    manifest_path.write_text(json.dumps(manifest, sort_keys=True, indent=2) + "\n", encoding="utf-8")
    tampered_ref = replace(ref, manifest_sha256=manifest["manifest_sha256"])

    with pytest.raises(ValueError, match="Deployable Q_H configuration rejects privileged"):
        QhExperiment.load_for_inference(tampered_ref, device="cpu")


def test_qh_bundle_rejects_rehashed_cf0_target_protocol_drift(tmp_path) -> None:
    """Deployable CF0 binds the observed target source through learning identity."""

    _experiment_instance, ref = _bundle(tmp_path)
    manifest_path = ref.bundle_path / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    learning_payload = manifest["identity"]["learning_contract"]
    learning_payload["data_contract"]["target_protocol"] = "v0_oracle_compatible"
    data_contract = QhDataContract(**learning_payload["data_contract"])
    learning_contract = QhLearningContract(
        data_contract=data_contract,
        max_horizon=int(learning_payload["max_horizon"]),
        horizon_weighting=str(learning_payload["horizon_weighting"]),
        objective_profile=learning_payload["objective_profile"],
    )
    learning_hash = stable_msgspec_hash(learning_contract)
    manifest["identity"]["learning_contract_hash"] = learning_hash
    manifest["module_config"]["learning_contract_hash"] = learning_hash
    manifest["manifest_sha256"] = _manifest_hash(manifest)
    manifest_path.write_text(json.dumps(manifest, sort_keys=True, indent=2) + "\n", encoding="utf-8")
    tampered_ref = replace(ref, manifest_sha256=manifest["manifest_sha256"])

    with pytest.raises(ValueError, match="requires target_protocol='v1_observed'"):
        QhExperiment.load_for_inference(tampered_ref, device="cpu")


def test_qh_bundle_rejects_missing_required_artifact(tmp_path) -> None:
    _experiment_instance, ref = _bundle(tmp_path)
    (ref.bundle_path / "training-receipt.json").unlink()

    with pytest.raises(ValueError, match="Cannot hash required Q_H bundle artifact"):
        QhExperiment.load_for_inference(ref, device="cpu")


def test_qh_bundle_strict_load_rejects_missing_state_key(tmp_path) -> None:
    _experiment_instance, ref = _bundle(tmp_path)
    state_path = ref.bundle_path / "scorer-state.pt"
    state = torch.load(state_path, map_location="cpu", weights_only=True)
    state.pop(next(iter(state)))
    torch.save(state, state_path)
    manifest_path = ref.bundle_path / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["artifacts"]["scorer-state.pt"]["sha256"] = hashlib.sha256(state_path.read_bytes()).hexdigest()
    manifest["manifest_sha256"] = _manifest_hash(manifest)
    manifest_path.write_text(json.dumps(manifest, sort_keys=True, indent=2) + "\n", encoding="utf-8")
    tampered_ref = replace(ref, manifest_sha256=manifest["manifest_sha256"])

    with pytest.raises(RuntimeError, match="Missing key"):
        QhExperiment.load_for_inference(tampered_ref, device="cpu")


@pytest.mark.parametrize(
    ("mutation", "message"),
    [
        ("missing_dependencies", "manifest fields"),
        ("dependency_drift", "dependency identity"),
        ("implementation_drift", "implementation identity"),
        ("missing_seed", "identity fields"),
        ("action_mask_drift", "action-mask semantics"),
        ("representation_drift", "representation semantics"),
    ],
)
def test_qh_bundle_rejects_recorded_identity_mutation(tmp_path, mutation: str, message: str) -> None:
    _experiment_instance, ref = _bundle(tmp_path)
    manifest_path = ref.bundle_path / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if mutation == "missing_dependencies":
        del manifest["dependencies"]
    elif mutation == "dependency_drift":
        manifest["dependencies"]["torch"] = "other"
    elif mutation == "implementation_drift":
        manifest["implementation"]["package_tree_sha256"] = "0" * 64
    elif mutation == "action_mask_drift":
        manifest["identity"]["action_mask_semantics"] = "actor_observed_action_mask_v1"
    elif mutation == "representation_drift":
        manifest["identity"]["representation_semantics"] = "other"
    else:
        del manifest["identity"]["seed"]
    manifest["manifest_sha256"] = _manifest_hash(manifest)
    manifest_path.write_text(json.dumps(manifest, sort_keys=True, indent=2) + "\n", encoding="utf-8")
    tampered_ref = replace(ref, manifest_sha256=manifest["manifest_sha256"])

    with pytest.raises(ValueError, match=message):
        QhExperiment.load_for_inference(tampered_ref, device="cpu")


def test_qh_bundle_dependencies_bind_exact_pytorch3d_vcs_identity() -> None:
    dependencies = qh_experiment_module._bundle_dependencies()  # noqa: SLF001

    assert dependencies["pytorch3d"] == "0.7.9"
    assert dependencies["pytorch3d_vcs_url"] == "https://github.com/facebookresearch/pytorch3d.git"
    assert dependencies["pytorch3d_vcs_commit"] == "b6a77ad7aaf41ed90fca80ce6a2bac3c462a7881"


def test_qh_bundle_dependencies_reject_moving_pytorch3d_runtime(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    direct_url = json.dumps(
        {
            "url": "https://github.com/facebookresearch/pytorch3d.git",
            "vcs_info": {
                "vcs": "git",
                "commit_id": "0" * 40,
                "requested_revision": "main",
            },
        }
    )
    distribution = SimpleNamespace(read_text=lambda name: direct_url if name == "direct_url.json" else None)
    monkeypatch.setattr(qh_experiment_module.importlib.metadata, "distribution", lambda _name: distribution)

    with pytest.raises(ValueError, match="does not match the exact project pin"):
        qh_experiment_module._installed_pytorch3d_vcs_commit()  # noqa: SLF001


def test_qh_bundle_rejects_learning_horizon_beyond_scorer_capacity(tmp_path) -> None:
    _experiment_instance, ref = _bundle(tmp_path)
    manifest_path = ref.bundle_path / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["scorer_config"]["max_horizon"] = 1
    scorer_config = TargetFiniteHorizonScorerConfig.model_validate(manifest["scorer_config"])
    manifest["scorer_config_hash"] = stable_config_hash(scorer_config, length=64)
    manifest["manifest_sha256"] = _manifest_hash(manifest)
    manifest_path.write_text(json.dumps(manifest, sort_keys=True, indent=2) + "\n", encoding="utf-8")
    tampered_ref = replace(ref, manifest_sha256=manifest["manifest_sha256"])

    with pytest.raises(ValueError, match="learning-contract max_horizon exceeds scorer max_horizon"):
        QhExperiment.load_for_inference(tampered_ref, device="cpu")


@pytest.mark.parametrize(
    "support",
    [
        {},
        {"2": {"state_count": 1, "candidate_count": 1}},
        {"1": {"state_count": 2, "candidate_count": 1}},
        {"1": {"state_count": 1, "candidate_count": 1}, "5": {"state_count": 1, "candidate_count": 1}},
    ],
)
def test_qh_bundle_rejects_invalid_trained_horizon_support(tmp_path, support: dict[str, object]) -> None:
    _experiment_instance, ref = _bundle(tmp_path)
    manifest_path = ref.bundle_path / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["identity"]["trained_horizon_support"] = support
    manifest["manifest_sha256"] = _manifest_hash(manifest)
    manifest_path.write_text(json.dumps(manifest, sort_keys=True, indent=2) + "\n", encoding="utf-8")
    tampered_ref = replace(ref, manifest_sha256=manifest["manifest_sha256"])

    with pytest.raises(ValueError, match="trained horizon|h=1 training support"):
        QhExperiment.load_for_inference(tampered_ref, device="cpu")


def test_qh_bundle_rejects_learned_feasibility_from_deployable_core(tmp_path) -> None:
    _experiment_instance, ref = _bundle(tmp_path)
    manifest_path = ref.bundle_path / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["identity"]["action_mask_semantics"] = "learned_feasibility_v1"
    manifest["manifest_sha256"] = _manifest_hash(manifest)
    manifest_path.write_text(json.dumps(manifest, sort_keys=True, indent=2) + "\n", encoding="utf-8")
    tampered_ref = replace(ref, manifest_sha256=manifest["manifest_sha256"])

    with pytest.raises(
        ValueError,
        match="learned_feasibility_v1|learned feasibility|deployable|action-mask semantics",
    ):
        QhExperiment.load_for_inference(tampered_ref, device="cpu")


@pytest.mark.parametrize(
    ("module_update", "message"),
    [
        ({"root_evl_profile": "none"}, "observation profiles differ"),
        ({"selected_observation_protocol": "cf_gt"}, "observation profiles differ"),
        ({"privileged": True}, "rejects privileged"),
    ],
)
def test_qh_bundle_rejects_module_actor_profile_drift(tmp_path, module_update, message: str) -> None:
    _experiment_instance, ref = _bundle(tmp_path)
    manifest_path = ref.bundle_path / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["module_config"].update(module_update)
    manifest["manifest_sha256"] = _manifest_hash(manifest)
    manifest_path.write_text(json.dumps(manifest, sort_keys=True, indent=2) + "\n", encoding="utf-8")
    tampered_ref = replace(ref, manifest_sha256=manifest["manifest_sha256"])

    with pytest.raises(ValueError, match=message):
        QhExperiment.load_for_inference(tampered_ref, device="cpu")


def test_qh_bundle_ref_and_selection_rule_are_closed_and_immutable(tmp_path) -> None:
    _experiment_instance, ref = _bundle(tmp_path)
    assert set(ref.__dataclass_fields__) == {"bundle_path", "schema_version", "manifest_sha256"}
    with pytest.raises(FrozenInstanceError):
        ref.schema_version = "other"  # type: ignore[misc]
    assert QhCheckpointSelectionSpec().monitor == "val/loss"
    with pytest.raises(ValueError, match="fixed to val/loss"):
        QhCheckpointSelectionSpec(monitor="train/loss")  # type: ignore[arg-type]


def test_qh_experiment_config_is_factory_without_running_fit() -> None:
    experiment = _experiment()
    assert isinstance(experiment, QhExperiment)
    assert experiment.config.target_type is QhExperiment


def test_qh_warm_start_requires_exact_learning_contract_hash(tmp_path) -> None:
    experiment, ref = _bundle(tmp_path)
    manifest = json.loads((ref.bundle_path / "manifest.json").read_text(encoding="utf-8"))
    identity = manifest["identity"]
    module_config = QhLightningModuleConfig.model_validate(manifest["module_config"])

    with pytest.raises(ValueError, match="learning_contract_hash"):
        experiment._warm_start_weights(  # noqa: SLF001
            ref,
            scorer=experiment.config.scorer.setup_target(),
            scorer_config=experiment.config.scorer,
            module_config=module_config,
            actor_state_contract_hash=identity["actor_state_contract_hash"],
            learning_contract_hash="different-learning-contract",
            target_protocol=identity["learning_contract"]["data_contract"]["target_protocol"],
            action_mask_semantics=identity["action_mask_semantics"],
            geometry_contract_hash=identity["geometry_contract_hash"],
        )


def test_qh_checkpoint_selection_breaks_exact_loss_tie_by_earliest_update(tmp_path) -> None:
    checkpoint_dir = tmp_path / "checkpoints"
    checkpoint_dir.mkdir()
    for name, loss_sum, rows, updates in (
        ("later.ckpt", 2.0, 2, 8),
        ("earlier.ckpt", 1.0, 1, 3),
        ("worse.ckpt", 1.5, 1, 1),
    ):
        torch.save(
            {
                "state_dict": {
                    "validation_loss_sum": torch.tensor(loss_sum, dtype=torch.float64),
                    "validation_row_count": torch.tensor(rows),
                    "optimizer_updates": torch.tensor(updates),
                }
            },
            checkpoint_dir / name,
        )

    selected, validation_loss, optimizer_updates = QhExperiment._selected_checkpoint(tmp_path)  # noqa: SLF001

    assert selected.name == "earlier.ckpt"
    assert validation_loss == 1.0
    assert optimizer_updates == 3


def test_qh_checkpoint_selection_fails_closed_on_malformed_candidate(tmp_path) -> None:
    checkpoint_dir = tmp_path / "checkpoints"
    checkpoint_dir.mkdir()
    torch.save(
        {
            "state_dict": {
                "validation_loss_sum": torch.tensor(1.0),
                "optimizer_updates": torch.tensor(1),
            }
        },
        checkpoint_dir / "malformed.ckpt",
    )
    torch.save(
        {
            "state_dict": {
                "validation_loss_sum": torch.tensor(1.0),
                "validation_row_count": torch.tensor(1),
                "optimizer_updates": torch.tensor(2),
            }
        },
        checkpoint_dir / "valid.ckpt",
    )

    with pytest.raises(ValueError, match="malformed.ckpt.*validation_row_count"):
        QhExperiment._selected_checkpoint(tmp_path)  # noqa: SLF001


class _DatasetConfig:
    def __init__(self, path: Path, dataset: _ChainDataset) -> None:
        self.rollout_store_dirs = (path,)
        self._dataset = dataset

    def setup_target(self) -> _ChainDataset:
        return self._dataset


def _dense_dataset(scene: str, offset: int) -> _ChainDataset:
    chain = _chain(steps=2, width=3, offset=offset)
    chain = replace(
        chain,
        key=replace(
            chain.key,
            scene_id=scene,
            configured_horizon=2,
            candidate_width_min=3,
            candidate_width_max=3,
            candidate_config_hash="candidate-test-v1",
            rollout_config_hash="rollout-test-v1",
            selection_policy="q_h",
        ),
    )
    dataset = _ChainDataset([chain], scene=scene)
    dataset.contract = QhDataContract(
        schema_version="qh-v1",
        target_protocol="v1_observed",
        reward_metric="target-root-gain",
        return_semantics="finite-horizon",
        td_semantics="fitted-q",
        discount_gamma=0.95,
        reason_code_version="reasons-v1",
        actor_store_version="vin-v1",
        candidate_config_hashes=("candidate-test-v1",),
        rollout_config_hashes=("rollout-test-v1",),
        selection_policies=("q_h",),
        oracle_query_mode="dense_valid",
        label_support_semantics="equals_action_on_realized_steps_v1",
    )
    return dataset


def _publish_contracts(experiment: QhExperiment) -> tuple[QhLightningModuleConfig, dict[str, object]]:
    dataset = _dense_dataset("bundle", 0)
    actor_contract = dataset.actor_state_contract
    learning_contract = QhLearningContract(
        data_contract=dataset.contract,
        max_horizon=dataset.max_horizon,
        objective_profile="qh_dense_valid_fitted_q_v1",
    )
    actor_hash = stable_msgspec_hash(actor_contract)
    learning_hash = stable_msgspec_hash(learning_contract)
    module = experiment.config.module.model_copy(
        deep=True,
        update={
            "actor_state_contract_hash": actor_hash,
            "learning_contract_hash": learning_hash,
            "geometry_contract_hash": actor_contract.geometry_contract_hash,
            "max_horizon": experiment.config.scorer.max_horizon,
        },
    )
    stages = {"train": {"kind": "test"}, "validation": {"kind": "test"}, "test": {"kind": "test"}}
    return module, {
        "actor_state_contract": actor_contract,
        "actor_state_contract_hash": actor_hash,
        "learning_contract": learning_contract,
        "learning_contract_hash": learning_hash,
        "geometry_contract_hash": actor_contract.geometry_contract_hash,
        "datasets": stages,
        "dataset_provenance": stages,
        "ordered_store_manifests": {"train": [], "validation": [], "test": []},
        "ordered_store_paths": {"train": [], "validation": [], "test": []},
        "warm_start_parent_manifest_sha256": None,
        "action_mask_semantics": dataset.contract.action_mask_semantics,
        "representation_semantics": experiment.config.scorer.representation_semantics,
        "trained_horizon_support": {
            "1": {"state_count": 2, "candidate_count": 6},
            "2": {"state_count": 1, "candidate_count": 1},
        },
        "seed": 0,
    }


def _stub_artifacts(bundle_dir: Path) -> dict[str, str]:
    payloads = {
        "training-receipt.json": b'{"schema_version":"test"}\n',
        "checkpoint-selection-receipt.json": b'{"schema_version":"test"}\n',
    }
    hashes: dict[str, str] = {}
    for name, payload in payloads.items():
        (bundle_dir / name).write_bytes(payload)
        hashes[name] = hashlib.sha256(payload).hexdigest()
    return hashes


def test_qh_fit_publishes_new_bundle_and_hashed_receipts(tmp_path) -> None:
    base = _experiment().config
    trainer = TrainerFactoryConfig(
        accelerator="cpu",
        devices=1,
        max_epochs=1,
        deterministic=True,
        use_wandb=False,
        enable_validation=True,
        limit_train_batches=1,
        limit_val_batches=1,
        num_sanity_val_steps=0,
        callbacks=base.trainer.callbacks,
    )
    experiment = base.model_copy(deep=True, update={"trainer": trainer}).setup_target()
    train_dataset = _dense_dataset("train", 0)
    validation_dataset = _dense_dataset("val", 20)
    validation_dataset.contract = replace(
        validation_dataset.contract,
        rollout_config_hashes=("rollout-validation-v1",),
    )
    test_dataset = _dense_dataset("test", 40)
    test_dataset.contract = replace(
        test_dataset.contract,
        rollout_config_hashes=("rollout-test-v1",),
    )
    request = QhFitRequest(
        train=_DatasetConfig(tmp_path / "train.zarr", train_dataset),  # type: ignore[arg-type]
        validation=_DatasetConfig(tmp_path / "val.zarr", validation_dataset),  # type: ignore[arg-type]
        test=_DatasetConfig(tmp_path / "test.zarr", test_dataset),  # type: ignore[arg-type]
        warm_start_from=None,
        checkpoint_selection=QhCheckpointSelectionSpec(),
        seed=23,
        output_bundle_dir=tmp_path / "published",
    )

    result = experiment.fit(request)
    runtime = QhExperiment.load_for_inference(result.bundle, device="cpu")

    assert result.bundle.bundle_path == (tmp_path / "published").resolve()
    assert result.training_receipt_path.is_file()
    assert result.checkpoint_selection_receipt_path.is_file()
    assert not (result.bundle.bundle_path / "resume.ckpt").exists()
    assert runtime.scorer.training is False
    training_receipt = json.loads(result.training_receipt_path.read_text(encoding="utf-8"))
    assert training_receipt["warm_start_parent_manifest_sha256"] is None
    assert "test_loss" not in training_receipt
    assert training_receipt["target_descriptor_identity"] == {
        stage: dataset.target_descriptor_identity
        for stage, dataset in {
            "train": train_dataset,
            "validation": validation_dataset,
            "test": test_dataset,
        }.items()
    }

    held_out = experiment.evaluate_held_out(
        QhHeldOutEvaluationRequest(
            bundle=result.bundle,
            test=request.test,
            output_receipt_path=tmp_path / "held-out.json",
        )
    )
    held_out_receipt = json.loads(held_out.receipt_path.read_text(encoding="utf-8"))
    assert held_out_receipt["diagnostic_only"] is True
    assert held_out_receipt["endpoint_policy_evidence"] is False
    assert held_out_receipt["target_descriptor_identity"] == test_dataset.target_descriptor_identity
    assert (
        held_out_receipt["test_provenance_sha256"]
        == hashlib.sha256(
            json.dumps(test_dataset.provenance, sort_keys=True, separators=(",", ":")).encode("utf-8")
        ).hexdigest()
    )
    assert held_out_receipt["ordered_store_manifest_sha256s"] == []
    assert held_out_receipt["bound_contract"] == {
        "learning_contract_hash": training_receipt["learning_contract_hash"],
        "actor_state_contract_hash": training_receipt["actor_state_contract_hash"],
        "geometry_contract_hash": test_dataset.actor_state_contract.geometry_contract_hash,
    }

    certification = experiment.certify_exact_q2(
        QhExactQ2CertificationRequest(
            bundle=result.bundle,
            test=request.test,
            spec=QhExactQ2CertificationSpec(
                absolute_tolerance=1e-5,
                relative_tolerance=1e-5,
                minimum_independent_units=5,
                minimum_exact_rows_per_independent_unit=1,
                independent_unit_aggregation="all_units_v1",
                minimum_population_coverage=1.0,
            ),
            output_receipt_path=tmp_path / "exact-q2.json",
        )
    )
    certification_receipt = json.loads(certification.receipt_path.read_text(encoding="utf-8"))
    assert certification_receipt["bundle_manifest_sha256"] == result.bundle.manifest_sha256
    assert certification_receipt["exact_q2"]["population_census"]["near_exhaustive"] is True
    assert certification_receipt["exact_q2"]["aggregate"]["factual_selected_action_exact_q2_row_count"] == 1
    assert certification_receipt["schema_version"] == "qh-exact-q2-certification-receipt-v3"
    assert certification_receipt["exact_q2"]["independent_unit_gate"]["selected_independent_unit_count"] == 1
    assert certification_receipt["exact_q2"]["independent_unit_gate"]["minimum_independent_units_met"] is False
    assert certification_receipt["oracle_headroom"]["available"] is False
    assert certification_receipt["longer_horizon_gate"]["independent_positive_headroom"] is False
    assert certification_receipt["longer_horizon_gate"]["passed"] is False
    with pytest.raises(FileExistsError, match="already exists"):
        experiment.certify_exact_q2(
            QhExactQ2CertificationRequest(
                bundle=result.bundle,
                test=request.test,
                spec=QhExactQ2CertificationSpec(
                    absolute_tolerance=1e-5,
                    relative_tolerance=1e-5,
                    minimum_independent_units=5,
                    minimum_exact_rows_per_independent_unit=1,
                    independent_unit_aggregation="all_units_v1",
                ),
                output_receipt_path=certification.receipt_path,
            )
        )
    with pytest.raises(FileExistsError, match="already exists"):
        experiment.fit(request)

    repeated = experiment.fit(
        replace(
            request,
            warm_start_from=result.bundle,
            output_bundle_dir=tmp_path / "published-again",
        )
    )
    repeated_receipt = json.loads(repeated.training_receipt_path.read_text(encoding="utf-8"))
    assert repeated_receipt["warm_start_parent_manifest_sha256"] == result.bundle.manifest_sha256
    assert repeated_receipt["optimizer_updates"] == training_receipt["optimizer_updates"]

    test_dataset.provenance = {"scene": "same-path-replacement"}
    drift_receipt = tmp_path / "held-out-after-replacement.json"
    with pytest.raises(ValueError, match="held-out diagnostic test provenance drifted"):
        experiment.evaluate_held_out(
            QhHeldOutEvaluationRequest(
                bundle=result.bundle,
                test=request.test,
                output_receipt_path=drift_receipt,
            )
        )
    assert not drift_receipt.exists()
