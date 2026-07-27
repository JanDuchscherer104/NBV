#!/usr/bin/env python3
"""Frozen, shape-structural loader benchmark for the Q_H H/F comparison.

The benchmark intentionally knows no Q_H production DTOs.  It reads the two
facts required at the DataLoader boundary from object structure: a batch's
lineage keys and its selected-transition admission mask.  That makes the H
instrument valid for both the legacy transition batch and the planned chain
batch without version switches or production imports.
"""

from __future__ import annotations

import argparse
import hashlib
import importlib
import importlib.metadata
import json
import platform
import time
from collections.abc import Callable, Iterable, Iterator, Sequence
from dataclasses import asdict, dataclass
from functools import partial
from pathlib import Path
from typing import Any


SCHEMA_VERSION = 1
DEFAULT_WARMUP_BATCHES = 5
DEFAULT_MIN_BATCHES = 100
DEFAULT_MIN_SECONDS = 30.0
DEFAULT_MAX_PINNED_HOST_BYTES = 1 << 30


@dataclass(frozen=True)
class BatchWorkload:
    """Ordered dataset keys and admitted selected transitions for one batch."""

    keys: tuple[str, ...]
    admitted_transitions: int


@dataclass(frozen=True)
class CycleSummary:
    """Auditable counters from one deterministic cycling interval."""

    batch_count: int
    cycle_count: int
    admitted_transitions: int
    yielded_key_digest: str


@dataclass(frozen=True)
class BenchmarkRepetition:
    """One complete warmup/reset/measurement result in the frozen schema."""

    warmup: CycleSummary
    batch_count: int
    elapsed_seconds: float
    cycle_count: int
    admitted_transitions: int
    yielded_key_digest: str
    ordered_key_digest: str
    bytes_per_sample_estimate: float | None
    peak_pinned_host_memory_bytes: int | None
    pinned_memory_source: str
    worker_count: int | None
    batch_size: int
    runtime_versions: dict[str, str]
    feasible: bool
    infeasible_reason: str | None


def _as_bool_rows(value: Any) -> tuple[tuple[bool, ...], ...]:
    """Normalize a tensor-like scalar/vector/matrix mask without importing torch."""

    if hasattr(value, "detach"):
        value = value.detach()
    if hasattr(value, "cpu"):
        value = value.cpu()
    if hasattr(value, "tolist"):
        value = value.tolist()
    if isinstance(value, bool):
        return ((value,),)
    if not isinstance(value, (tuple, list)):
        raise ValueError("Q_H admission mask must be a bool scalar, vector, or matrix.")
    if not value:
        return ()
    if all(not isinstance(item, (tuple, list)) for item in value):
        return tuple((bool(item),) for item in value)
    rows: list[tuple[bool, ...]] = []
    for row in value:
        if not isinstance(row, (tuple, list)):
            raise ValueError("Q_H admission mask mixes scalar and matrix rows.")
        rows.append(tuple(bool(item) for item in row))
    return tuple(rows)


def _lineage_keys(lineage: Sequence[Any]) -> tuple[str, ...]:
    """Extract legacy ``current`` or planned chain lineage keys structurally."""

    keys: list[str] = []
    for item in lineage:
        source = getattr(item, "current", item)
        key = getattr(source, "source_sample_key", None)
        if not isinstance(key, str) or not key:
            raise ValueError("Q_H batch lineage lacks a non-empty source_sample_key.")
        keys.append(key)
    if not keys:
        raise ValueError("Q_H batch lineage is empty.")
    return tuple(keys)


def extract_batch_workload(batch: Any) -> BatchWorkload:
    """Return ordered keys and admitted-transition count from either batch shape.

    Legacy batches expose ``transition.row_train_mask`` with one mask value per
    lineage row.  Planned chain batches expose ``supervision.row_train_mask``
    with one ``[S]`` row per lineage item.  The choice follows available
    structure only; no class name, schema version, or production import is
    consulted.
    """

    lineage = getattr(batch, "lineage", None)
    if not isinstance(lineage, (tuple, list)):
        raise ValueError("Q_H batch must expose a tuple or list lineage.")
    keys = _lineage_keys(lineage)
    transition = getattr(batch, "transition", None)
    supervision = getattr(batch, "supervision", None)
    mask = getattr(transition, "row_train_mask", None)
    if mask is None:
        mask = getattr(supervision, "row_train_mask", None)
    if mask is None:
        raise ValueError("Q_H batch lacks transition or supervision row_train_mask.")
    rows = _as_bool_rows(mask)
    if len(rows) != len(keys):
        raise ValueError(
            f"Q_H batch lineage length {len(keys)} does not match admission rows {len(rows)}."
        )
    return BatchWorkload(keys=keys, admitted_transitions=sum(sum(row) for row in rows))


