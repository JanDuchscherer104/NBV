"""Composition tests for the dedicated Q_H experiment."""

# ruff: noqa: S101

import json
from pathlib import Path

import pytest
import torch
from pydantic import ValidationError

from aria_nbv.data_handling.offline.store import VinOfflineStoreConfig
from aria_nbv.data_handling.qh import QhDatasetConfig
from aria_nbv.lightning import qh_experiment
from aria_nbv.lightning.lit_trainer_factory import TrainerFactoryConfig
from aria_nbv.lightning.qh_datamodule import QhDataModuleConfig
from aria_nbv.lightning.qh_experiment import QhExperimentConfig
from aria_nbv.lightning.qh_module import QhLightningModuleConfig
from aria_nbv.rollouts.qh_reader import QhRolloutReaderConfig
from aria_nbv.utils import Stage
from aria_nbv.utils.fingerprints import stable_config_hash


def _data(tmp_path: Path, *, val: bool = False, test: bool = False) -> QhDataModuleConfig:
    def dataset(split: str) -> QhDatasetConfig:
        return QhDatasetConfig(
            rollout=QhRolloutReaderConfig(store_dirs=(tmp_path / f"rollouts-{split}",)),
            actor=VinOfflineStoreConfig(store_dir=tmp_path / "vin"),
            split=split,
        )

    return QhDataModuleConfig(
        train=dataset("train"),
        val=dataset("val") if val else None,
        test=dataset("val") if test else None,
    )


def _trainer(**kwargs: object) -> TrainerFactoryConfig:
    return TrainerFactoryConfig(
        use_distributed_sampler=True,
        gradient_clip_val=None,
        accumulate_grad_batches=1,
        use_wandb=False,
        **kwargs,
    )


class _Data:
    training_horizon = 2
    batch_size = 4

    def __init__(self, events: list[str]) -> None:
        self.events = events
        self.train_dataset = [object()] * 4
        self.val_dataset = [object()]
        self.test_dataset = [object()]

    @property
    def provenance(self) -> dict[str, object]:
        return {"train": {"manifest": "abc"}, "val": None, "test": None}

    @property
    def learning_contract(self) -> dict[str, object]:
        return {
            "rollout": {
                "schema_version": "qh-rollout-v1",
                "q_h_horizon": self.training_horizon,
                "discount_gamma": 0.9,
                "split_manifest_hash": "split-abc",
            },
            "actor": {"store_version": "vin-offline-v7", "manifest_hash": "actor-abc"},
        }

    def dataset_for_stage(self, stage: Stage) -> object | None:
        return {
            Stage.TRAIN: self.train_dataset,
            Stage.VAL: self.val_dataset,
            Stage.TEST: self.test_dataset,
        }[stage]

    def setup(self, stage: str) -> None:
        self.events.append(f"data.setup:{stage}")


def test_default_trainer_is_safe_for_manual_optimization(tmp_path: Path) -> None:
    config = QhExperimentConfig(datamodule_config=_data(tmp_path))

    assert config.trainer_config.use_distributed_sampler is True
    assert config.trainer_config.gradient_clip_val is None
    assert config.trainer_config.accumulate_grad_batches == 1


@pytest.mark.parametrize("seed", [-1, 2**32])
def test_seed_rejects_values_outside_unsigned_32_bit_range(tmp_path: Path, seed: int) -> None:
    with pytest.raises(ValidationError) as error:
        QhExperimentConfig(datamodule_config=_data(tmp_path), seed=seed)

    assert error.value.errors()[0]["loc"] == ("seed",)


@pytest.mark.parametrize("seed", [0, 2**32 - 1])
def test_seed_accepts_unsigned_32_bit_boundaries(tmp_path: Path, seed: int) -> None:
    assert QhExperimentConfig(datamodule_config=_data(tmp_path), seed=seed).seed == seed


@pytest.mark.parametrize("value", [float("nan"), float("inf"), float("-inf")])
def test_experiment_propagates_shared_optimizer_finiteness(tmp_path: Path, value: float) -> None:
    with pytest.raises(ValidationError) as error:
        QhExperimentConfig.model_validate(
            {
                "datamodule_config": _data(tmp_path),
                "module_config": {"optimizer": {"learning_rate": value}},
            }
        )

    assert error.value.errors()[0]["loc"] == ("module_config", "optimizer", "learning_rate")


