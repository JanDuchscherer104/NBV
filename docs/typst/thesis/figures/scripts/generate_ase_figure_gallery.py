#!/usr/bin/env python3
"""Render a reviewable, data-derived ASE thesis-figure gallery.

The gallery deliberately separates candidate generation from thesis adoption.
Use ``--select`` to record the candidate identifiers that survived review, then
``--promote`` to copy just those rendered assets into the thesis figure tree.
The active Typst section is never edited implicitly.

Examples:
    PYTHONPATH=aria_nbv:external/efm3d aria_nbv/.venv/bin/python \\
      docs/typst/thesis/figures/scripts/generate_ase_figure_gallery.py --render
    ... --select scene-evidence subset-statistics
    ... --promote
"""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import subprocess
from collections.abc import Callable
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import trimesh

from aria_nbv.data_handling.ase_efm import AseEfmDatasetConfig
from aria_nbv.utils.data_plotting import SnippetPlotBuilder

REPO_ROOT = Path(__file__).resolve().parents[5]
GALLERY_DIR = REPO_ROOT / "docs/typst/thesis/data/ase-figure-gallery"
PROMOTED_DIR = REPO_ROOT / "docs/typst/thesis/figures/ase-promoted"
MESH_DIR = REPO_ROOT / ".data/ase_meshes"
ATEK_DIR = REPO_ROOT / ".data/ase_efm"
SCENE_ID = "81286"

PALETTE = {
    "navy": "#102A43",
    "blue": "#2F80ED",
    "teal": "#00A6A6",
    "gold": "#F2B134",
    "coral": "#E76F51",
    "ink": "#243B53",
    "muted": "#627D98",
    "grid": "#D9E2EC",
    "paper": "#F7FAFC",
}


@dataclass(frozen=True)
class MeshStats:
    """Exact per-mesh geometry statistics used to select and describe scenes."""

    scene_id: str
    vertices: int
    faces: int
    source_bytes: int


@dataclass(frozen=True)
class Candidate:
    """A rendered figure candidate and its review-facing provenance."""

    identifier: str
    title: str
    filename: str
    purpose: str
    source_evidence: str
    typst_caption: str


CANDIDATES = (
    Candidate(
        identifier="scene-evidence",
        title="Scene-level geometric evidence",
        filename="scene-evidence.png",
        purpose="Show the actual GT mesh, a recorded trajectory, and semi-dense points in one fixed illustrative local scene.",
        source_evidence="Fixed ASE scene 81286 and its first shard snippet, loaded through AseEfmDatasetConfig and SnippetPlotBuilder.",
        typst_caption="A fixed illustrative local ASE snippet (scene 81286): GT mesh (grey), recorded rig trajectory (black), and MPS-style semi-dense points (height-coloured). This panel does not claim scene representativeness; it visualizes the evidence layers used by the offline protocol, with the mesh retained as privileged evaluation evidence.",
    ),
    Candidate(
        identifier="mesh-atlas",
        title="GT-mesh subset atlas",
        filename="mesh-atlas.png",
        purpose="Show that the 100-scene local GT subset contains varied indoor geometry without implying corpus-wide representativeness.",
        source_evidence="Six deterministic inner face-count quantiles from the 100 local EFM3D GT meshes.",
        typst_caption="Six deterministic inner face-count-quantile examples from the local 100-scene GT-mesh subset. Panels are top-down, log-scaled vertex-density projections of GT meshes, not rendered RGB observations and not evidence of corpus-wide representativeness.",
    ),
    Candidate(
        identifier="subset-statistics",
        title="100-scene GT subset statistics",
        filename="subset-statistics.png",
        purpose="Quantify the scope and geometric spread of the exact local mesh-evaluation subset.",
        source_evidence="All 100 local PLY meshes under .data/ase_meshes and ATEK shard inventory under .data/ase_efm.",
        typst_caption="Geometry-header and storage statistics for the exact local 100-scene GT-mesh subset. Face and vertex counts are read from PLY headers; GT-mesh asset size is serialized-file size in MB, not physical scene extent. Shard counts are a local ATEK inventory rather than a property of the full ASE release.",
    ),
)


def _configure_matplotlib() -> None:
    plt.rcParams.update(
        {
            "font.family": "DejaVu Sans",
            "font.size": 8,
            "axes.titlesize": 9,
            "axes.labelsize": 8,
            "xtick.labelsize": 7,
            "ytick.labelsize": 7,
            "axes.titleweight": "bold",
            "figure.facecolor": "white",
            "axes.facecolor": "white",
        }
    )


