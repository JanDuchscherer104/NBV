# ARIA-NBV

[![Root Verification](https://github.com/JanDuchscherer104/ARIA-NBV/actions/workflows/ci.yml/badge.svg)](https://github.com/JanDuchscherer104/ARIA-NBV/actions/workflows/ci.yml)
[![Documentation](https://github.com/JanDuchscherer104/ARIA-NBV/actions/workflows/quarto-publish.yml/badge.svg)](https://janduchscherer104.github.io/ARIA-NBV/)
[![License](https://img.shields.io/badge/license-Apache--2.0-blue.svg)](LICENSE)

ARIA-NBV is a research codebase for target-conditioned next-best-view (NBV)
selection in egocentric indoor reconstruction. It studies finite candidate
policies whose utility is target-specific Relative Reconstruction Improvement
(RRI). Experiments use [Aria Synthetic Environments
(ASE)](https://facebookresearch.github.io/projectaria_tools/docs/open_datasets/aria_synthetic_environments_dataset)
and actor-visible local scene evidence from
[EFM3D](https://github.com/facebookresearch/efm3d) and its
[Egocentric Voxel Lifting (EVL)](https://facebookresearch.github.io/projectaria_tools/docs/open_models/evl)
model.[^ase][^efm3d] The quality-driven objective and historical one-step
control follow [VIN-NBV](https://arxiv.org/abs/2505.06219), which ranks
candidate views by predicted reconstruction improvement.[^vin-nbv]

The current thesis asks whether multi-step selection improves endpoint
reconstruction of a selected target over myopic selection when candidate
support, validity rules, acquisition budget, and oracle evaluation are held
fixed. The [research questions](docs/typst/thesis/sections/01-research-questions.typ)
and [development roadmap](docs/typst/thesis/development/roadmap.typ) define the
current scientific scope and evidence gates. They are also available in the
rendered thesis at [Research Questions](https://janduchscherer104.github.io/ARIA-NBV/typst/thesis/main.pdf#page=30)
and [Development roadmap](https://janduchscherer104.github.io/ARIA-NBV/typst/thesis/main.pdf#page=104).

## Research Scope

The experimental protocol separates four kinds of information:

- **Actor-visible evidence:** observed snippets, trajectory and calibration,
  semi-dense or EVL support, finite candidate poses, validity masks, and logged
  history.
- **Privileged supervision:** ground-truth scene and target geometry,
  counterfactual candidate renders, and oracle RRI labels.
- **Decision variables:** a finite, provenance-preserving candidate table and a
  hard action-validity mask at each acquisition step.
- **Evaluation:** endpoint target reconstruction, cumulative and marginal RRI,
  invalid-action rates, path cost, runtime, and coverage under matched budgets.

Ground-truth geometry defines target tasks, labels, and evaluation. It is not an
ordinary policy input. Invalid candidates are excluded by explicit masks and
reason codes rather than represented as low-reward actions.

### Implementation and evidence status

- **Implemented substrate:** scene- and target-RRI oracles, finite-candidate
  generation and rendering, immutable VIN stores, rollout generation and
  [Zarr](https://github.com/zarr-developers/zarr-python) persistence,
  [Streamlit](https://github.com/streamlit/streamlit)/[Rerun](https://github.com/rerun-io/rerun)
  inspection, one-step VIN training, actor/oracle-separated finite-horizon
  `Q_H` datasets, modular regression and CORAL scorers, masked Double-Q
  optimization, immutable inference bundles, online hard-masked selection, and
  bounded exact-`Q_2` certification.
- **Open thesis gates:** actor-visible target matching, a target-conditioned
  one-step control, trusted scene-disjoint evidence at scale, measured positive
  oracle-lookahead headroom, and a production learned `Q_H` evaluation.
- **Deferred scope:** online discrete learning, continuous or simulator-backed
  control, VLM/global planning, and real-device deployment.

The repository therefore provides research infrastructure and executable
contracts; it does not yet report a completed target-conditioned multi-step
policy result.

## Computational Workflow

1. **Load observations.** Read ASE/[ATEK](https://github.com/facebookresearch/ATEK)
   snippets and EFM3D/EVL evidence while preserving the actor/oracle boundary.
2. **Construct candidates.** Generate a finite candidate table with strategy
   provenance, feasibility masks, and invalid-reason codes.
3. **Generate labels.** Render candidate depths and compute scene- or
   target-specific RRI against privileged mesh evidence.
4. **Persist one-step evidence.** Store immutable source rows, candidate tables,
   cached features, and oracle labels in `vin_offline`.
5. **Generate rollouts.** Select valid actions under configured policies and
   persist lineage, factual transitions, selected depth, and derived `Q_H`
   views in `rollouts.zarr`.
6. **Inspect and learn.** Audit artifacts through Streamlit or Rerun and use the
   validated stores for one-step VIN or finite-horizon experiments.

## Getting Started

ARIA-NBV requires Python 3.11. Full oracle generation, counterfactual rendering,
and training target the repository's Linux environment with CUDA 12.1 and
[PyTorch3D](https://github.com/facebookresearch/pytorch3d). They also require
recursive submodules, ASE access, and external checkpoints. Follow the [portable
setup and one-scene smoke guide](SETUP.md) before using real data.

Launch the interactive inspection and bounded generation application from the
package directory:

```sh
cd aria_nbv
uv run nbv-st
```

Data generation and training are separate, data-dependent workflows documented
by their package owners.

## Documentation

| Purpose | Source |
| --- | --- |
| Scientific framing and current thesis | Rendered thesis: [Introduction](https://janduchscherer104.github.io/ARIA-NBV/typst/thesis/main.pdf#page=29), [Research Questions](https://janduchscherer104.github.io/ARIA-NBV/typst/thesis/main.pdf#page=30), [Method](https://janduchscherer104.github.io/ARIA-NBV/typst/thesis/main.pdf#page=62), [Experimental Design](https://janduchscherer104.github.io/ARIA-NBV/typst/thesis/main.pdf#page=87), [Results](https://janduchscherer104.github.io/ARIA-NBV/typst/thesis/main.pdf#page=98), and [Development roadmap](https://janduchscherer104.github.io/ARIA-NBV/typst/thesis/main.pdf#page=104); [Typst source](docs/typst/thesis/main.typ) |
| Installation, dependencies, and data | [Portable setup](SETUP.md) |
| Package architecture and entrypoints | [`aria-nbv` package overview](aria_nbv/README.md) and [generated API reference](docs/reference/index.qmd) |
| Offline evidence generation | [Data-handling and generation runbook](aria_nbv/aria_nbv/data_handling/README.md) |
| Rollout persistence and read model | [Rollout contracts](aria_nbv/aria_nbv/rollouts/README.md) |
| Interactive inspection | [Streamlit application](aria_nbv/aria_nbv/app/README.md) and [Rerun inspector](aria_nbv/aria_nbv/rerun_inspector/README.md) |
| Training contracts | [Lightning](aria_nbv/aria_nbv/lightning/README.md) and [VIN](aria_nbv/aria_nbv/vin/README.md) |
| Scientific notation | [Symbols](docs/typst/shared/symbols.typ), [equations](docs/typst/shared/equations.typ), and [glossary](docs/typst/shared/glossary.typ) |
| Literature and source provenance | [Reviewed literature](docs/contents/literature/index.qmd), [bibliography](docs/references.bib), and [source registry](docs/literature/sources.jsonl) |

## Repository Layout

| Path | Purpose |
| --- | --- |
| `aria_nbv/aria_nbv/` | Python package: data, geometry, oracle, rollouts, models, training, and inspection. |
| `aria_nbv/tests/` | Executable contract, integration, and regression tests. |
| `.configs/` | Tracked configurations for data generation, inspection, and training. |
| `docs/typst/thesis/` | Active thesis, scientific framing, research questions, and evidence gates. |
| `docs/contents/` | Public documentation, background, literature reviews, and navigation. |
| `external/` | Pinned or forked upstream dependencies, including [EFM3D](https://github.com/facebookresearch/efm3d), [ATEK](https://github.com/facebookresearch/ATEK), and [PointNeXt](https://github.com/guochengqian/PointNeXt). |

### Documentation ownership

| Surface | Responsibility |
| --- | --- |
| Python source, tests, and active configuration | Executable behavior and its verification. |
| Public Python docstrings and generated API pages | Shapes, coordinate frames, invariants, errors, lifecycle, and symbol-level implementation contracts. |
| Active Typst thesis | Scientific estimands, architectural rationale, evidence status, and limitations. |
| Package READMEs | User workflows, entrypoints, architecture orientation, troubleshooting, and links to the detailed owners. |
| `AGENTS.md` files | Contributor routing, cross-module hazards, and required verification. |

Historical plans, reports, and refactor inventories are evidence rather than
current documentation owners.

## License

ARIA-NBV is licensed under the [Apache License 2.0](LICENSE). Dataset, model,
and upstream dependency terms remain governed by their respective providers.

[^ase]: Meta, [*Aria Synthetic Environments Dataset*](https://facebookresearch.github.io/projectaria_tools/docs/open_datasets/aria_synthetic_environments_dataset). See also Armen Avetisyan et al., [*SceneScript: Reconstructing Scenes With an Autoregressive Structured Language Model*](https://arxiv.org/abs/2403.13064), 2024.
[^efm3d]: Julian Straub et al., [*EFM3D: A Benchmark for Measuring Progress Towards 3D Egocentric Foundation Models*](https://arxiv.org/abs/2406.10224), 2024; [official implementation](https://github.com/facebookresearch/efm3d).
[^vin-nbv]: Noah Frahm et al., [*VIN-NBV: A View Introspection Network for Next-Best-View Selection for Resource-Efficient 3D Reconstruction*](https://arxiv.org/abs/2505.06219), 2025.
