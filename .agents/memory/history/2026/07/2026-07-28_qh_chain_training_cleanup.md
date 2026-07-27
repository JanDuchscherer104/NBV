---
id: 2026-07-28_qh_chain_training_cleanup
date: 2026-07-28
title: "QH Chain Training Cleanup"
status: done
topics: [QH, dataset, lightning, distributed-training, docstrings]
confidence: high
canonical_updates_needed: []
files_touched:
  - aria_nbv/aria_nbv/data_handling/qh.py
  - aria_nbv/aria_nbv/lightning/qh_datamodule.py
  - aria_nbv/aria_nbv/lightning/qh_experiment.py
  - aria_nbv/aria_nbv/lightning/qh_module.py
  - aria_nbv/aria_nbv/rollouts/qh_reader.py
  - aria_nbv/aria_nbv/data_handling/offline/store.py
---

## Task

Remove remaining QH training-seam leakage and stale documentation without
widening the five-DTO data plane or replacing Lightning's standard samplers.

## Outcome

The scorer now derives temporal history only from right-shifted actor inputs;
selected indices, row ids, and Oracle labels remain supervision-only. Validation
and test loss metrics all-reduce exact loss sums and admitted-row counts over
Lightning sampler emissions, including documented padding duplicates. Both
repository training TOMLs use the current dataset-config shape. Contract
docstrings now cover V0 Oracle-GT ablation inputs, the V1 boundary, shapes,
frames, masks, residual budget, DDP semantics, and runtime ownership.

## Verification

Focused QH data, reader, experiment, module, and four two-rank CPU/Gloo scenarios
passed. Ruff format/check, the docstring audit, Quartodoc generation, frozen
instrument comparison, and `git diff --check` passed. The mechanical final
surface is 1,834 physical LOC versus the 2,480-line H baseline.

## Canonical State Impact

None. This pass repairs implementation and documentation of the already
approved chain-native QH contract.