def _mesh_paths() -> list[Path]:
    return sorted(MESH_DIR.glob("scene_ply_*.ply"))


def _ply_counts(mesh_path: Path) -> tuple[int, int]:
    """Read vertex/face counts from a PLY header without loading multi-GB geometry."""

    prefix = mesh_path.open("rb").read(65_536)
    marker = b"end_header\n"
    header_end = prefix.find(marker)
    if header_end < 0:
        raise ValueError(f"PLY header was not found in first 64 KiB: {mesh_path}")
    header = prefix[: header_end + len(marker)].decode("ascii", errors="strict")
    vertex_count = face_count = None
    for line in header.splitlines():
        parts = line.split()
        if len(parts) == 3 and parts[:2] == ["element", "vertex"]:
            vertex_count = int(parts[2])
        elif len(parts) == 3 and parts[:2] == ["element", "face"]:
            face_count = int(parts[2])
        elif line == "end_header":
            break
    if vertex_count is None or face_count is None:
        raise ValueError(f"Could not read vertex/face counts from {mesh_path}")
    return vertex_count, face_count


def load_mesh_stats() -> list[MeshStats]:
    """Read exact 100-mesh inventory statistics without reloading all geometry."""

    stats: list[MeshStats] = []
    for mesh_path in _mesh_paths():
        vertices, faces = _ply_counts(mesh_path)
        stats.append(
            MeshStats(
                scene_id=mesh_path.stem.removeprefix("scene_ply_"),
                vertices=vertices,
                faces=faces,
                source_bytes=mesh_path.stat().st_size,
            )
        )
    if len(stats) != 100:
        raise RuntimeError(f"Expected exactly 100 local GT meshes, found {len(stats)} under {MESH_DIR}.")
    return stats


def _quantile_scenes(stats: list[MeshStats], count: int = 6) -> list[MeshStats]:
    """Select six deterministic inner quantiles of the local face-count distribution."""

    ordered = sorted(stats, key=lambda item: (item.faces, item.scene_id))
    # Use inner quantiles: the extreme maximum is a 13M-face outlier whose
    # display proxy obscures the comparative purpose of a small-multiple atlas.
    positions = np.linspace(5, len(ordered) - 6, count, dtype=int)
    selected = [ordered[index] for index in positions]
    return selected


def _top_down_mesh_png(mesh_path: Path, output_path: Path) -> None:
    """Export a readable top-down density thumbnail from an exact GT mesh asset."""

    mesh = trimesh.load(mesh_path, process=False)
    if not isinstance(mesh, trimesh.Trimesh):
        raise TypeError(f"Expected a triangular mesh at {mesh_path}, found {type(mesh)!r}")
    vertices_xy = np.asarray(mesh.vertices[:, :2])
    density, _, _ = np.histogram2d(vertices_xy[:, 0], vertices_xy[:, 1], bins=280)
    # Log density preserves both structural walls and sparse furnishings at one
    # journal-scale colour range. It is a projection, not an observation image.
    plt.imsave(output_path, np.log1p(density.T), cmap="mako", origin="lower")


def render_scene_evidence(output_path: Path) -> None:
    """Render a SceneScript-inspired evidence panel from a real local snippet."""

    config = AseEfmDatasetConfig(
        scene_ids=[SCENE_ID],
        snippet_ids=["shards-0000"],
        load_meshes=True,
        require_mesh=True,
        mesh_simplify_ratio=0.025,
        semidense_points_pad=5_000,
        verbosity=0,
    )
    snippet = next(iter(config.setup_target()))
    figure = (
        SnippetPlotBuilder.from_snippet(
            snippet,
            title="ASE scene 81286 — local evidence layers",
            height=760,
        )
        .add_mesh(color="#A8B8C8", opacity=0.52)
        .add_semidense(max_points=3_000, color="Viridis")
        .add_trajectory(first_color=PALETTE["teal"], last_color=PALETTE["coral"])
        .add_frusta(frame_indices=[0, 9, 19], scale=0.55, include_axes=False, include_center=False)
        .finalize()
    )
    figure.update_layout(
        font={"family": "Arial", "size": 17, "color": PALETTE["ink"]},
        legend={"orientation": "h", "yanchor": "bottom", "y": 1.01, "xanchor": "left", "x": 0.0},
        margin={"l": 0, "r": 0, "t": 80, "b": 0},
    )
    figure.write_image(output_path, width=1200, height=740, scale=1)


