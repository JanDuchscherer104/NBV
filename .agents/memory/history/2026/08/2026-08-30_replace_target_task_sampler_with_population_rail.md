---
id: 2026-08-30_replace_target_task_sampler_with_population_rail
date: 2026-08-30
title: "Replace target-task sampler with population rail"
status: done
topics: [thesis, figures, target-selection, typst]
confidence: high
canonical_updates_needed: []
touched_owner_paths:
  - docs/typst/thesis/figures/target_task_sampler_contract.typ
  - docs/typst/thesis/sections/03-oracle-and-data-generation/03-02-target-task-and-rri-labels.typ
codex_thread: codex://threads/01a04fd9-0c7c-7813-a9c5-dc49f2f867a6
repo_object_format: sha1
repo_head: a2ee169aa1e10de40950e470535d95182ed9d314
repo_branch: "codex/thesis-figure-target-task-sampler-contract"
worktree_kind: linked
---

## Task
Replace the dense oracle target-task sampler inventory with a clean,
implementation-exact population-flow figure and complementary prose.

## Method
Mapped the exact padding, row-construction, geometry-admission, seeded-cap, and
rollout-writer boundaries from the target-selection owners. Preserved color and
grayscale baselines, iterated a CeTZ population rail under professor and student
critiques, compiled the standalone figure and full thesis, and independently
reviewed the exact rendered page before publication.

## Findings
The sampler first selects the latest GT OBB slice containing a non-padding row;
an all-padding block yields no task rows. For each source row it first computes
status from full serialized-payload finiteness and finite positive extents, then
constructs the descriptor. Descriptor validation raises on any non-finite
object or relative pose or extent and on non-positive extents before the row is
appended. A descriptor-constructible OBB with a non-finite auxiliary tensor
field is instead retained as `INVALID_GEOMETRY` and excluded from the sampling
pool. The retained invalid count therefore does not measure all invalid inputs.
A successful result emits `selected_rows`; it does not persist final store rows.
The replacement in
`docs/typst/thesis/figures/target_task_sampler_contract.typ` therefore
separates slice selection and padding removal, source rows, full-payload status,
descriptor construction, retained invalid rows, seeded capped sampling of
`matched` rows, and emitted provenance. The adjacent owner in
`03-02-target-task-and-rri-labels.typ` states both failure boundaries and that
no confidence threshold, IoU, visibility, support, headroom, or utility rule
ranks otherwise finite GT rows.

## Commits
- [1497d3b2cb114626432ae23affc959a9b51500f5](https://github.com/JanDuchscherer104/ARIA-NBV/commit/1497d3b2cb114626432ae23affc959a9b51500f5)
- [ce3eeab0395a3937d5086840b4184257a1303ff4](https://github.com/JanDuchscherer104/ARIA-NBV/commit/ce3eeab0395a3937d5086840b4184257a1303ff4)
- [08aff600d580519719c25198824243f35f3f82a8](https://github.com/JanDuchscherer104/ARIA-NBV/commit/08aff600d580519719c25198824243f35f3f82a8)
- [d0b87bcaad99036f2b2cea4bd6b404da48983690](https://github.com/JanDuchscherer104/ARIA-NBV/commit/d0b87bcaad99036f2b2cea4bd6b404da48983690)

## Verification
- PASS: 28 tests in `aria_nbv/tests/oracle/test_target_selection.py` and
  `aria_nbv/tests/targets/test_descriptor.py`.
- PASS: `make thesis-pdf`, `make thesis-pdf-ci`,
  `make typst-authoring-contract`, and `make thesis-marker-contract`.
- PASS: exact A4 page 56 color and grayscale inspection; no collisions,
  clipping, or hue-only distinctions.
- PASS: exact scientific and visual rereviews; zero valid P0--P2 findings.
- PASS: `git diff --check`.

## Canonical Owner Impact
- Replaced the canonical target-task sampler figure and tightened its immediate
  explanatory prose, caption, and alternative text.
- No Python behavior, configuration, notation registry, or evidence claim was
  changed.
