"""Metadata management for ASE dataset download manifests."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path


@dataclass
class SceneMetadata:
    """Aggregated metadata for one ASE scene across ATEK configs."""

    scene_id: str
    has_gt_mesh: bool
    mesh_url: str | None
    mesh_sha: str | None
    shard_count: int
    shard_ids: list[str]
    atek_config: str
    total_frames: int


class ASEMetadata:
    """Parse mesh + ATEK URL JSONs to expose scene-level metadata."""

    def __init__(
        self,
        url_dir: Path,
        mesh_json_filename: str = "ase_mesh_download_urls.json",
        atek_json_filename: str = "AriaSyntheticEnvironment_ATEK_download_urls.json",
    ):
        self.url_dir = url_dir
        self.mesh_json = url_dir / mesh_json_filename
        self.atek_json = url_dir / atek_json_filename
        self.mesh_scene_ids: set[str] = set()
        self.scenes: dict[str, SceneMetadata] = {}
        self.scenes_by_config: dict[str, dict[str, SceneMetadata]] = {}
        self._parse()

    def _maybe_store(self, scene_id: str, meta: SceneMetadata) -> None:
        """Store scene metadata, preferring entries with more shards."""

        existing = self.scenes.get(scene_id)
        if existing is None or meta.shard_count >= existing.shard_count:
            self.scenes[scene_id] = meta

    def _parse(self) -> None:
        mesh_data = json.load(self.mesh_json.open()) if self.mesh_json.exists() else []
        atek_data = json.load(self.atek_json.open()) if self.atek_json.exists() else {"atek_data_for_all_configs": {}}

        mesh_lookup: dict[str, tuple[str | None, str | None]] = {}
        for entry in mesh_data:
            scene_id = entry["filename"].replace("scene_ply_", "").replace(".zip", "")
            mesh_lookup[scene_id] = (entry.get("cdn"), entry.get("sha"))
            self.mesh_scene_ids.add(scene_id)

        configs = atek_data.get("atek_data_for_all_configs", {})
        for cfg_name, cfg in configs.items():
            cfg_store: dict[str, SceneMetadata] = {}
            wds_urls = cfg.get("wds_file_urls", {}) or {}
            for scene_id, shards in wds_urls.items():
                shard_ids = [k.replace("_tar", "") for k in shards.keys()]
                mesh_url, mesh_sha = mesh_lookup.get(scene_id, (None, None))
                meta = SceneMetadata(
                    scene_id=scene_id,
                    has_gt_mesh=scene_id in mesh_lookup,
                    mesh_url=mesh_url,
                    mesh_sha=mesh_sha,
                    shard_count=len(shard_ids),
                    shard_ids=shard_ids,
                    atek_config=cfg_name,
                    total_frames=0,
                )
                cfg_store[scene_id] = meta
                self._maybe_store(scene_id, meta)

            for entry in cfg.get("sequences", []) or []:
                scene_id = entry.get("sequence_name") or "unknown"
                tar_urls = entry.get("tar_urls") or []
                shard_ids = tar_urls if isinstance(tar_urls, list) else []
                mesh_url, mesh_sha = mesh_lookup.get(scene_id, (None, None))
                meta = SceneMetadata(
                    scene_id=scene_id,
                    has_gt_mesh=scene_id in mesh_lookup,
                    mesh_url=mesh_url,
                    mesh_sha=mesh_sha,
                    shard_count=len(shard_ids),
                    shard_ids=shard_ids,
                    atek_config=cfg_name,
                    total_frames=entry.get("num_frames", 0),
                )
                cfg_store[scene_id] = meta
                self._maybe_store(scene_id, meta)

            self.scenes_by_config[cfg_name] = cfg_store

    def get_scenes_with_meshes(self, config: str | None = None) -> list[SceneMetadata]:
        """Return scenes that have GT meshes.

        Args:
            config: Optional ATEK config name. If provided, scenes are returned for that
                specific ATEK config.

        Returns:
            List of scenes that have GT meshes.
        """
        if config is None:
            return [s for s in self.scenes.values() if s.has_gt_mesh]
        return [s for s in self.scenes_by_config.get(config, {}).values() if s.has_gt_mesh]

    def filter_scenes(
        self, min_shards: int = 0, require_mesh: bool = False, config: str | None = None
    ) -> list[SceneMetadata]:
        scenes = list(self.scenes_by_config.get(config, {}).values()) if config else list(self.scenes.values())
        if require_mesh:
            scenes = [s for s in scenes if s.has_gt_mesh]
        scenes = [s for s in scenes if s.shard_count >= min_shards]
        return scenes

    def get_scenes(self, n: int | None = None, max_shards: int | None = None) -> list[SceneMetadata]:
        scenes = sorted(self.scenes.values(), key=lambda s: s.scene_id)
        if max_shards is not None:
            scenes = [
                SceneMetadata(
                    scene_id=s.scene_id,
                    has_gt_mesh=s.has_gt_mesh,
                    mesh_url=s.mesh_url,
                    mesh_sha=s.mesh_sha,
                    shard_count=min(s.shard_count, max_shards),
                    shard_ids=s.shard_ids[:max_shards],
                    atek_config=s.atek_config,
                    total_frames=s.total_frames,
                )
                for s in scenes
            ]
        return scenes[:n] if n else scenes

    def save(self, path: Path) -> None:
        data = {
            "mesh_scene_ids": list(self.mesh_scene_ids),
            "scenes": [scene.__dict__ for scene in self.scenes.values()],
        }
        path.write_text(json.dumps(data))

    @staticmethod
    def load(path: Path) -> "ASEMetadata":
        data = json.loads(path.read_text())
        url_dir = path.parent
        meta = ASEMetadata(url_dir)
        meta.mesh_scene_ids = set(data.get("mesh_scene_ids", []))
        meta.scenes = {s["scene_id"]: SceneMetadata(**s) for s in data.get("scenes", [])}
        return meta


__all__ = ["SceneMetadata", "ASEMetadata"]
