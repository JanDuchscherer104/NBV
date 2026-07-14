"""Worker-local on-demand access to raw ATEK/EFM snippets.

This module provides live source reattachment for immutable offline rows. It
reconstructs :class:`AseEfmDataset` instances from manifest-captured config,
caches one iterable per ASE scene inside a worker, and returns
:class:`EfmSnippetView` objects without mutating the offline store.
"""

from __future__ import annotations

from typing import Any

from ..configs import PathConfig
from ..utils import Verbosity
from .efm_dataset import AseEfmDataset, AseEfmDatasetConfig
from .efm_views import EfmSnippetView


class EfmSnippetLoader:
    """Resolve source snippets through worker-owned, per-scene dataset caches.

    Instances are intentionally not a persisted store component. They reopen
    ATEK WebDataset shards when a reader requests raw camera, MPS, calibration,
    or optional GT-mesh context that was not duplicated into offline blocks.
    """

    def __init__(
        self,
        *,
        dataset_payload: dict[str, Any] | None,
        device: str,
        paths: PathConfig,
        include_gt_mesh: bool,
    ) -> None:
        """Store the raw dataset payload and worker-local dataset cache."""
        self._dataset_payload = dict(dataset_payload or {})
        self._device = str(device)
        self._paths = paths
        self._include_gt_mesh = include_gt_mesh
        self._datasets: dict[str, AseEfmDataset] = {}

    def _build_dataset(self, scene_id: str) -> AseEfmDataset:
        """Build and cache a single-scene raw dataset for snippet lookup."""
        payload = dict(self._dataset_payload)
        payload["paths"] = payload.get("paths", self._paths)
        payload["scene_ids"] = [scene_id]
        payload["snippet_ids"] = []
        payload["snippet_key_filter"] = []
        payload["batch_size"] = 1
        payload["device"] = self._device
        payload["wds_shuffle"] = False
        payload["wds_repeat"] = False
        payload["load_meshes"] = bool(self._include_gt_mesh)
        payload.setdefault("require_mesh", False)
        payload["verbosity"] = Verbosity.QUIET
        cfg = AseEfmDatasetConfig(**payload)
        dataset = cfg.setup_target()
        self._datasets[scene_id] = dataset
        return dataset

    def load(self, *, scene_id: str, snippet_id: str) -> EfmSnippetView:
        """Load one source snippet, rebuilding a stale scene iterator once.

        Args:
            scene_id: ASE scene identifier used to locate ATEK shards.
            snippet_id: Compact or raw ATEK sample identifier to match.

        Returns:
            Live :class:`EfmSnippetView` backed by the source shard.
        """
        for attempt in range(2):
            dataset = self._datasets.get(scene_id)
            if dataset is None:
                dataset = self._build_dataset(scene_id)
            dataset._snippet_key_filter = {snippet_id}  # type: ignore[attr-defined]
            for sample in dataset:
                return sample
            if attempt == 0:
                self._datasets.pop(scene_id, None)
        raise FileNotFoundError(
            f"Failed to locate snippet={snippet_id} in scene={scene_id}.",
        )


__all__ = ["EfmSnippetLoader"]
