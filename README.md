# ARIA-NBV

ARIA-NBV develops quality-driven next-best-view planning for egocentric indoor
reconstruction. The current thesis path focuses on ASE/EFM3D snippets,
target-specific Relative Reconstruction Improvement (RRI), finite-candidate
rollouts, and a target-conditioned finite-horizon value model `Q_H`.

The public documentation is published at
<https://janduchscherer104.github.io/ARIA-NBV/>.

## Current Focus

- Keep the active Typst thesis focused on target-conditioned, RRI-based
  multi-step NBV and keep Quarto indexes synchronized to it.
- Validate ASE offline-store, pose-frame, candidate-label, invalidity-mask, and
  oracle-RRI contracts before scale-up.
- Use one-step VIN-style scoring as the myopic baseline, then measure bounded
  oracle-lookahead headroom and train `Q_H` over trusted finite candidate sets.
- Treat online discrete control, continuous actor-critic policies, VLM/global
  planning, and real-device deployment as gated follow-up work.

## Documentation Map

- [Published documentation](https://janduchscherer104.github.io/ARIA-NBV/):
  rendered Quarto site.
- [Quarto home](docs/index.qmd) and [Quarto navigation](docs/_quarto.yml):
  public navigation/reference entry point and sidebar/navbar source.
- [Thesis Roadmap Index](docs/contents/thesis/roadmap.qmd) and
  [Research Question Index](docs/contents/thesis/questions.qmd): Quarto indexes
  into the active Typst thesis.
- [Historical M1 Index](docs/contents/thesis/m1_contract_report.qmd): navigation
  to the historical data/cache/oracle evidence ledger.
- [Literature index](docs/contents/literature/index.qmd): thesis-oriented
  adoption map for NBV, ARIA/EFM3D, rollout/value learning, 3DGS, and semantic
  scene references.
- [Finite-candidate rollout and `Q_H` contract](docs/contents/theory/rl_planning.qmd),
  [candidate sampling and target selection](docs/contents/theory/candidate_sampling_target_selection.qmd),
  and [RRI theory](docs/contents/theory/rri_theory.qmd): reference pages.
- [Thesis Typst source](docs/typst/thesis/main.typ): sole scientific narrative
  and interpretation owner, citing direct implementation, empirical, and
  literature authorities; active master's-thesis compile entry point.
- [Advisor meeting 2026-05-22](docs/typst/thesis_slides/advisor_meeting_2026_05_22.typ):
  historical advisor-alignment deck; use it as provenance, not as the current
  thesis source of truth.
- [API Reference](docs/reference/index.qmd): generated `aria_nbv`
  implementation contracts.
- [Local setup](SETUP.md) and [Quarto setup page](docs/contents/setup.qmd):
  environment, data/cache, and smoke-check instructions.

## Common Local Commands

Run package commands from `aria_nbv/` with the uv-managed environment.

```sh
# Launch the Streamlit app
uv run nbv-st

# Train the VIN model
uv run nbv-train --config-path offline_only.toml

# Single forward pass that summarizes VIN outputs
uv run nbv-summary --config-path offline_only.toml

# Dump resolved config to stdout
uv run nbv-cli --run-mode dump-config --config-path offline_only.toml
```

See [SETUP.md](SETUP.md) for downloader usage, Rerun inspection, offline-store
diagnostics, and smoke checks.
