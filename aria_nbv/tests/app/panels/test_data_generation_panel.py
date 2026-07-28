"""Streamlit contracts for config-driven local generation."""

# ruff: noqa: S101

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest
from streamlit.testing.v1 import AppTest

from aria_nbv.app.panels import data_generation
from aria_nbv.configs import PathConfig
from aria_nbv.oracle.pipelines.generation import (
    GenerationConfigRef,
    GenerationKind,
    GenerationPlan,
    GenerationResult,
)
from aria_nbv.oracle.pipelines.progress import GenerationProgress


@pytest.fixture
def isolated_paths(tmp_path: Path):
    original = PathConfig()
    original_values = {field: getattr(original, field) for field in type(original).model_fields}
    config_path = tmp_path / ".configs" / "generation" / "vin" / "smoke.toml"
    config_path.parent.mkdir(parents=True)
    config_path.write_text("", encoding="utf-8")
    paths = PathConfig(root=tmp_path, configs_dir=tmp_path / ".configs")
    try:
        yield paths, config_path.resolve()
    finally:
        PathConfig(**original_values)


def _app(tmp_path: Path) -> AppTest:
    script = tmp_path / "render_data_generation.py"
    script.write_text(
        "from aria_nbv.app.panels.data_generation import render_data_generation_page\nrender_data_generation_page()\n",
        encoding="utf-8",
    )
    return AppTest.from_file(str(script), default_timeout=10)


def test_page_is_lazy_and_runs_only_after_explicit_action(isolated_paths, tmp_path: Path, monkeypatch) -> None:
    paths, config_path = isolated_paths
    destination = tmp_path / "vin-store"
    ref = GenerationConfigRef(GenerationKind.VIN_OFFLINE, config_path, "generation/vin/smoke.toml")
    plan = GenerationPlan(
        kind=GenerationKind.VIN_OFFLINE,
        config_path=config_path,
        config=SimpleNamespace(),
        source=None,
        destination=destination,
        max_samples=1,
        effective_config={"max_samples": 1, "store": {"store_dir": destination.as_posix()}},
        blockers=(),
        requires_overwrite_confirmation=False,
    )
    calls: list[GenerationPlan] = []
    monkeypatch.setattr(data_generation, "discover_generation_configs", lambda _root: (ref,))
    monkeypatch.setattr(data_generation, "load_generation_plan", lambda _path, _kind: plan)

    def _run(selected: GenerationPlan, *, progress, allow_overwrite: bool = False) -> GenerationResult:
        del allow_overwrite
        calls.append(selected)
        progress(GenerationProgress(stage="complete", completed=1, total=1, message="Complete"))
        return GenerationResult(selected.kind, selected.destination, {"num_samples": 1})

    monkeypatch.setattr(data_generation, "run_generation", _run)

    app = _app(tmp_path).run()

    assert not app.exception
    assert calls == []
    assert [header.value for header in app.header] == ["Data Generation"]
    assert "Preflight passed" in [success.value for success in app.success]
    assert not app.number_input
    assert not app.slider
    assert not app.text_input

    next(button for button in app.button if button.label == "Generate local dataset").click()
    app = app.run()

    assert not app.exception
    assert calls == [plan]
    assert any("Generation complete" in success.value for success in app.success)
