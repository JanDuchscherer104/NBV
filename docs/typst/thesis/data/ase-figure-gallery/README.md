# ASE thesis figure gallery

Generated from the exact local ASE/ATEK snapshot. This is a review surface,
not an implicit edit to the active thesis section.

| ID | Candidate | Asset | Decision question |
| --- | --- | --- | --- |
| `scene-evidence` | Scene-level geometric evidence | `scene-evidence.png` | Show the actual GT mesh, a recorded trajectory, and semi-dense points in one representative local scene. |
| `mesh-atlas` | GT-mesh subset atlas | `mesh-atlas.png` | Show that the 100-scene local GT subset contains varied indoor geometry without implying corpus-wide representativeness. |
| `subset-statistics` | 100-scene GT subset statistics | `subset-statistics.png` | Quantify the scope and geometric spread of the exact local mesh-evaluation subset. |

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

- Generated: 2026-08-31T20:54:25.868904+00:00
- Local mesh source: `.data/ase_meshes` (100 PLY meshes)
- Local ATEK source: `.data/ase_efm` (576 shard files)
- Representative-scene selection: deterministic quantiles of mesh face count and GT-mesh asset size.
