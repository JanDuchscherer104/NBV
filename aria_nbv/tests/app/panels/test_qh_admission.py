from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from types import SimpleNamespace

import pytest
import torch

from aria_nbv.app.panels._stored_rollouts import qh_admission
from aria_nbv.dataset_topology import build_runtime_topology


@dataclass(frozen=True)
class _Inputs:
    actor_action_mask: torch.Tensor
    step_mask: torch.Tensor


@dataclass(frozen=True)
class _Supervision:
    q_train_mask: torch.Tensor
    row_train_mask: torch.Tensor
    candidate_row_id: torch.Tensor


@dataclass(frozen=True)
class _Lineage:
    rollout_row_id: int
    scene_id: str


@dataclass(frozen=True)
class _Chain:
    inputs: _Inputs
    supervision: _Supervision
    lineage: _Lineage


@dataclass(frozen=True)
class _Batch:
    inputs: _Inputs
    supervision: _Supervision
    lineage: tuple[_Lineage, ...]


class _Dataset:
    def __init__(self, *, stage: str, scenes: set[str], store: Path, length: int = 3) -> None:
        self.stage = stage
        self.scene_ids = frozenset(scenes)
        self.q_h_horizon = 2
        self.length = length
        self.getitem_calls: list[int] = []
        self.provenance = {
            "rollout": {
                "stores": [{"path": str(store), "manifest_sha256": f"rollout-{stage}"}],
                "compatibility": {"schema_version": "3"},
            },
            "actor": {
                "store_path": f"/actor/{stage}",
                "manifest_hash": f"actor-{stage}",
            },
        }

    def __len__(self) -> int:
        return self.length

    def __getitem__(self, index: int) -> _Chain:
        self.getitem_calls.append(index)
        return _chain(index=index, scene=next(iter(self.scene_ids)))


class _Loader:
    def __init__(self, stage: str) -> None:
        self.stage = stage
        self.iter_calls = 0
        self.yield_count = 0

    def __iter__(self):
        self.iter_calls += 1
        self.yield_count += 1
        yield _batch(scene=f"batch-{self.stage}")
        self.yield_count += 1
        yield _batch(scene="must-not-be-read")


class _DataModule:
    def __init__(self, store: Path) -> None:
        self.train_dataset = _Dataset(stage="train", scenes={"scene-a"}, store=store)
        self.val_dataset = _Dataset(stage="val", scenes={"scene-b"}, store=store, length=2)
        self.test_dataset = _Dataset(stage="test", scenes={"scene-c"}, store=store, length=1)
        self.batch_size = 2
        self.num_workers = 0
        self.pin_memory = False
        self.persistent_workers = False
        self.learning_contract = {"rollout": {"schema_version": "3"}, "actor": {"store_version": "5"}}
        self.provenance = {
            name: dataset.provenance
            for name, dataset in (
                ("train", self.train_dataset),
                ("val", self.val_dataset),
                ("test", self.test_dataset),
            )
        }
        self.loaders = {name: _Loader(name) for name in ("train", "val", "test")}

    def train_dataloader(self) -> _Loader:
        return self.loaders["train"]

    def val_dataloader(self) -> _Loader:
        return self.loaders["val"]

    def test_dataloader(self) -> _Loader:
        return self.loaders["test"]


class _DataModuleConfig:
    def __init__(self, datamodule: _DataModule) -> None:
        self.datamodule = datamodule
        self.setup_seeds: list[int] = []

    def setup_target(self, *, seed: int) -> _DataModule:
        self.setup_seeds.append(seed)
        return self.datamodule


def _chain(*, index: int, scene: str) -> _Chain:
    return _Chain(
        inputs=_Inputs(
            actor_action_mask=torch.ones((2, 3), dtype=torch.bool),
            step_mask=torch.ones((2,), dtype=torch.bool),
        ),
        supervision=_Supervision(
            q_train_mask=torch.ones((2, 3), dtype=torch.bool),
            row_train_mask=torch.ones((2,), dtype=torch.bool),
            candidate_row_id=torch.arange(6).reshape(2, 3),
        ),
        lineage=_Lineage(rollout_row_id=index + 10, scene_id=scene),
    )


def _batch(*, scene: str) -> _Batch:
    return _Batch(
        inputs=_Inputs(
            actor_action_mask=torch.ones((2, 2, 3), dtype=torch.bool),
            step_mask=torch.ones((2, 2), dtype=torch.bool),
        ),
        supervision=_Supervision(
            q_train_mask=torch.ones((2, 2, 3), dtype=torch.bool),
            row_train_mask=torch.ones((2, 2), dtype=torch.bool),
            candidate_row_id=torch.arange(12).reshape(2, 2, 3),
        ),
        lineage=(_Lineage(10, scene), _Lineage(11, scene)),
    )


