"""Contracts for config-driven local dataset generation."""

# ruff: noqa: S101

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest

from aria_nbv.oracle.pipelines import generation
from aria_nbv.oracle.pipelines.generation import (
    GenerationBlockedError,
    GenerationConfigRef,
    GenerationKind,
    GenerationPlan,
    discover_generation_configs,
    load_generation_plan,
    run_generation,
)
from aria_nbv.oracle.pipelines.progress import GenerationProgress


def test_generation_catalog_is_recursive_and_domain_typed(tmp_path: Path) -> None:
    vin = tmp_path / "generation" / "vin" / "smoke" / "offline.toml"
    rollouts = tmp_path / "generation" / "rollouts" / "campaigns" / "rollouts.toml"
    unrelated = tmp_path / "training" / "vin" / "offline.toml"
    for path in (vin, rollouts, unrelated):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("", encoding="utf-8")

    refs = discover_generation_configs(tmp_path)

    assert refs == (
        GenerationConfigRef(
            kind=GenerationKind.ROLLOUTS,
            path=rollouts.resolve(),
            label="generation/rollouts/campaigns/rollouts.toml",
        ),
        GenerationConfigRef(
            kind=GenerationKind.VIN_OFFLINE,
            path=vin.resolve(),
            label="generation/vin/smoke/offline.toml",
        ),
    )


def test_loading_plan_delegates_toml_to_typed_config_and_keeps_defaults(tmp_path: Path, monkeypatch) -> None:
    config_path = tmp_path / "generation" / "vin" / "smoke.toml"
    config_path.parent.mkdir(parents=True)
    config_path.write_text("max_samples = 2\n", encoding="utf-8")
    destination = tmp_path / "vin-store"
    loaded: list[Path] = []

    class _FakeConfig:
        max_samples = 2
        overwrite = False
        store = SimpleNamespace(store_dir=destination)

        @classmethod
        def from_toml(cls, path: Path) -> "_FakeConfig":
            loaded.append(path)
            return cls()

        def model_dump_jsonable(self) -> dict[str, object]:
            return {"max_samples": self.max_samples, "overwrite": self.overwrite}

    monkeypatch.setitem(generation._CONFIG_TYPES, GenerationKind.VIN_OFFLINE, _FakeConfig)

    plan = load_generation_plan(config_path, GenerationKind.VIN_OFFLINE)

    assert loaded == [config_path.resolve()]
    assert plan.destination == destination.resolve()
    assert plan.max_samples == 2
    assert plan.effective_config == {"max_samples": 2, "overwrite": False}
    assert plan.blockers == ()


def test_rollout_plan_blocks_an_existing_destination(tmp_path: Path, monkeypatch) -> None:
    config_path = tmp_path / "rollouts.toml"
    config_path.write_text("", encoding="utf-8")
    destination = tmp_path / "rollouts.zarr"
    destination.mkdir()
    source_path = tmp_path / "vin"
    source_path.mkdir()

    class _FakeConfig:
        max_samples = 1
        source = SimpleNamespace(store=SimpleNamespace(store_dir=source_path))
        store = SimpleNamespace(store_dir=destination)

        @classmethod
        def from_toml(cls, _path: Path) -> "_FakeConfig":
            return cls()

        def model_dump_jsonable(self) -> dict[str, object]:
            return {}

    monkeypatch.setitem(generation._CONFIG_TYPES, GenerationKind.ROLLOUTS, _FakeConfig)

    plan = load_generation_plan(config_path, GenerationKind.ROLLOUTS)

    assert plan.blockers == (f"Rollout destination already exists: {destination.resolve()}",)


def test_rollout_plan_blocks_a_missing_vin_source(tmp_path: Path, monkeypatch) -> None:
    config_path = tmp_path / "rollouts.toml"
    config_path.write_text("", encoding="utf-8")
    source_path = tmp_path / "missing-vin"

    class _FakeConfig:
        max_samples = 1
        source = SimpleNamespace(store=SimpleNamespace(store_dir=source_path))
        store = SimpleNamespace(store_dir=tmp_path / "rollouts.zarr")

        @classmethod
        def from_toml(cls, _path: Path) -> "_FakeConfig":
            return cls()

        def model_dump_jsonable(self) -> dict[str, object]:
            return {}

    monkeypatch.setitem(generation._CONFIG_TYPES, GenerationKind.ROLLOUTS, _FakeConfig)

    plan = load_generation_plan(config_path, GenerationKind.ROLLOUTS)

    assert plan.blockers == (f"VIN source store does not exist: {source_path.resolve()}",)


