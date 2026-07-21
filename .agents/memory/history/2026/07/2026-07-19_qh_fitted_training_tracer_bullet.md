---
id: 2026-07-19_qh_fitted_training_tracer_bullet
date: 2026-07-19
title: "Q_H Fitted Training Tracer Bullet"
status: done
topics: [qh, lightning, fitted-q, lrz, torchrun]
confidence: high
canonical_updates_needed:
  - .agents/memory/state/PROJECT_STATE.md
files_touched:
  - aria_nbv/aria_nbv/vin/models/target_finite_horizon.py
  - aria_nbv/aria_nbv/lightning/qh_module.py
  - aria_nbv/aria_nbv/lightning/qh_experiment.py
  - aria_nbv/aria_nbv/lightning/qh_cli.py
  - scripts/templates/lrz/qh_training_one_node.sbatch
---

## Task

Complete the V0 target-conditioned multi-step training seam without widening
the existing one-step `VinLightningModule`, adding DTOs, changing persisted
schemas, or claiming scientific Q_H performance.

## Result

The existing transition-level `QhDataset` and sampler-owning `QhDataModule`
remain the data boundary. Training is sharded with explicit padding accounting;
validation/test are replicated exactly so every DDP rank executes the same
number of evaluation steps. Redundant bootstrap tensors were removed from the
DTOs because successor presence, terminal state, and the next action mask
already determine eligibility. `MultiStepCandidateScorer` now performs
independent candidate-to-state queries over actor evidence, target geometry,
selected history, and remaining budget. A separate `QhLightningModule`
implements fail-closed selected-row admission, masked Double-Q targets, Huber
loss, a frozen eval target network, optimizer-update hard sync, and checkpointed
sync state. `QhExperimentConfig` and `nbv-train-qh` own strict TOML composition
and full-state resume. The LRZ template uses one Pyxis `srun` task containing
one standalone TorchRun launcher on one node.

No new DTO, dependency, rollout/VIN schema, V1 path, online-RL path, or
`lightning/lit_module.py` behavior was added.

## Verification

- Existing plus new focused suite: 115 passed, including the prior 63 data-seam
  tests, real CPU fast-dev training, uninterrupted-versus-resumed parity, and a
  two-process CPU/Gloo TorchRun run.
- Scorer/loss tests cover permutation, invalid-candidate isolation, exact
  Double-Q arithmetic, all-invalid successor handling, target freezing/sync,
  and distributed zero-local-admission reduction.
- LRZ contract tests run `bash -n` and reject invalid GPU counts, multi-node or
  per-GPU Slurm tasks, duplicate launchers, and bypass of the prepared frozen
  `uv` environment.
- Changed Python surfaces are Ruff-formatted and Ruff-clean.
- Independent code and architecture re-review returned `CLEAR` after the LRZ
  environment repair; UltraQA completed one adversarial cycle.

## Canonical state impact

`PROJECT_STATE.md` now distinguishes the runnable isolated training tracer
bullet from the still-open M5 scaled scientific result.