@pytest.fixture
def fake_experiment(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    repo_root = tmp_path
    config_dir = repo_root / ".configs"
    config_dir.mkdir()
    config_path = config_dir / "train_qh_test.toml"
    config_path.write_text("seed = 17\n", encoding="utf-8")
    rollout_store = tmp_path / "rollouts.zarr"
    datamodule = _DataModule(rollout_store)
    datamodule_config = _DataModuleConfig(datamodule)

    class _ConfigType:
        from_toml_calls: list[Path] = []
        setup_target_calls = 0

        @classmethod
        def from_toml(cls, path: Path):
            cls.from_toml_calls.append(path)
            return SimpleNamespace(seed=17, datamodule_config=datamodule_config)

        @classmethod
        def setup_target(cls):
            cls.setup_target_calls += 1
            raise AssertionError("full experiment setup must not run")

    monkeypatch.setattr(qh_admission, "_load_qh_experiment_config_type", lambda: _ConfigType)
    return repo_root, config_path, rollout_store, datamodule, datamodule_config, _ConfigType


def test_report_uses_only_canonical_datamodule_factory_for_all_stages(fake_experiment) -> None:
    repo_root, config_path, rollout_store, datamodule, factory, config_type = fake_experiment

    runtime = qh_admission.build_qh_admission_report(config_path, world_size=2, repo_root=repo_root)

    assert config_type.from_toml_calls == [config_path.resolve()]
    assert config_type.setup_target_calls == 0
    assert factory.setup_seeds == [17]
    assert runtime.datamodule is datamodule
    assert [stage.stage for stage in runtime.report.stages] == ["train", "val", "test"]
    assert runtime.report.scene_disjoint is True
    train = runtime.report.stage("train")
    assert train.rollout_store_paths == (str(rollout_store),)
    assert train.source_manifest_hash == "actor-train"
    assert train.distributed_padding_rows == 1
    assert runtime.report.loader_policy["preview_exact_rank_order"] is False


def test_materialization_reads_one_selected_chain_and_first_loader_batch(fake_experiment) -> None:
    repo_root, config_path, _store, datamodule, _factory, _config_type = fake_experiment
    runtime = qh_admission.build_qh_admission_report(config_path, repo_root=repo_root)

    materialized = qh_admission.materialize_qh_stage(runtime, stage="val", dataset_index=1)

    assert materialized.dataset_index == 1
    assert datamodule.val_dataset.getitem_calls == [1]
    assert datamodule.loaders["val"].iter_calls == 1
    assert datamodule.loaders["val"].yield_count == 1
    assert materialized.chain.lineage.rollout_row_id == 11
    assert materialized.batch.lineage[0].scene_id == "batch-val"


def test_materialization_rejects_out_of_bounds_without_reading(fake_experiment) -> None:
    repo_root, config_path, _store, datamodule, _factory, _config_type = fake_experiment
    runtime = qh_admission.build_qh_admission_report(config_path, repo_root=repo_root)

    with pytest.raises(IndexError, match="outside"):
        qh_admission.materialize_qh_stage(runtime, stage="test", dataset_index=2)

    assert datamodule.test_dataset.getitem_calls == []
    assert datamodule.loaders["test"].iter_calls == 0


def test_runtime_topology_explains_qh_masks_padding_and_lineage() -> None:
    topology = build_runtime_topology(_batch(scene="scene-a"), root_name="batch")
    rows = {row["path"]: row for row in topology.node_rows()}

    assert "finite actor-valid Oracle supervision mask" in rows["batch.supervision.q_train_mask"]["context"]
    assert (
        "selected-transition loss gate; distinct from q_train_mask"
        in rows["batch.supervision.row_train_mask"]["context"]
    )
    assert "leading B axis; S/N axes may contain collation padding" in rows["batch.supervision.q_train_mask"]["context"]
    assert rows["batch.lineage[0].rollout_row_id"]["role"] == "provenance"


def test_config_admission_accepts_an_explicit_local_qh_toml(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repo_root = tmp_path / "repo"
    (repo_root / ".configs").mkdir(parents=True)
    local_config = tmp_path / "local" / "local-qh.toml"
    local_config.parent.mkdir()
    local_config.write_text("seed = 17\n", encoding="utf-8")
    rollout_store = tmp_path / "rollouts.zarr"
    datamodule_config = _DataModuleConfig(_DataModule(rollout_store))

    class _ConfigType:
        @classmethod
        def from_toml(cls, _path: Path):
            return SimpleNamespace(seed=17, datamodule_config=datamodule_config)

    monkeypatch.setattr(qh_admission, "_load_qh_experiment_config_type", lambda: _ConfigType)

    runtime = qh_admission.build_qh_admission_report(local_config, repo_root=repo_root)

    assert runtime.report.config_path == local_config.resolve()
    assert datamodule_config.setup_seeds == [17]


@pytest.mark.parametrize("name", ["missing.toml", "not-a-toml.txt"])
def test_config_admission_rejects_missing_or_non_toml_paths(tmp_path: Path, name: str) -> None:
    with pytest.raises((FileNotFoundError, ValueError), match="TOML|toml|exist"):
        qh_admission.build_qh_admission_report(tmp_path / name, repo_root=tmp_path)


def test_config_admission_rejects_unresolved_template_paths(tmp_path: Path) -> None:
    config_path = tmp_path / "local-qh.toml"
    config_path.write_text(
        """
[datamodule_config.train.rollout]
store_dirs = ["/ABS/PATH/TO/ARIA_DSS/caches/oracle/rollouts.zarr"]

[datamodule_config.train.actor]
store_dir = "/ABS/PATH/TO/ARIA_DSS/caches/vin/vin-offline.zarr"
""",
        encoding="utf-8",
    )

    assert qh_admission._template_placeholder_fields(config_path) == (
        "datamodule_config.train.rollout.store_dirs[0]",
        "datamodule_config.train.actor.store_dir",
    )

    with pytest.raises(ValueError, match="template placeholders"):
        qh_admission.build_qh_admission_report(config_path, repo_root=tmp_path)


def test_config_factory_errors_fail_closed(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:

    config_dir = tmp_path / ".configs"
    config_dir.mkdir()
    admitted = config_dir / "train_qh_broken.toml"
    admitted.write_text("", encoding="utf-8")

    class _BrokenConfig:
        @classmethod
        def from_toml(cls, _path: Path):
            raise ValueError("broken config")

    monkeypatch.setattr(qh_admission, "_load_qh_experiment_config_type", lambda: _BrokenConfig)
    with pytest.raises(ValueError, match="broken config"):
        qh_admission.build_qh_admission_report(admitted, repo_root=tmp_path)


def test_config_discovery_does_not_import_qh_runtime(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    config_dir = tmp_path / ".configs"
    config_dir.mkdir()
    config_path = config_dir / "train_qh_lazy.toml"
    config_path.write_text("", encoding="utf-8")
    monkeypatch.setattr(
        qh_admission,
        "_load_qh_experiment_config_type",
        lambda: (_ for _ in ()).throw(AssertionError("QH runtime import must stay lazy")),
    )

    assert qh_admission.discover_qh_experiment_configs(tmp_path) == (config_path.resolve(),)


def test_lineage_handoff_is_store_scoped(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    state: dict[str, object] = {}
    monkeypatch.setattr(qh_admission.st, "session_state", state)
    store = (tmp_path / "rollouts.zarr").resolve()
    session = SimpleNamespace(
        store_path=store,
        steps=lambda *, rollout_row_id: [{"rollout_row_id": rollout_row_id, "step_row_id": 31}],
    )

    error = qh_admission._carry_lineage_to_inspect(
        _Lineage(12, "scene-a"),
        session=session,
        rollout_store_paths=(str(store),),
    )

    assert error is None
    assert state["stored_rollout_id"] == 12
    assert state["stored_step_id"] == 31
    assert state["stored_rollouts_section"] == "Inspect & Rerun"

    state.clear()
    error = qh_admission._carry_lineage_to_inspect(
        _Lineage(12, "scene-a"),
        session=session,
        rollout_store_paths=(str(tmp_path / "different.zarr"),),
    )
    assert error is not None
    assert state == {}


def test_lineage_handoff_rejects_ambiguous_multi_store_provenance(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    state: dict[str, object] = {}
    monkeypatch.setattr(qh_admission.st, "session_state", state)
    active_store = (tmp_path / "active.zarr").resolve()
    session = SimpleNamespace(
        store_path=active_store,
        steps=lambda *, rollout_row_id: [{"rollout_row_id": rollout_row_id, "step_row_id": 31}],
    )

    error = qh_admission._carry_lineage_to_inspect(
        _Lineage(12, "overlapping-row-id"),
        session=session,
        rollout_store_paths=(str(active_store), str(tmp_path / "other.zarr")),
    )

    assert error is not None
    assert "exactly one" in error
    assert state == {}


def test_stale_selection_state_is_not_displayed_or_handed_off(fake_experiment) -> None:
    repo_root, config_path, _store, _datamodule, _factory, _config_type = fake_experiment
    runtime = qh_admission.build_qh_admission_report(config_path, world_size=2, repo_root=repo_root)
    materialized = qh_admission.materialize_qh_stage(runtime, stage="val", dataset_index=1)

    preflight = qh_admission._PreflightState(key=(config_path.resolve(), 2), runtime=runtime)
    materialization = qh_admission._MaterializationState(
        key=(config_path.resolve(), "val", 1),
        materialization=materialized,
    )

    assert qh_admission._selected_preflight(preflight, key=(config_path.resolve(), 2)) is runtime
    assert qh_admission._selected_preflight(preflight, key=(config_path.resolve(), 1)) is None
    assert (
        qh_admission._selected_materialization(
            materialization,
            key=(config_path.resolve(), "val", 1),
        )
        is materialized
    )
    assert (
        qh_admission._selected_materialization(
            materialization,
            key=(config_path.resolve(), "val", 0),
        )
        is None
    )
    assert (
        qh_admission._selected_materialization(
            materialization,
            key=(config_path.resolve(), "train", 1),
        )
        is None
    )
    assert (
        qh_admission._selected_materialization(
            materialization,
            key=((repo_root / ".configs" / "train_qh_other.toml").resolve(), "val", 1),
        )
        is None
    )
