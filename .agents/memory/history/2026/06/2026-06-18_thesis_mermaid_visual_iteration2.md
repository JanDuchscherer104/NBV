---
id: 2026-06-18_thesis_mermaid_visual_iteration2
date: 2026-06-18
title: "Thesis Mermaid Visual Iteration 2"
status: done
topics: [thesis, mermaid, typst, figures, target-selection]
confidence: high
canonical_updates_needed: []
files_touched:
  - docs/typst/thesis/figures/oracle_target_task_sampler_contract.mmd
  - docs/typst/thesis/figures/oracle_target_task_sampler_contract.svg
  - docs/typst/thesis/figures/oracle_target_task_sampler_contract.pdf
---

## Task

Refine the target-selection diagram after page-level QA showed the first iteration was correct but too visually compressed.

## Method

Tried a two-lane and a two-row Mermaid layout to express oracle-owned target-task sampling, actor-visible hypothesis selection, and GT-EVAL rollout labels. Rejected those layouts because ELK rendered them too tall for the thesis page. Kept the compact horizontal Mermaid contract, but reduced the node count so the figure emphasizes the actual conceptual boundary: oracle source, identity/labelability gate, sampled target-task rows, and rollout/GT-EVAL labels, with the actor-visible selector as a dashed non-label-truth sidecar.

## Outputs

- Updated `oracle_target_task_sampler_contract.mmd` so automatic target selection is explicitly oracle/data-generation-owned.
- Preserved actor-visible OBS-SEL/PRED-Q as a diagnostic or later-deployable sidecar that must pass GT-EVAL before it can supply thesis labels.
- Regenerated the SVG export and Typst-safe PDF inclusion artifact.

## Verification

Ran `python3 tools/mermaid/scripts/aria_mermaid_lint.py docs/typst/thesis/figures/oracle_target_task_sampler_contract.mmd`; it passed with zero errors and warnings. Rendered SVG and PDF through Chrome-backed Mermaid CLI. Recompiled `docs/typst/thesis/main.typ` to `/tmp/thesis-mermaid-iteration2-simplified.pdf`, rendered page 29 with `pdftoppm`, and visually confirmed Figure 3 stays on the target-selection page without overflow.

## Canonical State Impact

No canonical thesis-direction update is needed. This iteration corrects figure-level communication of an already accepted source-of-truth decision: target-task selection for labels belongs to the oracle/data-generation pipeline, not to a deployable actor-visible selector.
