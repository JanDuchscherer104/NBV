from __future__ import annotations

from dataclasses import dataclass
from unittest.mock import Mock

import pytest
import torch

from aria_nbv.dataset_topology import (
    DatasetTopology,
    NativeDatasetLayout,
    RuntimeTopology,
    TopologyNode,
    TopologyRelationship,
    TopologySnapshot,
    build_dataset_topology,
    build_native_dataset_layout,
    build_runtime_topology,
)
from aria_nbv.dataset_topology.rendering import render_topology_snapshot


class _PoseLike:
    def __init__(self, value: torch.Tensor) -> None:
        self._value = value

    def tensor(self) -> torch.Tensor:
        return self._value


@dataclass(frozen=True)
class _Inputs:
    candidate_pose_relative_root: _PoseLike
    actor_action_mask: torch.Tensor
    step_mask: torch.Tensor


@dataclass(frozen=True)
class _Supervision:
    q_train_mask: torch.Tensor
    row_train_mask: torch.Tensor
    invalid_reason_bitset: torch.Tensor


@dataclass(frozen=True)
class _Lineage:
    rollout_row_id: int
    scene_id: str


@dataclass(frozen=True)
class _DemoBatch:
    inputs: _Inputs
    supervision: _Supervision
    lineage: tuple[_Lineage, ...]


class _Tab:
    def __enter__(self) -> None:
        return None

    def __exit__(self, *_args: object) -> None:
        return None


def test_package_root_preserves_semantic_and_physical_imports() -> None:
    assert build_dataset_topology.__module__ == "aria_nbv.dataset_topology.semantic"
    assert build_native_dataset_layout.__module__ == "aria_nbv.dataset_topology.physical"
    assert DatasetTopology.__module__ == "aria_nbv.dataset_topology.semantic"
    assert NativeDatasetLayout.__module__ == "aria_nbv.dataset_topology.physical"
    assert RuntimeTopology.__module__ == "aria_nbv.dataset_topology.runtime"


def test_runtime_topology_recurses_dtos_tensors_pose_and_mask_context() -> None:
    batch = _DemoBatch(
        inputs=_Inputs(
            candidate_pose_relative_root=_PoseLike(torch.zeros((2, 3, 4, 12))),
            actor_action_mask=torch.ones((2, 3, 4), dtype=torch.bool),
            step_mask=torch.ones((2, 3), dtype=torch.bool),
        ),
        supervision=_Supervision(
            q_train_mask=torch.ones((2, 3, 4), dtype=torch.bool),
            row_train_mask=torch.ones((2, 3), dtype=torch.bool),
            invalid_reason_bitset=torch.zeros((2, 3, 4), dtype=torch.int64),
        ),
        lineage=(_Lineage(7, "81286"), _Lineage(8, "81286")),
    )

    topology = build_runtime_topology(batch, root_name="batch")
    assert isinstance(topology, TopologySnapshot)
    assert all(isinstance(node, TopologyNode) for node in topology.nodes)
    assert all(isinstance(edge, TopologyRelationship) for edge in topology.edges)
    rows = {row["path"]: row for row in topology.node_rows()}

    pose = rows["batch.inputs.candidate_pose_relative_root"]
    assert pose["python_type"] == "_PoseLike"
    assert pose["shape"] == [2, 3, 4, 12]
    assert pose["dtype"] == "torch.float32"
    assert pose["device"] == "cpu"
    assert pose["role"] == "actor-visible"
    q_mask = rows["batch.supervision.q_train_mask"]
    assert "finite actor-valid Oracle supervision mask" in q_mask["context"]
    assert "leading B axis; S/N axes may contain collation padding" in q_mask["context"]
    row_mask = rows["batch.supervision.row_train_mask"]
    assert "selected-transition loss gate; distinct from q_train_mask" in row_mask["context"]
    invalid = rows["batch.supervision.invalid_reason_bitset"]
    assert "hard-invalid reason flags; not a low-value label" in invalid["context"]
    assert rows["batch.lineage[0].scene_id"]["role"] == "provenance"
    assert any(edge["target"] == "batch.inputs.actor_action_mask" for edge in topology.edge_rows())
    assert "q_train_mask: Tensor shape=[2, 3, 4]" in topology.tree_text()


def test_runtime_topology_rejects_empty_sequence_budget() -> None:
    try:
        build_runtime_topology([], max_sequence_items=0)
    except ValueError as exc:
        assert "at least one" in str(exc)
    else:
        raise AssertionError("Expected max_sequence_items validation.")


def test_renderer_consumes_shared_snapshot(monkeypatch: pytest.MonkeyPatch) -> None:
    topology = build_runtime_topology(_Lineage(7, "81286"), root_name="lineage")
    dataframe = Mock()
    code = Mock()
    monkeypatch.setattr("aria_nbv.dataset_topology.rendering.st.tabs", lambda _labels: (_Tab(), _Tab(), _Tab()))
    monkeypatch.setattr("aria_nbv.dataset_topology.rendering.st.dataframe", dataframe)
    monkeypatch.setattr("aria_nbv.dataset_topology.rendering.st.code", code)

    render_topology_snapshot(snapshot=topology)

    assert dataframe.call_count == 2
    code.assert_called_once_with(topology.tree_text(), language="text")
