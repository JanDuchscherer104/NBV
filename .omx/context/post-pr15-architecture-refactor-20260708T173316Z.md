# Post-PR15 Architecture Refactor Deep-Interview Context

Timestamp: 2026-07-08T17:33:16Z

## Task Statement

The user says PR15 has been merged and asks how to proceed with a visual,
conceptual, deep `plan-grill` plus `deep-interview` handoff for improving
`aria_nbv` package module hierarchy, separation of concerns, and architecture.

## Desired Outcome

Produce an interview-grounded architecture route that can hand off to:

1. a visual architecture review report using the `improve-codebase-architecture`
   skill vocabulary: module, interface, depth, seam, adapter, leverage, locality;
2. a conceptual `plan-grill` decision plan;
3. a later implementation plan or execution workflow only after the user picks
   the package candidate and non-goals.

## Probable Intent Hypothesis

The user wants to avoid another broad PR15-sized refactor and instead choose the
highest-leverage post-merge deepening package. The active candidates from recent
evidence are Oracle RRI pipeline ownership, `data_handling._target_selection`
decomposition, `rl/` archive/quarantine, rollout read-model cleanup, zarr schema
cleanup, and geometry/CW90 consolidation.

## Known Facts And Evidence

- Source-order owner for thesis direction is
  `.agents/references/source_order.md`, `docs/contents/thesis/roadmap.qmd`,
  `docs/contents/thesis/questions.qmd`, and `.agents/memory/state/`.
- Project state says target-conditioned finite-candidate `Q_H` is the hard
  thesis core, while generic online RL and continuous control remain bridge or
  future work.
- Current checkout is `codex/full-rri-rollout-worktree`, not confirmed updated
  `main`.
- The worktree is dirty with unrelated docs/glossary/API-reference changes and
  `.agents/external/litkg-rs` submodule changes.
- Live package tree contains the PR15 rollout move:
  `aria_nbv/aria_nbv/rollouts/counterfactuals.py` and
  `aria_nbv/aria_nbv/rollouts/target_counterfactuals.py` exist, while
  `pose_generation` is candidate-table-only in the inspected tree.
- Existing post-PR15 evidence artifact:
  `.omx/specs/autoresearch-aria-nbv-refactor-evidence-20260708/report.md`.
- Existing visual roadmap artifact:
  `.omx/specs/autoresearch-aria-nbv-refactor-evidence-20260708/refactor-architecture-map.html`.
- `CONTEXT.md` and `docs/adr/` were not found at repository root/depth 3 during
  preflight; project domain terms are instead owned by thesis docs and
  `docs/typst/shared/glossary.typ`.
- The `codebase-design` vocabulary exists at
  `/home/jd/.agents/skills/codebase-design/SKILL.md`.

## Constraints

- Do not implement target descriptors, target-conditioned scoring, `Q_H`, scene
  memory, online RL baselines, or broad `data_handling` restructuring during the
  architecture-review/interview phase.
- Deep-interview is active as a requirements mode; it must not implement
  directly.
- Current runtime is outside tmux, so `omx question` is unavailable. Use one
  concise plain-text question per round.
- The first decision should be human-owned: whether the architecture review
  should be comprehensive or start with the next actionable package.

## Unknowns / Open Questions

- Should the next step be a full fresh architecture scan/report over all
  `aria_nbv`, or should it grill the already-evidenced top package first?
- Which base should execution eventually use: updated clean `main`, this dirty
  checkout, or a new worktree from `origin/main`?
- Is `rl/` archival a mandatory first-pass action, or only a candidate in the
  architecture report?
- Should the visual report be written to OS temp per
  `improve-codebase-architecture`, or should the existing `.omx` HTML roadmap
  remain the report surface?

## Decision-Boundary Unknowns

- Whether the agent may create a fresh architecture-review HTML report in the
  OS temp directory before further questioning.
- Whether the first post-PR15 implementation should be Oracle RRI pipeline
  ownership or a broader scan-generated candidate chosen later.
- Whether durable terminology/context changes are allowed. No opt-in has been
  given yet.

## Likely Codebase Touchpoints

- `aria_nbv/aria_nbv/pipelines/oracle_rri_labeler.py`
- `aria_nbv/aria_nbv/rollouts/counterfactuals.py`
- `aria_nbv/aria_nbv/rollouts/target_counterfactuals.py`
- `aria_nbv/aria_nbv/rollouts/dataset_writer.py`
- `aria_nbv/aria_nbv/rri_metrics/oracle_rri.py`
- `aria_nbv/aria_nbv/data_handling/_target_selection.py`
- `aria_nbv/aria_nbv/data_handling/__init__.py`
- `aria_nbv/aria_nbv/rl/counterfactual_env.py`
- `aria_nbv/aria_nbv/app/config.py`
- `aria_nbv/aria_nbv/app/panels/rl.py`
- `aria_nbv/aria_nbv/rollouts/zarr_store.py`
- `aria_nbv/aria_nbv/rollouts/inspection.py`
- `aria_nbv/aria_nbv/rerun_inspector/_rollout_zarr.py`
- `aria_nbv/aria_nbv/app/panels/stored_rollouts.py`
- `aria_nbv/aria_nbv/app/panels/counterfactual_rollouts.py`

## Relevant Repo Docs / Rules Inspected

- Root `AGENTS.md` provided in prompt.
- `.agents/skills/agent-behavior/SKILL.md`
- `.agents/references/source_order.md`
- `docs/contents/thesis/roadmap.qmd`
- `docs/contents/thesis/questions.qmd`
- `.agents/memory/state/PROJECT_STATE.md`
- `.agents/skills/plan-grill/references/plan-mode-theory-patterns.md`
- `/home/jd/.agents/skills/improve-codebase-architecture/SKILL.md`
- `/home/jd/.agents/skills/improve-codebase-architecture/HTML-REPORT.md`
- `/home/jd/.agents/skills/codebase-design/SKILL.md`
- `.omx/specs/autoresearch-aria-nbv-refactor-evidence-20260708/report.md`

## Terminology / Doc-Code Conflicts

- The improve-codebase skill expects `CONTEXT.md`, but this repository did not
  show one in preflight. Use ARIA thesis docs and glossary as the domain source
  unless the user opts into creating `CONTEXT.md`.
- The user says PR15 is merged; local checkout is still a dirty worktree on
  `codex/full-rri-rollout-worktree`. The code tree does include the rollout move
  locally, but execution base still requires a decision.

## Prompt-Safe Initial Context Summary Status

Not needed. The initial context is large, but the relevant material has been
summarized here with source paths.
