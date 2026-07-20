"""Export target-centred camera directions and Mollweide projection geometry."""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path

import numpy as np
import torch
from efm3d.aria.aria_constants import ARIA_SNIPPET_T_WORLD_SNIPPET
from efm3d.aria.obb import ObbTW
from efm3d.aria.pose import PoseTW

from aria_nbv.configs import PathConfig
from aria_nbv.data_handling import AseEfmDatasetConfig
from aria_nbv.utils.frames import world_from_camera


def parse_args() -> argparse.Namespace:
    """Parse the pinned sample, target, and output controls."""
    repo_root = Path(__file__).resolve().parents[5]
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo-root", type=Path, default=repo_root)
    parser.add_argument("--data-root", type=Path, default=repo_root / ".data")
    parser.add_argument("--external-dir", type=Path, default=repo_root / "external")
    parser.add_argument("--scene-id", default="81286")
    parser.add_argument("--shard-id", default="shards-0003")
    parser.add_argument("--sample-suffix", default="000024")
    parser.add_argument("--target-instance-id", type=int, default=128)
    parser.add_argument("--history-frames", default="0,2,4,6,8,10")
    parser.add_argument("--query-frame", type=int, default=15)
    parser.add_argument(
        "--output",
        type=Path,
        default=repo_root
        / "docs/typst/thesis/figures/data/directional_memory_81286_000024_inst128.json",
    )
    return parser.parse_args()


def _latest_world_obbs(sample: object) -> ObbTW:
    """Return the latest non-padding GT OBB slice in world coordinates."""
    view = sample.obbs
    if view is None:
        raise ValueError("Pinned sample has no GT OBB rows.")
    data = view.obbs.tensor().detach().cpu().to(dtype=torch.float32)
    rows = data.reshape(-1, data.shape[-2], data.shape[-1])
    selected: ObbTW | None = None
    for index in range(rows.shape[0] - 1, -1, -1):
        candidate = ObbTW(rows[index])
        valid = ~candidate.get_padding_mask()
        if bool(valid.any().item()):
            selected = ObbTW(rows[index][valid])
            break
    if selected is None:
        raise ValueError("Pinned sample has no non-padding GT OBB row.")
    transform = sample.efm.get(ARIA_SNIPPET_T_WORLD_SNIPPET)
    if transform is None:
        return selected
    if isinstance(transform, PoseTW):
        transform = PoseTW(transform.tensor().reshape(-1, 12)[:1])
    else:
        transform = PoseTW(torch.as_tensor(transform).reshape(-1, 12)[:1])
    return selected.transform(transform)


def _target_obb(world_obbs: ObbTW, instance_id: int) -> ObbTW:
    """Select one target OBB by instance id."""
    for index in range(int(world_obbs.shape[0])):
        row = ObbTW(world_obbs.tensor()[index])
        if int(row.inst_id.reshape(-1)[0].item()) == instance_id:
            return row
    raise LookupError(f"instance_id={instance_id} is absent from the pinned sample")


def _mollweide(longitude: float, latitude: float) -> tuple[float, float]:
    """Project radians to a standard equal-area Mollweide map."""
    if abs(abs(latitude) - math.pi / 2) < 1e-12:
        theta = math.copysign(math.pi / 2, latitude)
    else:
        theta = latitude
        for _ in range(12):
            numerator = 2 * theta + math.sin(2 * theta) - math.pi * math.sin(latitude)
            denominator = 2 + 2 * math.cos(2 * theta)
            theta -= numerator / denominator
    x = 2 * math.sqrt(2) / math.pi * longitude * math.cos(theta)
    y = math.sqrt(2) * math.sin(theta)
    return x, y


def _project_direction(direction: np.ndarray) -> tuple[float, float]:
    """Project a target-local unit vector with +X as map centre."""
    longitude = math.atan2(float(direction[1]), float(direction[0]))
    latitude = math.asin(float(np.clip(direction[2], -1.0, 1.0)))
    return _mollweide(longitude, latitude)