def render_mesh_atlas(output_path: Path, stats: list[MeshStats], assets_dir: Path) -> list[str]:
    """Compose top-down GT-mesh vertex-density projections into a scientific atlas."""

    selected = _quantile_scenes(stats)
    thumbnails: list[Path] = []
    for item in selected:
        thumbnail_path = assets_dir / f"mesh-density-{item.scene_id}.png"
        if not thumbnail_path.exists():
            _top_down_mesh_png(MESH_DIR / f"scene_ply_{item.scene_id}.ply", thumbnail_path)
        thumbnails.append(thumbnail_path)

    _configure_matplotlib()
    figure, axes = plt.subplots(2, 3, figsize=(11.5, 6.1), constrained_layout=True)
    for axis, item, thumbnail in zip(axes.flat, selected, thumbnails, strict=True):
        thumbnail_rgba = plt.imread(thumbnail)
        axis.imshow(thumbnail_rgba)
        axis.set_title(f"Scene {item.scene_id}", loc="left", color=PALETTE["navy"])
        axis.text(
            0.02,
            0.02,
            f"{item.faces / 1e6:.2f} M faces\n{item.source_bytes / 1e6:.0f} MB asset",
            transform=axis.transAxes,
            va="bottom",
            ha="left",
            color="white",
            fontsize=7.5,
            bbox={"boxstyle": "round,pad=0.3", "facecolor": PALETTE["navy"], "edgecolor": "none", "alpha": 0.9},
        )
        axis.axis("off")
    figure.suptitle(
        "Local 100-scene GT-mesh subset: face-count-quantile atlas",
        x=0.01,
        ha="left",
        color=PALETTE["navy"],
        fontsize=13,
        fontweight="bold",
    )
    figure.savefig(output_path, dpi=300, bbox_inches="tight", pad_inches=0.06)
    plt.close(figure)
    return [item.scene_id for item in selected]


def _histogram(axis: plt.Axes, values: np.ndarray, *, label: str, color: str, unit: str, log: bool = False) -> None:
    axis.hist(values, bins=16, color=color, edgecolor="white", linewidth=0.8)
    median = float(np.median(values))
    axis.axvline(median, color=PALETTE["navy"], linewidth=1.5, linestyle="--")
    axis.set_title(label, loc="left", color=PALETTE["navy"])
    axis.set_xlabel(unit)
    axis.set_ylabel("Scenes")
    if log:
        axis.set_xscale("log")
    axis.grid(axis="y", color=PALETTE["grid"], linewidth=0.7)
    axis.text(
        0.98,
        0.92,
        f"median {median:,.1f}",
        transform=axis.transAxes,
        ha="right",
        va="top",
        color=PALETTE["muted"],
        fontsize=7.5,
    )


def render_subset_statistics(output_path: Path, stats: list[MeshStats]) -> dict[str, float | int]:
    """Render a four-panel statistical portrait of the exact local GT subset."""

    _configure_matplotlib()
    faces = np.asarray([item.faces for item in stats], dtype=float)
    vertices = np.asarray([item.vertices for item in stats], dtype=float)
    source_size_mb = np.asarray([item.source_bytes / 1e6 for item in stats], dtype=float)
    shard_count = len(list(ATEK_DIR.glob("*/*.tar")))

    figure, axes = plt.subplots(2, 2, figsize=(11.5, 7.2), constrained_layout=True)
    _histogram(axes[0, 0], faces / 1e6, label="Mesh complexity", color=PALETTE["blue"], unit="Faces (millions)")
    _histogram(axes[0, 1], source_size_mb, label="GT-mesh asset size", color=PALETTE["teal"], unit="MB", log=True)
    _histogram(axes[1, 0], vertices / 1e6, label="Mesh vertices", color=PALETTE["gold"], unit="Vertices (millions)")
    axes[1, 1].scatter(
        faces / 1e6, source_size_mb, s=34, color=PALETTE["coral"], alpha=0.82, edgecolor="white", linewidth=0.4
    )
    axes[1, 1].set_xscale("log")
    axes[1, 1].set_yscale("log")
    axes[1, 1].set_title("Complexity versus asset size", loc="left", color=PALETTE["navy"])
    axes[1, 1].set_xlabel("Faces (millions)")
    axes[1, 1].set_ylabel("GT-mesh asset size (MB)")
    axes[1, 1].grid(color=PALETTE["grid"], linewidth=0.7)
    figure.suptitle(
        f"Exact local GT-mesh evaluation subset (n = 100 scenes; {shard_count:,} ATEK shards)",
        x=0.01,
        ha="left",
        color=PALETTE["navy"],
        fontsize=14,
        fontweight="bold",
    )
    figure.savefig(output_path, dpi=300, bbox_inches="tight", pad_inches=0.06)
    plt.close(figure)
    return {
        "scene_count": len(stats),
        "shard_count": shard_count,
        "faces_median": float(np.median(faces)),
        "faces_p10": float(np.percentile(faces, 10)),
        "faces_p90": float(np.percentile(faces, 90)),
        "source_size_mb_median": float(np.median(source_size_mb)),
        "source_size_mb_p10": float(np.percentile(source_size_mb, 10)),
        "source_size_mb_p90": float(np.percentile(source_size_mb, 90)),
        "vertices_median": float(np.median(vertices)),
    }


