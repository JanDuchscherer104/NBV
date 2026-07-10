import multiprocessing
import time
from pathlib import Path

import torch
import trimesh

from aria_nbv.configs import PathConfig
from aria_nbv.data_handling.mesh_cache import MeshProcessSpec, load_or_process_mesh
from aria_nbv.utils import Console


def _mesh_spec() -> MeshProcessSpec:
    return MeshProcessSpec(
        scene_id="123",
        crop=True,
        bounds_min=[-1.0, -1.0, -1.0],
        bounds_max=[1.0, 1.0, 1.0],
        margin_m=0.1,
        simplify_ratio=0.5,
        crop_min_keep_ratio=0.1,
    )


def _load_shared_mesh(cache_root: str, barrier, result_queue) -> None:
    """Request one cache artifact while deliberately holding the export lock."""

    original_export = trimesh.Trimesh.export

    def delayed_export(self, *args, **kwargs):
        result = original_export(self, *args, **kwargs)
        time.sleep(0.2)
        return result

    trimesh.Trimesh.export = delayed_export
    try:
        barrier.wait(timeout=10)
        processed = load_or_process_mesh(
            trimesh.creation.box(extents=(1.0, 1.0, 1.0)),
            _mesh_spec(),
            PathConfig(root=Path(cache_root)),
        )
        result_queue.put((processed.cache_hit, processed.faces.shape[0]))
    finally:
        trimesh.Trimesh.export = original_export


def test_processed_mesh_is_cached(tmp_path):
    console = Console.with_prefix("test_mesh_cache")
    path_cfg = PathConfig(root=tmp_path)

    mesh_raw = trimesh.creation.box(extents=(1.0, 1.0, 1.0))
    spec = _mesh_spec()

    processed_first = load_or_process_mesh(mesh_raw, spec, path_cfg, console=console)
    assert processed_first.path.exists()
    faces_first = processed_first.faces.shape[0]
    assert faces_first > 0
    assert not processed_first.cache_hit

    # second call should reuse cache and keep face count
    processed_second = load_or_process_mesh(mesh_raw, spec, path_cfg, console=console)
    assert processed_second.cache_hit
    assert processed_second.faces.shape[0] == faces_first
    assert torch.allclose(processed_second.verts.float(), processed_first.verts.float())


def test_processed_mesh_cache_rebuilds_unreadable_artifact(tmp_path):
    path_cfg = PathConfig(root=tmp_path)
    spec = _mesh_spec()
    out_path = path_cfg.resolve_processed_mesh_path(
        spec.scene_id,
        simplification_ratio=spec.simplify_ratio,
        is_crop=spec.crop,
        spec_hash=spec.hash(),
    )
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_bytes(b"not a valid PLY")

    processed = load_or_process_mesh(trimesh.creation.box(extents=(1.0, 1.0, 1.0)), spec, path_cfg)

    assert not processed.cache_hit
    assert isinstance(trimesh.load(out_path, process=False), trimesh.Trimesh)


def test_processed_mesh_cache_serializes_concurrent_writers(tmp_path):
    context = multiprocessing.get_context("spawn")
    barrier = context.Barrier(2)
    result_queue = context.Queue()
    workers = [context.Process(target=_load_shared_mesh, args=(str(tmp_path), barrier, result_queue)) for _ in range(2)]

    for worker in workers:
        worker.start()
    for worker in workers:
        worker.join(timeout=30)
        assert worker.exitcode == 0

    results = [result_queue.get(timeout=5) for _ in workers]
    assert sorted(cache_hit for cache_hit, _ in results) == [False, True]
    assert len({face_count for _, face_count in results}) == 1

    cached = load_or_process_mesh(
        trimesh.creation.box(extents=(1.0, 1.0, 1.0)),
        _mesh_spec(),
        PathConfig(root=tmp_path),
    )
    assert cached.cache_hit