def digest_keys(keys: Sequence[str]) -> str:
    """Return the SHA-256 of the exact ordered key sequence."""

    encoded = json.dumps(list(keys), ensure_ascii=False, separators=(",", ":")).encode(
        "utf-8"
    )
    return hashlib.sha256(encoded).hexdigest()


class CyclingLoader:
    """Resettable deterministic iterator shared by warmup and measurement."""

    def __init__(self, loader_factory: Callable[[], Iterable[Any]]) -> None:
        self._loader_factory = loader_factory
        self.reset()

    def reset(self) -> None:
        """Restart at the first non-shuffled workload batch and clear counters."""

        self._iterator: Iterator[Any] = iter(self._loader_factory())
        self.cycle_count = 0
        self._yielded_keys: list[str] = []
        self._admitted_transitions = 0
        self._batch_count = 0

    def cycling_next(self) -> BatchWorkload:
        """Yield one batch, recreating the same iterator exactly on exhaustion."""

        try:
            batch = next(self._iterator)
        except StopIteration:
            self._iterator = iter(self._loader_factory())
            self.cycle_count += 1
            try:
                batch = next(self._iterator)
            except StopIteration as error:
                raise ValueError("Q_H benchmark loader is empty.") from error
        self.last_raw_batch = batch
        workload = (
            batch if isinstance(batch, BatchWorkload) else extract_batch_workload(batch)
        )
        self._yielded_keys.extend(workload.keys)
        self._admitted_transitions += workload.admitted_transitions
        self._batch_count += 1
        return workload

    def summary(self) -> CycleSummary:
        """Return counters for the current interval."""

        return CycleSummary(
            batch_count=self._batch_count,
            cycle_count=self.cycle_count,
            admitted_transitions=self._admitted_transitions,
            yielded_key_digest=digest_keys(self._yielded_keys),
        )

    def warmup(self, batches: int = DEFAULT_WARMUP_BATCHES) -> CycleSummary:
        """Perform exactly five cycling calls by default, then reset to key zero."""

        if batches != DEFAULT_WARMUP_BATCHES:
            raise ValueError(
                f"Frozen Q_H warmup requires exactly {DEFAULT_WARMUP_BATCHES} batches."
            )
        self.reset()
        for _ in range(batches):
            self.cycling_next()
        summary = self.summary()
        self.reset()
        return summary


def ordered_workload_digest(loader_factory: Callable[[], Iterable[Any]]) -> str:
    """Digest every key in one frozen ordered, non-shuffled loader pass."""

    keys: list[str] = []
    for batch in loader_factory():
        workload = (
            batch if isinstance(batch, BatchWorkload) else extract_batch_workload(batch)
        )
        keys.extend(workload.keys)
    if not keys:
        raise ValueError("Q_H benchmark loader is empty.")
    return digest_keys(keys)


def runtime_versions() -> dict[str, str]:
    """Return runtime identity without treating optional packages as required."""

    versions = {"python": platform.python_version(), "platform": platform.platform()}
    for package in ("torch", "pytorch-lightning"):
        try:
            versions[package] = importlib.metadata.version(package)
        except importlib.metadata.PackageNotFoundError:
            versions[package] = "not-installed"
    return versions


def _vm_pin_bytes() -> tuple[int | None, str]:
    """Read current Linux pinned-memory accounting when exposed by the kernel."""

    status = Path("/proc/self/status")
    if not status.is_file():
        return None, "unavailable"
    for line in status.read_text(encoding="utf-8").splitlines():
        if line.startswith("VmPin:"):
            fields = line.split()
            return int(fields[1]) * 1024, "proc_status_vmpin"
    return None, "unavailable"


def _estimate_bytes(value: Any, seen: set[int] | None = None) -> int:
    """Estimate tensor payload bytes generically, retaining no production coupling."""

    seen = set() if seen is None else seen
    identity = id(value)
    if identity in seen:
        return 0
    seen.add(identity)
    if hasattr(value, "numel") and hasattr(value, "element_size"):
        return int(value.numel()) * int(value.element_size())
    if isinstance(value, dict):
        return sum(_estimate_bytes(item, seen) for item in value.values())
    if isinstance(value, (tuple, list)):
        return sum(_estimate_bytes(item, seen) for item in value)
    slots = getattr(type(value), "__slots__", ())
    attributes = tuple(slots) if isinstance(slots, (tuple, list)) else (slots,)
    if attributes:
        return sum(
            _estimate_bytes(getattr(value, name), seen)
            for name in attributes
            if hasattr(value, name)
        )
    if hasattr(value, "__dict__"):
        return _estimate_bytes(vars(value), seen)
    return 0