def _load_selection(selection_path: Path) -> list[str]:
    if not selection_path.exists():
        return []
    return list(json.loads(selection_path.read_text())["selected"])


def _sha256_file(path: Path) -> str:
    """Return a content digest for a generated asset or generator source file."""

    return hashlib.sha256(path.read_bytes()).hexdigest()


def _git_head() -> str | None:
    """Return the local commit identity when the gallery is generated inside Git."""

    completed = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=REPO_ROOT,
        check=False,
        capture_output=True,
        text=True,
    )
    return completed.stdout.strip() if completed.returncode == 0 else None


def _write_selection(selection_path: Path, identifiers: list[str]) -> None:
    allowed = {candidate.identifier for candidate in CANDIDATES}
    unknown = sorted(set(identifiers) - allowed)
    if unknown:
        raise ValueError(f"Unknown candidate identifier(s): {', '.join(unknown)}")
    selection_path.write_text(json.dumps({"selected": identifiers}, indent=2) + "\n")


def _write_readme(output_dir: Path, manifest: dict[str, object]) -> None:
    rows = []
    for candidate in CANDIDATES:
        rows.append(f"| `{candidate.identifier}` | {candidate.title} | `{candidate.filename}` | {candidate.purpose} |")
    readme = f"""# ASE thesis figure gallery

Generated from the exact local ASE/ATEK snapshot. This is a review surface,
not an implicit edit to the active thesis section.

| ID | Candidate | Asset | Decision question |
| --- | --- | --- | --- |
{chr(10).join(rows)}

## Review workflow

1. Regenerate all candidates: `PYTHONPATH=aria_nbv:external/efm3d aria_nbv/.venv/bin/python docs/typst/thesis/figures/scripts/generate_ase_figure_gallery.py --render`
2. Inspect the rendered PNGs in this directory and choose identifiers.
3. Record a reviewed set: `...generate_ase_figure_gallery.py --select scene-evidence subset-statistics`
4. Copy only that reviewed set to the thesis figure tree: `...generate_ase_figure_gallery.py --promote`
5. Print ready-to-review Typst figure blocks: `...generate_ase_figure_gallery.py --print-typst`

`--candidate ID --render` re-renders only one candidate, making visual patches
small and reviewable. Promotion changes only `docs/typst/thesis/figures/ase-promoted/`;
the active dataset section remains an explicit editorial decision.

## Reproducibility

- Generated: {manifest["generated_at"]}
- Local mesh source: `.data/ase_meshes` ({manifest["statistics"]["scene_count"]} PLY meshes)
- Local ATEK source: `.data/ase_efm` ({manifest["statistics"]["shard_count"]} shard files)
- Scene evidence: fixed illustrative scene 81286; no representativeness claim.
- Atlas selection: six deterministic inner face-count quantiles; each panel is a log-scaled vertex-density projection.
"""
    (output_dir / "README.md").write_text(readme)


def _print_typst(selected: list[str]) -> None:
    by_id = {candidate.identifier: candidate for candidate in CANDIDATES}
    for identifier in selected:
        candidate = by_id[identifier]
        print(
            "#figure(\n"
            f'  image("../../figures/ase-promoted/{candidate.filename}", width: 100%),\n'
            f"  caption: [{candidate.typst_caption}],\n"
            f") <fig:thesis-ase-{identifier}>\n"
        )