def test_rollout_campaign_is_inspectable_but_not_streamlit_executable(tmp_path: Path, monkeypatch) -> None:
    config_path = tmp_path / "generation" / "rollouts" / "campaigns" / "campaign.toml"
    config_path.parent.mkdir(parents=True)
    config_path.write_text("max_samples = 3\n", encoding="utf-8")
    source_path = tmp_path / "vin"
    source_path.mkdir()

    class _FakeConfig:
        max_samples = 3
        source = SimpleNamespace(store=SimpleNamespace(store_dir=source_path))
        store = SimpleNamespace(store_dir=tmp_path / "rollouts.zarr")

        @classmethod
        def from_toml(cls, _path: Path) -> "_FakeConfig":
            return cls()

        def model_dump_jsonable(self) -> dict[str, object]:
            return {}

    monkeypatch.setitem(generation._CONFIG_TYPES, GenerationKind.ROLLOUTS, _FakeConfig)

    plan = load_generation_plan(config_path, GenerationKind.ROLLOUTS)

    assert plan.blockers == ("Campaign and template rollout configs are CLI/Slurm-owned and cannot run in Streamlit.",)


def test_run_generation_forwards_progress_and_summarizes_result(tmp_path: Path) -> None:
    events: list[GenerationProgress] = []
    destination = tmp_path / "vin"

    class _Target:
        def run(self, *, progress):
            progress(GenerationProgress(stage="generating", completed=1, total=1, message="Generated sample 1/1"))
            return SimpleNamespace(stats={"num_samples": 1, "num_shards": 1})

    config = SimpleNamespace(setup_target=lambda: _Target())
    plan = GenerationPlan(
        kind=GenerationKind.VIN_OFFLINE,
        config_path=(tmp_path / "vin.toml").resolve(),
        config=config,
        source=None,
        destination=destination.resolve(),
        max_samples=1,
        effective_config={},
        blockers=(),
        requires_overwrite_confirmation=False,
    )

    result = run_generation(plan, progress=events.append)

    assert [event.stage for event in events] == ["preparing", "generating", "complete"]
    assert result.destination == destination.resolve()
    assert result.summary == {"num_samples": 1, "num_shards": 1}


def test_rollout_run_records_selected_toml_provenance(tmp_path: Path) -> None:
    config_path = tmp_path / "rollout.toml"
    config_path.write_text("max_samples = 1\n", encoding="utf-8")
    invocations = []

    class _Target:
        def run(self, *, progress, invocation):
            del progress
            invocations.append(invocation)
            return SimpleNamespace(num_rollouts=1, num_steps=2, num_candidates=3)

    config = SimpleNamespace(setup_target=lambda: _Target())
    plan = GenerationPlan(
        kind=GenerationKind.ROLLOUTS,
        config_path=config_path,
        config=config,
        source=(tmp_path / "vin").resolve(),
        destination=(tmp_path / "rollouts.zarr").resolve(),
        max_samples=1,
        effective_config={},
        blockers=(),
        requires_overwrite_confirmation=False,
    )

    result = run_generation(plan)

    assert result.summary == {"num_rollouts": 1, "num_steps": 2, "num_candidates": 3}
    assert len(invocations) == 1
    assert invocations[0].mode == "programmatic"
    assert invocations[0].config_path == config_path.resolve().as_posix()
    assert invocations[0].raw_toml_text == "max_samples = 1\n"
    assert len(invocations[0].raw_toml_sha256) == 64


def test_run_generation_rejects_blocked_or_unconfirmed_overwrite(tmp_path: Path) -> None:
    base = {
        "kind": GenerationKind.VIN_OFFLINE,
        "config_path": (tmp_path / "vin.toml").resolve(),
        "config": SimpleNamespace(),
        "source": None,
        "destination": (tmp_path / "vin").resolve(),
        "max_samples": 1,
        "effective_config": {},
    }

    with pytest.raises(GenerationBlockedError, match="unsafe"):
        run_generation(
            GenerationPlan(
                **base,
                blockers=("unsafe destination",),
                requires_overwrite_confirmation=False,
            )
        )

    with pytest.raises(GenerationBlockedError, match="confirmation"):
        run_generation(
            GenerationPlan(
                **base,
                blockers=(),
                requires_overwrite_confirmation=True,
            )
        )


def test_local_plan_blocks_an_unbounded_config(tmp_path: Path, monkeypatch) -> None:
    config_path = tmp_path / "vin.toml"
    config_path.write_text("", encoding="utf-8")

    class _FakeConfig:
        max_samples = None
        overwrite = False
        store = SimpleNamespace(store_dir=tmp_path / "vin")

        @classmethod
        def from_toml(cls, _path: Path) -> "_FakeConfig":
            return cls()

        def model_dump_jsonable(self) -> dict[str, object]:
            return {}

    monkeypatch.setitem(generation._CONFIG_TYPES, GenerationKind.VIN_OFFLINE, _FakeConfig)

    plan = load_generation_plan(config_path, GenerationKind.VIN_OFFLINE)

    assert plan.blockers == ("Local generation requires a finite max_samples value in the TOML config.",)
