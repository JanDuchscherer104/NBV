"""EFM-formatted ASE dataset wrapper.

`AseEfmDataset` streams ATEK/ASE shards through the EFM adaptor and yields
typed `EfmSnippetView` objects. It is the live data source used by candidate
generation, VIN offline-cache construction, and rollout-data smoke builds.

ATEK shards are the tensorized provenance for calibrated VRS streams,
trajectories, online calibration, and MPS semidense points; this module does
not open raw VRS recordings. Semidense points and calibrated poses are
actor-visible observations, while attached ASE meshes and GT annotations are
oracle label/evaluation assets.

Scene/snippet identity, mesh attachment, taxonomy mapping, and semidense bounds
are part of the contract. Any downstream store that depends on oracle labels
must keep scene-level splits and manifest hashes instead of relying on sample
order alone.
"""

from __future__ import annotations

import tarfile
import warnings
from collections.abc import Iterable, Iterator, Mapping
from pathlib import Path
from typing import Any, ClassVar, Literal

import torch
import trimesh
from atek.data_loaders.atek_wds_dataloader import load_atek_wds_dataset
from efm3d.aria.aria_constants import ARIA_POINTS_VOL_MAX, ARIA_POINTS_VOL_MIN, ARIA_POINTS_WORLD
from efm3d.dataset.efm_model_adaptor import EfmModelAdaptor, pipelinefilter
from pydantic import Field, ValidationInfo, field_validator, model_validator
from torch.utils.data import IterableDataset

from ...configs import PathConfig
from ...utils import BaseConfig, Console, TargetConfig, Verbosity
from ..identifiers import ase_atek_identifier_variants, compact_ase_atek_sample_id
from ..mesh_cache import MeshProcessSpec, load_or_process_mesh
from .views import EfmSnippetView


def _infer_ids(
    efm_dict: Mapping[str, Any],
    sequence_name: str | None = None,
) -> tuple[str, str]:
    """Infer scene and snippet ids from keys/url."""
    scene_id = str(sequence_name or efm_dict.get("sequence_name", "unknown"))
    snippet_id = efm_dict.get("__key__") or efm_dict.get("__url__")
    if isinstance(snippet_id, str):
        snippet_id = compact_ase_atek_sample_id(Path(snippet_id).stem)
    else:
        snippet_id = "unknown"
    if scene_id == "unknown" and "__url__" in efm_dict:
        parent = Path(str(efm_dict["__url__"])).parent.name
        if parent.isdigit():
            scene_id = parent
    return scene_id, str(snippet_id)


def _unique_preserve_order(values: Iterable[str]) -> list[str]:
    """Return unique values while preserving their first-seen order."""
    return list(dict.fromkeys(values))


def _looks_like_shard_id(snippet_id: str) -> bool:
    """Return whether a snippet identifier refers to a shard tar."""
    stem = Path(snippet_id).name
    return stem.startswith("shards-") or stem.endswith("_tar") or stem.endswith(".tar")


def _normalize_shard_stem(snippet_id: str) -> str:
    """Normalize shard identifiers into a tar-file stem."""
    stem = Path(snippet_id).stem
    if stem.endswith("_tar"):
        stem = stem[: -len("_tar")]
    return stem


def _matches_snippet_token(prefix: str, token: str) -> bool:
    """Return whether a shard member prefix matches the requested token."""
    prefixes = ase_atek_identifier_variants(prefix)
    tokens = ase_atek_identifier_variants(token)
    return any(
        candidate == requested or candidate.endswith(requested) for candidate in prefixes for requested in tokens
    )


def _tar_contains_snippet(tar_path: Path, snippet_token: str) -> bool:
    """Return whether a shard tar contains the requested snippet token."""
    with tarfile.open(tar_path, "r") as tar:
        for member in tar:
            prefix = member.name.split(".", 1)[0]
            if _matches_snippet_token(prefix, snippet_token):
                return True
    return False


