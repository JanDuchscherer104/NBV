---
id: 2026-06-17_thesis_architecture_iteration12_online_bridge
date: 2026-06-17
title: "Thesis Architecture Iteration 12 Online Bridge"
status: done
topics: [thesis, literature, q-h, online-rl, simulators]
confidence: high
canonical_updates_needed:
  - docs/typst/thesis/sections/03-method.typ
  - docs/typst/thesis/sections/05-conclusion.typ
  - docs/contents/thesis/questions.qmd
  - docs/contents/thesis/roadmap.qmd
files_touched:
  - .omx/specs/autoresearch-thesis-lit-review/report.md
  - .omx/specs/autoresearch-thesis-lit-review/result.json
---

## Task

Continue the architecture autoresearch by critiquing the online discrete `Q_H`,
continuous control, and external simulator boundary.

## Findings

The source order is consistent: ASE mesh/oracle counterfactual rollouts remain
the thesis-core substrate. Online discrete `Q_H` over the same finite-candidate
contract is the first RQ5 bridge after offline `Q_H`; continuous target-then-
pose actor-critic and external simulator work are RQ6 or future escalation.

GenNBV contributes continuous 5-DoF notation, MDP discipline, action-history
features, and a warning that PPO/SB3-style control requires high-throughput
online rewards. Hestia contributes the better ARIA bridge shape: choose a target
or look-at hypothesis first, then choose a feasible collision-free pose with
directional observability features. Habitat and ProcTHOR mainly inform
environment APIs, sensor/action/task abstractions, scene/episode splits,
procedural diversity, target visibility eligibility, and transfer gates. They
do not provide thesis-core target-RRI evidence.

The new report section defines a bridge ladder: B0 offline `Q_H`, B1 online
discrete `Q_H` in ASE, B2 learned-transition finite candidates, B3
target-then-pose continuous control, and B4 external simulator or
semantic/global planning.

## Canonical State Impact

The autoresearch report now records explicit adoption/rejection rules for
GenNBV, Hestia, Habitat, ProcTHOR/AI2-THOR, and active 3DGS bridge signals. It
also states that the RQ5 online bridge can be a smoke/design result if time is
tight, but must not replace the offline `Q_H` evidence.

Follow-up thesis edits should add the bridge ladder and simulator escalation
gate to the method/discussion. A later advisor decision should choose whether
RQ5 online discrete `Q_H` means design-only, smoke experiment, or quantitative
comparator after offline `Q_H` exists.

## Verification

- Local scans covered `docs/contents/thesis/questions.qmd`,
  `docs/contents/thesis/roadmap.qmd`,
  `.agents/memory/state/DECISIONS.md`, `.agents/memory/state/OPEN_QUESTIONS.md`,
  `docs/contents/literature/gen_nbv.qmd`,
  `docs/contents/literature/hestia.qmd`,
  `docs/contents/literature/active_3dgs_nbv.qmd`, Habitat TeX sources,
  ProcTHOR TeX sources, and GenNBV/Hestia TeX sources.
- `make kg-route` returned roadmap/questions, canonical decisions, open
  questions, active simulator-gate backlog, active `Q_H` TODOs, and RL
  implementation surfaces as the owner stack.
- Follow-up validation should rerun artifact grep, JSON parse, whitespace check,
  and `make check-agent-memory`.
