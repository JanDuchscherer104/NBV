"""Deterministic one-root-per-scene selection for local ASE campaigns."""

from __future__ import annotations

import json
import os
import tarfile
from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path
from typing import Any

from ...utils.fingerprints import stable_msgspec_hash

ROOT_INVENTORY_VERSION = "ase-root-inventory-v1"
"""Version of the deterministic scene/snippet inventory payload."""


@dataclass(frozen=True, slots=True)
class RankedSnippet:
    """One ASE snippet candidate in deterministic scene-local order."""

    sample_key: str
    """ATEK WebDataset sample key."""

    shard_path: Path
    """Local tar shard containing ``sample_key``."""

    rank_digest: str
    """Stable campaign-seed ranking digest."""

    def to_jsonable(self, *, repo_root: Path) -> dict[str, str]:
        """Return a portable evidence payload relative to ``repo_root``."""

        try:
            shard_path = self.shard_path.relative_to(repo_root).as_posix()
        except ValueError:
            shard_path = self.shard_path.as_posix()
        return {
            "sample_key": self.sample_key,
            "shard_path": shard_path,
            "rank_digest": self.rank_digest,
        }


@dataclass(frozen=True, slots=True)
class SceneRootCandidates:
    """Ranked rollout-root candidates for one mesh-supervised ASE scene."""

    scene_id: str
    """ASE scene identifier."""

    mesh_path: Path
    """Local GT mesh paired with the scene."""

    candidates: tuple[RankedSnippet, ...]
    """All discovered snippet keys in deterministic reserve order."""

    @property
    def selected(self) -> RankedSnippet:
        """Return the first deterministic root candidate."""

        if not self.candidates:
            raise ValueError(f"Scene {self.scene_id!r} has no snippet candidates.")
        return self.candidates[0]


@dataclass(frozen=True, slots=True)
class RootInventory:
    """Complete deterministic root inventory for a local ASE campaign."""

    seed: int
    """Campaign seed used for scene-local snippet ranking."""

    scenes: tuple[SceneRootCandidates, ...]
    """Expected scenes in canonical numeric order."""

    @property
    def selected_sample_keys(self) -> tuple[str, ...]:
        """Return the initial one-root-per-scene sample-key selection."""

        return tuple(scene.selected.sample_key for scene in self.scenes)

    def to_jsonable(self, *, repo_root: Path) -> dict[str, Any]:
        """Return the complete human-inspectable inventory evidence payload."""

        rows = []
        for scene in self.scenes:
            try:
                mesh_path = scene.mesh_path.relative_to(repo_root).as_posix()
            except ValueError:
                mesh_path = scene.mesh_path.as_posix()
            rows.append(
                {
                    "scene_id": scene.scene_id,
                    "mesh_path": mesh_path,
                    "selected_sample_key": scene.selected.sample_key,
                    "candidates": [candidate.to_jsonable(repo_root=repo_root) for candidate in scene.candidates],
                }
            )
        payload: dict[str, Any] = {
            "version": ROOT_INVENTORY_VERSION,
            "seed": self.seed,
            "num_scenes": len(self.scenes),
            "num_candidates": sum(len(scene.candidates) for scene in self.scenes),
            "scenes": rows,
        }
        payload["inventory_hash"] = stable_msgspec_hash(payload)
        return payload


