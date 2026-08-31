#!/usr/bin/env python3
"""Measure Architecture-1 candidate-interface parity on two local ARIA scenes."""

from __future__ import annotations

import argparse
import contextlib
import io
import json
import resource
import statistics
import tempfile
import threading
import time
from pathlib import Path
from typing import Any, Callable

import psutil
import torch
from torch.profiler import ProfilerActivity, profile

from aria_nbv.configs import PathConfig
from aria_nbv.data_handling import AseEfmDatasetConfig
from aria_nbv.geometry import PreparedMeshQuery
from aria_nbv.oracle.pipelines.rollout_dataset import RolloutDatasetWriterConfig
from aria_nbv.pose_generation.candidate_interface import (
    ActorTargetContext,
    CandidateConditioning,
    CandidateRequest,
    GeometrySourceRole,
    PreparedCandidateScene,
    candidate_set_to_legacy_result,
)
from aria_nbv.pose_generation.candidate_program import compile_candidate_program
from aria_nbv.pose_generation.positional_sampling import PositionSampler
from aria_nbv.pose_generation.program_generator import ProgramCandidateGenerator
from aria_nbv.pose_generation.sampling_keys import (
    CandidateSamplingKey,
    CandidateSubstreamRevision,
)
from aria_nbv.pose_generation.types import CandidateGenerationRuntimeContext
from aria_nbv.targets import TargetDescriptor
from aria_nbv.utils import Verbosity
from aria_nbv.utils.canonical_binding import canonical_binding_sha256


def _quiet_call(call: Callable[[], Any]) -> Any:
    with (
        contextlib.redirect_stdout(io.StringIO()),
        contextlib.redirect_stderr(io.StringIO()),
    ):
        return call()


def _latencies_ms(call: Callable[[], Any], count: int) -> list[float]:
    values: list[float] = []
    for _ in range(count):
        torch.cuda.synchronize()
        start = time.perf_counter_ns()
        _quiet_call(call)
        torch.cuda.synchronize()
        values.append((time.perf_counter_ns() - start) / 1e6)
    return values


def _paired_latency_batches(
    first: Callable[[], Any],
    second: Callable[[], Any],
    *,
    batches: int,
    calls_per_batch: int,
) -> tuple[list[list[float]], list[list[float]]]:
    """Measure two implementations in alternating order to limit temporal bias."""
    first_batches: list[list[float]] = []
    second_batches: list[list[float]] = []
    for batch_index in range(batches):
        if batch_index % 2 == 0:
            first_values = _latencies_ms(first, calls_per_batch)
            second_values = _latencies_ms(second, calls_per_batch)
        else:
            second_values = _latencies_ms(second, calls_per_batch)
            first_values = _latencies_ms(first, calls_per_batch)
        first_batches.append(first_values)
        second_batches.append(second_values)
    return first_batches, second_batches


def _batched_summary(batches: list[list[float]]) -> dict[str, Any]:
    flattened = [value for batch in batches for value in batch]
    return {
        **_summary(flattened),
        "batches": [_summary(batch) for batch in batches],
    }


def _summary(values: list[float]) -> dict[str, float]:
    ordered = sorted(values)
    p95_index = min(len(ordered) - 1, max(0, int(0.95 * len(ordered))))
    return {
        "count": float(len(values)),
        "p50_ms": statistics.median(values),
        "p95_ms": ordered[p95_index],
    }


def _rss_peak_bytes(call: Callable[[], Any], count: int = 10) -> int:
    process = psutil.Process()
    samples: list[int] = []
    stop = threading.Event()

    def sample() -> None:
        while not stop.is_set():
            samples.append(process.memory_info().rss)
            time.sleep(0.001)

    thread = threading.Thread(target=sample, daemon=True)
    thread.start()
    try:
        for _ in range(count):
            _quiet_call(call)
        torch.cuda.synchronize()
    finally:
        stop.set()
        thread.join()
    samples.append(process.memory_info().rss)
    return max(samples)


def _cuda_peak_bytes(call: Callable[[], Any], count: int = 10) -> int:
    torch.cuda.empty_cache()
    torch.cuda.reset_peak_memory_stats()
    for _ in range(count):
        _quiet_call(call)
    torch.cuda.synchronize()
    return torch.cuda.max_memory_allocated()