def _resolve_tar_from_path(
    *,
    snippet_id: str,
    paths: PathConfig,
) -> Path | None:
    """Resolve an explicit shard path or relative shard reference."""
    candidate = Path(snippet_id)
    if candidate.is_absolute():
        if candidate.suffix != ".tar":
            candidate = candidate.with_suffix(".tar")
        return candidate if candidate.exists() else None
    if candidate.parent != Path():
        resolved = paths.resolve_under_root(candidate)
        if resolved.suffix != ".tar":
            resolved = resolved.with_suffix(".tar")
        return resolved if resolved.exists() else None
    return None


def _resolve_tar_for_shard(
    *,
    shard_id: str,
    scene_dirs: list[Path],
) -> list[Path]:
    """Resolve a shard identifier against the configured scene directories."""
    stem = _normalize_shard_stem(shard_id)
    matches: list[Path] = []
    for scene_dir in scene_dirs:
        candidate = scene_dir / f"{stem}.tar"
        if candidate.exists():
            matches.append(candidate)
    return matches


def _find_tar_for_sample(
    *,
    sample_key: str,
    scene_dirs: list[Path],
) -> Path | None:
    """Find the shard tar that contains the requested sample key."""
    for scene_dir in scene_dirs:
        for tar_path in sorted(scene_dir.glob("*.tar")):
            if _tar_contains_snippet(tar_path, sample_key):
                return tar_path
    return None


def _split_snippet_ids(snippet_ids: Iterable[str]) -> tuple[list[str], list[str]]:
    """Split mixed snippet identifiers into shard ids and sample keys."""
    shard_ids: list[str] = []
    sample_keys: list[str] = []
    for snippet_id in snippet_ids:
        if _looks_like_shard_id(snippet_id):
            shard_ids.append(snippet_id)
        else:
            sample_keys.append(snippet_id)
    return shard_ids, sample_keys


def _tensor3(value: Any) -> torch.Tensor | None:
    """Return ``value`` when it is a tensor with exactly three elements."""
    if isinstance(value, torch.Tensor) and value.numel() == 3:
        return value
    return None


def infer_semidense_bounds(
    efm_dict: Mapping[str, Any],
) -> tuple[torch.Tensor, torch.Tensor] | None:
    """Infer snippet world-space AABB from semidense metadata or points.

    Metadata bounds and finite-point bounds are compared when both exist; the
    smaller finite volume is retained to avoid an unnecessarily loose crop.
    Padded and non-finite semidense rows never contribute.

    Args:
        efm_dict: Adapted EFM payload containing world-frame semidense points
            and/or explicit volume bounds.

    Returns:
        Pair of ``Tensor["3", float32]`` world-frame AABB minima and maxima in
        metres on CPU, or ``None`` when no finite bounds are available.
    """
    vol_min = _tensor3(efm_dict.get(ARIA_POINTS_VOL_MIN))
    if vol_min is None:
        vol_min = _tensor3(efm_dict.get("points/vol_min"))

    vol_max = _tensor3(efm_dict.get(ARIA_POINTS_VOL_MAX))
    if vol_max is None:
        vol_max = _tensor3(efm_dict.get("points/vol_max"))
    vol_bounds: tuple[torch.Tensor, torch.Tensor] | None = None
    if vol_min is not None and vol_max is not None and torch.isfinite(vol_min).all() and torch.isfinite(vol_max).all():
        vol_bounds = (vol_min.detach().cpu(), vol_max.detach().cpu())

    points = efm_dict.get(ARIA_POINTS_WORLD)
    point_bounds: tuple[torch.Tensor, torch.Tensor] | None = None
    if isinstance(points, torch.Tensor) and points.shape[-1] == 3:
        lengths = efm_dict.get("msdpd#points_world_lengths") or efm_dict.get(
            "points/lengths",
        )
        if isinstance(lengths, torch.Tensor):
            lengths = lengths.to(dtype=torch.long)

        mask_valid = torch.isfinite(points).all(dim=-1)
        if isinstance(lengths, torch.Tensor) and lengths.shape[0] == points.shape[0]:
            idx = torch.arange(points.shape[1], device=points.device).unsqueeze(
                0,
            ) < lengths.unsqueeze(-1)
            mask_valid &= idx

        if mask_valid.any():
            valid_points = points[mask_valid]
            min_vec = valid_points.min(dim=0).values.detach().cpu()
            max_vec = valid_points.max(dim=0).values.detach().cpu()
            if torch.isfinite(min_vec).all() and torch.isfinite(max_vec).all():
                point_bounds = (min_vec, max_vec)

    if vol_bounds is None and point_bounds is None:
        base_bounds = None
    elif vol_bounds is None:
        base_bounds = point_bounds
    elif point_bounds is None:
        base_bounds = vol_bounds
    else:
        vol_extent = (vol_bounds[1] - vol_bounds[0]).clamp_min(1e-6)
        point_extent = (point_bounds[1] - point_bounds[0]).clamp_min(1e-6)
        vol_volume = torch.prod(vol_extent)
        point_volume = torch.prod(point_extent)
        base_bounds = point_bounds if point_volume < vol_volume else vol_bounds

    return base_bounds