def run_repetition(
    loader_factory: Callable[[], Iterable[Any]],
    *,
    ordered_key_digest: str,
    batch_size: int,
    worker_count: int | None,
    min_batches: int = DEFAULT_MIN_BATCHES,
    min_seconds: float = DEFAULT_MIN_SECONDS,
    max_pinned_host_bytes: int = DEFAULT_MAX_PINNED_HOST_BYTES,
) -> BenchmarkRepetition:
    """Run the exact warmup/reset/dual-threshold protocol once."""

    if min_batches != DEFAULT_MIN_BATCHES or min_seconds != DEFAULT_MIN_SECONDS:
        raise ValueError("Frozen Q_H measurement requires 100 batches and 30 seconds.")
    cycling = CyclingLoader(loader_factory)
    warmup = cycling.warmup()
    started = time.perf_counter()
    peak_pinned, pin_source = _vm_pin_bytes()
    sample_bytes: int | None = None
    while (
        cycling.summary().batch_count < min_batches
        or time.perf_counter() - started < min_seconds
    ):
        cycling.cycling_next()
        if sample_bytes is None:
            sample_bytes = _estimate_bytes(cycling.last_raw_batch)
        pinned, observed_source = _vm_pin_bytes()
        pin_source = observed_source
        if pinned is not None:
            peak_pinned = pinned if peak_pinned is None else max(peak_pinned, pinned)
    elapsed = time.perf_counter() - started
    summary = cycling.summary()
    feasible = peak_pinned is not None and peak_pinned <= max_pinned_host_bytes
    return BenchmarkRepetition(
        warmup=warmup,
        batch_count=summary.batch_count,
        elapsed_seconds=elapsed,
        cycle_count=summary.cycle_count,
        admitted_transitions=summary.admitted_transitions,
        yielded_key_digest=summary.yielded_key_digest,
        ordered_key_digest=ordered_key_digest,
        bytes_per_sample_estimate=None
        if sample_bytes is None
        else sample_bytes / batch_size,
        peak_pinned_host_memory_bytes=peak_pinned,
        pinned_memory_source=pin_source,
        worker_count=worker_count,
        batch_size=batch_size,
        runtime_versions=runtime_versions(),
        feasible=feasible,
        infeasible_reason=None
        if feasible
        else "pinned-host-memory-unavailable-or-over-limit",
    )


def instrumentation_hashes(repo_root: Path, allowlist: Path) -> dict[str, str]:
    """Hash every allowlisted frozen instrument and reject missing entries."""

    payload = json.loads(allowlist.read_text(encoding="utf-8"))
    paths = payload.get("paths")
    if not isinstance(paths, list) or not all(isinstance(path, str) for path in paths):
        raise ValueError("Instrumentation allowlist must contain string paths.")
    if len(paths) != len(set(paths)):
        raise ValueError("Instrumentation allowlist contains duplicate paths.")
    hashes: dict[str, str] = {}
    for relative in paths:
        target = repo_root / relative
        if not target.is_file():
            raise FileNotFoundError(
                f"Frozen instrumentation path is missing: {relative}"
            )
        hashes[relative] = hashlib.sha256(target.read_bytes()).hexdigest()
    return hashes


def _load_factory(spec: str) -> Callable[[int], Iterable[Any]]:
    """Load an operator-supplied iterable factory without naming production DTOs."""

    module_name, separator, attribute = spec.partition(":")
    if not separator or not module_name or not attribute:
        raise ValueError("--loader-factory must be MODULE:ATTRIBUTE.")
    factory = getattr(importlib.import_module(module_name), attribute)
    if not callable(factory):
        raise ValueError("--loader-factory target must be callable.")
    return factory


def main(argv: Sequence[str] | None = None) -> int:
    """Run all configured batch sizes and write external JSON evidence."""

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument(
        "--loader-factory", required=True, help="MODULE:ATTRIBUTE accepting batch_size"
    )
    parser.add_argument(
        "--output", type=Path, required=True, help="External evidence JSON path"
    )
    parser.add_argument("--repo-root", type=Path, default=Path.cwd())
    parser.add_argument("--execution-commit", required=True)
    arguments = parser.parse_args(argv)
    config = json.loads(arguments.config.read_text(encoding="utf-8"))
    factory = _load_factory(arguments.loader_factory)
    repetitions: list[dict[str, Any]] = []
    for batch_size in config["batch_sizes"]:
        loader_factory = partial(factory, batch_size)
        ordered_digest = ordered_workload_digest(loader_factory)
        for repetition in range(config["repetitions"]):
            result = run_repetition(
                loader_factory,
                ordered_key_digest=ordered_digest,
                batch_size=batch_size,
                worker_count=config.get("worker_count"),
                max_pinned_host_bytes=config["max_pinned_host_bytes"],
            )
            repetitions.append({"repetition": repetition, **asdict(result)})
    evidence = {
        "schema_version": SCHEMA_VERSION,
        "execution_commit": arguments.execution_commit,
        "config": config,
        "instrumentation_hashes": instrumentation_hashes(
            arguments.repo_root, arguments.repo_root / config["allowlist_path"]
        ),
        "repetitions": repetitions,
    }
    arguments.output.parent.mkdir(parents=True, exist_ok=True)
    arguments.output.write_text(
        json.dumps(evidence, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
