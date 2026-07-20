"""Export a controlled point--mesh metric fixture and exact witnesses.

The fixture isolates the implemented PyTorch3D distance reductions from scene,
camera, object-shape, and decimation effects.  It is deliberately synthetic:
the same planar support and point set are evaluated under a coarse and a
non-uniformly refined tessellation.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
import torch
import trimesh
from pytorch3d.loss.point_mesh_distance import (
    _DEFAULT_MIN_TRIANGLE_AREA,
    face_point_distance,
)

from aria_nbv.rri_metrics.point_mesh import chamfer_point_mesh


def parse_args() -> argparse.Namespace:
    """Parse the output path for the deterministic fixture."""
    repo_root = Path(__file__).resolve().parents[5]
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--output",
        type=Path,
        default=repo_root
        / "docs/typst/thesis/figures/data/point_mesh_metric_fixture.json",
    )
    return parser.parse_args()


def _grid_mesh(xs: list[float], ys: list[float]) -> tuple[np.ndarray, np.ndarray]:
    """Triangulate a planar Cartesian grid with a fixed diagonal."""
    vertices = np.asarray([[x, y, 0.0] for y in ys for x in xs], dtype=np.float32)
    faces: list[list[int]] = []
    nx = len(xs)
    for row in range(len(ys) - 1):
        for column in range(nx - 1):
            a = row * nx + column
            b = a + 1
            c = a + nx
            d = c + 1
            faces.extend(((a, b, d), (a, d, c)))
    return vertices, np.asarray(faces, dtype=np.int64)


def _project(points: np.ndarray) -> np.ndarray:
    """Apply the fixed oblique projection used by the vector figure."""
    points = np.asarray(points, dtype=np.float64)
    return np.column_stack(
        (
            points[..., 0] + 0.34 * points[..., 1],
            points[..., 2] + 0.55 * points[..., 1],
        )
    )


def _point_to_face_witnesses(
    points: np.ndarray,
    vertices: np.ndarray,
    faces: np.ndarray,
) -> list[dict[str, object]]:
    """Return the exact closest triangle point for every query point."""
    triangles = vertices[faces]
    witnesses: list[dict[str, object]] = []
    for point_index, point in enumerate(points):
        tiled_points = np.repeat(point[None, :], len(triangles), axis=0)
        closest = trimesh.triangles.closest_point(triangles, tiled_points)
        squared = np.sum((closest - tiled_points) ** 2, axis=1)
        face_index = int(np.argmin(squared))
        witnesses.append(
            {
                "point_index": point_index,
                "face_index": face_index,
                "point": _project(point[None, :])[0].tolist(),
                "closest": _project(closest[face_index][None, :])[0].tolist(),
                "squared_distance_m2": float(squared[face_index]),
            }
        )
    return witnesses


def _face_to_point_witnesses(
    points: np.ndarray,
    vertices: np.ndarray,
    faces: np.ndarray,
) -> list[dict[str, object]]:
    """Return the exact closest reconstruction point for every triangle."""
    triangles = vertices[faces]
    witnesses: list[dict[str, object]] = []
    for face_index, triangle in enumerate(triangles):
        tiled_triangles = np.repeat(triangle[None, :, :], len(points), axis=0)
        closest = trimesh.triangles.closest_point(tiled_triangles, points)
        squared = np.sum((closest - points) ** 2, axis=1)
        point_index = int(np.argmin(squared))
        witnesses.append(
            {
                "face_index": face_index,
                "point_index": point_index,
                "point": _project(points[point_index][None, :])[0].tolist(),
                "closest": _project(closest[point_index][None, :])[0].tolist(),
                "squared_distance_m2": float(squared[point_index]),
            }
        )
    return witnesses


def _metric_payload(
    name: str,
    vertices: np.ndarray,
    faces: np.ndarray,
    points: np.ndarray,
) -> dict[str, object]:
    """Evaluate the repository-owned metric and serialize display geometry."""
    vertices_t = torch.as_tensor(vertices, dtype=torch.float32)
    faces_t = torch.as_tensor(faces, dtype=torch.int64)
    points_t = torch.as_tensor(points, dtype=torch.float32)
    metric = chamfer_point_mesh(points_t, vertices_t, faces_t)

    triangles_t = vertices_t[faces_t]
    per_face = face_point_distance(
        points_t,
        torch.tensor([0], dtype=torch.int64),
        triangles_t,
        torch.tensor([0], dtype=torch.int64),
        len(faces),
        _DEFAULT_MIN_TRIANGLE_AREA,
    )
    accuracy = float(metric.accuracy.item())
    completeness = float(metric.completeness.item())
    bidirectional = float(metric.bidirectional.item())
    return {
        "name": name,
        "vertices": _project(vertices).tolist(),
        "faces": faces.tolist(),
        "points": _project(points).tolist(),
        "accuracy_m2": accuracy,
        "completeness_m2": completeness,
        "bidirectional_m2": bidirectional,
        "accuracy_display": f"{accuracy:.5f}",
        "completeness_display": f"{completeness:.5f}",
        "bidirectional_display": f"{bidirectional:.5f}",
        "per_face_completeness_m2": per_face.detach().cpu().tolist(),
        "point_to_face_witnesses": _point_to_face_witnesses(points, vertices, faces),
        "face_to_point_witnesses": _face_to_point_witnesses(points, vertices, faces),
    }


def main() -> None:
    """Write the exact primitive and controlled tessellation comparison."""
    args = parse_args()
    points = np.asarray(
        (
            (0.20, 0.20, 0.08),
            (0.20, 0.80, 0.08),
            (0.80, 0.20, 0.08),
            (0.80, 0.80, 0.08),
            (0.50, 0.50, 0.08),
        ),
        dtype=np.float32,
    )
    coarse_vertices, coarse_faces = _grid_mesh([0.0, 1.0, 2.0], [0.0, 1.0])
    refined_vertices, refined_faces = _grid_mesh(
        [0.0, 0.25, 0.50, 0.75, 1.0, 2.0],
        [0.0, 0.25, 0.50, 0.75, 1.0],
    )

    primitive_triangle = np.asarray(
        ((0.0, 0.0, 0.0), (1.45, 0.0, 0.0), (0.32, 1.05, 0.0)),
        dtype=np.float32,
    )
    primitive_point = np.asarray((0.48, 0.34, 0.58), dtype=np.float32)
    primitive_closest = trimesh.triangles.closest_point(
        primitive_triangle[None, :, :],
        primitive_point[None, :],
    )[0]

    payload = {
        "schema_version": 1,
        "evidential_role": "controlled metric-validity fixture; not an ASE result",
        "distance_backend": "aria_nbv.rri_metrics.point_mesh.chamfer_point_mesh (PyTorch3D)",
        "witness_backend": "trimesh.triangles.closest_point",
        "units": "metres and square metres",
        "point_set_3d": points.tolist(),
        "primitive": {
            "triangle": _project(primitive_triangle).tolist(),
            "point": _project(primitive_point[None, :])[0].tolist(),
            "closest": _project(primitive_closest[None, :])[0].tolist(),
            "squared_distance_m2": float(
                np.sum((primitive_point - primitive_closest) ** 2)
            ),
        },
        "coarse": _metric_payload(
            "coarse equal-area tessellation",
            coarse_vertices,
            coarse_faces,
            points,
        ),
        "refined": _metric_payload(
            "non-uniform left-half refinement",
            refined_vertices,
            refined_faces,
            points,
        ),
        "invariant_support": "[0,2] x [0,1] planar rectangle at z=0",
        "interpretation": (
            "The point set and planar support are identical. Only the triangle table changes; "
            "therefore the change in the equal-face completeness term isolates tessellation "
            "sensitivity of the implemented reduction."
        ),
    }

    output = args.output.expanduser().resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    print(output)


if __name__ == "__main__":
    main()
