---
id: 2026-07-30_pr27_qh_infrastructure_remediation
date: 2026-07-30
title: "PR 27 Q_H Infrastructure Remediation"
status: done
topics: [qh, rollouts, lightning, data-handling, code-review]
confidence: high
canonical_updates_needed: []
files_touched:
  - aria_nbv/aria_nbv/data_handling/qh.py
  - aria_nbv/aria_nbv/lightning/qh_datamodule.py
  - aria_nbv/aria_nbv/lightning/qh_module.py
  - aria_nbv/aria_nbv/rollouts/qh_reader.py
  - .agents/memory/state/PROJECT_STATE.md
  - .agents/todos.toml
---

## Task

Bring PR #27 back to its smallest truthful boundary after successive data-seam,
training-tracer, review, and complexity-reduction passes. Preserve the useful
replay-chain and scorer-independent training infrastructure without presenting
deleted experimental surfaces as runnable thesis evidence.

## Result

PR #27 owns bounded replay-chain reading and validation, `QhBatch` plus its
dataset and sampler-owning data module, a scorer-independent fitted Double-Q
Lightning adapter, infrastructure diagnostics, and distributed smoke coverage.
The fitted-Q contract distinguishes terminal or no-successor boundaries from
nonterminal actor-valid rows that lack a label-supported backup; the latter are
excluded and reported rather than silently trained as one-step targets.

The PR does not own a production `Q_H` scorer, training CLI, checkpoint/resume
lifecycle, or LRZ launcher. The non-runnable finite-horizon VIN scaffold and
its configuration branches were removed rather than retained as a placeholder.
An explicit requested-horizon query remains a design proposal for the next
scorer PR, not canonical thesis truth. Existing roadmap, theory, and glossary
sources continue to own the fixed finite-horizon direction until a reviewed
source-owner decision changes them.

The six intermediate Q_H PR debriefs were consolidated into this record. Git
history retains their episodic provenance; this debrief is the single current
summary of the PR boundary.

## Verification

The final PR closeout runs focused Q_H reader, data-module, Lightning,
distributed-smoke, scorer-contract, and public-API regressions; Ruff; `make
qh-ci`; API generation; agents-DB validation/rendering; agent-memory checks;
Graphify refresh/freshness; and hosted CI at the exact pushed head. This record
does not promote scientific performance evidence: no scaled training result or
policy comparison exists.

## Canonical state impact

`PROJECT_STATE.md` now records the infrastructure-only implementation boundary.
Existing TODO owners capture the scorer-interface decision, per-horizon support
and estimand reporting, and deferred dynamic-state work. No new backlog record
or thesis claim was introduced.
