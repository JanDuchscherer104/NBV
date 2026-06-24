---
id: 2026-06-17_thesis_architecture_iteration5_nbv_objective
date: 2026-06-17
title: "Thesis Architecture Iteration 5 NBV Objective Boundary"
status: done
topics: [thesis, literature, nbv, target-rri, support]
confidence: high
canonical_updates_needed:
  - docs/typst/thesis/sections/04-method/index.typ
  - docs/typst/thesis/sections/05-experimental-design/index.typ
  - docs/contents/theory/candidate_sampling_target_selection.qmd
  - docs/contents/theory/rri_theory.qmd
files_touched:
  - .omx/specs/autoresearch-thesis-lit-review/report.md
  - .omx/specs/autoresearch-thesis-lit-review/result.json
---

## Task

Continue the architecture autoresearch by critiquing ARIA-NBV's objective,
support signals, invalidity semantics, and hierarchy boundary against NBV
literature.

## Findings

Target-conditioned RRI should remain the thesis reward owner. VIN-NBV supports
moving beyond pure scene coverage toward predicted reconstruction-quality
criteria, and Instance-NBV supports object/target-centric view selection, but
neither justifies replacing the ARIA target-RRI protocol with generic scene
coverage or unverified pseudo-semantic masks.

Coverage, uncertainty, and camera-history methods such as SCONE, MACARONS,
FisherRF, and Next Best Sense are best adopted as support diagnostics, candidate
priors, and auxiliary representation channels. They should not become the
scalar `Q_H` target unless a declared ablation studies that tradeoff.

Low immediate target visibility is a soft support signal, not automatic
invalidity. Hard invalidity should be reserved for collision, no depth,
out-of-bounds pose, no oracle render, no valid target match, or protocol-invalid
target matching. Recoverable low-support states may be setup actions in
non-myopic rollouts.

Hestia supports a later target-then-pose hierarchy bridge and warns against
spurious future-reward credit assignment. It should not move continuous
actor-critic control, external simulators, or drone/object-centric coverage
reward into the thesis core before offline finite-candidate `Q_H` evidence is
stable.

## Canonical State Impact

The autoresearch report now records the NBV objective boundary, the
support-vs-invalidity distinction, a table of adoptable support channels, and
the RQ6 hierarchy boundary. Follow-up thesis edits should separate target
endpoint gain, cumulative target-RRI, diagnostic scene coverage,
support/uncertainty metrics, invalid-reason distributions, and candidate-set
headroom.

## Verification

- Local TeX scans covered VIN-NBV, Instance-NBV, PB-NBV, SCONE, MACARONS,
  FisherRF, Next Best Sense, and Hestia.
- Repo scans covered `docs/contents/theory`, `docs/contents/thesis`, and
  `.agents/work` leads for target, candidate, support, invalidity, rollout, and
  `Q_H` terminology.
- Follow-up validation should rerun artifact grep, JSON parse, whitespace check,
  and `make check-agent-memory`.
