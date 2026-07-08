---
id: 2026-06-17_thesis_architecture_iteration3_referenced_papers
date: 2026-06-17
title: "Thesis Architecture Iteration 3 Referenced Papers"
status: done
topics: [thesis, literature, architecture, referenced-papers, q-h]
confidence: medium
canonical_updates_needed:
  - docs/literature/sources.jsonl
  - docs/typst/thesis/sections/02-foundations/index.typ
  - docs/typst/thesis/sections/04-method/index.typ
files_touched:
  - .omx/specs/autoresearch-thesis-lit-review/report.md
  - .omx/specs/autoresearch-thesis-lit-review/result.json
---

## Task

Continue the architecture autoresearch beyond local archive entries by checking
primary-source referenced papers from QCNet/QCNeXt and Deja View, then distill
bounded transfer ideas for ARIA-NBV.

## Findings

HiVT, Perceiver, and Wayformer support a local/global/fusion vocabulary for
candidate-set value modeling. The most useful addition is a latent support
memory path: semidense support or point-attached feature tokens can be
cross-attended into a small latent set, while the candidate `Q_H` path remains
row-preserving and mask-safe.

Universal Transformer, RAFT, Raptor, and Deja View support recurrence only as a
measured ablation after fixed-depth set models are stable. The thesis should
decode `Q_H` at every iteration and report calibration, action-rank stability,
state-norm drift, logit drift, and runtime.

DUSt3R/VGGT/MASt3R-style models should motivate actor-visible geometry
representation baselines, not replace ASE mesh/oracle counterfactual rollout
supervision or target-RRI labels.

## Canonical State Impact

The autoresearch report now includes referenced-paper design transfers and a
decision point on whether these references should be promoted into
`docs/literature/sources.jsonl`.

## Verification

- Primary-source web search/open-access evidence was used for HiVT, Perceiver,
  Wayformer, Universal Transformer, RAFT, Raptor, DUSt3R, and VGGT.
- Follow-up validation should rerun artifact grep, JSON parse, whitespace check,
  and `make check-agent-memory`.
