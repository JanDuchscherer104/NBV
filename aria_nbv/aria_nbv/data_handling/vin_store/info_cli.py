"""Command-line diagnostics for immutable VIN offline stores.

This module provides read-only summary, tree, sample-table, and deterministic
random-index commands over :class:`VinOfflineStoreReader`. It validates through
the strict manifest/version path and never rewrites manifests, split arrays,
sample indices, shards, or optional diagnostic payloads.
"""

from __future__ import annotations

import json
import random
import sys
from collections.abc import Callable
from dataclasses import asdict
from enum import StrEnum
from pathlib import Path
from typing import Annotated, Any

import numpy as np
import typer
from rich.tree import Tree

from ...utils import Stage
from ...utils.cli_format import (
    cli_console,
    counts_table,
    format_value,
    key_value_panel,
    rows_table,
    summary_table,
)
from ...utils.typer_cli import run_typer_app
from ..identifiers import compact_ase_atek_identifiers, compact_ase_atek_sample_id
from .diagnostics import _numeric_summary, collect_vin_offline_dataset_stats
from .format import VinOfflineBlockSpec, VinOfflineIndexRecord, VinOfflineShardSpec
from .store import VinOfflineStoreConfig, VinOfflineStoreReader


class Split(StrEnum):
    """VIN offline store splits accepted by inspection commands."""

    all = "all"
    train = "train"
    val = "val"


_SPLITS = tuple(split.value for split in Split)
_HELP_SETTINGS = {"help_option_names": ["-h", "--help"]}

StoreOption = Annotated[
    Path,
    typer.Option("--store", help="VIN offline store path or cache artifact name."),
]
JsonOption = Annotated[bool, typer.Option("--json", help="Print machine-readable JSON.")]

app = typer.Typer(
    add_completion=False,
    context_settings=_HELP_SETTINGS,
    help="Inspect immutable VIN offline stores without mutating store artifacts.",
    pretty_exceptions_show_locals=False,
)


def main(argv: list[str] | None = None) -> None:
    """Run VIN offline-store inspection.

    Args:
        argv: Optional argument vector. Defaults to ``sys.argv[1:]``.
    """

    raw_argv = list(sys.argv[1:] if argv is None else argv)
    run_typer_app(app, _normalize_default_summary(raw_argv), prog_name="nbv-offline-info")


def _normalize_default_summary(argv: list[str]) -> list[str]:
    """Preserve the legacy default ``summary`` command."""

    if not argv or (argv[0].startswith("-") and argv[0] not in {"-h", "--help"}):
        return ["summary", *argv]
    return argv


@app.command("summary")
def summary_command(
    store: StoreOption = Path("vin_offline"),
    max_samples: Annotated[
        int,
        typer.Option("--max-samples", min=0, help="Maximum rows scanned for aggregate tensor statistics."),
    ] = 128,
    json_output: JsonOption = False,
) -> None:
    """Print store version, split coverage, materialized blocks, and tensor summaries."""

    payload = _summary_payload(store=VinOfflineStoreConfig(store_dir=store), max_samples=max_samples)
    _print_or_json(payload, json_output=json_output, text_printer=_print_summary)


@app.command("tree")
def tree_command(
    store: StoreOption = Path("vin_offline"),
    json_output: JsonOption = False,
) -> None:
    """Print the root files, splits, shards, and manifest block structure."""

    payload = _tree_payload(VinOfflineStoreConfig(store_dir=store))
    _print_or_json(payload, json_output=json_output, text_printer=_print_tree)


@app.command("samples")
def samples_command(
    store: StoreOption = Path("vin_offline"),
    split: Annotated[Split, typer.Option("--split", help="Split to sample from.")] = Split.train,
    limit: Annotated[int, typer.Option("--limit", min=0, help="Maximum rows printed.")] = 20,
    json_output: JsonOption = False,
) -> None:
    """Print a small table of split-local VIN offline rows."""

    payload = _samples_payload(store=VinOfflineStoreConfig(store_dir=store), split=split.value, limit=limit)
    _print_or_json(payload, json_output=json_output, text_printer=_print_samples)


@app.command("random-index")
def random_index_command(
    store: StoreOption = Path("vin_offline"),
    split: Annotated[Split, typer.Option("--split", help="Split used for random selection.")] = Split.train,
    seed: Annotated[int | None, typer.Option("--seed", help="Seed for deterministic selection.")] = None,
    json_output: JsonOption = False,
) -> None:
    """Print a deterministic random split-local index for Rerun inspection."""

    payload = _random_index_payload(store=VinOfflineStoreConfig(store_dir=store), split=split.value, seed=seed)
    if json_output:
        print(json.dumps(payload, indent=2, sort_keys=True))
    else:
        print(payload["index"])


def _print_or_json(
    payload: dict[str, Any],
    *,
    json_output: bool,
    text_printer: Callable[[dict[str, Any]], None],
) -> None:
    """Print a payload either as JSON or through the provided text printer."""

    payload = compact_ase_atek_identifiers(payload)
    if json_output:
        print(json.dumps(payload, indent=2, sort_keys=True))
    else:
        text_printer(payload)


