---
id: 2026-08-20_qh_readiness_inspection_cleanup
date: 2026-08-20
title: "Q_H Readiness And Inspection Cleanup"
status: done
topics: [q-h, rollout-inspection, streamlit, datamodule]
confidence: high
canonical_updates_needed: []
files_touched:
  - aria_nbv/aria_nbv/rollouts/qh_reader.py
  - aria_nbv/aria_nbv/dataset_bundle.py
  - aria_nbv/aria_nbv/rollouts/reporting.py
  - aria_nbv/aria_nbv/app/panels/training_dataset.py
  - aria_nbv/aria_nbv/app/panels/_stored_rollouts_page.py
---

## Task

Repair factual Q_H chain boundaries, prove the production dataset/DataModule and
collation seam, add safe explicit multi-store summaries, and reduce the two
Streamlit pages to essential progressive-disclosure workflows.

## Method And Findings

Q_H chains now follow factual contiguous rollout step runs rather than configured
horizons. The dataset-bundle owner constructs stage datasets and the actual
`QhDataModule`, while bounded preview reads one chain and one collated batch.
Reporting aggregates only validated additive evidence and preserves store,
profile, policy, horizon, generation-cohort, and failure identities. Streamlit
keeps construction, deep counts, corpus aggregation, topology, candidate-heavy
projections, and Rerun behind explicit actions.

No Zarr schema, dependency, service, model/training, campaign-generation, or
public `QhDataModule` constructor changed. The duplicate CORAL catalog was
removed from Training Dataset; `RRI Binning` remains its canonical page.

## Verification

Focused reader, dataset/DataModule, reporting, and UI suites passed in the shared
ARIA environment. Ruff format/check, module compilation, and diff checks passed.
Graphify was unavailable because the installed package and skill revisions were
incompatible and the graph revision was not an ancestor, so exact source and
tests were used as authority.
