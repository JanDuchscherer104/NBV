"""Shared helpers for processing and caching GT meshes.

This module centralises mesh cropping/simplification and persistence so that
both candidate generation (collision checks) and depth rendering can reuse the
same processed mesh without duplicating logic.
"""

from __future__ import annotations

import fcntl
import hashlib
import json
import os
import tempfile
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Any

import torch
import trimesh  # type: ignore[import-untyped]

from ..configs.path_config import PathConfig
from ..utils import Console

if TYPE_CHECKING:  # pragma: no cover
    pass


@dataclass(slots=True)
class MeshProcessSpec:
    """Specification that uniquely defines a processed mesh artifact."""

    scene_id: str
    """Scene identifier used for cache-path resolution."""

    crop: bool
    """Whether the mesh should be cropped to snippet bounds."""

    bounds_min: list[float]
    """World-space minimum crop bounds."""

    bounds_max: list[float]
    """World-space maximum crop bounds."""

    margin_m: float
    """Margin added to the crop bounds before clipping the mesh."""

    simplify_ratio: float | None
    """Optional face-count ratio used for mesh simplification."""

    crop_min_keep_ratio: float
    """Minimum face keep ratio tolerated during cropping."""

    def hash(self) -> str:
        """Stable short hash for filenames and cache keys."""

        payload: dict[str, Any] = {
            "scene_id": self.scene_id,
            "crop": self.crop,
            "margin_m": round(self.margin_m, 4),
            "simplify_ratio": None if self.simplify_ratio is None else round(self.simplify_ratio, 4),
        }
        if self.crop:
            payload["bounds_min"] = [round(x, 4) for x in self.bounds_min]
            payload["bounds_max"] = [round(x, 4) for x in self.bounds_max]
            payload["crop_min_keep_ratio"] = round(self.crop_min_keep_ratio, 4)

        spec_json = json.dumps(payload, sort_keys=True)
        return hashlib.sha1(spec_json.encode("utf-8")).hexdigest()[:12]


@dataclass(slots=True)
class ProcessedMesh:
    """Container for processed mesh and cached tensors."""

    mesh: trimesh.Trimesh
    """Processed mesh object."""

    bounds: tuple[torch.Tensor, torch.Tensor]
    """World-space bounds associated with the processed mesh."""

    verts: torch.Tensor
    """Cached vertex tensor for downstream tensor-based consumers."""

    faces: torch.Tensor
    """Cached face tensor for downstream tensor-based consumers."""

    cache_hit: bool
    """Whether the processed mesh was loaded from disk cache."""

    path: Path
    """Filesystem path of the processed mesh artifact."""

    spec_hash: str
    """Stable hash of the processing specification."""


@contextmanager
def _mesh_cache_lock(out_path: Path) -> Iterator[None]:
    """Serialize access to one processed-mesh artifact across processes."""

    lock_path = out_path.with_suffix(f"{out_path.suffix}.lock")
    with lock_path.open("a+") as lock_file:
        fcntl.flock(lock_file.fileno(), fcntl.LOCK_EX)
        try:
            yield
        finally:
            fcntl.flock(lock_file.fileno(), fcntl.LOCK_UN)


def _processed_mesh_from_cache(out_path: Path, spec: MeshProcessSpec, *, console: Console | None) -> ProcessedMesh:
    """Load one validated processed-mesh artifact from disk."""

    mesh_proc = trimesh.load(out_path, process=False)
    assert isinstance(mesh_proc, trimesh.Trimesh)
    if console:
        console.dbg(f"Loaded processed mesh from cache: crop={spec.crop}, simplify_ratio={spec.simplify_ratio}")

    return ProcessedMesh(
        mesh=mesh_proc,
        bounds=(
            torch.as_tensor(spec.bounds_min, dtype=torch.float32),
            torch.as_tensor(spec.bounds_max, dtype=torch.float32),
        ),
        verts=torch.as_tensor(mesh_proc.vertices, dtype=torch.float32),
        faces=torch.as_tensor(mesh_proc.faces, dtype=torch.int64),
        cache_hit=True,
        path=out_path,
        spec_hash=spec.hash(),
    )