@pytest.mark.parametrize(
    ("override", "message"),
    [
        ({"use_distributed_sampler": False}, "default distributed sampler"),
        ({"gradient_clip_val": 1.0}, "None or zero"),
        ({"accumulate_grad_batches": 2}, "accumulate_grad_batches=1"),
    ],
)
def test_experiment_rejects_conflicting_trainer_ownership(
    tmp_path: Path,
    override: dict[str, object],
    message: str,
) -> None:
    values = {
        "use_distributed_sampler": True,
        "gradient_clip_val": None,
        "accumulate_grad_batches": 1,
        **override,
    }
    with pytest.raises(ValueError, match=message):
        QhExperimentConfig(datamodule_config=_data(tmp_path), trainer_config=TrainerFactoryConfig(**values))


@pytest.mark.parametrize(
    ("stage", "method", "setup_name"),
    [(Stage.TRAIN, "fit", "fit"), (Stage.VAL, "validate", "validate"), (Stage.TEST, "test", "test")],
)
def test_stage_dispatch_forwards_checkpoint_exactly(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    stage: Stage,
    method: str,
    setup_name: str,
) -> None:
    checkpoint = tmp_path / "resume.ckpt"
    checkpoint.touch()
    trainer_config = _trainer(enable_validation=stage is Stage.VAL)
    config = QhExperimentConfig(
        stage=stage,
        ckpt_path=checkpoint,
        datamodule_config=_data(tmp_path, val=True, test=True),
        trainer_config=trainer_config,
    )
    calls: list[tuple[str, object]] = []

    class _Trainer:
        is_global_zero = False

        def fit(self, module, *, datamodule, ckpt_path):
            calls.append(("fit", ckpt_path))

        def validate(self, module, *, datamodule, ckpt_path):
            calls.append(("validate", ckpt_path))

        def test(self, module, *, datamodule, ckpt_path):
            calls.append(("test", ckpt_path))

    data = _Data([])
    monkeypatch.setattr(QhExperimentConfig, "setup_target", lambda self, setup_stage: (_Trainer(), object(), data))

    returned = config.setup_target_and_run()

    assert isinstance(returned, _Trainer)
    assert calls == [(method, str(checkpoint.resolve()))]
    assert setup_name


def test_removed_field_names_are_rejected(tmp_path: Path) -> None:
    for field in ("output_dir", "resume_checkpoint", "trainer", "data", "module"):
        with pytest.raises(ValueError, match=field):
            QhExperimentConfig.model_validate({"datamodule_config": _data(tmp_path), field: None})
    assert not hasattr(QhExperimentConfig, "run")


def test_strict_toml_rejects_unknown_nested_keys(tmp_path: Path) -> None:
    config_path = tmp_path / "bad.toml"
    config_path.write_text(
        """
[trainer_config]
use_distributed_sampler = true
gradient_clip_val = 0
unknown_nested = true
[datamodule_config]
[datamodule_config.train.rollout]
store_dirs = ["/tmp/rollouts"]
[datamodule_config.train.actor]
store_dir = "/tmp/vin"
"""
    )

    with pytest.raises(ValueError, match="unknown_nested"):
        QhExperimentConfig.from_toml(config_path)


@pytest.mark.parametrize("name", ["train_qh_v0_smoke.toml", "train_qh_v0_lrz.template.toml"])
def test_repo_qh_configs_match_current_dataset_shape(name: str) -> None:
    config_path = Path(__file__).resolve().parents[3] / ".configs" / name

    config = QhExperimentConfig.from_toml(config_path)

    assert config.datamodule_config.train.split is Stage.TRAIN
    assert config.datamodule_config.train.actor.store_dir.name == "vin-offline-v7"


def test_lightning_readme_matches_qh_runtime_contracts() -> None:
    readme = (Path(__file__).resolve().parents[2] / "aria_nbv" / "lightning" / "README.md").read_text()

    assert "`data_handling.qh.QhInputs`" in readme
    assert "QhActorInputs" not in readme
    assert "Lightning-partitioned train/validation/test loaders" in readme
    assert "reported metrics" in readme
    assert "replicated exact" not in readme
    assert "`run_manifest.json`" in readme
    assert "does not claim the Trainer's actual topology" in readme
    assert "`run_result.json`" in readme
    assert "success or failure" in readme


