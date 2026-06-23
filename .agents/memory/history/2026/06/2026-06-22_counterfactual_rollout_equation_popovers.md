---
id: 2026-06-22_counterfactual_rollout_equation_popovers
date: 2026-06-22
title: "Counterfactual Rollout Equation Popovers"
status: done
topics: [streamlit, rollouts, rri, ui]
confidence: high
canonical_updates_needed: []
files_touched:
  - aria_nbv/aria_nbv/app/panels/counterfactual_rollouts.py
  - aria_nbv/tests/app/panels/test_counterfactual_rollouts_panel.py
---

## Task

Implemented equation-aware Streamlit info popovers for the live counterfactual
rollout metric dashboard on 2026-06-22. The change covers endpoint target gain,
root-normalized selected return, state-relative diagnostic RRI fallback,
candidate empirical bands, top-k valid-candidate headroom, and endpoint log
gain.

## Method

The implementation keeps metric truth in the existing thesis/theory docs and
rollout metric helpers, then adds compact Markdown/KaTeX explanations to the
panel. The UI label for branch-level return was clarified from ambiguous
`G_t^(H)` to `G_0^(H)` where the panel summarizes whole selected branches, and
the fanout plot title was changed from a generic 95% band to an empirical
central 95% range.

## Verification

- `cd aria_nbv && uv run ruff format aria_nbv/app/panels/counterfactual_rollouts.py tests/app/panels/test_counterfactual_rollouts_panel.py`
- `cd aria_nbv && uv run ruff check aria_nbv/app/panels/counterfactual_rollouts.py tests/app/panels/test_counterfactual_rollouts_panel.py`
- `cd aria_nbv && uv run pytest tests/app/panels/test_counterfactual_rollouts_panel.py -q`
- `git diff --check -- aria_nbv/aria_nbv/app/panels/counterfactual_rollouts.py aria_nbv/tests/app/panels/test_counterfactual_rollouts_panel.py .omx/context/counterfactual-rollout-equation-popovers-20260622T184552Z.md .omx/state/ralph-progress.json`
- Native architect verification passed before and after the deslop pass.

## Canonical State Impact

No canonical thesis, theory, or project-state update was needed. The app now
points to existing canonical metric semantics instead of creating a new source
of truth.
