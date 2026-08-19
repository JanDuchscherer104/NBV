"""Cross-layer parity tests for frozen rollout-store projections."""

# ruff: noqa: S101

from __future__ import annotations

import numpy as np

from aria_nbv.rollouts import RolloutZarrStoreReader
from aria_nbv.rollouts.inspection import candidate_audit_rows, target_audit_rows
from aria_nbv.rollouts.read_model import rollout_at, rollout_steps, target_rows
from aria_nbv.rollouts.zarr_store import write_rollout_zarr_store
from tests.rollout_fixtures import build_rollout_records


def test_fixture_inspection_rows_match_typed_read_model_identity_and_masks(tmp_path) -> None:
    """Presentation rows must remain exact views of the frozen typed records."""

    result = write_rollout_zarr_store(
        tmp_path / "projection-parity.zarr",
        build_rollout_records(horizon=2, num_samples=6, seed=91)[:2],
    )
    reader = RolloutZarrStoreReader(result.store_dir)
    audit_rows = candidate_audit_rows(reader)

    expected_candidate_count = 0
    for rollout_position in range(result.num_rollouts):
        rollout = rollout_at(reader, rollout_position)
        steps = rollout_steps(reader, rollout)

        assert rollout.step_row_positions.tolist() == [step.row_position for step in steps]
        for step in steps:
            rows = [row for row in audit_rows if row["step_row_id"] == step.step_row_id]
            expected_candidate_count += step.num_candidates

            assert [row["candidate_row_id"] for row in rows] == step.candidate_row_ids.tolist()
            assert [row["shell_index"] for row in rows] == step.shell_indices.tolist()
            assert [row["actor_action"] for row in rows] == step.actor_action_mask.tolist()
            assert [row["selected"] for row in rows] == step.selected_mask.tolist()
            assert sum(bool(row["actor_action"]) for row in rows) == step.num_valid_candidates
            assert sum(bool(row["selected"]) for row in rows) == 1
            np.testing.assert_allclose(
                [float(row["target_rri"]) for row in rows],
                step.target_rri,
            )

    assert expected_candidate_count == result.num_candidates == len(audit_rows)


def test_fixture_target_audit_rows_match_typed_target_projection(tmp_path) -> None:
    """UI/report target dictionaries must preserve typed target identity exactly."""

    result = write_rollout_zarr_store(
        tmp_path / "target-parity.zarr",
        build_rollout_records(horizon=1, num_samples=6, seed=92)[:2],
    )
    reader = RolloutZarrStoreReader(result.store_dir)
    typed = target_rows(reader)
    projected = target_audit_rows(reader)

    assert [row.target_row_id for row in typed] == [row["target_row_id"] for row in projected]
    assert [row.target_id for row in typed] == [row["target_id"] for row in projected]
    assert [row.source for row in typed] == [row["source"] for row in projected]
    assert [row.class_name for row in typed] == [row["class"] for row in projected]
    assert [row.target_valid for row in typed] == [row["target_valid"] for row in projected]
    assert [row.gt_match_status for row in typed] == [row["gt_match_status"] for row in projected]
