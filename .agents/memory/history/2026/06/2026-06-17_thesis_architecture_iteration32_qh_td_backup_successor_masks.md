---
id: 2026-06-17_thesis_architecture_iteration32_qh_td_backup_successor_masks
date: 2026-06-17
title: "Thesis Architecture Iteration 32 Q_H TD Backup And Successor Masks"
status: done
topics: [thesis, architecture, q-h, double-dqn, rollouts-zarr, invalidity]
confidence: high
canonical_updates_needed:
  - docs/contents/theory/rl_planning.qmd
  - docs/typst/thesis/sections/04-method/index.typ
  - docs/typst/thesis/sections/05-experimental-design/index.typ
  - aria_nbv/aria_nbv/rollouts/zarr_store.py
  - aria_nbv/tests/rollouts/test_zarr_store.py
files_touched:
  - .omx/specs/autoresearch-thesis-lit-review/report.md
  - .omx/specs/autoresearch-thesis-lit-review/result.json
---

## Summary

Iteration 32 refined the planned `Q_H` training contract around TD backups,
successor masks, and all-invalid successors. The current store correctly owns
selected-transition replay facts, masks, root-gain rewards, next-step ids, and
terminal/discount fields. A future trainer should own DQN/Double-DQN scalar
targets and checkpoint predictions. The thesis should not treat those
trainer-derived targets as immutable replay truth.

## Evidence

- Canonical memory makes finite-candidate `Q_H` mandatory, says it predicts
  bounded cumulative root-normalized target gain, and makes fitted Double-Q the
  first value-learning target family.
- `docs/contents/theory/rl_planning.qmd` defines masked DQN and Double-DQN
  backups over successor candidates and says invalid candidates are masked
  before argmax, softmax, loss target, or selected action.
- `aria_nbv/aria_nbv/rollouts/zarr_store.py` writes `q_h/` fields for
  `valid_action_mask`, `q_train_mask`, selected candidate ids, `td_reward`,
  `td_next_step_row_id`, `td_terminal_mask`, and `td_discount` without computing
  network-dependent bootstrap targets.
- `aria_nbv/tests/rollouts/test_zarr_store.py` checks `q_train_mask <=
  valid_action_mask`, terminal discount behavior, root-gain reward ownership,
  and invalid-candidate NaN firewalls.
- The local Double-DQN and IQL sources motivate decoupled selector/evaluator
  backups and support-aware offline TD objectives; ARIA-NBV should instantiate
  those ideas through explicit successor masks and support diagnostics.

## Canonical Updates Needed

- Update thesis method text to state that `rollouts.zarr` stores immutable
  selected-transition facts while DQN/Double-DQN targets are trainer-derived
  views tied to a config/checkpoint.
- Add or document fields for successor actor-valid count, successor trainable
  count, `bootstrap_mask_kind`, blocked successor reason, terminal-versus-blocked
  status, horizon remaining, and selected-action lineage.
- Add tests for all-invalid successor masks, empty successor `q_train_mask`,
  terminal horizon versus blocked successor status, padded invalid-row leakage,
  and continued `target_root_gain` reward ownership.
- Keep exact gamma/clipping in open decisions until evaluation gates choose the
  default; store per-run discount metadata so experiments remain auditable.
