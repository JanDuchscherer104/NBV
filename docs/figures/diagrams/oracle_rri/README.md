# Oracle RRI label pipeline flowcharts (Mermaid)

This folder contains **flowchart-style** architecture diagrams for the **oracle RRI labeler pipeline**:

`AseEfmDataset -> CandidateViewGenerator -> CandidateDepthRenderer -> build_candidate_pointclouds -> PreparedRriScorer`.

- `mermaid/` contains Mermaid equivalents (one `.mmd` file per diagram).
- `renders/mermaid/` contains rendered outputs (SVG + PNG).

## Diagrams

- `docs/diagrams/oracle_rri/mermaid/overall.mmd` (pipeline overview)
- `docs/diagrams/oracle_rri/mermaid/overall_compact.mmd` (pipeline overview, compact)
- Compact per-stage:
  - `docs/diagrams/oracle_rri/mermaid/efm_dataset_compact.mmd`
  - `docs/diagrams/oracle_rri/mermaid/candidate_generation_compact.mmd`
  - `docs/diagrams/oracle_rri/mermaid/candidate_depth_renderer_compact.mmd`
  - `docs/diagrams/oracle_rri/mermaid/candidate_pointclouds_compact.mmd`
  - `docs/diagrams/oracle_rri/mermaid/oracle_rri_compact.mmd`
- Expanded per-stage:
  - `docs/diagrams/oracle_rri/mermaid/efm_dataset.mmd`
  - `docs/diagrams/oracle_rri/mermaid/candidate_generation.mmd` (includes `positional_sampling.py`, `orientations.py`, `candidate_generation_rules.py`)
  - `docs/diagrams/oracle_rri/mermaid/candidate_depth_renderer.mmd`
  - `docs/diagrams/oracle_rri/mermaid/candidate_pointclouds.mmd`
  - `docs/diagrams/oracle_rri/mermaid/aria_nbv.mmd`

## Render Mermaid diagrams

Use `mermaid-cli` (`mmdc`) to render each file to PNG for quick inspection:

```bash
npx -y @mermaid-js/mermaid-cli \
  -i docs/diagrams/oracle_rri/mermaid/overall.mmd \
  -o docs/diagrams/oracle_rri/renders/mermaid/overall.png
```

Repeat for the other `.mmd` files in `docs/diagrams/oracle_rri/mermaid/`.

To render everything (SVG + PNG):

```bash
for f in docs/diagrams/oracle_rri/mermaid/*.mmd; do
  b=$(basename "$f" .mmd)
  npx -y @mermaid-js/mermaid-cli -i "$f" -o "docs/diagrams/oracle_rri/renders/mermaid/$b.svg"
  npx -y @mermaid-js/mermaid-cli -i "$f" -o "docs/diagrams/oracle_rri/renders/mermaid/$b.png"
done
```

## Notes on math in Mermaid vs draw.io

- **draw.io** renders MathJax when enabled and typically uses `\(...\)` / `$$...$$`.
- **Mermaid** has dedicated math support (KaTeX) typically using `$$ ... $$`.

For consistency with the paper + draw.io exports, edge labels in these files use `\(...\)` as “math-like” shape annotations (single backslashes, since that imports more reliably into draw.io).