def _summary_payload(*, store: VinOfflineStoreConfig, max_samples: int) -> dict[str, Any]:
    stats = collect_vin_offline_dataset_stats(store, max_samples=max(0, int(max_samples)))
    return {
        "store_dir": stats.store_dir,
        "version": int(stats.version),
        "num_samples": int(stats.num_samples),
        "sampled_samples": int(stats.sampled_samples),
        "split_counts": dict(stats.split_counts),
        "num_scenes": int(stats.num_scenes),
        "num_snippets": int(stats.num_snippets),
        "materialized_blocks": dict(stats.materialized_blocks),
        "numeric_mib": _bytes_to_mib(stats.numeric_bytes),
        "summaries": {
            "candidate_count": asdict(stats.candidate_count),
            "rri": asdict(stats.rri),
            "vin_points": asdict(stats.vin_points),
        },
        "rri_components": {name: asdict(summary) for name, summary in stats.rri_component_summaries.items()},
        "candidate_pose": {name: asdict(summary) for name, summary in stats.candidate_pose_summaries.items()},
        "memory": [asdict(row) for row in stats.memory_diagnostics],
        "backbone": [asdict(row) for row in stats.backbone_diagnostics],
        "batch_shapes": dict(stats.batch_shapes),
    }


def _tree_payload(store: VinOfflineStoreConfig) -> dict[str, Any]:
    reader = VinOfflineStoreReader(store)
    root_files = [
        _path_entry("manifest", store.manifest_path, root=store.store_dir),
        _path_entry("sample_index", store.sample_index_path, root=store.store_dir),
        _path_entry("splits", store.splits_dir, root=store.store_dir),
        _path_entry("shards", store.shards_dir, root=store.store_dir),
    ]
    splits: dict[str, int] = {}
    for split in _SPLITS:
        split_path = store.split_path(split)
        if split_path.exists():
            splits[split] = len(reader.get_split_records(_stage_or_all(split)))
    return {
        "store_dir": store.store_dir.expanduser().resolve().as_posix(),
        "version": int(reader.manifest.version),
        "root_files": root_files,
        "splits": splits,
        "shards": [_shard_payload(shard) for shard in reader.manifest.shards],
    }


def _samples_payload(*, store: VinOfflineStoreConfig, split: str, limit: int) -> dict[str, Any]:
    reader = VinOfflineStoreReader(store)
    records = reader.get_split_records(_stage_or_all(split))
    rows = [_sample_row(reader, record) for record in records[: max(0, int(limit))]]
    return {
        "store_dir": store.store_dir.expanduser().resolve().as_posix(),
        "split": split,
        "limit": max(0, int(limit)),
        "num_eligible": len(records),
        "rows": rows,
    }


def _random_index_payload(*, store: VinOfflineStoreConfig, split: str, seed: int | None) -> dict[str, Any]:
    reader = VinOfflineStoreReader(store)
    records = reader.get_split_records(_stage_or_all(split))
    if not records:
        raise SystemExit(f"No VIN offline samples found for split {split!r}.")
    index = random.Random(seed).randrange(len(records))
    record = records[index]
    return {
        "store_dir": store.store_dir.expanduser().resolve().as_posix(),
        "split": split,
        "seed": seed,
        "index": int(index),
        "sample_key": compact_ase_atek_sample_id(record.sample_key),
        "scene_id": record.scene_id,
        "snippet_id": compact_ase_atek_sample_id(record.snippet_id),
        "sample_index": int(record.sample_index),
        "shard_id": record.shard_id,
        "shard_row": int(record.row),
    }


def _stage_or_all(value: str | Split) -> Stage | None:
    """Normalize an inspection CLI selection before querying the typed store reader."""

    text = value.value if isinstance(value, Split) else value
    return None if text == Split.all.value else Stage.from_str(text)


def _sample_row(reader: VinOfflineStoreReader, record: VinOfflineIndexRecord) -> dict[str, Any]:
    candidate_count = int(reader.read_numeric_block(record, "oracle.candidate_count").reshape(()))
    candidate_count = max(candidate_count, 0)
    rri = np.asarray(reader.read_numeric_block(record, "oracle.rri"), dtype=np.float32).reshape(-1)[:candidate_count]
    vin_lengths = np.asarray(reader.read_numeric_block(record, "vin.lengths"), dtype=np.float32).reshape(-1)
    return {
        "split": record.split,
        "sample_index": int(record.sample_index),
        "sample_key": compact_ase_atek_sample_id(record.sample_key),
        "scene_id": record.scene_id,
        "snippet_id": compact_ase_atek_sample_id(record.snippet_id),
        "shard_id": record.shard_id,
        "shard_row": int(record.row),
        "candidate_count": int(candidate_count),
        "rri": asdict(_numeric_summary(rri)),
        "vin_points": asdict(_numeric_summary(vin_lengths)),
    }