def _print_candidates() -> None:
    """Print stable candidate IDs with their review questions."""

    for candidate in CANDIDATES:
        print(f"{candidate.identifier}\t{candidate.title}\t{candidate.purpose}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, default=GALLERY_DIR)
    parser.add_argument(
        "--render", action="store_true", help="Render all selected candidates (or all candidates by default)."
    )
    parser.add_argument(
        "--candidate", action="append", default=[], help="Restrict rendering to one candidate ID; repeatable."
    )
    parser.add_argument("--select", nargs="+", help="Record the reviewed candidate IDs in selection.json.")
    parser.add_argument(
        "--promote", action="store_true", help="Copy reviewed candidate assets into the thesis figure tree."
    )
    parser.add_argument("--print-typst", action="store_true", help="Print Typst blocks for the reviewed candidate set.")
    parser.add_argument("--list", action="store_true", help="Print stable candidate IDs and review questions.")
    args = parser.parse_args()

    output_dir = args.output_dir.resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    assets_dir = output_dir / "assets"
    assets_dir.mkdir(exist_ok=True)
    selection_path = output_dir / "selection.json"
    if args.select:
        _write_selection(selection_path, args.select)
    if args.list:
        _print_candidates()

    candidate_ids = args.candidate or [candidate.identifier for candidate in CANDIDATES]
    allowed = {candidate.identifier for candidate in CANDIDATES}
    unknown = sorted(set(candidate_ids) - allowed)
    if unknown:
        raise ValueError(f"Unknown candidate identifier(s): {', '.join(unknown)}")

    if args.render:
        stats = load_mesh_stats()
        renderers: dict[str, Callable[[], object]] = {
            "scene-evidence": lambda: render_scene_evidence(output_dir / "scene-evidence.png"),
            "mesh-atlas": lambda: render_mesh_atlas(output_dir / "mesh-atlas.png", stats, assets_dir),
            "subset-statistics": lambda: render_subset_statistics(output_dir / "subset-statistics.png", stats),
        }
        results = {identifier: renderers[identifier]() for identifier in candidate_ids}
        summary = (
            render_subset_statistics(output_dir / "subset-statistics.png", stats)
            if "subset-statistics" not in results
            else results["subset-statistics"]
        )
        atlas_scene_ids = results.get("mesh-atlas", [item.scene_id for item in _quantile_scenes(stats)])
        source_inventory = {
            "mesh_statistics_sha256": hashlib.sha256(
                json.dumps([asdict(item) for item in stats], sort_keys=True).encode()
            ).hexdigest(),
            "atek_scene_ids": sorted(path.name for path in ATEK_DIR.iterdir() if path.is_dir()),
        }
        outputs = {
            candidate.identifier: {
                "filename": candidate.filename,
                "sha256": _sha256_file(output_dir / candidate.filename),
            }
            for candidate in CANDIDATES
            if (output_dir / candidate.filename).exists()
        }
        manifest = {
            "schema_version": 1,
            "generated_at": datetime.now(UTC).isoformat(),
            "generator": {
                "path": str(Path(__file__).resolve().relative_to(REPO_ROOT)),
                "sha256": _sha256_file(Path(__file__)),
                "git_head": _git_head(),
            },
            "source_inventory": source_inventory,
            "statistics": summary,
            "mesh_statistics": [asdict(item) for item in stats],
            "candidates": [asdict(candidate) for candidate in CANDIDATES],
            "atlas_scene_ids": atlas_scene_ids,
            "outputs": outputs,
            "selected": _load_selection(selection_path),
        }
        (output_dir / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
        _write_readme(output_dir, manifest)

    selected = _load_selection(selection_path)
    if args.promote:
        if not selected:
            raise ValueError("No reviewed selections. Run --select <candidate-id>... before --promote.")
        PROMOTED_DIR.mkdir(parents=True, exist_ok=True)
        by_id = {candidate.identifier: candidate for candidate in CANDIDATES}
        for identifier in selected:
            candidate = by_id[identifier]
            source = output_dir / candidate.filename
            if not source.exists():
                raise FileNotFoundError(f"Render {identifier!r} before promotion: {source}")
            shutil.copy2(source, PROMOTED_DIR / candidate.filename)
        (PROMOTED_DIR / "selection.json").write_text(json.dumps({"selected": selected}, indent=2) + "\n")

    if args.print_typst:
        if not selected:
            raise ValueError("No reviewed selections. Run --select <candidate-id>... before --print-typst.")
        _print_typst(selected)


if __name__ == "__main__":
    main()