def discover_ase_root_inventory(
    *,
    ase_efm_dir: Path | str,
    ase_meshes_dir: Path | str,
    seed: int,
    expected_scene_count: int = 100,
    candidates_per_shard: int = 1,
) -> RootInventory:
    """Discover and deterministically rank one snippet population per scene.

    Selection depends only on campaign seed and stable source identity. It does
    not inspect RRI, gain, candidate validity, or rollout outcomes.

    Args:
        ase_efm_dir: Directory containing one shard directory per ASE scene.
        ase_meshes_dir: Directory containing ``scene_ply_<scene>.ply`` meshes.
        seed: Campaign-level deterministic selection seed.
        expected_scene_count: Exact scene count required before generation.
        candidates_per_shard: Number of distinct sample keys retained from each
            tar shard. The default samples every shard while avoiding a full
            scan of millions of payload members.

    Returns:
        Complete scene inventory with every snippet retained as a reserve.

    Raises:
        ValueError: If scene, mesh, or snippet coverage is incomplete.
    """

    efm_root = Path(ase_efm_dir).expanduser().resolve()
    mesh_root = Path(ase_meshes_dir).expanduser().resolve()
    if candidates_per_shard < 1:
        raise ValueError("candidates_per_shard must be >= 1.")
    scene_dirs = sorted(
        (path for path in efm_root.iterdir() if path.is_dir() and path.name.isdigit()),
        key=lambda path: int(path.name),
    )
    if len(scene_dirs) != expected_scene_count:
        raise ValueError(
            f"Expected exactly {expected_scene_count} ASE scene directories under {efm_root}; found {len(scene_dirs)}."
        )

    scenes: list[SceneRootCandidates] = []
    missing_meshes: list[str] = []
    empty_scenes: list[str] = []
    for scene_dir in scene_dirs:
        scene_id = scene_dir.name
        mesh_path = mesh_root / f"scene_ply_{scene_id}.ply"
        if not mesh_path.is_file():
            missing_meshes.append(scene_id)
            continue
        candidates_by_key: dict[str, Path] = {}
        for shard_path in sorted(scene_dir.glob("*.tar")):
            shard_keys: set[str] = set()
            with tarfile.open(shard_path, "r") as archive:
                for member in archive:
                    sample_key = member.name.split(".", 1)[0]
                    if not sample_key.startswith(f"AriaSyntheticEnvironment_{scene_id}_AtekDataSample_"):
                        continue
                    candidates_by_key.setdefault(sample_key, shard_path.resolve())
                    shard_keys.add(sample_key)
                    if len(shard_keys) >= candidates_per_shard:
                        break
        if not candidates_by_key:
            empty_scenes.append(scene_id)
            continue
        ranked = tuple(
            RankedSnippet(
                sample_key=sample_key,
                shard_path=shard_path,
                rank_digest=_rank_digest(seed=seed, scene_id=scene_id, sample_key=sample_key),
            )
            for sample_key, shard_path in sorted(
                candidates_by_key.items(),
                key=lambda item: (_rank_digest(seed=seed, scene_id=scene_id, sample_key=item[0]), item[0]),
            )
        )
        scenes.append(SceneRootCandidates(scene_id=scene_id, mesh_path=mesh_path, candidates=ranked))

    if missing_meshes or empty_scenes:
        raise ValueError(
            "ASE root inventory is incomplete: "
            f"missing_mesh_scenes={missing_meshes}, empty_snippet_scenes={empty_scenes}."
        )
    inventory = RootInventory(seed=int(seed), scenes=tuple(scenes))
    if len(set(inventory.selected_sample_keys)) != len(inventory.scenes):
        raise ValueError("Deterministic root inventory produced duplicate selected sample keys.")
    return inventory


def write_root_inventory(path: Path | str, inventory: RootInventory, *, repo_root: Path | str) -> Path:
    """Atomically write a deterministic root-inventory JSON artifact."""

    output = Path(path).expanduser().resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    payload = inventory.to_jsonable(repo_root=Path(repo_root).expanduser().resolve())
    temp = output.with_name(f".{output.name}.tmp")
    temp.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    os.replace(temp, output)
    return output


def _rank_digest(*, seed: int, scene_id: str, sample_key: str) -> str:
    """Return the stable scene-local ranking digest for one snippet."""

    return sha256(f"{int(seed)}:{scene_id}:{sample_key}".encode()).hexdigest()


__all__ = [
    "ROOT_INVENTORY_VERSION",
    "RankedSnippet",
    "RootInventory",
    "SceneRootCandidates",
    "discover_ase_root_inventory",
    "write_root_inventory",
]
