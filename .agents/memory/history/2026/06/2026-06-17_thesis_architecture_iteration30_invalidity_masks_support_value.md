---
id: 2026-06-17_thesis_architecture_iteration30_invalidity_masks_support_value
date: 2026-06-17
title: "Thesis Architecture Iteration 30 Invalidity Masks And Support-Gated Value"
status: done
topics: [thesis, architecture, invalidity, masks, offline-rl, q-h, support]
confidence: high
canonical_updates_needed:
  - docs/typst/thesis/sections/03-method.typ
  - docs/typst/thesis/sections/04-evaluation.typ
  - docs/contents/theory/rl_planning.qmd
  - docs/contents/theory/candidate_sampling_target_selection.qmd
  - docs/contents/theory/candidate_view_dependence.qmd
  - aria_nbv/tests/rollouts/test_zarr_store.py
files_touched:
  - .omx/specs/autoresearch-thesis-lit-review/report.md
  - .omx/specs/autoresearch-thesis-lit-review/result.json
---

## Summary

Iteration 30 refined the invalidity and offline value-learning contract for the
planned finite-candidate `Q_H` architecture. Invalidity should remain a typed
hard-mask system, not a scalar reward effect: actor feasibility, target
validity, oracle labelability, training eligibility, support strata, behavior
support, and successor bootstrap masks have different owners and different
failure interpretations.

## Evidence

- `docs/contents/theory/rl_planning.qmd` defines the finite-candidate `Q_H`
  contract, root-normalized target-gain reward, symbolic gamma, masked
  Double-DQN backup, and IQL as a later support ablation.
- `docs/contents/theory/candidate_sampling_target_selection.qmd` separates hard
  eligibility from GT matching audit fields and requires invalid candidate rows,
  reason codes, and valid-count reporting.
- `docs/contents/theory/candidate_view_dependence.qmd` states that masks must
  apply to attention, argmax, softmax, loss, and bootstrap paths.
- `aria_nbv/aria_nbv/rollouts/zarr_store.py` already stores action, label,
  `q_train`, invalid-reason, target-support, target-root-gain, and TD fields;
  invalid candidates get false masks and NaN labels.
- `aria_nbv/aria_nbv/rl/counterfactual_env.py` has invalid-action penalty and
  termination controls for online experiments, which should remain RQ5 bridge
  ablations rather than offline replay truth.
- DQN/Double DQN support the first finite-action value baseline; CQL, IQL, and
  BCQ are useful later controls for offline support and extrapolation, not
  substitutes for feasibility masks.

## Canonical Updates Needed

- Add thesis method wording that explicitly distinguishes `actor_action_mask`,
  `oracle_label_mask`, `target_valid_mask`, `q_train_mask`, support strata,
  behavior-support strata, and successor bootstrap masks.
- Add evaluation wording for invalid-row firewall tests, all-invalid successor
  terminal handling, reason-code roundtrips, support-stratified `Q_H` metrics,
  behavior-support splits, Double-Q overestimation diagnostics, and online
  invalid-action penalty ablation boundaries.
- Keep support as a diagnostic stratum first; only hard-mask low-support rows
  when the oracle/evaluation sample is impossible.
