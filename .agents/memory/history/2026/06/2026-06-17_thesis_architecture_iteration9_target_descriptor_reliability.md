---
id: 2026-06-17_thesis_architecture_iteration9_target_descriptor_reliability
date: 2026-06-17
title: "Thesis Architecture Iteration 9 Target Descriptor Reliability"
status: done
topics: [thesis, literature, target-selection, descriptors, q-h]
confidence: high
canonical_updates_needed:
  - docs/typst/thesis/sections/03-method.typ
  - docs/typst/thesis/sections/04-evaluation.typ
  - docs/contents/theory/candidate_sampling_target_selection.qmd
  - docs/contents/theory/efm3d_scene_embeddings.qmd
files_touched:
  - .omx/specs/autoresearch-thesis-lit-review/report.md
  - .omx/specs/autoresearch-thesis-lit-review/result.json
---

## Task

Continue the architecture autoresearch by critiquing the target descriptor and
matching protocol that conditions one-step scoring and finite-candidate `Q_H`.

## Findings

OBS-SEL, PRED-Q, and GT-EVAL should be treated as three separate data products:
actor-visible selection fields, actor-visible model-conditioning fields, and
oracle-only target labels/evaluation fields. This prevents target-match
metadata from leaking into model-facing tensors or being used to explain model
performance after the fact.

The current implementation audit found low direct GT-leakage risk in V1 target
selection, but three methodology risks remain before scale: selected
zero-projection targets, saturated-support targets with zero product score, and
wording drift over whether support/projection are part of GT association or
eligibility/audit only.

EFM3D, Project Aria, Instance-NBV, and SceneScript support using target-centric
and object-centric descriptors, but they also warn against treating OBBs,
semantic masks, confidence, or structured scene commands as reliable target
truth without explicit calibration and actor-visible provenance checks.

## Canonical State Impact

The autoresearch report now adds a descriptor ladder from compact scalar
geometry/support fields through pooled local evidence and future structured
scene memory. It also requires target-selector coverage reports and `Q_H`
evaluation stratified by target source, support, projected visibility,
ambiguity, and class.

Follow-up thesis edits should add an OBS-SEL/PRED-Q/GT-EVAL data-product table,
the descriptor ladder, and the target-selector coverage report to the method
and evaluation chapters. The public docs should resolve whether
support/projection are eligibility/audit fields or part of a named compact GT
match score.

## Verification

- Local scans covered `docs/contents/theory/candidate_sampling_target_selection.qmd`,
  `.agents/work/target-selection-methodology/current-target-selection-audit-2026-06-17.md`,
  `.agents/memory/state/DECISIONS.md`, `.agents/memory/state/OPEN_QUESTIONS.md`,
  proposal-review work notes, and local EFM3D, Project Aria, Instance-NBV, and
  SceneScript TeX sources.
- `make kg-route` returned current thesis questions, thesis seed, active target
  backlog, canonical decisions, implementation, and test surfaces as the owner
  stack for target descriptor reliability.
- Follow-up validation should rerun artifact grep, JSON parse, whitespace check,
  and `make check-agent-memory`.
