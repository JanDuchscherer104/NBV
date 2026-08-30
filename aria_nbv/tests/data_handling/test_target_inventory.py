import json
from collections import Counter
from pathlib import Path
from typing import Any

import numpy as np
import numpy.typing as npt
import pytest

from aria_nbv.data_handling.vin_store import target_inventory
from aria_nbv.data_handling.vin_store.format import (
    VinOfflineBlockSpec,
    VinOfflineIndexRecord,
    VinOfflineManifest,
    VinOfflineMaterializedBlocks,
    VinOfflineShardSpec,
)


def _records() -> tuple[VinOfflineIndexRecord, ...]:
    return (
        VinOfflineIndexRecord(0, "sample-a", "scene-a", "snippet-a", "train", "shard-a", 0),
        VinOfflineIndexRecord(1, "sample-b", "scene-b", "snippet-b", "val", "shard-b", 0),
    )


def _manifest(*, detected: bool = True, gt: bool = True) -> VinOfflineManifest:
    blocks = {
        name: VinOfflineBlockSpec(name=name, kind="zarr_array", paths=[name.replace(".", "/")])
        for name in ("gt.obbs", "detected.obbs")
    }
    return VinOfflineManifest(
        version=10,
        created_at="2026-08-23T00:00:00Z",
        source={},
        oracle={},
        vin={},
        materialized_blocks=VinOfflineMaterializedBlocks(
            backbone=False,
            depths=False,
            candidate_pcs=False,
            detected_obbs=detected,
            gt_obbs=gt,
        ),
        shards=[
            VinOfflineShardSpec("shard-a", "shards/a", 0, 1, blocks),
            VinOfflineShardSpec("shard-b", "shards/b", 1, 1, blocks),
        ],
    )


