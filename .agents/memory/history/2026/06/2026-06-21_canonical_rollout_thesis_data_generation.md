---
id: 2026-06-21_canonical_rollout_thesis_data_generation
date: 2026-06-21
title: "Canonical Rollout Thesis Data Generation"
status: done
topics: [rollouts, thesis, data-generation, target-selection]
confidence: high
canonical_updates_needed: []
files_touched:
  - .configs/build_rollouts_v1_realistic.toml
  - docs/typst/thesis/sections/03-02-data-generation.typ
  - docs/typst/thesis/main.pdf
---

## Task

Align the checked-in realistic rollout profile with the canonical thesis data-generation contract and make the thesis data-generation section scientifically explicit about target-task sampling, finite candidate generation, validity pruning, rollout branch sampling, and downstream diagnostics.

## Outputs

- `.configs/build_rollouts_v1_realistic.toml` now encodes the audit-scale canonical real profile: train split, 25 source samples, one oracle target task per sample, strict label validity, cache-relative stores, 60 candidates from the three-family mixture, and motion realism caps.
- `docs/typst/thesis/sections/03-02-data-generation.typ` now describes the three-family candidate sampler mathematically, including Power Spherical direction sampling, family-specific target/forward/bypass directions, target-looking orientation, hard validity masks, and branch sampling recipes.
- The thesis text explicitly separates implemented evidence from scale claims and lists the diagnostics needed before attributing success or failure to planning.

## Verification

- `git diff --check`
- `cd aria_nbv && uv run nbv-build-rollouts --config-path ../.configs/build_rollouts_v1_realistic.toml --dry-run`
- `cd docs && typst compile typst/thesis/main.typ --root .`
- Rendered thesis pages 18-22 via `.agents/skills/typst-authoring/scripts/render_png.sh` and visually checked the edited section.
- `make check-agent-memory`
- `make agents-db AGENTS_ARGS='validate'`
- `make scaffold-audit` passed with zero errors; existing skill warnings remain.
