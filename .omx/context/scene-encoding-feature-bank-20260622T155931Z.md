# Ralph Context Snapshot: Scene Encoding Feature Bank

Created: 2026-06-22T15:59:31Z
Plan: `.omx/plans/scene-encoding-docs-thesis-feature-bank-20260622T152059Z.md`
Mode: `$ralph` direct implementation in Codex App.

## Objective

Implement the approved scene-encoding consolidation plan across internal docs,
Typst thesis/equation surfaces, and a first read-only VIN feature-bank
prototype.

## Loaded Guidance

- Root `AGENTS.md` pasted in-thread.
- `oh-my-codex:ralph`
- `mempalace-aria-nbv:agent-behavior`
- `mempalace-aria-nbv:docs-curator`
- `mempalace-aria-nbv:nbv-geometry-contracts`
- `mempalace-aria-nbv:typst-authoring`
- `docs/AGENTS.md`
- `aria_nbv/AGENTS.md`
- `aria_nbv/aria_nbv/vin/AGENTS.md`
- `aria_nbv/aria_nbv/data_handling/AGENTS.md`
- `.agents/references/source_order.md`
- `.agents/references/verification_matrix.md`
- `.agents/references/python_conventions.md`
- `.agents/references/external_stack_contracts.md`
- `.agents/memory/state/GOTCHAS.md`
- `.agents/skills/typst-authoring/references/aria-nbv-notation.md`
- `.agents/skills/typst-authoring/references/thesis-section-contracts.md`

## Current Evidence

- `docs/typst/shared/equations/features.typ` already owns feature and
  candidate-query equations, including `qh_scene_memory`, `point_dino_token`,
  and query pools.
- EFM3D projection evidence is in
  `external/efm3d/efm3d/model/lifter.py` and
  `external/efm3d/efm3d/utils/image_sampling.py`.
- VIN EVL output evidence is in `aria_nbv/aria_nbv/vin/types.py` and
  `aria_nbv/aria_nbv/vin/backbone_evl.py`.
- Semidense collapse metadata evidence is in
  `aria_nbv/aria_nbv/data_handling/efm_views.py`.

## Initial Worktree Notes

The target files had no pre-existing diffs at snapshot time. The worktree had
unrelated dirty OMX/log/README and external submodule state; these are not part
of this implementation and must not be reverted.

## Planned Patch Scope

- `docs/contents/theory/efm3d_scene_embeddings.qmd`
- `docs/contents/literature/efm3d.qmd` only if a short pointer is needed.
- `docs/contents/thesis/roadmap.qmd`
- `docs/contents/thesis/questions.qmd`
- `docs/typst/shared/equations/features.typ`
- `docs/typst/thesis/sections/03-method.typ`
- `aria_nbv/aria_nbv/vin/scene_feature_bank.py`
- focused tests under `aria_nbv/tests/vin/`

## Verification Targets

- `ruff format` and `ruff check` on changed Python files.
- Focused `uv run pytest` for feature-bank tests.
- Focused Quarto/Typst checks where feasible.
- KG claim check for advisor-facing scene-encoding claim.
- Ralph architect verification and follow-up de-slop pass on changed files.