def _path_entry(name: str, path: Path, *, root: Path) -> dict[str, Any]:
    try:
        relative = path.relative_to(root)
    except ValueError:
        relative = path
    return {"name": name, "path": relative.as_posix(), "exists": path.exists()}


def _shard_payload(shard: VinOfflineShardSpec) -> dict[str, Any]:
    return {
        "shard_id": shard.shard_id,
        "relative_dir": shard.relative_dir,
        "row_start": int(shard.row_start),
        "num_rows": int(shard.num_rows),
        "blocks": [_block_payload(block) for block in sorted(shard.blocks.values(), key=lambda block: block.name)],
    }


def _block_payload(block: VinOfflineBlockSpec) -> dict[str, Any]:
    estimated_mib = None
    if block.shape is not None and block.dtype is not None:
        estimated_mib = _bytes_to_mib(int(np.prod(block.shape, dtype=np.int64)) * np.dtype(block.dtype).itemsize)
    return {
        "name": block.name,
        "kind": block.kind,
        "dtype": block.dtype,
        "shape": block.shape,
        "optional": bool(block.optional),
        "estimated_mib": estimated_mib,
    }


def _bytes_to_mib(num_bytes: int) -> float:
    return float(num_bytes) / (1024.0 * 1024.0)


def _print_summary(payload: dict[str, Any]) -> None:
    console = cli_console()
    console.print(
        key_value_panel(
            "VIN Offline Store",
            [
                ("path", payload["store_dir"]),
                ("version", payload["version"]),
                ("samples", payload["num_samples"]),
                ("sampled", payload["sampled_samples"]),
                ("numeric MiB", f"{payload['numeric_mib']:.2f}"),
                ("scenes", payload["num_scenes"]),
                ("snippets", payload["num_snippets"]),
            ],
        )
    )
    console.print(counts_table("Splits", payload["split_counts"]))
    console.print(counts_table("Materialized Blocks", payload["materialized_blocks"]))
    console.print(summary_table("Core Tensor Summaries", payload["summaries"]))
    if payload["rri_components"]:
        console.print(summary_table("RRI Components", payload["rri_components"]))
    if payload["candidate_pose"]:
        console.print(summary_table("Candidate Pose Fields", payload["candidate_pose"]))
    if payload["memory"]:
        console.print(
            rows_table("Memory Diagnostics", tuple(payload["memory"][0].keys()), _dict_rows(payload["memory"]))
        )
    if payload["backbone"]:
        console.print(
            rows_table("Backbone Diagnostics", tuple(payload["backbone"][0].keys()), _dict_rows(payload["backbone"]))
        )
    if payload["batch_shapes"]:
        console.print(counts_table("Batch Shapes", payload["batch_shapes"]))


def _print_tree(payload: dict[str, Any]) -> None:
    console = cli_console()
    tree = Tree(f"VIN offline store v{payload['version']} [dim]{payload['store_dir']}[/dim]")
    roots = tree.add("root files")
    for entry in payload["root_files"]:
        marker = "ok" if entry["exists"] else "missing"
        roots.add(f"{entry['name']}: {entry['path']} ({marker})")
    splits = tree.add("splits")
    for name, count in payload["splits"].items():
        splits.add(f"{name}: {count}")
    shards = tree.add("shards")
    for shard in payload["shards"]:
        shard_node = shards.add(
            f"{shard['shard_id']} rows={shard['num_rows']} row_start={shard['row_start']} dir={shard['relative_dir']}"
        )
        blocks = shard_node.add("blocks")
        for block in shard["blocks"]:
            blocks.add(
                f"{block['name']} kind={block['kind']} dtype={block['dtype']} "
                f"shape={block['shape']} optional={format_value(block['optional'])} "
                f"mib={format_value(block['estimated_mib'])}"
            )
    console.print(tree)


def _print_samples(payload: dict[str, Any]) -> None:
    console = cli_console()
    console.print(
        key_value_panel(
            "VIN Offline Samples",
            [
                ("store", payload["store_dir"]),
                ("split", payload["split"]),
                ("rows", f"{len(payload['rows'])}/{payload['num_eligible']}"),
                ("limit", payload["limit"]),
            ],
        )
    )
    console.print(
        rows_table(
            "Rows",
            ("split", "index", "key", "scene", "snippet", "shard", "row", "candidates", "rri mean", "vin pts mean"),
            (
                (
                    row["split"],
                    row["sample_index"],
                    row["sample_key"],
                    row["scene_id"],
                    row["snippet_id"],
                    row["shard_id"],
                    row["shard_row"],
                    row["candidate_count"],
                    row["rri"]["mean"],
                    row["vin_points"]["mean"],
                )
                for row in payload["rows"]
            ),
        )
    )


def _dict_rows(rows: list[dict[str, Any]]) -> list[tuple[Any, ...]]:
    if not rows:
        return []
    columns = tuple(rows[0].keys())
    return [tuple(row.get(column) for column in columns) for row in rows]


__all__ = ["app", "main"]
