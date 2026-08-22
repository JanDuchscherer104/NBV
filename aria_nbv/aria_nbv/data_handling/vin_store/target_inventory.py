"""Read-only detected and GT OBB population evidence from a VIN store.

The inventory is deliberately separate from the training-bundle composer and
from Streamlit.  It reads the manifest-declared compact OBB blocks only;
missing blocks and malformed rows are reported as unavailable evidence rather
than being inferred from raw source snippets.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal

import numpy as np
import torch
from efm3d.aria.obb import ObbTW

from ...utils.semantic_names import semantic_class_name
from .format import VinOfflineIndexRecord, VinOfflineManifest
from .store import VinOfflineStoreConfig, VinOfflineStoreReader

TargetPopulation = Literal["detected", "gt"]


@dataclass(frozen=True, slots=True)
class TargetSampleCount:
    """Target count for one VIN sample, including zero-target samples."""

    sample_index: int
    sample_key: str
    scene_id: str
    snippet_id: str
    split: str
    count: int

    def to_jsonable(self) -> dict[str, Any]:
        """Return a JSON-compatible sample count row."""

        return {
            "sample_index": self.sample_index,
            "sample_key": self.sample_key,
            "scene_id": self.scene_id,
            "snippet_id": self.snippet_id,
            "split": self.split,
            "count": self.count,
        }


@dataclass(frozen=True, slots=True)
class TargetInventoryRow:
    """One finite, non-padding compact OBB row."""

    population: TargetPopulation
    sample_index: int
    sample_key: str
    scene_id: str
    snippet_id: str
    split: str
    source_row: int
    target_index: int
    semantic_id: int
    instance_id: int
    class_name: str
    confidence: float
    center: tuple[float, float, float]
    extents: tuple[float, float, float]
    diagonal: float
    volume: float
    aspect_ratio: float | None

    def to_jsonable(self) -> dict[str, Any]:
        """Return a compact JSON-compatible row without the raw OBB payload."""

        return {
            "population": self.population,
            "sample_index": self.sample_index,
            "sample_key": self.sample_key,
            "scene_id": self.scene_id,
            "snippet_id": self.snippet_id,
            "split": self.split,
            "source_row": self.source_row,
            "target_index": self.target_index,
            "semantic_id": self.semantic_id,
            "instance_id": self.instance_id,
            "class_name": self.class_name,
            "confidence": self.confidence,
            "center": list(self.center),
            "extents": list(self.extents),
            "diagonal": self.diagonal,
            "volume": self.volume,
            "aspect_ratio": self.aspect_ratio,
        }


@dataclass(frozen=True, slots=True)
class TargetPopulationEvidence:
    """Inventory evidence for one detected or GT population."""

    population: TargetPopulation
    available: bool
    reason: str | None
    rows: tuple[TargetInventoryRow, ...]
    excluded_padding_count: int
    excluded_nonfinite_count: int
    excluded_invalid_geometry_count: int
    sample_rows: tuple[TargetSampleCount, ...]
    sample_counts: tuple[tuple[int, int], ...]
    scene_counts: tuple[tuple[str, int], ...]
    split_counts: tuple[tuple[str, int], ...]
    class_counts: tuple[tuple[str, int], ...]

    @property
    def row_count(self) -> int:
        """Return the number of valid rows."""

        return len(self.rows)

    def to_jsonable(self) -> dict[str, Any]:
        """Return deterministic download-ready evidence."""

        return {
            "population": self.population,
            "available": self.available,
            "reason": self.reason,
            "row_count": self.row_count,
            "excluded_padding_count": self.excluded_padding_count,
            "excluded_nonfinite_count": self.excluded_nonfinite_count,
            "excluded_invalid_geometry_count": self.excluded_invalid_geometry_count,
            "sample_rows": [row.to_jsonable() for row in self.sample_rows],
            "sample_counts": {str(key): value for key, value in self.sample_counts},
            "scene_counts": dict(self.scene_counts),
            "split_counts": dict(self.split_counts),
            "class_counts": dict(self.class_counts),
            "rows": [row.to_jsonable() for row in self.rows],
        }


@dataclass(frozen=True, slots=True)
class TargetInventory:
    """Complete detected/GT target inventory for one immutable VIN root."""

    path: str
    detected: TargetPopulationEvidence
    gt: TargetPopulationEvidence

    def to_jsonable(self) -> dict[str, Any]:
        """Return deterministic JSON-compatible evidence."""

        return {
            "path": self.path,
            "detected": self.detected.to_jsonable(),
            "gt": self.gt.to_jsonable(),
        }


def inspect_target_inventory(root_store: Path | str) -> TargetInventory:
    """Inspect manifest-declared detected and GT OBB blocks.

    The scan is read-only and deterministic in sample-index/row order.  A
    population is unavailable when its manifest flag or any shard block is
    absent, or when a block has an invalid shape.  No raw-source fallback is
    attempted.
    """

    store = Path(root_store).expanduser().resolve()
    try:
        manifest = VinOfflineManifest.read(store / "manifest.json")
        records = tuple(VinOfflineIndexRecord.read_many(store / "sample_index.jsonl"))
    except Exception as exc:
        reason = f"root_store_unreadable:{type(exc).__name__}:{exc}"
        return TargetInventory(store.as_posix(), _unavailable("detected", reason), _unavailable("gt", reason))

    try:
        reader = VinOfflineStoreReader(VinOfflineStoreConfig(store_dir=store))
    except Exception as exc:
        reason = f"root_store_unreadable:{type(exc).__name__}:{exc}"
        return TargetInventory(store.as_posix(), _unavailable("detected", reason), _unavailable("gt", reason))
    return TargetInventory(
        store.as_posix(),
        _inspect_population("detected", manifest, records, reader),
        _inspect_population("gt", manifest, records, reader),
    )


def _inspect_population(
    population: TargetPopulation,
    manifest: VinOfflineManifest,
    records: tuple[VinOfflineIndexRecord, ...],
    reader: VinOfflineStoreReader,
) -> TargetPopulationEvidence:
    flag = (
        population == "gt"
        and manifest.materialized_blocks.gt_obbs
        or (population == "detected" and manifest.materialized_blocks.detected_obbs)
    )
    block_name = f"{population}.obbs"
    if not flag:
        return _unavailable(population, f"{block_name}_not_materialized")
    shard_specs = {spec.shard_id: spec for spec in manifest.shards}
    missing = sorted(
        {
            record.shard_id
            for record in records
            if record.shard_id not in shard_specs or block_name not in shard_specs[record.shard_id].blocks
        }
    )
    if missing:
        return _unavailable(population, f"{block_name}_block_missing:{','.join(missing)}")

    rows: list[TargetInventoryRow] = []
    padding_count = 0
    nonfinite_count = 0
    invalid_geometry_count = 0
    sample_counts: Counter[int] = Counter({record.sample_index: 0 for record in records})
    scene_counts: Counter[str] = Counter({record.scene_id: 0 for record in records})
    split_counts: Counter[str] = Counter({record.split: 0 for record in records})
    try:
        for record in records:
            values = np.asarray(reader.read_numeric_block(record, block_name))
            if values.ndim < 2 or values.shape[-1] != 34:
                return _unavailable(population, f"{block_name}_shape_invalid:{list(values.shape)}")
            semantic_names = reader.read_optional_record(record, f"{population}.obb_sem_id_to_name")
            for target_index, raw in enumerate(values.reshape(-1, values.shape[-1])):
                finite = bool(np.all(np.isfinite(raw)))
                if not finite:
                    nonfinite_count += 1
                    continue
                if bool(np.all(raw == -1.0)):
                    padding_count += 1
                    continue
                obb = ObbTW(torch.as_tensor(raw, dtype=torch.float32).reshape(1, -1))
                extents_array = obb.bb3_diagonal.detach().cpu().numpy().reshape(-1)
                center_array = obb.bb3_center_world.detach().cpu().numpy().reshape(-1)
                if extents_array.size != 3 or center_array.size != 3:
                    invalid_geometry_count += 1
                    continue
                extents = (float(extents_array[0]), float(extents_array[1]), float(extents_array[2]))
                center = (float(center_array[0]), float(center_array[1]), float(center_array[2]))
                positive = bool(np.all(extents_array > 0.0))
                if not positive:
                    invalid_geometry_count += 1
                    continue
                volume = float(np.prod(extents_array))
                diagonal = float(np.linalg.norm(extents_array))
                minimum = float(np.min(extents_array))
                aspect_ratio = float(np.max(extents_array) / minimum)
                semantic_id = int(obb.sem_id.reshape(-1)[0].item())
                sample_counts[record.sample_index] += 1
                scene_counts[record.scene_id] += 1
                split_counts[record.split] += 1
                rows.append(
                    TargetInventoryRow(
                        population=population,
                        sample_index=record.sample_index,
                        sample_key=record.sample_key,
                        scene_id=record.scene_id,
                        snippet_id=record.snippet_id,
                        split=record.split,
                        source_row=target_index,
                        target_index=target_index,
                        semantic_id=semantic_id,
                        instance_id=int(obb.inst_id.reshape(-1)[0].item()),
                        class_name=semantic_class_name(semantic_id, semantic_names),
                        confidence=float(obb.prob.reshape(-1)[0].item()),
                        center=center,
                        extents=extents,
                        diagonal=diagonal,
                        volume=volume,
                        aspect_ratio=aspect_ratio,
                    ),
                )
    except Exception as exc:
        return _unavailable(population, f"{block_name}_block_unreadable:{type(exc).__name__}:{exc}")
    return _available(
        population,
        rows,
        padding_count,
        nonfinite_count,
        invalid_geometry_count,
        records,
        sample_counts,
        scene_counts,
        split_counts,
    )


def _available(
    population: TargetPopulation,
    rows: list[TargetInventoryRow],
    padding_count: int,
    nonfinite_count: int,
    invalid_geometry_count: int,
    records: tuple[VinOfflineIndexRecord, ...],
    sample_counts: Counter[Any],
    scene_counts: Counter[str],
    split_counts: Counter[str],
) -> TargetPopulationEvidence:
    classes = Counter(row.class_name for row in rows)
    sample_rows = tuple(
        TargetSampleCount(
            record.sample_index,
            record.sample_key,
            record.scene_id,
            record.snippet_id,
            record.split,
            sample_counts[record.sample_index],
        )
        for record in records
    )
    return TargetPopulationEvidence(
        population,
        True,
        None,
        tuple(rows),
        padding_count,
        nonfinite_count,
        invalid_geometry_count,
        sample_rows,
        tuple(sorted(sample_counts.items())),
        tuple(sorted(scene_counts.items())),
        tuple(sorted(split_counts.items())),
        tuple(sorted(classes.items())),
    )


def _unavailable(population: TargetPopulation, reason: str) -> TargetPopulationEvidence:
    return TargetPopulationEvidence(population, False, reason, (), 0, 0, 0, (), (), (), (), ())


__all__ = [
    "TargetInventory",
    "TargetInventoryRow",
    "TargetSampleCount",
    "TargetPopulationEvidence",
    "inspect_target_inventory",
]