def _transfer_stats(call: Callable[[], Any]) -> dict[str, Any]:
    with profile(activities=[ProfilerActivity.CPU, ProfilerActivity.CUDA]) as measured:
        _quiet_call(call)
        torch.cuda.synchronize()
    with tempfile.NamedTemporaryFile(suffix=".json") as trace:
        measured.export_chrome_trace(trace.name)
        payload = json.loads(Path(trace.name).read_text())
    rows = [
        event for event in payload["traceEvents"] if event.get("cat") == "gpu_memcpy"
    ]
    by_direction: dict[str, dict[str, int]] = {}
    for row in rows:
        name = str(row["name"])
        bucket = by_direction.setdefault(name, {"count": 0, "bytes": 0})
        bucket["count"] += 1
        bucket["bytes"] += int(row.get("args", {}).get("bytes", 0))
    host_device = {
        name: values
        for name, values in by_direction.items()
        if "HtoD" in name or "DtoH" in name
    }
    return {
        "total_count": len(rows),
        "total_bytes": sum(row["bytes"] for row in by_direction.values()),
        "host_device_count": sum(row["count"] for row in host_device.values()),
        "host_device_bytes": sum(row["bytes"] for row in host_device.values()),
        "by_direction": by_direction,
    }


def _instrument_one_call(call: Callable[[], Any]) -> dict[str, int]:
    counters = {
        "prepared_query_calls": 0,
        "prepared_query_creations": 0,
        "center_sampling_calls": 0,
    }
    original_acquire = PreparedMeshQuery.acquire.__func__
    original_sample = PositionSampler.sample

    def acquire(cls, prepared, *args, **kwargs):
        counters["prepared_query_calls"] += 1
        result = original_acquire(cls, prepared, *args, **kwargs)
        counters["prepared_query_creations"] += int(result is not prepared)
        return result

    def sample(self, *args, **kwargs):
        counters["center_sampling_calls"] += 1
        return original_sample(self, *args, **kwargs)

    PreparedMeshQuery.acquire = classmethod(acquire)
    PositionSampler.sample = sample
    try:
        _quiet_call(call)
        torch.cuda.synchronize()
    finally:
        PreparedMeshQuery.acquire = classmethod(original_acquire)
        PositionSampler.sample = original_sample
    return counters


def _scene_verdict(result: dict[str, Any]) -> dict[str, Any]:
    legacy = result["legacy"]
    candidate = result["candidate_program"]
    ratios = {
        "cold_p50": candidate["cold"]["p50_ms"] / legacy["cold"]["p50_ms"],
        "warm_p50": candidate["warm"]["p50_ms"] / legacy["warm"]["p50_ms"],
        "warm_p95": candidate["warm"]["p95_ms"] / legacy["warm"]["p95_ms"],
        "peak_rss": candidate["peak_rss_bytes"] / legacy["peak_rss_bytes"],
        "peak_cuda_allocated": (
            candidate["peak_cuda_allocated_bytes"] / legacy["peak_cuda_allocated_bytes"]
        ),
    }
    checks = {
        "cold_p50_at_most_1_10x": ratios["cold_p50"] <= 1.10,
        "warm_p50_at_most_1_05x": ratios["warm_p50"] <= 1.05,
        "warm_p95_at_most_1_10x": ratios["warm_p95"] <= 1.10,
        "peak_rss_within_gate": candidate["peak_rss_bytes"]
        <= max(1.10 * legacy["peak_rss_bytes"], legacy["peak_rss_bytes"] + 64 * 2**20),
        "peak_cuda_allocated_within_gate": candidate["peak_cuda_allocated_bytes"]
        <= max(
            1.05 * legacy["peak_cuda_allocated_bytes"],
            legacy["peak_cuda_allocated_bytes"] + 64 * 2**20,
        ),
        "host_device_transfer_count_no_increase": candidate["transfers"][
            "host_device_count"
        ]
        <= legacy["transfers"]["host_device_count"],
        "host_device_transfer_bytes_no_increase": candidate["transfers"][
            "host_device_bytes"
        ]
        <= legacy["transfers"]["host_device_bytes"],
        "zero_warm_query_acquisitions": candidate["one_warm_call"][
            "prepared_query_calls"
        ]
        == 0,
        "zero_warm_query_creations": candidate["one_warm_call"][
            "prepared_query_creations"
        ]
        == 0,
        "one_cold_query_acquisition": candidate["one_cold_call"]["prepared_query_calls"]
        == 1,
        "one_cold_query_creation": candidate["one_cold_call"][
            "prepared_query_creations"
        ]
        == 1,
        "one_center_call_per_group": candidate["one_warm_call"]["center_sampling_calls"]
        == result["program_groups"],
        "exact_shell_views_mask_parity": all(
            result["parity"][name] for name in ("shell", "views", "mask")
        ),
    }
    return {"passed": all(checks.values()), "ratios": ratios, "checks": checks}