def _crop_mesh(
    mesh: trimesh.Trimesh,
    bounds_min: torch.Tensor,
    bounds_max: torch.Tensor,
    margin_m: float,
    *,
    crop_min_keep_ratio: float,
    console: Console | None,
) -> trimesh.Trimesh:
    """Crop a mesh to the requested bounds while keeping face connectivity."""
    lo = (bounds_min - margin_m).numpy()
    hi = (bounds_max + margin_m).numpy()

    verts = mesh.vertices
    in_bounds = ((verts >= lo) & (verts <= hi)).all(axis=1)
    if not in_bounds.any():
        if console:
            console.warn("Mesh cropping skipped: no vertices within bounds; returning original mesh.")
        return mesh

    face_mask = in_bounds[mesh.faces].any(axis=1)
    if not face_mask.any():
        if console:
            console.warn("Mesh cropping skipped: no faces intersect bounds; returning original mesh.")
        return mesh

    cropped = mesh.submesh([face_mask], append=True)
    assert isinstance(cropped, trimesh.Trimesh)

    keep_ratio = cropped.faces.shape[0] / float(mesh.faces.shape[0])
    if keep_ratio < crop_min_keep_ratio:
        if console:
            console.warn(f"Cropping dropped too many faces (keep_ratio={keep_ratio:.3f} < {crop_min_keep_ratio}).")

    return cropped


def load_or_process_mesh(
    mesh: trimesh.Trimesh,
    spec: MeshProcessSpec,
    paths: PathConfig,
    *,
    console: Console | None = None,
) -> ProcessedMesh:
    """Crop/simplify a mesh once and persist the result on disk.

    Args:
        mesh: Raw scene mesh.
        spec: Processing specification (bounds, simplification, etc.).
        paths: PathConfig providing the processed-mesh directory.
        console: Optional logger.

    Returns:
        ProcessedMesh with trimesh object, bounds, torch tensors, and cache flag.
    """

    spec_hash = spec.hash()
    out_path = paths.resolve_processed_mesh_path(
        spec.scene_id, simplification_ratio=spec.simplify_ratio, is_crop=spec.crop, spec_hash=spec_hash
    )
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with _mesh_cache_lock(out_path):
        if out_path.exists():
            try:
                return _processed_mesh_from_cache(out_path, spec, console=console)
            except (AssertionError, IndexError, OSError, ValueError) as exc:
                if console:
                    console.warn(f"Discarding unreadable processed mesh cache {out_path}: {exc}")
                out_path.unlink()

        mesh_work = mesh.copy()

        faces_before = mesh_work.faces.shape[0]
        target_faces = faces_before
        if spec.simplify_ratio not in (None, 0):
            target_faces = min(target_faces, int(faces_before * spec.simplify_ratio))

        # Bounds are needed for the return value regardless of cropping
        bounds_min = torch.as_tensor(spec.bounds_min, dtype=torch.float32)
        bounds_max = torch.as_tensor(spec.bounds_max, dtype=torch.float32)

        if spec.crop:
            mesh_work = _crop_mesh(
                mesh_work,
                bounds_min=bounds_min,
                bounds_max=bounds_max,
                margin_m=spec.margin_m,
                crop_min_keep_ratio=spec.crop_min_keep_ratio,
                console=console,
            )
            if console:
                console.dbg(
                    f"Cropped mesh from {faces_before} to {mesh_work.faces.shape[0]} faces within bounds "
                    f"[{spec.bounds_min}] - [{spec.bounds_max}] with margin {spec.margin_m} m."
                )

        if target_faces < mesh_work.faces.shape[0]:
            mesh_work = mesh_work.simplify_quadric_decimation(face_count=target_faces)
            if console:
                console.dbg(
                    f"Simplified mesh from {faces_before} to {mesh_work.faces.shape[0]} faces (target={target_faces}) with ratio {spec.simplify_ratio}."
                )

        file_descriptor, temp_name = tempfile.mkstemp(
            dir=out_path.parent,
            prefix=f".{out_path.stem}.",
            suffix=".tmp.ply",
        )
        os.close(file_descriptor)
        temp_path = Path(temp_name)
        try:
            mesh_work.export(temp_path)
            os.replace(temp_path, out_path)
        finally:
            temp_path.unlink(missing_ok=True)
        if console:
            console.dbg(f"Saved processed mesh to {out_path}")

        return ProcessedMesh(
            mesh=mesh_work,
            bounds=(bounds_min, bounds_max),
            verts=torch.as_tensor(mesh_work.vertices, dtype=torch.float32),
            faces=torch.as_tensor(mesh_work.faces, dtype=torch.int64),
            cache_hit=False,
            path=out_path,
            spec_hash=spec_hash,
        )


__all__ = [
    "MeshProcessSpec",
    "ProcessedMesh",
    "load_or_process_mesh",
]
