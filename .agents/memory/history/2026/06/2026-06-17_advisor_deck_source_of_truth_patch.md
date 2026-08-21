---
id: 2026-06-17_advisor_deck_source_of_truth_patch
date: 2026-06-17
title: "Advisor Deck Source Of Truth Patch"
status: done
topics: [thesis, typst, advisor, source-truth]
confidence: high
canonical_updates_needed:
  - .agents/references/source_order.md
  - docs/contents/thesis/questions.qmd
  - docs/contents/thesis/roadmap.qmd
  - .agents/memory/state/PROJECT_STATE.md
files_touched:
  - docs/typst/thesis/advisor_meeting_2026_05_22.typ
artifacts:
  - .omx/specs/autoresearch-advisor-deck-source-of-truth/report.md
  - /tmp/advisor_meeting_2026_05_22.pdf
assumptions:
  - "This pass patches the May 22 advisor deck itself; source-order and public mirror promotion should follow after advisor acceptance."
---

## Task

Patched `docs/typst/thesis/advisor_meeting_2026_05_22.typ` from the local autoresearch artifact so the deck can act as the compact advisor-facing thesis contract.

## Method

Used the Typst authoring workflow and the autoresearch report to add source governance, state categories, typed `dashy-todo` wrappers, source/citation anchors, a visible TODO flavor legend, WIP/open-decision slides, and a literature adopt/reject backup slide. Replaced stale local equation displays with shared-equation or shared-symbol forms and demoted the operational next-edit list into WIP/prune framing.

## Outputs

- The deck now states its intended advisor-facing source-truth role and explicitly says roadmap/questions/memory should mirror it after acceptance.
- Added category separation for implemented substrate, current thesis core, WIP necessary, optional ablation, open decision, conflict/historical, and prune candidate.
- Added inline todo wrappers for open decisions, WIP, optional ablations, conflicts, and prune candidates.
- Added citations for Project Aria/ASE, VIN-NBV, EFM3D/EVL, Double DQN/IQL, GenNBV, Hestia, and SceneScript.
- Fixed the raw candidate-pose TODO typo and moved it into a typed open-decision marker.
- Replaced raw `cal(A)`-based display drift in the RQ2 value equations with shared-symbol notation.

## Verification

- `cd docs && typst compile typst/thesis/advisor_meeting_2026_05_22.typ --root . /tmp/advisor_meeting_2026_05_22.pdf`
- `pdftoppm -png -r 120 /tmp/advisor_meeting_2026_05_22.pdf /tmp/advisor_meeting_pages/page`
- Visual inspection of the new source-governance, state-matrix, TODO-legend, central-question, implemented-substrate, RQ3 detail, RQ2, WIP, advisor-locks, literature, and references slides.
- `make kg-status`
- `make kg-claim-check KG_CLAIM="ARIA-NBV treats Hestia-style hierarchy, GenNBV-style continuous control, and SceneScript-style semantic memory as design references, not thesis-core claims."`
- `make kg-claim-check KG_CLAIM="ARIA-NBV's thesis core is a target-conditioned finite-candidate Q_H value model trained from ASE oracle rollout traces and evaluated by oracle re-evaluation under equal budgets."`
- `rg -n "#todo\\[|gamma = 0\\.1|vin_offline\\.counterfactuals|online RL.*stretch|highest-level project ground truth|cal\\(A\\)_t|arg max_\\(i in cal\\(A\\)|decsriptor|QCNet like" docs/typst/thesis/advisor_meeting_2026_05_22.typ`
- `git diff --check`

## Canonical State Impact

The deck now has the advisor-facing contract language, but repo routing still needs a later mirror pass after acceptance: `source_order.md`, `questions.qmd`, `roadmap.qmd`, and `PROJECT_STATE.md` should be updated to say the May 22 deck is the highest current advisor source.