def _target_context(
    reference_pose,
) -> tuple[ActorTargetContext, CandidateGenerationRuntimeContext]:
    center = reference_pose.t.reshape(-1).detach().cpu() + torch.tensor([0.0, 0.0, 2.0])
    pose = (1.0, 0.0, 0.0, 0.0, 1.0, 0.0, 0.0, 0.0, 1.0, *map(float, center.tolist()))
    descriptor = TargetDescriptor(
        sem_id=1,
        class_name="benchmark_target",
        pose_world_object=pose,
        extents_m=(1.0, 1.0, 1.0),
        relative_pose_reference_object=pose,
    )
    actor = ActorTargetContext(
        descriptor=descriptor,
        protocol_version="benchmark_v1_observed",
        descriptor_hash=canonical_binding_sha256(descriptor),
        source_binding_hash="benchmark-actor-visible-source",
    )
    return actor, CandidateGenerationRuntimeContext(descriptor=descriptor)


def _scene_benchmark(
    scene_id: str,
    config_path: Path,
    *,
    warm_batches: int,
    warm_calls: int,
    cold_calls: int,
) -> dict[str, Any]:
    dataset = AseEfmDatasetConfig(
        scene_ids=[scene_id],
        batch_size=None,
        load_meshes=True,
        require_mesh=True,
        mesh_simplify_ratio=0.02,
        device="cpu",
        verbosity=Verbosity.QUIET,
        is_debug=False,
    ).setup_target()
    sample = next(iter(dataset))
    device = torch.device("cuda")
    verts = sample.mesh_verts.to(device=device, dtype=torch.float32)
    faces = sample.mesh_faces.to(device=device, dtype=torch.int64)
    reference_pose = sample.trajectory.final_pose.to(device=device)
    camera = sample.get_camera("rgb").calib.to(device=device)
    extent = sample.get_occupancy_extend().to(device=device, dtype=torch.float32)
    actor, runtime = _target_context(reference_pose)
    writer = RolloutDatasetWriterConfig.from_toml(config_path)
    config = writer.candidate_mixture.model_copy(
        update={
            "base": writer.candidate_mixture.base.model_copy(
                update={"device": device, "verbosity": 0}
            )
        }
    )
    program = compile_candidate_program(config)

    def new_bundle():
        query = PreparedMeshQuery.acquire(
            None,
            verts,
            faces,
            device=device,
            dtype=torch.float32,
            mesh=sample.mesh,
        )
        scene = PreparedCandidateScene(
            scene_identity=f"{scene_id}:benchmark-snippet",
            source_binding_hash=f"{scene_id}:benchmark-source",
            mesh_identity=f"{scene_id}:processed-mesh",
            gt_mesh=sample.mesh,
            mesh_verts=verts,
            mesh_faces=faces,
            prepared_mesh_query=query,
            occupancy_extent_world=extent,
            camera_calibration=camera,
            camera_calibration_hash=canonical_binding_sha256(camera),
            geometry_source_role=GeometrySourceRole.ORACLE_ADMISSION,
            device=device,
            dtype=torch.float32,
        )
        request = CandidateRequest.bind(
            program=program,
            conditioning=CandidateConditioning(reference_pose),
            scene=scene,
            actor_target=actor,
            random_key=CandidateSamplingKey(
                CandidateSubstreamRevision.SHIPPED_V1,
                "rollout_proposal",
                17,
            ),
        )
        generator = ProgramCandidateGenerator()
        return generator, request

    def legacy_cold():
        return config.setup_target().generate(
            reference_pose=reference_pose,
            gt_mesh=sample.mesh,
            mesh_verts=verts,
            mesh_faces=faces,
            camera_calib_template=camera,
            occupancy_extent=extent,
            runtime_context=runtime,
            seed=17,
        )

    def new_cold():
        generator, request = new_bundle()
        return generator.generate(request)

    legacy_generator = config.setup_target()

    def legacy_warm():
        return legacy_generator.generate(
            reference_pose=reference_pose,
            gt_mesh=sample.mesh,
            mesh_verts=verts,
            mesh_faces=faces,
            camera_calib_template=camera,
            occupancy_extent=extent,
            runtime_context=runtime,
            seed=17,
        )

    new_generator, new_request = new_bundle()

    def new_warm():
        return new_generator.generate(new_request)

    for _ in range(5):
        _quiet_call(legacy_warm)
        _quiet_call(new_warm)
    torch.cuda.synchronize()
    legacy_result = _quiet_call(legacy_warm)
    new_result = candidate_set_to_legacy_result(_quiet_call(new_warm))
    parity = {
        "shell": torch.equal(
            legacy_result.shell_poses.tensor(), new_result.shell_poses.tensor()
        ),
        "views": torch.equal(legacy_result.views.tensor(), new_result.views.tensor()),
        "views_allclose_1e-6": torch.allclose(
            legacy_result.views.tensor(),
            new_result.views.tensor(),
            atol=1e-6,
            rtol=1e-6,
        ),
        "views_max_abs_delta": float(
            (legacy_result.views.tensor() - new_result.views.tensor())
            .abs()
            .max()
            .item()
        ),
        "mask": torch.equal(legacy_result.mask_valid, new_result.mask_valid),
    }
    if not parity["shell"] or not parity["mask"] or not parity["views_allclose_1e-6"]:
        raise RuntimeError(f"Candidate parity failed for scene {scene_id}: {parity}")

    legacy_cold_batches, new_cold_batches = _paired_latency_batches(
        legacy_cold,
        new_cold,
        batches=1,
        calls_per_batch=cold_calls,
    )
    legacy_warm_batches, new_warm_batches = _paired_latency_batches(
        legacy_warm,
        new_warm,
        batches=warm_batches,
        calls_per_batch=warm_calls,
    )

    result = {
        "scene_id": scene_id,
        "mesh_vertices": int(verts.shape[0]),
        "mesh_faces": int(faces.shape[0]),
        "program_groups": len(program.groups),
        "parity": parity,
        "legacy": {
            "cold": _batched_summary(legacy_cold_batches),
            "warm": _batched_summary(legacy_warm_batches),
            "peak_rss_bytes": _rss_peak_bytes(legacy_warm),
            "peak_cuda_allocated_bytes": _cuda_peak_bytes(legacy_warm),
            "transfers": _transfer_stats(legacy_warm),
            "one_cold_call": _instrument_one_call(legacy_cold),
            "one_warm_call": _instrument_one_call(legacy_warm),
        },
        "candidate_program": {
            "cold": _batched_summary(new_cold_batches),
            "warm": _batched_summary(new_warm_batches),
            "peak_rss_bytes": _rss_peak_bytes(new_warm),
            "peak_cuda_allocated_bytes": _cuda_peak_bytes(new_warm),
            "transfers": _transfer_stats(new_warm),
            "one_cold_call": _instrument_one_call(new_cold),
            "one_warm_call": _instrument_one_call(new_warm),
        },
    }
    result["verdict"] = _scene_verdict(result)
    if not result["verdict"]["passed"]:
        raise RuntimeError(
            f"Candidate performance gate failed for scene {scene_id}: "
            f"{result['verdict']}"
        )
    return result


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo-root", type=Path, default=Path.cwd())
    parser.add_argument(
        "--config",
        type=Path,
        default=Path(".configs/build_rollouts_v1_cuda_campaign_writer.toml"),
    )
    parser.add_argument("--scenes", nargs="+", default=["81283", "81807"])
    parser.add_argument("--warm-batches", type=int, default=5)
    parser.add_argument("--warm-calls", type=int, default=30)
    parser.add_argument("--cold-calls", type=int, default=5)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    if not torch.cuda.is_available():
        raise RuntimeError("CUDA is required for the Architecture-1 performance gate.")
    repo_root = args.repo_root.resolve()
    PathConfig(root=repo_root)
    config = args.config if args.config.is_absolute() else repo_root / args.config
    started = time.time()
    scenes = [
        _scene_benchmark(
            scene_id,
            config,
            warm_batches=args.warm_batches,
            warm_calls=args.warm_calls,
            cold_calls=args.cold_calls,
        )
        for scene_id in args.scenes
    ]
    result = {
        "schema": "candidate_interface_pr1_performance_v1",
        "hardware": {
            "gpu": torch.cuda.get_device_name(0),
            "cuda": torch.version.cuda,
            "torch": torch.__version__,
            "python_peak_rss_bytes": resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
            * 1024,
        },
        "config": str(config),
        "warmups": 5,
        "warm_batches": args.warm_batches,
        "warm_calls": args.warm_calls,
        "cold_calls": args.cold_calls,
        "duration_s": time.time() - started,
        "scenes": scenes,
        "passed": all(scene["verdict"]["passed"] for scene in scenes),
    }
    text = json.dumps(result, indent=2, sort_keys=True)
    if args.output is not None:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(text + "\n")
    print(text)


if __name__ == "__main__":
    main()