def test_inventory_extracts_geometry_class_and_excludes_padding_and_nonfinite(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    valid: npt.NDArray[np.float32] = np.zeros((34,), dtype=np.float32)
    valid[:6] = [0, 2, 0, 1, 0, 3]
    valid[18:30] = [1, 0, 0, 0, 1, 0, 0, 0, 1, 10, 20, 30]
    valid[30:33] = [7, 11, 0.8]
    padded: npt.NDArray[np.float32] = np.full((34,), -1, dtype=np.float32)
    nonfinite = valid.copy()
    nonfinite[0] = np.nan
    invalid = valid.copy()
    invalid[0:2] = [2, 0]
    optional_reads: list[str] = []

    class Reader:
        def __init__(self, _config: Any) -> None:
            pass

        def read_numeric_block(self, record: VinOfflineIndexRecord, name: str) -> npt.NDArray[np.float32]:
            return np.stack([valid, padded, nonfinite]) if record.sample_index == 0 else np.stack([valid, invalid])

        def read_optional_record(self, _record: VinOfflineIndexRecord, name: str) -> Any:
            optional_reads.append(name)
            return {7: "chair"} if name.endswith("obb_sem_id_to_name") else None

    monkeypatch.setattr(VinOfflineManifest, "read", classmethod(lambda _cls, _path: _manifest()))
    monkeypatch.setattr(VinOfflineIndexRecord, "read_many", classmethod(lambda _cls, _path: list(_records())))
    monkeypatch.setattr(target_inventory, "VinOfflineStoreReader", Reader)

    result = target_inventory.inspect_target_inventory(tmp_path)

    assert result.gt.available is True
    assert result.gt.row_count == 2
    assert result.gt.excluded_padding_count == 1
    assert result.gt.excluded_nonfinite_count == 1
    assert result.gt.excluded_invalid_geometry_count == 1
    assert result.gt.class_counts == (("chair", 2),)
    assert result.gt.sample_counts == ((0, 1), (1, 1))
    assert result.gt.scene_counts == (("scene-a", 1), ("scene-b", 1))
    assert optional_reads.count("gt.obb_sem_id_to_name") == 2
    assert optional_reads.count("detected.obb_sem_id_to_name") == 2
    assert result.gt.rows[0].center == (11.0, 20.5, 31.5)
    assert result.gt.rows[0].volume == 6.0
    assert result.gt.rows[0].aspect_ratio == 3.0
    assert result.to_jsonable()["detected"]["row_count"] == 2


def test_inventory_keeps_missing_population_explicitly_unavailable(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setattr(
        VinOfflineManifest,
        "read",
        classmethod(lambda _cls, _path: _manifest(gt=False, detected=False)),
    )
    monkeypatch.setattr(VinOfflineIndexRecord, "read_many", classmethod(lambda _cls, _path: list(_records())))
    monkeypatch.setattr(target_inventory, "VinOfflineStoreReader", lambda _config: object())

    result = target_inventory.inspect_target_inventory(tmp_path)

    assert result.detected.available is False
    assert result.gt.available is False
    assert result.gt.rows == ()
    assert result.gt.reason == "gt.obbs_not_materialized"


def test_inventory_retains_zero_target_samples_and_scenes(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    valid: npt.NDArray[np.float32] = np.zeros((34,), dtype=np.float32)
    valid[:6] = [0, 1, 0, 1, 0, 1]
    valid[18:30] = [1, 0, 0, 0, 1, 0, 0, 0, 1, 1, 2, 3]
    padded: npt.NDArray[np.float32] = np.full((34,), -1, dtype=np.float32)

    class Reader:
        def __init__(self, _config: Any) -> None:
            pass

        def read_numeric_block(self, record: VinOfflineIndexRecord, _name: str) -> npt.NDArray[np.float32]:
            return padded.reshape(1, 34) if record.sample_index == 0 else valid.reshape(1, 34)

        def read_optional_record(self, _record: VinOfflineIndexRecord, _name: str) -> Any:
            return None

    monkeypatch.setattr(VinOfflineManifest, "read", classmethod(lambda _cls, _path: _manifest()))
    monkeypatch.setattr(VinOfflineIndexRecord, "read_many", classmethod(lambda _cls, _path: list(_records())))
    monkeypatch.setattr(target_inventory, "VinOfflineStoreReader", Reader)

    result = target_inventory.inspect_target_inventory(tmp_path)

    assert result.gt.sample_counts == ((0, 0), (1, 1))
    assert result.gt.scene_counts == (("scene-a", 0), ("scene-b", 1))
    assert result.gt.split_counts == (("train", 0), ("val", 1))


def test_inventory_rejects_malformed_shape_without_fallback(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    class Reader:
        def __init__(self, _config: Any) -> None:
            pass

        def read_numeric_block(self, _record: VinOfflineIndexRecord, _name: str) -> npt.NDArray[np.float32]:
            return np.zeros((3, 33), dtype=np.float32)

    monkeypatch.setattr(VinOfflineManifest, "read", classmethod(lambda _cls, _path: _manifest()))
    monkeypatch.setattr(VinOfflineIndexRecord, "read_many", classmethod(lambda _cls, _path: list(_records())))
    monkeypatch.setattr(target_inventory, "VinOfflineStoreReader", Reader)

    result = target_inventory.inspect_target_inventory(tmp_path)

    assert result.gt.available is False
    assert result.gt.reason == "gt.obbs_shape_invalid:[3, 33]"
    assert result.gt.rows == ()


def _report_inventory(tmp_path: Path) -> target_inventory.TargetInventory:
    """Return typed factual support for every characterized report figure."""

    def row(
        population: str, scene_id: str, class_name: str, volume: float, confidence: float
    ) -> target_inventory.TargetInventoryRow:
        return target_inventory.TargetInventoryRow(
            population=population,  # type: ignore[arg-type]
            sample_index=0,
            sample_key=f"{population}-{scene_id}",
            scene_id=scene_id,
            snippet_id=f"snippet-{scene_id}",
            split="train",
            source_row=0,
            target_index=0,
            semantic_id=1,
            instance_id=1,
            class_name=class_name,
            confidence=confidence,
            center=(0.0, 0.0, 0.0),
            extents=(1.0, 2.0, volume / 2.0),
            diagonal=1.0,
            volume=volume,
            aspect_ratio=volume / 2.0,
        )

    records = _records()

    def population(
        name: str, rows: list[target_inventory.TargetInventoryRow]
    ) -> target_inventory.TargetPopulationEvidence:
        return target_inventory._available(
            name,  # type: ignore[arg-type]
            rows,
            1,
            2,
            3,
            records,
            Counter({0: len(rows), 1: 0}),
            Counter({"scene-a": len(rows), "scene-b": 0}),
            Counter({"train": len(rows), "val": 0}),
        )

    return target_inventory.TargetInventory(
        tmp_path.as_posix(),
        population(
            "detected", [row("detected", "scene-a", "chair", 6.0, 0.7), row("detected", "scene-b", "table", 8.0, 0.8)]
        ),
        population("gt", [row("gt", "scene-a", "chair", 10.0, 0.0), row("gt", "scene-b", "chair", 12.0, 0.0)]),
    )


def test_report_is_pure_and_figures_are_canonical_and_mutation_isolated(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """The report reducer consumes typed inventory without filesystem inspection."""

    inventory = _report_inventory(tmp_path)
    monkeypatch.setattr(
        target_inventory, "inspect_target_inventory", lambda _root: pytest.fail("report read inventory")
    )

    first = target_inventory.build_target_inventory_report(inventory)
    second = target_inventory.build_target_inventory_report(inventory)
    figures = {figure.key: figure for figure in first.figures}
    figure = figures["exclusions"].build_figure()
    figure.update_layout(title="mutated")

    assert tuple(figures) == (
        "exclusions",
        "per-sample-counts",
        "class-support",
        "obb-volume",
        "obb-aspect-ratio",
        "detection-confidence",
    )
    assert first.summaries[0].valid_row_count == 2
    assert first.summaries[0].physical_sample_count == 2
    assert first.summaries[0].zero_target_sample_count == 1
    assert first.export_bytes() == second.export_bytes()
    assert first.figures[0].plotly_json == second.figures[0].plotly_json
    assert figures["exclusions"].build_figure().layout.title.text != "mutated"
    assert first.acquisition is None
    assert first.to_jsonable()["acquisition"] is None


def test_report_figures_preserve_population_class_and_axis_semantics(tmp_path: Path) -> None:
    """Every characterized figure retains its factual grouping and units."""

    figures = {
        figure.key: figure
        for figure in target_inventory.build_target_inventory_report(_report_inventory(tmp_path)).figures
    }

    exclusions = figures["exclusions"].build_figure()
    assert tuple(trace.name for trace in exclusions.data) == ("detected", "gt")
    assert exclusions.layout.barmode == "group"
    assert exclusions.layout.xaxis.title.text == "Exclusion reason"
    assert exclusions.layout.yaxis.title.text == "Excluded rows"

    per_sample = figures["per-sample-counts"].build_figure()
    assert tuple((trace.name, trace.type) for trace in per_sample.data) == (
        ("detected", "histogram"),
        ("detected marginal", "box"),
        ("gt", "histogram"),
        ("gt marginal", "box"),
    )
    assert tuple(per_sample.data[0].x) == (2, 0)
    assert per_sample.layout.barmode == "overlay"
    assert tuple((trace.xaxis, trace.yaxis) for trace in per_sample.data if trace.type == "histogram") == (
        ("x2", "y2"),
        ("x2", "y2"),
    )
    assert tuple((trace.xaxis, trace.yaxis) for trace in per_sample.data if trace.type == "box") == (
        ("x", "y"),
        ("x", "y"),
    )
    assert all(trace.orientation == "h" for trace in per_sample.data if trace.type == "box")
    assert per_sample.layout.xaxis.matches == "x2"
    assert per_sample.layout.xaxis2.title.text == "Finite valid OBB rows per physical sample"
    assert per_sample.layout.yaxis2.title.text == "Sample frequency"

    class_support = figures["class-support"].build_figure()
    assert tuple(trace.name for trace in class_support.data) == ("detected", "gt")
    assert class_support.layout.barmode == "group"
    assert tuple(class_support.data[0].x) == ("chair", "table")
    assert tuple(class_support.data[1].x) == ("chair",)
    assert class_support.layout.xaxis.title.text == "Semantic class"
    assert class_support.layout.yaxis.title.text == "Target rows"
    gt_trace = next(trace for trace in class_support.data if trace.name == "gt")
    assert gt_trace.customdata[0][0] == 2

    volume = figures["obb-volume"].build_figure()
    assert tuple(trace.name for trace in volume.data) == ("detected", "gt")
    assert volume.layout.barmode == "overlay"
    assert all(trace.histnorm == "probability" for trace in volume.data)
    assert volume.data[0].x[0] == pytest.approx(np.log10(6.0))
    assert volume.layout.xaxis.title.text == "log10(volume [m^3])"
    assert volume.layout.yaxis.title.text == "Probability"

    aspect_ratio = figures["obb-aspect-ratio"].build_figure()
    assert tuple(trace.name for trace in aspect_ratio.data) == ("detected", "gt")
    assert aspect_ratio.layout.barmode == "overlay"
    assert all(trace.histnorm == "probability" for trace in aspect_ratio.data)
    assert aspect_ratio.data[0].x[0] == pytest.approx(np.log10(3.0))
    assert aspect_ratio.layout.xaxis.title.text == "log10(largest extent / smallest extent)"
    assert aspect_ratio.layout.yaxis.title.text == "Probability"

    confidence = figures["detection-confidence"].build_figure()
    assert tuple(trace.name for trace in confidence.data) == ("chair", "table")
    assert confidence.layout.barmode == "relative"
    assert confidence.layout.xaxis.title.text == "Detection confidence"
    assert confidence.layout.yaxis.title.text == "Detected target rows"


def test_report_figures_bind_exact_factual_and_theory_owners(tmp_path: Path) -> None:
    """Frozen explanations name the exact DTO fields and canonical implementation."""

    figures = {
        figure.key: figure
        for figure in target_inventory.build_target_inventory_report(_report_inventory(tmp_path)).figures
    }
    expected_source_fields = {
        "exclusions": (
            "TargetPopulationEvidence.population",
            "TargetPopulationEvidence.excluded_padding_count",
            "TargetPopulationEvidence.excluded_nonfinite_count",
            "TargetPopulationEvidence.excluded_invalid_geometry_count",
        ),
        "per-sample-counts": (
            "TargetPopulationEvidence.population",
            "TargetPopulationEvidence.sample_rows",
            "TargetSampleCount.count",
        ),
        "class-support": (
            "TargetPopulationEvidence.population",
            "TargetInventoryRow.class_name",
            "TargetInventoryRow.scene_id",
        ),
        "obb-volume": ("TargetPopulationEvidence.population", "TargetInventoryRow.volume"),
        "obb-aspect-ratio": ("TargetPopulationEvidence.population", "TargetInventoryRow.aspect_ratio"),
        "detection-confidence": (
            "TargetPopulationEvidence.population",
            "TargetInventoryRow.confidence",
            "TargetInventoryRow.class_name",
        ),
    }
    expected_units = {
        "exclusions": "rows",
        "per-sample-counts": "rows per sample",
        "class-support": "target rows",
        "obb-volume": "log10(volume [m^3])",
        "obb-aspect-ratio": "log10(largest extent / smallest extent)",
        "detection-confidence": "confidence",
    }
    expected_theory = (
        "observed-target-selection",
        "ground-truth-target-evaluation",
        "oriented-bounding-box",
    )
    implementation_url = (
        "https://github.com/JanDuchscherer104/ARIA-NBV/blob/main/"
        "aria_nbv/aria_nbv/data_handling/vin_store/target_inventory.py"
    )

    assert {key: figure.explanation.source_fields for key, figure in figures.items()} == expected_source_fields
    assert {key: figure.explanation.units for key, figure in figures.items()} == expected_units
    assert all(figure.explanation.theory.term_ids == expected_theory for figure in figures.values())
    assert all(figure.explanation.evidence_role == "provenance" for figure in figures.values())
    assert all(
        figure.explanation.external_implementation_reference == implementation_url for figure in figures.values()
    )
    assert {"TargetFigureExplanation", "TargetPopulation", "TargetPopulationSummary"}.issubset(target_inventory.__all__)


def test_report_serializes_exact_optional_acquisition_identity(tmp_path: Path) -> None:
    """A deep acquisition binding survives both JSON and byte export unchanged."""

    acquisition = target_inventory.TargetInventoryAcquisitionIdentity(
        identity_version="dataset-bundle-generation-v2",
        generation_digest="generation-sha256",
        request_digest="request-sha256",
    )
    report = target_inventory.build_target_inventory_report(
        _report_inventory(tmp_path),
        acquisition=acquisition,
    )
    expected = {
        "identity_version": "dataset-bundle-generation-v2",
        "generation_digest": "generation-sha256",
        "request_digest": "request-sha256",
    }

    assert report.acquisition is acquisition
    assert report.to_jsonable()["acquisition"] == expected
    assert json.loads(report.export_bytes())["acquisition"] == expected
    assert "TargetInventoryAcquisitionIdentity" in target_inventory.__all__


def test_report_keeps_unavailable_population_counts_unknown(tmp_path: Path) -> None:
    report = target_inventory.build_target_inventory_report(
        target_inventory.TargetInventory(
            tmp_path.as_posix(),
            target_inventory._unavailable("detected", "missing"),
            target_inventory._unavailable("gt", "missing"),
        )
    )

    assert report.figures == ()
    assert report.summaries[0].valid_row_count is None
    assert report.summaries[0].physical_sample_count is None
    assert report.summaries[0].zero_target_sample_count is None
    assert report.summaries[0].unavailable_reason == "missing"


def test_report_omits_unavailable_population_instead_of_plotting_zero(tmp_path: Path) -> None:
    """An unavailable population remains absent from traces and explicit in summaries."""

    inventory = _report_inventory(tmp_path)
    report = target_inventory.build_target_inventory_report(
        target_inventory.TargetInventory(
            inventory.path,
            inventory.detected,
            target_inventory._unavailable("gt", "gt.obbs_not_materialized"),
        )
    )

    assert report.summaries[1].available is False
    assert report.summaries[1].valid_row_count is None
    assert report.summaries[1].unavailable_reason == "gt.obbs_not_materialized"
    for figure in report.figures:
        assert all(trace.name != "gt" and trace.name != "gt marginal" for trace in figure.build_figure().data)
