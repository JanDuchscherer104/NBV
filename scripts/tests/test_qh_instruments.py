"""Regression tests for the frozen Q_H H-baseline instruments."""

# ruff: noqa: S101

from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
import tomllib
from pathlib import Path
from types import SimpleNamespace

import pytest

_ROOT = Path(__file__).resolve().parents[2]


def _load_script(name: str):
    path = _ROOT / "scripts" / f"{name}.py"
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def test_extract_batch_workload_matches_legacy_and_chain_shapes() -> None:
    instrument = _load_script("qh_loader_benchmark")
    legacy = SimpleNamespace(
        lineage=(
            SimpleNamespace(current=SimpleNamespace(source_sample_key="scene-a:one")),
            SimpleNamespace(current=SimpleNamespace(source_sample_key="scene-b:two")),
        ),
        transition=SimpleNamespace(row_train_mask=(True, False)),
    )
    chain = SimpleNamespace(
        lineage=(
            SimpleNamespace(source_sample_key="scene-a:one"),
            SimpleNamespace(source_sample_key="scene-b:two"),
        ),
        supervision=SimpleNamespace(row_train_mask=((True, False), (False, True))),
    )

    assert instrument.extract_batch_workload(legacy) == instrument.BatchWorkload(
        keys=("scene-a:one", "scene-b:two"), admitted_transitions=1
    )
    assert instrument.extract_batch_workload(chain) == instrument.BatchWorkload(
        keys=("scene-a:one", "scene-b:two"), admitted_transitions=2
    )


def test_extract_batch_workload_rejects_lineage_and_mask_length_mismatch() -> None:
    instrument = _load_script("qh_loader_benchmark")
    invalid = SimpleNamespace(
        lineage=(SimpleNamespace(current=SimpleNamespace(source_sample_key="scene-a:one")),),
        transition=SimpleNamespace(row_train_mask=(True, False)),
    )

    with pytest.raises(ValueError, match="lineage length"):
        instrument.extract_batch_workload(invalid)


def test_cycling_loader_resets_after_warmup_and_restarts_at_first_key() -> None:
    instrument = _load_script("qh_loader_benchmark")
    batches = (
        instrument.BatchWorkload(keys=("a",), admitted_transitions=1),
        instrument.BatchWorkload(keys=("b",), admitted_transitions=2),
    )
    cycling = instrument.CyclingLoader(lambda: iter(batches))

    warmup = cycling.warmup()

    assert warmup.batch_count == 5
    assert warmup.cycle_count == 2
    assert warmup.admitted_transitions == 7
    assert cycling.cycle_count == 0
    assert cycling.cycling_next() == batches[0]


def test_ordered_workload_digest_covers_the_entire_frozen_loader() -> None:
    instrument = _load_script("qh_loader_benchmark")
    batches = (
        instrument.BatchWorkload(keys=("a",), admitted_transitions=1),
        instrument.BatchWorkload(keys=("b", "c"), admitted_transitions=2),
    )

    digest = instrument.ordered_workload_digest(lambda: iter(batches))

    assert digest == instrument.digest_keys(("a", "b", "c"))


def test_frozen_loc_config_records_the_2480_h_baseline() -> None:
    config = json.loads((_ROOT / ".configs" / "qh_loc_audit.json").read_text())

    assert config["baseline_total"] == 2480


def test_loc_audit_rejects_duplicate_manifest_targets(tmp_path: Path) -> None:
    config = {
        "baseline_total": 1,
        "future_symbols": [],
        "files": [
            {"owner": "first", "path": "scripts/qh_loc_audit.py"},
            {"owner": "second", "path": "scripts/qh_loc_audit.py"},
        ],
    }
    config_path = tmp_path / "duplicate.json"
    config_path.write_text(json.dumps(config), encoding="utf-8")

    completed = subprocess.run(
        [
            sys.executable,
            "scripts/qh_loc_audit.py",
            "--repo-root",
            str(_ROOT),
            "--config",
            str(config_path),
        ],
        cwd=_ROOT,
        text=True,
        capture_output=True,
    )

    assert completed.returncode != 0
    assert "double counts" in completed.stderr.lower()


def test_loc_audit_baseline_phase_accepts_absent_future_symbols(tmp_path: Path) -> None:
    (tmp_path / "legacy.py").write_text("x = 1\n", encoding="utf-8")
    config = {
        "schema_version": 1,
        "baseline_total": 1,
        "files": [{"owner": "legacy", "path": "legacy.py"}],
        "future_symbols": [{"owner": "future", "path": "future.py", "kind": "function", "name": "future_symbol"}],
    }
    config_path = tmp_path / "audit.json"
    config_path.write_text(json.dumps(config), encoding="utf-8")

    completed = subprocess.run(
        [
            sys.executable,
            "scripts/qh_loc_audit.py",
            "--repo-root",
            str(tmp_path),
            "--config",
            str(config_path),
            "--phase",
            "baseline",
        ],
        cwd=_ROOT,
        check=True,
        text=True,
        capture_output=True,
    )

    assert json.loads(completed.stdout)["total_physical_loc"] == 1


def test_loc_audit_final_phase_requires_and_counts_every_future_symbol() -> None:
    completed = subprocess.run(
        [
            sys.executable,
            "scripts/qh_loc_audit.py",
            "--repo-root",
            str(_ROOT),
            "--phase",
            "final",
        ],
        cwd=_ROOT,
        check=True,
        text=True,
        capture_output=True,
    )

    result = json.loads(completed.stdout)
    assert result["phase"] == "final"
    assert result["total_physical_loc"] == 1834


def test_v0_baseline_generation_config_keeps_truthful_v0_identity() -> None:
    config = tomllib.loads((_ROOT / ".configs" / "build_rollouts_qh_v0_baseline.toml").read_text())

    assert config["max_samples"] == 1
    assert config["max_targets_per_sample"] == 1
    assert config["min_valid_root_candidates"] == 1
    assert config["store"]["target_protocol_version"] == "v0_gt_input"
    assert "v1" not in config["store"]["store_dir"]


def test_instrumentation_allowlist_hashes_every_frozen_path() -> None:
    instrument = _load_script("qh_loader_benchmark")

    hashes = instrument.instrumentation_hashes(_ROOT, _ROOT / ".configs" / "qh_instrumentation_allowlist.json")

    paths = json.loads((_ROOT / ".configs" / "qh_instrumentation_allowlist.json").read_text())["paths"]
    assert set(hashes) == set(paths)
    assert all(len(value) == 64 for value in hashes.values())