def _graticule() -> dict[str, list[list[list[float]]]]:
    """Return latitude and longitude curves for a Mollweide inset."""
    latitude_curves: list[list[list[float]]] = []
    longitude_curves: list[list[list[float]]] = []
    for latitude_deg in (-60, -30, 0, 30, 60):
        latitude = math.radians(latitude_deg)
        latitude_curves.append(
            [
                list(_mollweide(math.radians(longitude_deg), latitude))
                for longitude_deg in range(-180, 181, 4)
            ]
        )
    for longitude_deg in (-120, -60, 0, 60, 120):
        longitude = math.radians(longitude_deg)
        longitude_curves.append(
            [
                list(_mollweide(longitude, math.radians(latitude_deg)))
                for latitude_deg in range(-90, 91, 3)
            ]
        )
    return {"latitudes": latitude_curves, "longitudes": longitude_curves}


def main() -> None:
    """Write actual logged directions plus a hypothetical novelty query."""
    args = parse_args()
    repo_root = args.repo_root.expanduser().resolve()
    data_root = args.data_root.expanduser().resolve()
    paths = PathConfig(
        root=repo_root,
        data_root=data_root,
        ase_meshes=data_root / "ase_meshes",
        processed_meshes=data_root / "ase_meshes_processed",
        external_dir=args.external_dir.expanduser().resolve(),
    )
    sample = next(
        iter(
            AseEfmDatasetConfig(
                paths=paths,
                scene_ids=[args.scene_id],
                snippet_ids=[args.shard_id],
                snippet_key_filter=[args.sample_suffix],
                batch_size=1,
                wds_shuffle=False,
                wds_repeat=False,
                load_meshes=False,
                require_mesh=False,
                device="cpu",
            ).setup_target()
        )
    )
    target = _target_obb(_latest_world_obbs(sample), args.target_instance_id)
    history_frames = [
        int(value) for value in args.history_frames.split(",") if value.strip()
    ]
    all_frames = history_frames + [args.query_frame]
    rgb = sample.camera_rgb
    target_center = target.T_world_object.t.detach().cpu().reshape(3)
    rotation_world_target = target.T_world_object.R.detach().cpu().reshape(3, 3)
    directions: list[np.ndarray] = []
    for frame_index in all_frames:
        pose = world_from_camera(
            sample.trajectory.t_world_rig[frame_index], rgb.calib, frame_index
        )
        direction_world = pose.t.detach().cpu().reshape(3) - target_center
        direction_world = direction_world / torch.linalg.vector_norm(direction_world)
        direction_target = rotation_world_target.transpose(0, 1) @ direction_world
        directions.append(direction_target.numpy().astype(np.float64))

    history = np.stack(directions[:-1], axis=0)
    query = directions[-1]
    moment = np.einsum("ni,nj->ij", history, history)
    trace = float(np.trace(moment))
    novelty = 1.0 - float(query @ moment @ query) / (trace + 1e-8)

    payload = {
        "schema_version": 1,
        "construction_provenance": "directions reconstructed from logged ASE CameraTW poses",
        "evidential_role": "design hypothesis fixture, not an implemented model feature",
        "scene_id": sample.scene_id,
        "snippet_id": sample.snippet_id,
        "target_instance_id": args.target_instance_id,
        "frame": "target_object",
        "sphere_convention": "+X is map centre; +Z is north; longitude wraps at +/-180 degrees",
        "history_frames": history_frames,
        "query_frame": args.query_frame,
        "history_directions": history.tolist(),
        "query_direction": query.tolist(),
        "history_mollweide": [
            list(_project_direction(direction)) for direction in history
        ],
        "query_mollweide": list(_project_direction(query)),
        "mollweide_outline": [
            [2 * math.sqrt(2) * math.cos(angle), math.sqrt(2) * math.sin(angle)]
            for angle in np.linspace(0, 2 * math.pi, 181)
        ],
        "mollweide_graticule": _graticule(),
        "second_moment": moment.tolist(),
        "query_novelty": novelty,
        "note": (
            "History markers are a deterministic subsample of the logged trajectory, not learned "
            "selected actions. The query is another logged pose used only to illustrate the "
            "prospective second-moment novelty definition."
        ),
    }
    output = args.output.expanduser().resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    print(output)


if __name__ == "__main__":
    main()