class AseEfmDatasetConfig(TargetConfig["AseEfmDataset"]):
    """Configure the canonical ATEK-shard to EFM-snippet streaming path.

    The config resolves scene/shard/sample filters, the ATEK-to-EFM taxonomy,
    and optional ASE mesh pairing before constructing :class:`AseEfmDataset`.
    ``EfmModelAdaptor`` owns flattened-key remapping; this config does not
    introduce a parallel schema.
    """

    cache_exclude_fields: ClassVar[set[str]] = {"tar_urls", "scene_to_mesh"}
    """Fields omitted from cache snapshots because they are large or derived."""

    @property
    def target_type(self) -> type["AseEfmDataset"]:
        """Factory target for `BaseConfig.setup_target`."""
        return AseEfmDataset

    paths: PathConfig = Field(default_factory=PathConfig)
    """Project path resolver (data roots, mesh locations, etc.)."""
    atek_variant: Literal["efm", "efm_eval", "cubercnn", "cubercnn_eval"] = Field(
        default="efm",
    )
    """ATEK payload variant and on-disk shard subdirectory under the data root."""
    scene_ids: list[str] = Field(default_factory=list)
    """Optional list of ASE scene IDs to include.

    Empty means all scenes under ``tar_urls``.
    """
    snippet_ids: list[str] = Field(default_factory=list)
    """Optional snippet IDs to include for each scene.

    Each entry can be:
    - shard IDs (e.g., ``"shards-0003"`` or ``"shards-0003_tar"``),
    - shard filenames (e.g., ``"shards-0003.tar"``),
    - relative/absolute paths to shard tar files, or
    - sample keys (e.g., ``"AriaSyntheticEnvironment_81286_AtekDataSample_000000"``).
    """
    snippet_key_filter: list[str] = Field(default_factory=list)
    """Optional sample key filter applied after loading shards."""
    tar_urls: list[str] = Field(default_factory=list)
    """ATEK WebDataset shard paths or globs carrying tensorized ASE snippets.

    Auto-populated from ``scene_ids`` when empty.
    """
    scene_to_mesh: dict[str, Path] = Field(default_factory=dict)
    """Optional mapping of ``scene_id`` to ASE GT-mesh evaluation asset.

    Auto-filled when ``load_meshes=True`` and mesh paths exist.
    """

    taxonomy_csv_filename: str = Field(default="atek_to_efm.csv")
    """Filename for the ATEK→EFM taxonomy mapping CSV."""
    batch_size: int | None = Field(default=2)
    """WebDataset batch size inside ATEK loader.

    If set, the ATEK loader yields lists of snippet dicts which this wrapper
    immediately flattens back to individual snippets. Set to ``None`` to let
    the PyTorch DataLoader handle batching instead.
    """
    wds_shuffle: bool = Field(default=False)
    """Enable shuffled sampling in the underlying WebDataset pipeline.

    This is forwarded to `efm3d.dataset.efm_model_adaptor.load_atek_wds_dataset_as_efm(..., shuffle_flag=...)`.
    """

    wds_repeat: bool = Field(default=False)
    """Repeat the underlying WebDataset stream (infinite iterator).

    This is forwarded to `efm3d.dataset.efm_model_adaptor.load_atek_wds_dataset_as_efm(..., repeat_flag=...)`.
    """
    snippet_length_s: float = Field(default=2.0, gt=0)
    """Snippet duration in seconds used by the EFM adaptor."""
    freq_hz: int = Field(default=10, gt=0)
    """Sampling frequency (Hz) used by the EFM adaptor."""
    semidense_points_pad: int = Field(default=50000, gt=0)
    """Pad/clip semi-dense points to this count per snippet frame."""

    load_meshes: bool = Field(default=True)
    """Attach GT meshes to snippets when available."""
    require_mesh: bool = Field(default=False)
    """Raise if a GT mesh is missing for any requested scene."""
    mesh_simplify_ratio: float | None = Field(default=0.1, ge=0.0, le=1.0)
    """Fraction of faces to keep when simplifying meshes. ``None`` disables."""
    crop_mesh: bool = False
    """If ``True``, crop meshes to snippet bounds before simplification."""
    mesh_crop_margin_m: float | None = Field(default=0.5, ge=0.0)
    """Margin added to semidense bounds when cropping meshes. ``None`` disables cropping."""
    cache_meshes: bool = Field(default=True)
    """Cache loaded meshes in memory per dataset instance."""
    mesh_crop_min_keep_ratio: float = Field(
        default=0.1,
        ge=0.0,
        le=1.0,
        description="Abort cropping if fewer than this fraction of faces would remain (protects walls).",
    )
    """Minimum face keep ratio tolerated during mesh cropping."""
    device: str = Field(
        default="cpu",
        description="Target device for snippet tensors (e.g., 'cpu', 'cuda', 'cuda:0').",
    )
    """Device to move snippet tensors onto."""

    verbosity: Verbosity = Field(
        default=Verbosity.VERBOSE,
        description="Verbosity level for logging (0=quiet, 1=normal, 2=verbose).",
    )
    """Verbosity level for dataset logging."""
    is_debug: bool = Field(default=False)
    """Enable debug logging and extra diagnostics."""

    @field_validator("device", mode="before")
    @classmethod
    def _coerce_device(cls, value: Any) -> str:
        """Normalize the configured device into a canonical string."""
        dev = torch.device(value) if not isinstance(value, torch.device) else value
        return str(dev)

    @field_validator("taxonomy_csv_filename", mode="before")
    @classmethod
    def _strip_taxonomy(cls, value: str | Path) -> str:
        """Keep only the taxonomy CSV filename component."""
        return Path(value).name

    @field_validator("tar_urls", mode="before")
    @classmethod
    def _populate_tar_urls(cls, _: list[str] | None, info: ValidationInfo) -> list[str]:
        """Populate shard URLs from the requested scenes when omitted."""
        data = info.data
        paths: PathConfig = data.get("paths") or PathConfig()
        scene_ids: list[str] = data.get("scene_ids")  # type: ignore[assignment]
        atek_variant: str = data.get("atek_variant")  # type: ignore[assignment]

        base = paths.resolve_atek_data_dir(atek_variant)

        resolved: list[Path] = []
        if scene_ids:
            for scene in scene_ids:
                resolved.extend(sorted((base / scene).glob("*.tar")))
        else:
            resolved = sorted(base.glob("**/*.tar"))

        # Be defensive: ignore empty placeholder shards (e.g. `dummy.tar`) and non-files.
        resolved_tar_urls = [str(p) for p in resolved if p.is_file() and p.stat().st_size > 0]

        if not resolved_tar_urls:
            raise ValueError(f"No tar files found under {base}.")

        return resolved_tar_urls

    _coerce_verbosity = field_validator("verbosity", mode="before")(BaseConfig._coerce_verbosity)

    @property
    def taxonomy_csv(self) -> Path:
        """Resolve the ATEK-to-EFM semantic taxonomy used by ``EfmModelAdaptor``."""
        taxonomy_pth = self.paths.external_dir / "efm3d" / "efm3d" / "config" / "taxonomy" / self.taxonomy_csv_filename
        if not taxonomy_pth.exists():
            raise FileNotFoundError(f"Taxonomy CSV not found at {taxonomy_pth}")
        return taxonomy_pth

    @model_validator(mode="after")
    def _autofill_paths(self) -> AseEfmDatasetConfig:
        """Resolve shard URLs, scene ids, mesh paths, and snippet filters."""
        paths = self.paths
        tar_urls = list(self.tar_urls)
        snippet_ids = _unique_preserve_order(self.snippet_ids)
        snippet_key_filter = _unique_preserve_order(self.snippet_key_filter)

        scene_ids = list(self.scene_ids)

        if snippet_ids:
            shard_ids, sample_keys = _split_snippet_ids(snippet_ids)
            snippet_key_filter = _unique_preserve_order(
                list(snippet_key_filter) + list(sample_keys),
            )

            scene_dirs: list[Path] = []
            if scene_ids:
                base = paths.resolve_atek_data_dir(self.atek_variant)
                scene_dirs = [base / scene for scene in scene_ids]

            resolved_tars: list[Path] = []
            for shard_id in shard_ids:
                resolved = _resolve_tar_from_path(
                    snippet_id=shard_id,
                    paths=paths,
                )
                if resolved is not None:
                    resolved_tars.append(resolved)
                    continue
                if not scene_dirs:
                    raise ValueError(
                        "snippet_ids require scene_ids when using shard IDs without explicit paths.",
                    )
                matches = _resolve_tar_for_shard(
                    shard_id=shard_id,
                    scene_dirs=scene_dirs,
                )
                if not matches:
                    raise FileNotFoundError(
                        f"No shard tar found for snippet_id={shard_id} in scenes={scene_ids}.",
                    )
                resolved_tars.extend(matches)

            for sample_key in sample_keys:
                if not scene_dirs:
                    raise ValueError(
                        "snippet_ids require scene_ids when using sample keys.",
                    )
                match = _find_tar_for_sample(
                    sample_key=sample_key,
                    scene_dirs=scene_dirs,
                )
                if match is None:
                    raise FileNotFoundError(
                        f"No shard tar found containing sample key {sample_key} in scenes={scene_ids}.",
                    )
                resolved_tars.append(match)

            tar_urls = [str(p) for p in _unique_preserve_order(p.as_posix() for p in resolved_tars)]

        if not tar_urls:
            base = paths.resolve_atek_data_dir(self.atek_variant)
            tar_urls = [str(p) for scene in scene_ids for p in sorted((base / scene).glob("*.tar"))]
            if not tar_urls:
                raise ValueError(
                    f"No tar files found under {base} for scenes: {self.scene_ids}",
                )

        if self.wds_shuffle and len(tar_urls) > 1:
            # Shuffle shard order so short runs (e.g., binner fitting on a handful of snippets)
            # see multiple scenes early. The underlying ATEK loader only shuffles *samples*
            # within a fixed buffer and otherwise reads shards sequentially.
            perm = torch.randperm(len(tar_urls)).tolist()
            tar_urls = [tar_urls[i] for i in perm]

        if not scene_ids:
            inferred: set[str] = set()
            for url in tar_urls:
                parent = Path(url).parent.name
                if parent.isdigit():
                    inferred.add(parent)

            if not inferred:
                raise ValueError(
                    "scene_ids not provided and could not be inferred from tar_urls.",
                )

            scene_ids = sorted(inferred)

        scene_to_mesh = dict(self.scene_to_mesh)
        if self.load_meshes and not scene_to_mesh:
            if scene_ids:
                scene_to_mesh = {scene: paths.resolve_mesh_path(scene) for scene in scene_ids}
            else:
                mesh_dir = paths.ase_meshes
                scene_to_mesh = {p.stem.replace("scene_ply_", ""): p for p in mesh_dir.glob("scene_ply_*.ply")}

        if self.load_meshes and not scene_to_mesh and self.require_mesh:
            raise ValueError("load_meshes=True but no meshes resolved.")

        if self.taxonomy_csv and not self.taxonomy_csv.exists():
            raise FileNotFoundError(f"Taxonomy CSV not found at {self.taxonomy_csv}")

        object.__setattr__(self, "tar_urls", tar_urls)
        object.__setattr__(self, "scene_ids", scene_ids)
        object.__setattr__(self, "scene_to_mesh", scene_to_mesh)
        object.__setattr__(self, "snippet_ids", snippet_ids)
        object.__setattr__(self, "snippet_key_filter", snippet_key_filter)

        return self

    def setup_target(self) -> AseEfmDataset:
        """Instantiate the configured raw EFM dataset."""
        console = Console.with_prefix(
            self.__class__.__name__,
            "setup_target",
        ).set_verbosity(self.verbosity)
        expanded_urls = [
            str(path)
            for url in self.tar_urls or []
            for path in (sorted(Path().glob(url)) if any(ch in url for ch in "*?[]") else [Path(url)])
        ]
        if not expanded_urls:
            raise FileNotFoundError("No tar files matched derived tar_urls")
        self.tar_urls = expanded_urls
        taxonomy = self.taxonomy_csv.name
        console.log(
            f"Preparing AseEfmDataset (tar URLs: {len(self.tar_urls)}, scenes: {len(self.scene_ids)}) | "
            f"taxonomy={taxonomy}",
        )
        return self.target(self)


