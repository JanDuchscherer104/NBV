<h1 align="center">ARIA-NBV</h1>

<p align="center">
  <strong>Choose the next view for what you want to reconstruct.</strong><br>
  Target-conditioned, quality-driven view planning for egocentric indoor scenes.
</p>

<p align="center">
  <a href="https://github.com/JanDuchscherer104/ARIA-NBV/actions/workflows/ci.yml"><img alt="Root verification status" src="https://github.com/JanDuchscherer104/ARIA-NBV/actions/workflows/ci.yml/badge.svg"></a>
  <a href="https://janduchscherer104.github.io/ARIA-NBV/"><img alt="Published documentation" src="https://github.com/JanDuchscherer104/ARIA-NBV/actions/workflows/quarto-publish.yml/badge.svg"></a>
  <a href="LICENSE"><img alt="Apache 2.0 license" src="https://img.shields.io/badge/license-Apache--2.0-blue.svg"></a>
</p>

<p align="center">
  <a href="https://janduchscherer104.github.io/ARIA-NBV/"><strong>Explore the research →</strong></a>
</p>

## Why ARIA-NBV?

Point an egocentric camera into a complex room, choose a target—a chair, a
sofa, a shelf—and ask: **which valid next viewpoint will improve its 3D
reconstruction most?** ARIA-NBV turns that choice into an auditable finite
decision problem.

Many next-best-view systems optimize geometric coverage as a proxy for
reconstruction quality. ARIA-NBV instead studies target-specific Relative
Reconstruction Improvement (RRI) over Aria Synthetic Environments (ASE) and
EFM3D/EVL scene evidence:

> Given the same candidate support, validity rules, and acquisition budget,
> can a multi-step policy produce better endpoint reconstruction of a selected
> target than the best myopic choice?

The [research questions](docs/typst/thesis/sections/01-research-questions.typ)
and [development roadmap](docs/typst/thesis/development/roadmap.typ) own the
current thesis scope and evidence gates.

## One Decision, End to End

**Observe → Propose → Measure → Roll out → Inspect → Learn**

1. **Observe.** Load ASE/ATEK snippets and EFM3D/EVL evidence while keeping
   actor-visible observations separate from privileged supervision.
2. **Propose.** Build a finite, target-aware candidate table with explicit
   provenance, hard feasibility masks, and invalid-reason codes.
3. **Measure.** Render candidate depths and compute scene- or target-specific
   RRI against ground-truth mesh evidence.
4. **Roll out.** Select valid actions and persist selected-transition and
   selected-depth evidence in lineage-preserving `rollouts.zarr` stores without
   mutating immutable VIN roots.
5. **Inspect.** Audit offline samples and stored rollouts in Streamlit or Rerun,
   including saved `.rrd` recordings.
6. **Learn.** Train the one-step VIN control and use scorer-independent replay
   contracts for finite-horizon `Q_H` experiments.

> [!IMPORTANT]
> **Research status:** the oracle, data, rollout, inspection, and
> scorer-independent finite-horizon training substrate are implemented. An
> actor-visible target matcher, a target-conditioned one-step control, positive
> oracle-lookahead headroom, and a production learned `Q_H` policy/evaluation
> remain active gates. Online or continuous control and real-device deployment
> are later work, not current results.

## First Useful Run

ARIA-NBV is a Linux/Python 3.11 research stack. Full oracle generation,
counterfactual rendering, and training require recursive submodules, ASE access,
external checkpoints, and a compatible CUDA 12.1/PyTorch3D environment. Follow
the [portable setup and one-scene smoke path](SETUP.md) first.

Then launch the interactive inspection and bounded generation surface:

```sh
cd aria_nbv
uv run nbv-st
```

The app provides one place to see the system's data, candidate, oracle, rollout,
and diagnostic surfaces together. Data generation and training are separate,
data-dependent workflows documented by their owners below.

## Explore by Intent

- **Understand the thesis.** Start with the
  [published documentation](https://janduchscherer104.github.io/ARIA-NBV/),
  [active thesis](docs/typst/thesis/main.typ), and
  [research questions](docs/typst/thesis/sections/01-research-questions.typ).
- **Install and run locally.** Use the [portable setup guide](SETUP.md), then
  open the [Streamlit application guide](aria_nbv/aria_nbv/app/README.md).
- **Generate evidence.** Follow the
  [data-generation runbook](aria_nbv/aria_nbv/data_handling/README.md) and the
  [rollout storage contract](aria_nbv/aria_nbv/rollouts/README.md).
- **Inspect an experiment.** Use the
  [Rerun inspector](aria_nbv/aria_nbv/rerun_inspector/README.md) for offline
  samples, stored rollouts, and `.rrd` evidence.
- **Train or extend a scorer.** Read the [package overview](aria_nbv/README.md),
  [Lightning contracts](aria_nbv/aria_nbv/lightning/README.md),
  [VIN contracts](aria_nbv/aria_nbv/vin/README.md), and
  [generated API reference](docs/reference/index.qmd).
- **Trace the scientific vocabulary.** Use the canonical
  [symbols](docs/typst/shared/symbols.typ),
  [equations](docs/typst/shared/equations.typ),
  [glossary](docs/typst/shared/glossary.typ), and
  [literature reviews](docs/contents/literature/index.qmd).
- **Report a problem or propose an improvement.** Open a
  [GitHub issue](https://github.com/JanDuchscherer104/ARIA-NBV/issues).

## Repository at a Glance

| Path | Purpose |
| --- | --- |
| `aria_nbv/aria_nbv/` | Python package: data, geometry, oracle, rollouts, models, training, and inspection. |
| `aria_nbv/tests/` | Executable contract, integration, and regression tests. |
| `.configs/` | Tracked configurations for data generation, inspection, and training. |
| `docs/typst/thesis/` | Active thesis, scientific framing, research questions, and evidence gates. |
| `docs/contents/` | Public documentation, background, literature reviews, and navigation. |
| `external/` | Pinned or forked upstream dependencies, including EFM3D, ATEK, and PointNeXt. |

Exact Python source, tests, and active configuration own executable behavior.
The active Typst thesis owns current scientific claims; rendered documentation
and historical material provide navigation and evidence.

## License

ARIA-NBV is licensed under the [Apache License 2.0](LICENSE). Dataset, model,
and upstream dependency terms remain governed by their respective providers.
