# ARIA-NBV

[![Root Verification](https://github.com/JanDuchscherer104/ARIA-NBV/actions/workflows/ci.yml/badge.svg)](https://github.com/JanDuchscherer104/ARIA-NBV/actions/workflows/ci.yml)
[![Documentation](https://github.com/JanDuchscherer104/ARIA-NBV/actions/workflows/quarto-publish.yml/badge.svg)](https://janduchscherer104.github.io/ARIA-NBV/)
[![License](https://img.shields.io/badge/license-Apache--2.0-blue.svg)](LICENSE)

ARIA-NBV is a research prototype for target-conditioned, quality-driven
next-best-view planning in egocentric indoor scenes. It uses Aria Synthetic
Environments (ASE) and EFM3D/EVL evidence to study finite-candidate policies
whose utility is target-specific Relative Reconstruction Improvement (RRI).

The active thesis asks whether multi-step selection can improve endpoint target
quality under fixed candidate support, validity rules, and acquisition budgets.
Current `main` implements the oracle, data, rollout, inspection, and
finite-horizon training infrastructure; actor-visible target conditioning and a
production `Q_H` policy evaluation remain active research gates.

## Key Ideas

- **Quality-driven selection:** optimize reconstruction improvement rather than
  treating geometric coverage as the final objective.
- **Actor/oracle separation:** actor-visible state comes from observed evidence;
  ground-truth geometry and counterfactual renders remain supervision,
  evaluation, or explicitly named upper bounds.
- **Finite candidate actions:** every decision uses an auditable candidate
  table, hard validity mask, and explicit invalid-reason codes.
- **Two-store lineage:** immutable one-step evidence stays in `vin_offline`;
  target-conditioned multi-step replay lives in a separate `rollouts.zarr`
  store that references its source rows.
- **Matched evaluation:** any learned policy result must re-evaluate selections
  with the oracle under the same candidate support and acquisition budget as
  its baselines.

## Current State

| State | Scope |
| --- | --- |
| Available | Oracle scene/target RRI, candidate generation and rendering, immutable VIN stores, rollout generation and Zarr persistence, Streamlit/Rerun inspection, and scorer-independent `Q_H` data/training contracts. |
| Active gates | Observed or predicted target matching, an actor-visible target-conditioned one-step scorer, trusted scene-disjoint support, bounded-lookahead headroom, and a production `Q_H` scorer/evaluation path. |
| Deferred | Online discrete learning, continuous or simulator-backed control, VLM/global planning, and real-device deployment. |

The [active research questions](docs/typst/thesis/sections/01-research-questions.typ)
and [development roadmap](docs/typst/thesis/development/roadmap.typ) own the
current scientific scope and evidence gates.

## Start Here

| Goal | Owner |
| --- | --- |
| Install dependencies, obtain data, and run smoke checks | [Portable setup](SETUP.md) |
| Understand the current thesis and research gates | [Active thesis](docs/typst/thesis/main.typ) and [research questions](docs/typst/thesis/sections/01-research-questions.typ) |
| Inspect stores and experiments interactively | [Streamlit app](aria_nbv/aria_nbv/app/README.md) |
| Generate or understand offline and rollout data | [Data-handling and generation runbook](aria_nbv/aria_nbv/data_handling/README.md) |
| Validate or inspect persisted rollouts | [Rollout storage and read model](aria_nbv/aria_nbv/rollouts/README.md) |
| Understand one-step VIN and finite-horizon training | [Lightning training contracts](aria_nbv/aria_nbv/lightning/README.md) and [VIN model contracts](aria_nbv/aria_nbv/vin/README.md) |
| Browse executable package contracts | [Generated API reference](docs/reference/index.qmd) |
| Find notation, equations, terms, or literature | [Symbols](docs/typst/shared/symbols.typ), [equations](docs/typst/shared/equations.typ), [glossary](docs/typst/shared/glossary.typ), and [literature index](docs/contents/literature/index.qmd) |
| Contribute code or use a coding agent | [Repository guidance](AGENTS.md), then the nearest package or docs guide |

The [published documentation](https://janduchscherer104.github.io/ARIA-NBV/)
is the rendered public view. Exact Python source, tests, and active
configuration own executable behavior; the active Typst thesis owns current
scientific claims.

## Requirements

- Python 3.11 and recursive Git submodules.
- Linux with the CUDA 12.1 toolchain for full ASE oracle generation, rendering,
  and training. CPU-only environments support documentation, lightweight tests,
  immutable-store reads, and inspection utilities.
- ASE access manifests and the external checkpoints listed in
  [SETUP.md](SETUP.md) for real-data workflows.

Follow [SETUP.md](SETUP.md) for the supported environment and data layout. Do
not treat a successful PyTorch CUDA import as proof that the separately compiled
PyTorch3D renderer is usable.

## First Useful Commands

List repository-level validation and inspection targets:

```sh
make help
```

After completing setup, run package commands from `aria_nbv/`:

```sh
cd aria_nbv

# Interactive inspection and bounded generation surface
uv run nbv-st

# Discover immutable-store and rollout-store diagnostics
uv run nbv-offline-info --help
uv run nbv-rollouts-info --help
```

Validate the configured one-step VIN path before starting a training run:

```sh
uv run nbv-summary --config-path offline_only.toml
uv run nbv-train --config-path offline_only.toml
```

`nbv-train` owns the existing one-step VIN/Lightning path. The retained `Q_H`
surface is scorer-independent infrastructure and does not yet have a dedicated
production CLI.

## Repository Map

| Path | Purpose |
| --- | --- |
| `aria_nbv/aria_nbv/` | Python package: data, oracle, rollout, model, training, app, and inspection owners. |
| `aria_nbv/tests/` | Focused executable contract and regression tests. |
| `.configs/` | Active TOML configurations for data generation, inspection, and training. |
| `docs/typst/thesis/` | Active thesis, research questions, development gates, and scientific claims. |
| `docs/contents/` | Public Quarto navigation, literature reviews, and background material. |
| `external/` | Pinned or forked upstream dependencies such as EFM3D, ATEK, and PointNeXt. |

## License

ARIA-NBV is licensed under the [Apache License 2.0](LICENSE).
