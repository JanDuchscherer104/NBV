#!/usr/bin/env python3
"""Verify the deterministic CPU replay/oracle/store golden fixture."""

from __future__ import annotations

import argparse
import contextlib
import hashlib
import importlib.metadata
import json
import math
import sys
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Any

import numpy as np

from aria_nbv.rollouts import RolloutZarrStoreReader
from aria_nbv.rollouts.manifest import ROLLOUT_MANIFEST_VERSION
from aria_nbv.rollouts.zarr_store import (
    ROLLOUT_ZARR_SCHEMA_VERSION,
    validate_rollout_zarr_store,
    write_rollout_zarr_store,
)
from tests.rollout_fixtures import build_rollout_records

_ROOT = Path(__file__).resolve().parents[1]
_GOLDEN = _ROOT / "aria_nbv" / "tests" / "fixtures" / "replay_oracle_golden.json"


def _json_array(value: Any) -> Any:
    array = np.asarray(value)
    return array.tolist()


def _array_digest(value: Any) -> str:
    """Hash canonical JSON rows after the fixture's field-specific float rounding."""

    payload = json.dumps(_json_array(value), sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def _json_digest(value: Any) -> str:
    payload = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def _source_hash(relative_path: str) -> str:
    return hashlib.sha256((_ROOT / relative_path).read_bytes()).hexdigest()


def _dependency_version(distribution: str) -> str:
    try:
        return importlib.metadata.version(distribution)
    except importlib.metadata.PackageNotFoundError:
        return "unavailable"


def _snapshot() -> dict[str, Any]:
    with contextlib.redirect_stdout(sys.stderr):
        records = build_rollout_records(horizon=2, num_samples=6, seed=23)
    in_memory: list[dict[str, Any]] = []
    for record in records:
        trajectory = record.evaluated.result.trajectories[0]
        steps: list[dict[str, Any]] = []
        for step in trajectory.steps:
            evaluated = record.evaluated.step(0, step.step_index)
            if evaluated is None:
                raise RuntimeError("Golden replay fixture is missing its oracle evaluation.")
            steps.append(
                {
                    "step_index": step.step_index,
                    "candidate_count": int(step.candidates.mask_valid.numel()),
                    "valid_count": int(step.candidates.mask_valid.sum()),
                    "candidate_mask_sha256": _array_digest(step.candidates.mask_valid.detach().cpu()),
                    "candidate_shell_indices_sha256": _array_digest(
                        step.candidates.candidate_shell_indices().detach().cpu()
                    ),
                    "candidate_pose_world": _json_array(step.candidates.shell_poses.tensor().detach().cpu()),
                    "selected_valid_index": step.selected_valid_index,
                    "selected_shell_index": step.selected_shell_index,
                    "selection_scores_sha256": _array_digest(step.selection_scores.detach().cpu()),
                    "selection_score_label": step.selection_score_label,
                    "target_rri_sha256": _array_digest(
                        evaluated.evaluation.labels.metrics["target_rri"].detach().cpu()
                    ),
                    "target_root_gain_sha256": _array_digest(
                        evaluated.evaluation.labels.metrics["target_root_gain"].detach().cpu()
                    ),
                }
            )
        final = record.evaluated.step(0, trajectory.steps[-1].step_index)
        if final is None:
            raise RuntimeError("Golden replay fixture is missing its terminal evaluation.")
        selected = trajectory.steps[-1].selected_valid_index
        in_memory.append(
            {
                "rollout_id_prefix": record.rollout_id_prefix,
                "selection_policy": record.evaluated.result.selection_policy.value,
                "root_pose_world": _json_array(trajectory.root_pose_world.tensor().detach().cpu()),
                "steps": steps,
                "endpoint": {
                    "acquisitions": len(trajectory.steps),
                    "terminated_early": trajectory.terminated_early,
                    "target_rri": float(final.evaluation.labels.metrics["target_rri"][selected]),
                    "target_root_gain": float(final.evaluation.labels.metrics["target_root_gain"][selected]),
                },
            }
        )

    with TemporaryDirectory(prefix="aria-replay-golden-") as temporary:
        result = write_rollout_zarr_store(Path(temporary) / "golden.zarr", records)
        validation = validate_rollout_zarr_store(result.store_dir)
        if not validation.ok:
            raise RuntimeError(f"Golden replay store validation failed: {validation.errors}")
        reader = RolloutZarrStoreReader(result.store_dir)
        stored = {
            "counts": {
                "rollouts": result.num_rollouts,
                "steps": result.num_steps,
                "candidates": result.num_candidates,
            },
            "rollout_ids_sha256": _array_digest(reader.array("rollouts/rollout_id")),
            "termination_reason_sha256": _array_digest(reader.array("rollouts/termination_reason")),
            "step_row_ids_sha256": _array_digest(reader.array("steps/step_row_id")),
            "selected_shell_indices": _json_array(reader.array("steps/selected_shell_index")),
            "actor_action_mask_sha256": _array_digest(reader.array("candidates/actor_action_mask")),
            "oracle_label_mask_sha256": _array_digest(reader.array("candidates/oracle_label_mask")),
            "selected_mask_sha256": _array_digest(reader.array("candidates/selected_mask")),
            "shell_indices_sha256": _array_digest(reader.array("candidates/shell_index")),
            "target_rri_sha256": _array_digest(reader.array("candidates/target_rri")),
            "target_root_gain_sha256": _array_digest(reader.array("candidates/target_root_gain")),
            "qh_state_step_row_ids_sha256": _array_digest(reader.array("q_h/state_step_row_id")),
            "qh_valid_action_mask_sha256": _array_digest(reader.array("q_h/valid_action_mask")),
            "qh_selected_candidate_index": _json_array(reader.array("q_h/selected_candidate_index")),
            "qh_td_reward_sha256": _array_digest(reader.array("q_h/td_reward")),
            "qh_td_terminal_mask_sha256": _array_digest(reader.array("q_h/td_terminal_mask")),
        }
    fixture_config = {"device": "cpu", "horizon": 2, "num_samples": 6, "seed": 23}
    return {
        "schema_version": "replay-oracle-cpu-golden-v2",
        "fixture": fixture_config,
        "identity": {
            "configuration_sha256": _json_digest(fixture_config),
            "contracts": {
                "rollout_manifest_version": ROLLOUT_MANIFEST_VERSION,
                "rollout_zarr_schema_version": ROLLOUT_ZARR_SCHEMA_VERSION,
            },
            "dependencies": {
                "efm3d": _dependency_version("efm3d"),
                "numpy": np.__version__,
                "python": f"{sys.version_info.major}.{sys.version_info.minor}",
                "torch": _dependency_version("torch"),
                "zarr": _dependency_version("zarr"),
            },
            "sources": {
                path: _source_hash(path)
                for path in (
                    "aria_nbv/aria_nbv/oracle/pipelines/evaluated_rollout.py",
                    "aria_nbv/aria_nbv/rollouts/replay/engine.py",
                    "aria_nbv/aria_nbv/rollouts/zarr_store.py",
                    "aria_nbv/tests/rollout_fixtures.py",
                )
            },
        },
        "tolerances": {"float_rtol": 1e-6, "float_atol": 1e-7},
        "in_memory": in_memory,
        "stored": stored,
    }


def _mismatches(expected: Any, actual: Any, *, rtol: float, atol: float, path: str = "$") -> list[str]:
    if isinstance(expected, dict) and isinstance(actual, dict):
        errors = []
        if set(expected) != set(actual):
            errors.append(f"{path}: keys differ")
        for key in sorted(set(expected) & set(actual)):
            errors.extend(_mismatches(expected[key], actual[key], rtol=rtol, atol=atol, path=f"{path}.{key}"))
        return errors
    if isinstance(expected, list) and isinstance(actual, list):
        if len(expected) != len(actual):
            return [f"{path}: lengths differ ({len(expected)} != {len(actual)})"]
        errors = []
        for index, (expected_item, actual_item) in enumerate(zip(expected, actual, strict=True)):
            errors.extend(_mismatches(expected_item, actual_item, rtol=rtol, atol=atol, path=f"{path}[{index}]"))
        return errors
    if (
        isinstance(expected, (int, float))
        and not isinstance(expected, bool)
        and isinstance(actual, (int, float))
        and not isinstance(actual, bool)
    ):
        return [] if math.isclose(float(expected), float(actual), rel_tol=rtol, abs_tol=atol) else [f"{path}: differs"]
    return [] if expected == actual else [f"{path}: differs"]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--emit-current", action="store_true", help="Print the canonical current snapshot.")
    parser.add_argument("--update-golden", action="store_true", help="Replace the checked-in fixture intentionally.")
    args = parser.parse_args()
    current = _snapshot()
    if args.emit_current:
        print(json.dumps(current, sort_keys=True, indent=2))
        return 0
    if args.update_golden:
        _GOLDEN.write_text(json.dumps(current, sort_keys=True, indent=2) + "\n", encoding="utf-8")
        print(f"Updated {_GOLDEN}.")
        return 0
    expected = json.loads(_GOLDEN.read_text(encoding="utf-8"))
    tolerances = expected.get("tolerances", {})
    errors = _mismatches(
        expected,
        current,
        rtol=float(tolerances.get("float_rtol", 0.0)),
        atol=float(tolerances.get("float_atol", 0.0)),
    )
    if errors:
        print("Replay/oracle CPU golden mismatch: " + "; ".join(errors[:10]), file=sys.stderr)
        return 1
    print("Replay/oracle CPU golden parity passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
