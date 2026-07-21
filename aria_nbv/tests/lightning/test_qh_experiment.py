"""Composition tests for the dedicated Q_H experiment."""

# ruff: noqa: S101

from pathlib import Path

import pytest

from aria_nbv.data_handling.offline.actor import VinActorSourceConfig
from aria_nbv.data_handling.offline.store import VinOfflineStoreConfig
from aria_nbv.lightning.lit_trainer_factory import TrainerFactoryConfig
from aria_nbv.lightning.qh_data import QhDataModuleConfig, QhDatasetConfig
from aria_nbv.lightning.qh_experiment import QhExperimentConfig
from aria_nbv.lightning.qh_module import QhLightningModuleConfig
from aria_nbv.rollouts.qh_reader import QhRolloutReaderConfig
from aria_nbv.vin.models.target_finite_horizon import MultiStepCandidateScorerConfig


def _data(tmp_path: Path) -> QhDataModuleConfig:
    return QhDataModuleConfig(
        train=QhDatasetConfig(
            rollout=QhRolloutReaderConfig(store_dirs=(tmp_path / "rollouts",)),
            actor=VinActorSourceConfig(store=VinOfflineStoreConfig(store_dir=tmp_path / "vin"), split="train"),
        )
    )


def test_experiment_rejects_lightning_sampler_replacement(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="QhDataModule owns all samplers"):
        QhExperimentConfig(data=_data(tmp_path), trainer=TrainerFactoryConfig(use_distributed_sampler=True))


def test_run_forwards_full_resume_checkpoint(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    checkpoint = tmp_path / "resume.ckpt"
    config = QhExperimentConfig(data=_data(tmp_path), resume_checkpoint=checkpoint)
    calls: dict[str, object] = {}

    class _Trainer:
        def fit(self, module, *, datamodule, ckpt_path):
            calls.update(module=module, datamodule=datamodule, ckpt_path=ckpt_path)

    module = object()
    data = object()
    monkeypatch.setattr(QhExperimentConfig, "setup_target", lambda self: (_Trainer(), module, data))

    config.run()

    assert calls == {"module": module, "datamodule": data, "ckpt_path": str(checkpoint.resolve())}


def test_strict_toml_rejects_unknown_keys(tmp_path: Path) -> None:
    config_path = tmp_path / "bad.toml"
    config_path.write_text(
        """
unknown = true
[data]
[data.train.rollout]
store_dirs = ["/tmp/rollouts"]
[data.train.actor.store]
store_dir = "/tmp/vin"
"""
    )

    with pytest.raises(ValueError, match="unknown"):
        QhExperimentConfig.from_toml(config_path)


@pytest.mark.parametrize("corpus_horizon", [2, 3])
def test_setup_target_admits_matching_horizon_before_trainer_construction(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    corpus_horizon: int,
) -> None:
    events: list[str] = []

    class _Data:
        training_horizon = corpus_horizon

        def setup(self, stage: str) -> None:
            events.append(f"data.setup:{stage}")

    data = _Data()
    monkeypatch.setattr(QhDataModuleConfig, "setup_target", lambda self: data)
    monkeypatch.setattr(QhLightningModuleConfig, "setup_target", lambda self: events.append("module") or object())
    monkeypatch.setattr(TrainerFactoryConfig, "setup_target", lambda self: events.append("trainer") or object())
    config = QhExperimentConfig(
        data=_data(tmp_path),
        module=QhLightningModuleConfig(scorer=MultiStepCandidateScorerConfig(horizon=corpus_horizon)),
    )

    config.setup_target()

    assert events == ["data.setup:fit", "module", "trainer"]


def test_setup_target_rejects_horizon_mismatch_before_module_or_trainer_construction(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    events: list[str] = []

    class _Data:
        training_horizon = 3

        def setup(self, stage: str) -> None:
            events.append(f"data.setup:{stage}")

    monkeypatch.setattr(QhDataModuleConfig, "setup_target", lambda self: _Data())
    monkeypatch.setattr(QhLightningModuleConfig, "setup_target", lambda self: events.append("module") or object())
    monkeypatch.setattr(TrainerFactoryConfig, "setup_target", lambda self: events.append("trainer") or object())
    config = QhExperimentConfig(
        data=_data(tmp_path),
        module=QhLightningModuleConfig(scorer=MultiStepCandidateScorerConfig(horizon=2)),
    )

    with pytest.raises(ValueError, match="scorer horizon 2.*training rollout corpus maximum 3"):
        config.setup_target()

    assert events == ["data.setup:fit"]