class AseEfmDataset(IterableDataset[EfmSnippetView]):
    """Stream zero-copy EFM views from ATEK shards with optional ASE meshes.

    Each iteration adapts one WebDataset sample into the consumed EFM key
    families, infers stable scene/snippet lineage, and attaches processed mesh
    tensors when configured. The iterable owns per-instance mesh memoization;
    yielded :class:`EfmSnippetView` objects retain the backing EFM dictionary.
    Meshes never become actor-visible observations.
    """

    def __init__(self, config: AseEfmDatasetConfig):
        """Initialize the dataset wrapper and its WebDataset source."""
        warnings.filterwarnings(
            "ignore",
            message=r"You are using `torch\.load` with `weights_only=False`.*",
            category=FutureWarning,
        )

        super().__init__()
        self.config = config
        self.console = Console.with_prefix(self.__class__.__name__).set_verbosity(
            config.verbosity,
        )

        self.console.log(
            f"Loading EFM-formatted ATEK WDS from {len(config.tar_urls)} shards",
        )

        self._efm_wds = self._load_atek_wds_dataset_as_efm()
        self._mesh_cache: dict[str, trimesh.Trimesh] = {}
        self._snippet_key_filter = {key for key in self.config.snippet_key_filter if key}
        self.console.log("EFM loader ready")

    def _load_atek_wds_dataset_as_efm(self):
        """Build the underlying ATEK-to-EFM WebDataset pipeline."""
        return load_atek_wds_dataset(
            urls=self.config.tar_urls,
            dict_key_mapping=EfmModelAdaptor.get_dict_key_mapping_all(),
            data_transform_fn=pipelinefilter(
                EfmModelAdaptor(
                    freq=self.config.freq_hz,
                    snippet_length_s=self.config.snippet_length_s,
                    semidense_points_pad_to_num=self.config.semidense_points_pad,
                    atek_to_efm_taxonomy_mapping_file=self.config.taxonomy_csv.as_posix()
                    if self.config.taxonomy_csv
                    else None,
                ).atek_to_efm,
            )(
                train=False,
            ),
            batch_size=self.config.batch_size,
            collation_fn=None,
            repeat_flag=self.config.wds_repeat,
            shuffle_flag=self.config.wds_shuffle,
        )

    def _load_mesh(self, scene_id: str) -> trimesh.Trimesh | None:
        """Load and optionally memoize the GT mesh for a scene."""
        if scene_id in self._mesh_cache:
            return self._mesh_cache[scene_id]
        mesh_path = self.config.scene_to_mesh.get(scene_id)
        if mesh_path is None or not mesh_path.exists():
            if self.config.require_mesh:
                raise FileNotFoundError(
                    f"GT mesh for scene {scene_id} not found (require_mesh=True).",
                )
            return None
        mesh = trimesh.load(str(mesh_path), process=False)
        if not isinstance(mesh, trimesh.Trimesh):
            raise TypeError(f"Mesh for scene {scene_id} is not Trimesh")
        if self.config.cache_meshes:
            self._mesh_cache[scene_id] = mesh
        return mesh

    def _iter_efm_samples(self) -> Iterator[dict[str, Any]]:
        """Yield per-snippet EFM dicts from the WebDataset loader.

        ``load_atek_wds_dataset_as_efm`` already returns a list of snippet dicts
        when ``batch_size`` is set, so we simply iterate that list and avoid any
        further explosion along the frame dimension (which corrupted shapes).
        """
        for raw in self._efm_wds:
            if isinstance(raw, Mapping):
                yield dict(raw)
                continue

            if isinstance(raw, (list, tuple)):
                for sample in raw:
                    if not isinstance(sample, Mapping):
                        raise TypeError(
                            f"Unexpected sample type {type(sample)} from batched list",
                        )
                    yield dict(sample)
                continue

            raise TypeError(f"Unexpected sample type from loader: {type(raw)}")

    def __iter__(self) -> Iterator[EfmSnippetView]:
        """Yield adapted snippets with actor-visible EFM tensors and optional GT meshes.

        Yields:
            :class:`EfmSnippetView` backed by one ATEK sample. Camera,
            trajectory, and semidense tensors preserve EFM frame conventions;
            mesh fields are oracle-only ASE assets.
        """
        for efm_dict in self._iter_efm_samples():
            scene_id, snippet_id = _infer_ids(
                efm_dict,
                efm_dict.get("sequence_name", ""),
            )
            if self._snippet_key_filter and not any(
                _matches_snippet_token(snippet_id, token) for token in self._snippet_key_filter
            ):
                continue
            mesh_base = self._load_mesh(scene_id) if self.config.load_meshes else None
            mesh = mesh_base
            crop_bounds = None
            mesh_verts = None
            mesh_faces = None

            bounds = infer_semidense_bounds(efm_dict)

            mesh_specs = None
            if mesh_base is not None:
                if bounds is None:
                    raise ValueError(
                        f"Unable to infer crop bounds for snippet {snippet_id} (scene {scene_id}) with mesh present.",
                    )

                spec = MeshProcessSpec(
                    scene_id=scene_id,
                    crop=self.config.crop_mesh,
                    bounds_min=bounds[0].tolist(),
                    bounds_max=bounds[1].tolist(),
                    margin_m=float(self.config.mesh_crop_margin_m or 0.0),
                    simplify_ratio=self.config.mesh_simplify_ratio,
                    crop_min_keep_ratio=self.config.mesh_crop_min_keep_ratio,
                )

                processed = load_or_process_mesh(
                    mesh_base,
                    spec,
                    self.config.paths,
                    console=self.console,
                )
                mesh = processed.mesh
                crop_bounds = processed.bounds
                mesh_verts = processed.verts
                mesh_faces = processed.faces
                mesh_cache_key = processed.spec_hash
                mesh_specs = spec
            else:
                if bounds is None:
                    raise ValueError(
                        f"Unable to infer crop bounds for snippet {snippet_id} (scene {scene_id}).",
                    )
                margin = float(self.config.mesh_crop_margin_m or 0.0)
                crop_bounds = (bounds[0] - margin, bounds[1] + margin)
                mesh_cache_key = None

            sample = EfmSnippetView(
                efm=efm_dict,
                scene_id=scene_id,
                snippet_id=snippet_id,
                mesh=mesh,
                crop_bounds=crop_bounds,
                mesh_verts=mesh_verts,
                mesh_faces=mesh_faces,
                mesh_cache_key=mesh_cache_key,
                mesh_specs=mesh_specs,
            )

            yield sample


__all__ = ["AseEfmDataset", "AseEfmDatasetConfig"]