def test_setup_admits_without_eager_datamodule_setup_and_writes_manifest_before_runtime(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    events: list[str] = []
    data = _Data(events)
    config = QhExperimentConfig(out_dir=tmp_path / "run", datamodule_config=_data(tmp_path))
    monkeypatch.setenv("LRZ_CONTAINER_IMAGE", "registry.example/aria@sha256:exact")
    monkeypatch.setenv("SLURM_JOB_ID", "48151623")
    monkeypatch.setattr(
        qh_experiment.pl, "seed_everything", lambda seed, *, workers: events.append(f"seed:{seed}:{workers}")
    )
    monkeypatch.setattr(QhDataModuleConfig, "setup_target", lambda self, *, seed: data)
    monkeypatch.setattr(
        QhLightningModuleConfig,
        "setup_target",
        lambda self, *, learning_contract: events.append("module") or object(),
    )
    monkeypatch.setattr(TrainerFactoryConfig, "setup_target", lambda self: events.append("trainer") or object())
    original_write = qh_experiment._create_json

    def record_write(path: Path, payload: dict[str, object]) -> None:
        events.append("manifest")
        original_write(path, payload)

    monkeypatch.setattr(qh_experiment, "_create_json", record_write)

    config.setup_target()

    assert events == ["seed:0:False", "manifest", "module", "trainer"]
    manifest = json.loads((tmp_path / "run" / "run_manifest.json").read_text())
    assert manifest["config_hash"]
    assert manifest["corpus"] == data.provenance
    assert "world_size" not in manifest["run"]
    assert "effective_emitted_batch_size" not in manifest["run"]
    assert "training_padding_rows" not in manifest["run"]
    assert manifest["run"]["container_image"] == "registry.example/aria@sha256:exact"
    assert manifest["run"]["launcher_kind"] == "slurm-torchrun"
    assert manifest["run"]["slurm_job_id"] == "48151623"


def test_manifest_write_failure_prevents_module_and_trainer(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    events: list[str] = []
    config = QhExperimentConfig(out_dir=tmp_path / "run", datamodule_config=_data(tmp_path))
    monkeypatch.setattr(QhDataModuleConfig, "setup_target", lambda self, *, seed: _Data(events))
    monkeypatch.setattr(qh_experiment, "_create_json", lambda *args: (_ for _ in ()).throw(OSError("full")))
    monkeypatch.setattr(
        QhLightningModuleConfig,
        "setup_target",
        lambda self, *, learning_contract: events.append("module"),
    )
    monkeypatch.setattr(TrainerFactoryConfig, "setup_target", lambda self: events.append("trainer"))

    with pytest.raises(OSError, match="full"):
        config.setup_target()

    assert events == []


def test_nonzero_launcher_rank_skips_manifest_write(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    events: list[str] = []
    config = QhExperimentConfig(out_dir=tmp_path / "run", datamodule_config=_data(tmp_path))
    monkeypatch.setenv("RANK", "1")
    monkeypatch.setattr(QhDataModuleConfig, "setup_target", lambda self, *, seed: _Data(events))
    monkeypatch.setattr(qh_experiment, "_create_json", lambda *args: events.append("manifest"))
    monkeypatch.setattr(QhLightningModuleConfig, "setup_target", lambda self, *, learning_contract: object())
    monkeypatch.setattr(TrainerFactoryConfig, "setup_target", lambda self: object())

    config.setup_target()

    assert events == []


@pytest.mark.parametrize(("stage", "attr"), [(Stage.VAL, "val"), (Stage.TEST, "test")])
def test_missing_requested_eval_stage_fails_before_module_or_trainer(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    stage: Stage,
    attr: str,
) -> None:
    events: list[str] = []
    data = _Data(events)
    setattr(data, f"{attr}_dataset", None)
    checkpoint = tmp_path / "parent.ckpt"
    config = QhExperimentConfig(
        stage=stage,
        ckpt_path=checkpoint,
        datamodule_config=_data(tmp_path),
        trainer_config=_trainer(enable_validation=stage is Stage.VAL),
    )
    _write_checkpoint(checkpoint, config, data)
    monkeypatch.setattr(QhDataModuleConfig, "setup_target", lambda self, *, seed: data)
    monkeypatch.setattr(QhLightningModuleConfig, "setup_target", lambda self: events.append("module"))
    monkeypatch.setattr(TrainerFactoryConfig, "setup_target", lambda self: events.append("trainer"))

    with pytest.raises(ValueError, match=f"requires a configured {stage}"):
        config.setup_target()

    assert events == []


def test_validation_override_rejects_disabled_validation_before_data_setup(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    events: list[str] = []
    config = QhExperimentConfig(datamodule_config=_data(tmp_path, val=True), trainer_config=_trainer())
    monkeypatch.setattr(QhDataModuleConfig, "setup_target", lambda self, *, seed: events.append("data"))

    with pytest.raises(ValueError, match="enable_validation=true"):
        config.setup_target(Stage.VAL)

    assert events == []


@pytest.mark.parametrize("stage", [Stage.VAL, Stage.TEST])
def test_standalone_evaluation_requires_checkpoint_before_data_setup(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    stage: Stage,
) -> None:
    events: list[str] = []
    config = QhExperimentConfig(
        stage=stage,
        datamodule_config=_data(tmp_path, val=True, test=True),
        trainer_config=_trainer(enable_validation=stage is Stage.VAL),
    )
    monkeypatch.setattr(QhDataModuleConfig, "setup_target", lambda self, *, seed: events.append("data"))

    with pytest.raises(ValueError, match="requires ckpt_path"):
        config.setup_target()

    assert events == []


def _write_checkpoint(
    path: Path,
    config: QhExperimentConfig,
    data: _Data,
    *,
    module_config: dict[str, object] | None = None,
    learning_contract: dict[str, object] | None = None,
) -> None:
    torch.save(
        {
            "state_dict": {},
            "hyper_parameters": {
                "config": config.module_config.model_dump_jsonable() if module_config is None else module_config,
                "learning_contract": data.learning_contract if learning_contract is None else learning_contract,
            },
        },
        path,
    )


@pytest.mark.parametrize("mismatch", ["module", "corpus"])
def test_checkpoint_semantic_mismatch_fails_before_module_or_trainer(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    mismatch: str,
) -> None:
    events: list[str] = []
    data = _Data(events)
    checkpoint = tmp_path / "parent.ckpt"
    config = QhExperimentConfig(
        ckpt_path=checkpoint,
        datamodule_config=_data(tmp_path),
    )
    module_config = config.module_config.model_dump_jsonable()
    learning_contract = data.learning_contract
    if mismatch == "module":
        module_config["huber_delta"] = 2.0
    else:
        learning_contract["rollout"]["discount_gamma"] = 0.5
    _write_checkpoint(
        checkpoint,
        config,
        data,
        module_config=module_config,
        learning_contract=learning_contract,
    )
    monkeypatch.setattr(QhDataModuleConfig, "setup_target", lambda self, *, seed: data)
    monkeypatch.setattr(
        QhLightningModuleConfig,
        "setup_target",
        lambda self, *, learning_contract: events.append("module"),
    )
    monkeypatch.setattr(TrainerFactoryConfig, "setup_target", lambda self: events.append("trainer"))

    with pytest.raises(ValueError, match="hyper_parameters do not match"):
        config.setup_target()

    assert events == []


def test_unreadable_checkpoint_fails_before_runtime_construction(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    events: list[str] = []
    checkpoint = tmp_path / "parent.ckpt"
    checkpoint.write_bytes(b"not a checkpoint")
    config = QhExperimentConfig(ckpt_path=checkpoint, datamodule_config=_data(tmp_path))
    monkeypatch.setattr(QhDataModuleConfig, "setup_target", lambda self, *, seed: _Data(events))
    monkeypatch.setattr(
        QhLightningModuleConfig,
        "setup_target",
        lambda self, *, learning_contract: events.append("module"),
    )
    monkeypatch.setattr(TrainerFactoryConfig, "setup_target", lambda self: events.append("trainer"))

    with pytest.raises(ValueError, match="readable full-state"):
        config.setup_target()

    assert events == []


def test_stage_override_controls_manifest_config_and_hash(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    data = _Data([])
    checkpoint = tmp_path / "parent.ckpt"
    config = QhExperimentConfig(
        stage=Stage.TRAIN,
        out_dir=tmp_path / "run",
        ckpt_path=checkpoint,
        datamodule_config=_data(tmp_path, test=True),
    )
    _write_checkpoint(checkpoint, config, data)
    monkeypatch.setattr(QhDataModuleConfig, "setup_target", lambda self, *, seed: data)
    monkeypatch.setattr(QhLightningModuleConfig, "setup_target", lambda self, *, learning_contract: object())
    monkeypatch.setattr(TrainerFactoryConfig, "setup_target", lambda self: object())

    config.setup_target(Stage.TEST)

    manifest = json.loads((tmp_path / "run" / "run_manifest.json").read_text())
    effective = QhExperimentConfig.model_validate(manifest["config"])
    assert manifest["config"]["stage"] == "test"
    assert manifest["config_hash"] == stable_config_hash(effective)
    assert manifest["checkpoint"]["parent_reference"] == str(checkpoint.resolve())
    assert len(manifest["checkpoint"]["sha256"]) == 64


def test_manifest_is_create_only(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    events: list[str] = []
    data = _Data(events)
    out_dir = tmp_path / "run"
    config = QhExperimentConfig(out_dir=out_dir, datamodule_config=_data(tmp_path))
    monkeypatch.setattr(QhDataModuleConfig, "setup_target", lambda self, *, seed: data)
    monkeypatch.setattr(
        QhLightningModuleConfig,
        "setup_target",
        lambda self, *, learning_contract: events.append("module") or object(),
    )
    monkeypatch.setattr(TrainerFactoryConfig, "setup_target", lambda self: events.append("trainer") or object())

    config.setup_target()
    original = (out_dir / "run_manifest.json").read_bytes()
    with pytest.raises(FileExistsError):
        config.setup_target()

    assert (out_dir / "run_manifest.json").read_bytes() == original
    assert events == ["module", "trainer"]


@pytest.mark.parametrize("fail", [False, True])
def test_run_result_records_terminal_status_and_actual_topology(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    fail: bool,
) -> None:
    data = _Data([])
    out_dir = tmp_path / "run"
    out_dir.mkdir()
    checkpoint = tmp_path / "parent.ckpt"
    checkpoint.write_bytes(b"checkpoint contents")
    best_checkpoint = tmp_path / "best.ckpt"
    best_checkpoint.write_bytes(b"best checkpoint contents")
    last_checkpoint = tmp_path / "last.ckpt"
    last_checkpoint.write_bytes(b"last checkpoint contents")
    config = QhExperimentConfig(out_dir=out_dir, ckpt_path=checkpoint, datamodule_config=_data(tmp_path))

    class _Trainer:
        is_global_zero = True
        world_size = 3
        global_step = 7
        checkpoint_callback = type(
            "_CheckpointCallback",
            (),
            {"best_model_path": str(best_checkpoint), "last_model_path": str(last_checkpoint)},
        )()

        def fit(self, module, *, datamodule, ckpt_path):
            assert ckpt_path == str(checkpoint.resolve())
            if fail:
                raise RuntimeError("loop failed")

    trainer = _Trainer()
    monkeypatch.setattr(QhExperimentConfig, "setup_target", lambda self, setup_stage: (trainer, object(), data))

    if fail:
        with pytest.raises(RuntimeError, match="loop failed"):
            config.setup_target_and_run()
    else:
        assert config.setup_target_and_run() is trainer

    result = json.loads((out_dir / "run_result.json").read_text())
    assert result["status"] == ("failure" if fail else "success")
    assert result["run"]["world_size"] == 3
    assert result["run"]["global_step"] == 7
    assert result["run"]["effective_emitted_batch_size"] == 12
    assert result["run"]["padding_rows"] == 2
    assert result["run"]["padding_fraction"] == pytest.approx(1 / 3)
    assert result["checkpoint"]["parent"]["parent_reference"] == str(checkpoint.resolve())
    assert result["checkpoint"]["evaluated"] is None
    assert result["checkpoint"]["best"]["parent_reference"] == str(best_checkpoint.resolve())
    assert result["checkpoint"]["last"]["parent_reference"] == str(last_checkpoint.resolve())
    assert len(result["checkpoint"]["parent"]["sha256"]) == 64
    assert result["error"] is not None if fail else result["error"] is None


def test_run_result_is_create_only(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    data = _Data([])
    out_dir = tmp_path / "run"
    out_dir.mkdir()
    result_path = out_dir / "run_result.json"
    result_path.write_text('{"status": "prior"}\n')
    original = result_path.read_bytes()
    config = QhExperimentConfig(out_dir=out_dir, datamodule_config=_data(tmp_path))

    class _Trainer:
        is_global_zero = True
        world_size = 1
        global_step = 1
        checkpoint_callback = None

        def fit(self, module, *, datamodule, ckpt_path):
            return None

    monkeypatch.setattr(QhExperimentConfig, "setup_target", lambda self, setup_stage: (_Trainer(), object(), data))

    with pytest.raises(FileExistsError):
        config.setup_target_and_run()

    assert result_path.read_bytes() == original
