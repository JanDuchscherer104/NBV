"""Composition tests for the dedicated Q_H experiment."""

# ruff: noqa: S101

import json
from pathlib import Path

import pytest
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
    trainer_config = _trainer(enable_validation=stage is Stage.VAL)
    config = QhExperimentConfig(
        stage=stage,
        ckpt_path=checkpoint,
        datamodule_config=_data(tmp_path, val=True, test=True),
        trainer_config=trainer_config,
    )
    calls: list[tuple[str, object]] = []

    class _Trainer:
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


def test_setup_admits_without_eager_datamodule_setup_and_writes_manifest_before_runtime(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    events: list[str] = []
    data = _Data(events)
    config = QhExperimentConfig(out_dir=tmp_path / "run", datamodule_config=_data(tmp_path))
    monkeypatch.setenv("LRZ_CONTAINER_IMAGE", "registry.example/aria@sha256:exact")
    monkeypatch.setenv("WORLD_SIZE", "3")
    monkeypatch.setenv("SLURM_JOB_ID", "48151623")
    monkeypatch.setattr(
        qh_experiment.pl, "seed_everything", lambda seed, *, workers: events.append(f"seed:{seed}:{workers}")
    )
    monkeypatch.setattr(QhDataModuleConfig, "setup_target", lambda self, *, seed: data)
    monkeypatch.setattr(QhLightningModuleConfig, "setup_target", lambda self: events.append("module") or object())
    monkeypatch.setattr(TrainerFactoryConfig, "setup_target", lambda self: events.append("trainer") or object())
    original_write = qh_experiment._atomic_write_json

    def record_write(path: Path, payload: dict[str, object]) -> None:
        events.append("manifest")
        original_write(path, payload)

    monkeypatch.setattr(qh_experiment, "_atomic_write_json", record_write)

    config.setup_target()

    assert events == ["seed:0:False", "manifest", "module", "trainer"]
    manifest = json.loads((tmp_path / "run" / "run_manifest.json").read_text())
    assert manifest["config_hash"]
    assert manifest["corpus"] == data.provenance
    assert manifest["run"]["launched_world_size"] == 3
    assert manifest["run"]["effective_emitted_batch_size"] == 12
    assert manifest["run"]["training_padding_rows"] == 2
    assert manifest["run"]["training_padding_fraction"] == pytest.approx(1 / 3)
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
    monkeypatch.setattr(qh_experiment, "_atomic_write_json", lambda *args: (_ for _ in ()).throw(OSError("full")))
    monkeypatch.setattr(QhLightningModuleConfig, "setup_target", lambda self: events.append("module"))
    monkeypatch.setattr(TrainerFactoryConfig, "setup_target", lambda self: events.append("trainer"))

    with pytest.raises(OSError, match="full"):
        config.setup_target()

    assert events == []


def test_nonzero_launcher_rank_skips_manifest_write(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    events: list[str] = []
    config = QhExperimentConfig(out_dir=tmp_path / "run", datamodule_config=_data(tmp_path))
    monkeypatch.setenv("RANK", "1")
    monkeypatch.setattr(QhDataModuleConfig, "setup_target", lambda self, *, seed: _Data(events))
    monkeypatch.setattr(qh_experiment, "_atomic_write_json", lambda *args: events.append("manifest"))
    monkeypatch.setattr(QhLightningModuleConfig, "setup_target", lambda self: object())
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
    config = QhExperimentConfig(
        stage=stage,
        datamodule_config=_data(tmp_path),
        trainer_config=_trainer(enable_validation=stage is Stage.VAL),
    )
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
