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
an all-padding block yields no task rows. It then emits `selected_rows`; it does
not persist final store rows. The replacement in
`docs/typst/thesis/figures/target_task_sampler_contract.typ` therefore
separates slice selection, complete non-padding audit rows, the local
geometry-eligible target-row set $cal(R)_s^"geom"$, seeded capped sampling, and
emitted provenance. Invalid geometry remains visible but cannot enter the
eligible set. The adjacent owner in `03-02-target-task-and-rri-labels.typ` now
states that confidence, IoU, visibility, support, headroom, and utility do not
gate this privileged GT-only sampling step.

## Commits
- [1497d3b2cb114626432ae23affc959a9b51500f5](https://github.com/JanDuchscherer104/ARIA-NBV/commit/1497d3b2cb114626432ae23affc959a9b51500f5)
- [ce3eeab0395a3937d5086840b4184257a1303ff4](https://github.com/JanDuchscherer104/ARIA-NBV/commit/ce3eeab0395a3937d5086840b4184257a1303ff4)

## Verification
- PASS: 24 tests in `aria_nbv/tests/oracle/test_target_selection.py`.
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
