"""Stable dataset-topology API for persisted and runtime inspection."""

from .contracts import (
    TopologyNode,
    TopologyRelationship,
    TopologyRole,
    TopologySnapshot,
    TopologyStatus,
    assert_topology_snapshot,
)
from .physical import (
    NativeDatasetLayout,
    NativeDatasetLayoutEdge,
    NativeDatasetLayoutNode,
    NativeLayoutRole,
    build_native_dataset_layout,
)
from .runtime import (
    RuntimeTopology,
    RuntimeTopologyEdge,
    RuntimeTopologyNode,
    RuntimeTopologyRole,
    build_runtime_topology,
)
from .semantic import (
    DatasetTopology,
    DatasetTopologyEdge,
    DatasetTopologyNode,
    TopologyAvailability,
    TopologyResolution,
    build_dataset_topology,
    discover_vin_store_dirs,
)

__all__ = [
    "DatasetTopology",
    "DatasetTopologyEdge",
    "DatasetTopologyNode",
    "NativeDatasetLayout",
    "NativeDatasetLayoutEdge",
    "NativeDatasetLayoutNode",
    "NativeLayoutRole",
    "RuntimeTopology",
    "RuntimeTopologyEdge",
    "RuntimeTopologyNode",
    "RuntimeTopologyRole",
    "TopologyAvailability",
    "TopologyNode",
    "TopologyRelationship",
    "TopologyResolution",
    "TopologyRole",
    "TopologySnapshot",
    "TopologyStatus",
    "assert_topology_snapshot",
    "build_dataset_topology",
    "build_native_dataset_layout",
    "build_runtime_topology",
    "discover_vin_store_dirs",
]
